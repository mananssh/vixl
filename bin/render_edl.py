#!/usr/bin/env python3
"""render_edl.py - render work/edl.json into a video (EDL v2).

Two-phase: normalize each clip to a uniform near-lossless intermediate, then
assemble with xfade/concat transitions + a full audio graph (music + optional
per-clip audio + sfx + ducking), two-pass loudnorm, atomic output.

Implements: focus-aware framing, HDR tonemap, exposure correction, grade (preset
or inline), Ken Burns (real pan interpolation) / zoompunch / shake / rgbsplit /
speedramp, freeze (speed:0), captions (with shadow + pop), cutout compositing,
overlay compositing, sfx mixing, ducking.

Usage:
    python bin/render_edl.py work/edl.json --check      # strict validate only
    python bin/render_edl.py work/edl.json --preview    # fast low-res -> work/previews/
    python bin/render_edl.py work/edl.json              # full quality -> out/
    python bin/render_edl.py work/edl.json --clip 3     # one clip -> work/cache/
    python bin/render_edl.py work/edl.json --from 2 --to 5   # subset -> work/cache/
"""
import argparse, hashlib, json, os, re, subprocess, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif")

VALID_FRAMING = {"auto", "fill", "blurpad"}
VALID_MOTION_KINDS = {"none", "kenburns", "zoompunch", "shake", "rgbsplit", "speedramp"}
VALID_CLIP_KEYS = {
    "src", "in", "out", "dur", "speed", "grade", "correct", "framing", "focus",
    "motion", "transition", "caption", "overlay", "cutout", "audio", "sfx",
    "notes", "_note"}
VALID_TOP_KEYS = {"meta", "audio", "clips", "edl_version", "_note", "$schema_note"}
EDL_VERSION = 2


# ------------------------- helpers -------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def abspath(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def rel(p):
    try:
        return os.path.relpath(p, ROOT).replace("\\", "/")
    except Exception:
        return p


def is_image(path):
    return os.path.splitext(path)[1].lower() in IMAGE_EXT


_probe_cache = {}


def probe(path):
    """Return {w,h,dur,fps,pix_fmt,transfer,primaries,has_audio,codec}."""
    if path in _probe_cache:
        return _probe_cache[path]
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", path],
        capture_output=True, text=True)
    info = {"w": 0, "h": 0, "dur": None, "fps": None, "pix_fmt": None,
            "transfer": None, "primaries": None, "has_audio": False, "codec": None}
    try:
        j = json.loads(r.stdout)
        fmt = j.get("format", {})
        if fmt.get("duration"):
            info["dur"] = float(fmt["duration"])
        for s in j.get("streams", []):
            if s.get("codec_type") == "video" and info["w"] == 0:
                info["w"] = int(s.get("width") or 0)
                info["h"] = int(s.get("height") or 0)
                info["pix_fmt"] = s.get("pix_fmt")
                info["transfer"] = s.get("color_transfer")
                info["primaries"] = s.get("color_primaries")
                info["codec"] = s.get("codec_name")
                if s.get("duration") and not info["dur"]:
                    info["dur"] = float(s["duration"])
            elif s.get("codec_type") == "audio":
                info["has_audio"] = True
    except Exception:
        pass
    _probe_cache[path] = info
    return info


_filter_cache = {}


def ffmpeg_has_filter(name):
    if name in _filter_cache:
        return _filter_cache[name]
    r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                       capture_output=True, text=True)
    has = bool(re.search(rf"\b{re.escape(name)}\b", r.stdout))
    _filter_cache[name] = has
    return has


def run(cmd, desc=""):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[render] FAILED: {desc}\n{' '.join(str(c) for c in cmd)[:400]}\n"
              f"{r.stderr[-1200:]}", file=sys.stderr)
        raise SystemExit(1)
    return r


def esc_drawtext(s):
    """Escape text for drawtext (used with expansion=none, so % is safe literal).
    Apostrophes -> typographic to dodge filtergraph single-quote hell."""
    s = s.replace("\\", "\\\\").replace(":", "\\:")
    s = s.replace("'", "’")
    return s


def is_hdr(info):
    t = (info.get("transfer") or "").lower()
    p = (info.get("primaries") or "").lower()
    return t in ("smpte2084", "arib-std-b67") or p == "bt2020"


# ------------------------- config -------------------------

def load_config():
    cfgp = os.path.join(ROOT, "config", "project.json")
    cfg = load_json(cfgp) if os.path.exists(cfgp) else {}
    presets = {}
    for name in ("grades", "transitions", "motion", "captions"):
        p = os.path.join(ROOT, "config", "presets", f"{name}.json")
        d = load_json(p) if os.path.exists(p) else {}
        presets[name] = {k: v for k, v in d.items() if not k.startswith("_")}
    return cfg, presets


def resolve_motion(motion, presets):
    """Return a normalized motion dict merging preset defaults with overrides."""
    if not motion:
        return {"kind": "none"}
    if isinstance(motion, str):
        base = dict(presets["motion"].get(motion, {}))
        if not base:
            base = {"kind": motion}
        return base
    m = dict(motion)
    kind = m.get("kind", "none")
    # merge defaults from a same-kind preset if present
    for pk, pv in presets["motion"].items():
        if isinstance(pv, dict) and pv.get("kind") == kind:
            merged = dict(pv)
            merged.update(m)
            return merged
    return m


# ------------------------- filter builders -------------------------

def framing_filter(w, h, focus):
    """Focus-aware fill crop into WxH. focus=(fx,fy) in 0..1."""
    fx, fy = focus
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h}:'(in_w-{w})*{fx:.4f}':'(in_h-{h})*{fy:.4f}'")


def blurpad_graph(w, h, in_label, out_label):
    """Multi-node blurred-fill background graph."""
    return (f"[{in_label}]split[bg][fg];"
            f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"boxblur=40:10,eq=brightness=-0.12[bgb];"
            f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2[{out_label}]")


def pan_centers(pan):
    """Return (cxs, cxe, cys, cye) start/end crop-window centers in 0..1."""
    d = {"none": (0.5, 0.5, 0.5, 0.5),
         "left": (1.0, 0.0, 0.5, 0.5),
         "right": (0.0, 1.0, 0.5, 0.5),
         "up": (0.5, 0.5, 1.0, 0.0),
         "down": (0.5, 0.5, 0.0, 1.0)}
    return d.get(pan, d["none"])


def motion_filter(m, w, h, fps, dur):
    """Return a filter fragment for the resolved motion dict, or ''."""
    kind = m.get("kind", "none")
    if kind in ("none", None):
        return ""
    frames = max(2, round(dur * fps))
    if kind == "kenburns":
        amt = float(m.get("amount", 0.10))
        zoom = m.get("zoom") or ("out" if m.get("to") == "out" else "in")
        # pan: explicit, else derive from from/to if they are directions
        pan = m.get("pan")
        if not pan:
            for cand in (m.get("from"), m.get("to")):
                if cand in ("left", "right", "up", "down"):
                    pan = cand
                    break
        pan = pan or "none"
        z0, z1 = (1.0, 1.0 + amt) if zoom == "in" else (1.0 + amt, 1.0)
        cxs, cxe, cys, cye = pan_centers(pan)
        pre = float(m.get("prescale", 2.0))
        z = f"'{z0}+({z1 - z0})*on/{frames - 1}'"
        x = f"'(iw-iw/zoom)*({cxs}+({cxe - cxs})*on/{frames - 1})'"
        y = f"'(ih-ih/zoom)*({cys}+({cye - cys})*on/{frames - 1})'"
        return (f"scale=iw*{pre}:ih*{pre},"
                f"zoompan=z={z}:x={x}:y={y}:d=1:s={w}x{h}:fps={fps}")
    if kind == "zoompunch":
        amt = float(m.get("amount", 0.20))
        at = float(m.get("at", 0.0))
        hold = float(m.get("hold", 0.4))
        f0, f1 = round(at * fps), round((at + hold) * fps)
        z = f"'if(between(on,{f0},{f1}),{1 + amt},1)'"
        return (f"scale=iw*2:ih*2,zoompan=z={z}:x='iw/2-(iw/zoom/2)':"
                f"y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}")
    if kind == "shake":
        i = int(m.get("intensity", 10))
        return (f"crop=in_w-{2 * i}:in_h-{2 * i}:'{i}*sin(n/2)+{i}':"
                f"'{i}*cos(n/3)+{i}',scale={w}:{h}")
    if kind == "rgbsplit":
        a = int(m.get("amount", 6))
        return f"rgbashift=rh={a}:bh=-{a}"
    return ""


def speed_filter(clip, is_img):
    """Video setpts fragment for constant speed or a linear speed ramp."""
    if is_img:
        return ""
    m = clip.get("motion") or {}
    if isinstance(m, dict) and m.get("kind") == "speedramp":
        s0 = float(m.get("from_speed", 1.0))
        s1 = float(m.get("to_speed", 0.5))
        if abs(s1 - s0) < 1e-3:
            return f"setpts=PTS/{s0}"
        span = float(clip.get("out", 0) or 0) - float(clip.get("in", 0) or 0)
        span = span or 1.0
        # T_out = (D/(s1-s0)) * ln(s(T)/s0);  s(T)=s0+(s1-s0)*T/D
        return (f"setpts='({span}/({s1 - s0}))*"
                f"log(({s0}+({s1 - s0})*T/{span})/{s0})/TB'")
    speed = float(clip.get("speed", 1.0)) or 1.0
    if speed != 1.0:
        return f"setpts=PTS/{speed}"
    return ""


def correct_filter(correct):
    """Exposure/WB correction (applied before grade)."""
    if not correct:
        return ""
    parts = []
    if "brightness" in correct:
        parts.append(f"brightness={correct['brightness']}")
    if "contrast" in correct:
        parts.append(f"contrast={correct['contrast']}")
    if "saturation" in correct:
        parts.append(f"saturation={correct['saturation']}")
    for k in ("gamma", "gamma_r", "gamma_g", "gamma_b"):
        if k in correct:
            parts.append(f"{k}={correct[k]}")
    return "eq=" + ":".join(parts) if parts else ""


def grade_filter(grade, presets):
    if not grade:
        return ""
    if grade in presets["grades"]:
        return presets["grades"][grade]
    if "=" in grade:            # inline filter string
        return grade
    return ""                    # unknown -> caught by validation


def caption_filter(cap, presets, w, h):
    if not cap or not cap.get("text"):
        return ""
    style = presets["captions"].get(cap.get("style", "impact"), {})

    def g(key, default=None):
        return cap.get(key, style.get(key, default))

    text = esc_drawtext(cap["text"])
    parts = [f"text='{text}'", "expansion=none"]  # expansion=none => literal %, no %{..}
    font = g("font")
    if font and os.path.exists(abspath(font)):
        fp = abspath(font).replace("\\", "/").replace(":", "\\:")
        parts.append(f"fontfile='{fp}'")
    parts.append(f"fontcolor={g('fontcolor', 'white')}")
    bw = g("borderw", 0)
    if bw:
        parts.append(f"borderw={bw}")
        parts.append(f"bordercolor={g('bordercolor', 'black')}")
    sx, sy = g("shadowx"), g("shadowy")
    if sx is not None and sy is not None:
        parts.append(f"shadowx={sx}")
        parts.append(f"shadowy={sy}")
        parts.append(f"shadowcolor={g('shadowcolor', 'black@0.5')}")
    yfrac = g("y", 0.74)
    parts.append("x=(w-text_w)/2")
    # pop animation: scale font up briefly at start via a stepped size expr
    base_size = int(g("fontsize", 84))
    start, end = cap.get("start"), cap.get("end")
    if cap.get("pop") and start is not None:
        # overshoot then settle over ~0.18s
        parts.append(
            f"fontsize='if(lt(t-{start},0.18),{base_size}*(0.6+2.5*(t-{start})),"
            f"{base_size})'")
    else:
        parts.append(f"fontsize={base_size}")
    parts.append(f"y=h*{yfrac}")
    if start is not None and end is not None:
        parts.append(f"enable='between(t,{start},{end})'")
    return "drawtext=" + ":".join(parts)


# ------------------------- per-clip normalization -------------------------

def clip_duration(clip, info):
    """On-timeline duration of a clip (after speed)."""
    speed = float(clip.get("speed", 1.0)) or 1.0
    if is_image(clip["src"]):
        return float(clip.get("dur") or 3.0)
    tin = float(clip.get("in", 0.0))
    tout = clip.get("out")
    if tout is not None:
        span = float(tout) - tin
    else:
        span = float(clip.get("dur") or 3.0) * speed
    m = clip.get("motion") or {}
    if isinstance(m, dict) and m.get("kind") == "speedramp":
        # ramp changes duration; approximate on-timeline dur via avg speed
        s0 = float(m.get("from_speed", 1.0)); s1 = float(m.get("to_speed", 0.5))
        import math
        if abs(s1 - s0) < 1e-3:
            return span / (s0 or 1.0)
        return span * math.log(s1 / s0) / (s1 - s0)
    return float(clip.get("dur") or (span / speed))


def keep_audio_flag(clip):
    src = abspath(clip["src"])
    if is_image(src):
        return False
    if float(clip.get("speed", 1.0) or 1.0) == 0:
        return False
    return (clip.get("audio") or {}).get("mode") == "keep"


def clip_cache_key(clip, cfg, presets, preview):
    """Stable hash of everything that affects a normalized clip, so unchanged
    clips are reused across renders (edit one clip -> only it re-encodes)."""
    src = abspath(clip["src"])
    try:
        st = os.stat(src)
        sig = f"{st.st_mtime_ns}:{st.st_size}"
    except OSError:
        sig = "0"
    payload = json.dumps(
        {"clip": clip, "fmt": cfg.get("format"), "pv": preview, "sig": sig,
         "grades": presets["grades"], "motion": presets["motion"],
         "captions": presets["captions"]},
        sort_keys=True, default=str)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:16]


def normalize_clip(clip, idx, cfg, presets, out_path, preview=False):
    """Render one EDL clip to a uniform intermediate. Returns (dur, has_audio)."""
    fmt = cfg.get("format", {})
    w, h = fmt.get("width", 1080), fmt.get("height", 1920)
    fps = fmt.get("fps", 30)
    if preview:
        ph = cfg.get("render", {}).get("preview_height", 640)
        h = ph if ph % 2 == 0 else ph + 1
        w = round(w * h / (fmt.get("height", 1920)))
        w += w % 2

    src = abspath(clip["src"])
    info = probe(src)
    img = is_image(src)
    speed = float(clip.get("speed", 1.0)) or 1.0
    freeze = (speed == 0)
    dur = clip_duration(clip, info)

    keep_audio = (not img and not freeze
                  and (clip.get("audio") or {}).get("mode") == "keep")

    # ---- inputs ----
    inputs = []
    if img or freeze:
        if freeze:
            # grab a single frame at 'in' and loop it
            tin = float(clip.get("in", 0.0))
            inputs += ["-framerate", str(fps), "-loop", "1", "-ss", f"{tin:.3f}",
                       "-t", f"{dur:.3f}", "-i", src]
        else:
            inputs += ["-framerate", str(fps), "-loop", "1", "-t", f"{dur:.3f}",
                       "-i", src]
    else:
        tin = float(clip.get("in", 0.0))
        tout = clip.get("out")
        span = (float(tout) - tin) if tout is not None else (dur * speed)
        inputs += ["-ss", f"{tin:.3f}", "-t", f"{span:.3f}", "-i", src]
    base_idx = 0

    cutout = clip.get("cutout")
    overlay = clip.get("overlay")
    cutout_idx = overlay_idx = None
    if cutout:
        cp = abspath(cutout)
        if is_image(cp):
            inputs += ["-i", cp]
        else:
            inputs += ["-i", cp]      # RGBA video (qtrle/prores)
        cutout_idx = 1
    if overlay and overlay.get("src"):
        op = abspath(overlay["src"])
        oi = (2 if cutout else 1)
        if is_image(op):
            inputs += ["-i", op]
        else:
            inputs += ["-stream_loop", "-1", "-i", op]
        overlay_idx = oi

    # ---- video graph ----
    graph = []
    cur = f"{base_idx}:v"

    # HDR tonemap
    if is_hdr(info):
        if ffmpeg_has_filter("zscale") and ffmpeg_has_filter("tonemap"):
            graph.append(f"[{cur}]zscale=t=linear:npl=100,tonemap=tonemap=hable:desat=0,"
                         f"zscale=p=bt709:t=bt709:m=bt709,format=yuv420p[hdr{idx}]")
            cur = f"hdr{idx}"
        else:
            print(f"[render] ~ clip {idx}: HDR source but zscale/tonemap unavailable; "
                  f"colors may look washed. (install an ffmpeg with libzimg)")

    # speed / ramp (video only)
    sf = speed_filter(clip, img or freeze)
    pre_chain = []
    if sf:
        pre_chain.append(sf)
    # framing
    framing = clip.get("framing", "auto")
    focus = clip.get("focus") or {}
    fxy = (float(focus.get("x", 0.5)), float(focus.get("y", 0.5)))
    if framing == "blurpad":
        if pre_chain:
            graph.append(f"[{cur}]" + ",".join(pre_chain) + f"[sp{idx}]")
            cur = f"sp{idx}"
        graph.append(blurpad_graph(w, h, cur, f"fr{idx}"))
        cur = f"fr{idx}"
    else:
        pre_chain.append(framing_filter(w, h, fxy))
        graph.append(f"[{cur}]" + ",".join(pre_chain) + f"[fr{idx}]")
        cur = f"fr{idx}"

    # motion (after framing)
    mres = resolve_motion(clip.get("motion"), presets)
    if mres.get("kind") not in (None, "none", "speedramp"):
        mf = motion_filter(mres, w, h, fps, dur)
        if mf:
            graph.append(f"[{cur}]{mf}[mo{idx}]")
            cur = f"mo{idx}"

    # exposure correction then grade
    cf = correct_filter(clip.get("correct"))
    gf = grade_filter(clip.get("grade"), presets)
    cg = ",".join([x for x in (cf, gf) if x])
    if cg:
        graph.append(f"[{cur}]{cg}[cg{idx}]")
        cur = f"cg{idx}"

    # cutout composite (subject over blurred/darkened same frame)
    if cutout_idx is not None:
        graph.append(f"[{cur}]boxblur=25:4,eq=brightness=-0.18[bgc{idx}]")
        c_scale = float((clip.get("cutout_opts") or {}).get("scale", 1.0)) \
            if isinstance(clip.get("cutout_opts"), dict) else 1.0
        graph.append(f"[{cutout_idx}:v]scale=-1:{int(h * c_scale)}[cut{idx}]")
        graph.append(f"[bgc{idx}][cut{idx}]overlay=(W-w)/2:(H-h)/2:format=auto[co{idx}]")
        cur = f"co{idx}"

    # overlay composite
    if overlay_idx is not None:
        mode = overlay.get("mode", "screen")
        op = float(overlay.get("opacity", 0.4))
        if mode == "screen":
            graph.append(f"[{overlay_idx}:v]scale={w}:{h},format=yuv420p[ov{idx}]")
            graph.append(f"[{cur}][ov{idx}]blend=all_mode=screen:all_opacity={op}[oc{idx}]")
        else:
            sc = float(overlay.get("scale", 1.0))
            pos = {"center": "(W-w)/2:(H-h)/2", "top-right": "W-w-40:40",
                   "top-left": "40:40", "bottom-right": "W-w-40:H-h-40",
                   "bottom-left": "40:H-h-40"}.get(overlay.get("pos", "center"),
                                                   "(W-w)/2:(H-h)/2")
            en = ""
            if overlay.get("start") is not None and overlay.get("end") is not None:
                en = f":enable='between(t,{overlay['start']},{overlay['end']})'"
            graph.append(f"[{overlay_idx}:v]scale=iw*{sc}:-1[ov{idx}]")
            graph.append(f"[{cur}][ov{idx}]overlay={pos}{en}[oc{idx}]")
        cur = f"oc{idx}"

    # caption
    capf = caption_filter(clip.get("caption"), presets, w, h)
    tail = [x for x in [capf, f"fps={fps}", "format=yuv420p", "setsar=1"] if x]
    graph.append(f"[{cur}]" + ",".join(tail) + f"[vout{idx}]")

    # ---- encode ----
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # near-lossless intermediates so the final encode isn't a 2nd generation loss
    crf = 18 if preview else 12
    enc = ["-c:v", "libx264", "-crf", str(crf), "-preset",
           "veryfast" if preview else "fast", "-pix_fmt", "yuv420p"]
    amap = []
    if keep_audio:
        vol = float((clip.get("audio") or {}).get("volume_db", 0.0))
        af = []
        if speed != 1.0:
            # atempo supports 0.5..2.0; chain for larger factors
            s = speed
            while s > 2.0:
                af.append("atempo=2.0"); s /= 2.0
            while s < 0.5:
                af.append("atempo=0.5"); s *= 2.0
            af.append(f"atempo={s:.4f}")
        if vol:
            af.append(f"volume={vol}dB")
        af.append("aresample=48000")
        graph.append(f"[{base_idx}:a]" + ",".join(af) + f"[aout{idx}]")
        amap = ["-map", f"[aout{idx}]", "-c:a", "aac", "-b:a", "256k"]
    else:
        enc += ["-an"]

    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(graph),
           "-map", f"[vout{idx}]", *amap, "-t", f"{dur:.3f}", *enc, out_path]
    run(cmd, f"normalize clip {idx} ({os.path.basename(src)})")
    return dur, keep_audio


# ------------------------- audio graph -------------------------

def measure_loudness(path):
    """Two-pass loudnorm: measure input, return the measured-values dict."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", path, "-af",
         "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# ------------------------- assembly -------------------------

def assemble(clip_files, durs, has_audio, edl, cfg, presets, out_path,
             preview=False, audio_offset=0.0):
    clips = edl["clips"]
    rcfg = cfg.get("render", {})

    # transitions between consecutive clips
    trans = []
    for i in range(len(clip_files) - 1):
        t = clips[i].get("transition", {"type": "cut"})
        tp = presets["transitions"].get(t.get("type", "cut"),
                                        {"xfade": None, "dur": 0.0})
        tdur = float(t.get("dur", tp.get("dur", 0.0)))
        xf = tp.get("xfade")
        if xf is None:
            tdur = 0.0
        trans.append((xf, tdur))

    inputs = []
    for cf in clip_files:
        inputs += ["-i", cf]

    fps = cfg.get("format", {}).get("fps", 30)

    # Normalize timebase + fps on every clip stream first. Without a common
    # timebase, xfade fails ("do not match ... xfade timebase") once its output
    # tb diverges from the next raw input's tb.
    fc = []
    for i in range(len(clip_files)):
        # settb must come AFTER fps (fps resets tb to 1/fps); AVTB matches xfade's
        # output tb so chained xfades/concats stay consistent.
        fc.append(f"[{i}:v]fps={fps},format=yuv420p,setsar=1,settb=AVTB[n{i}]")

    # video chain + per-clip timeline start times
    cur = "[n0]"
    acc = durs[0]
    starts = [0.0]
    for i in range(1, len(clip_files)):
        xf, tdur = trans[i - 1]
        out = f"[v{i}]"
        if xf is None or tdur <= 0:
            fc.append(f"{cur}[n{i}]concat=n=2:v=1:a=0{out}")
            starts.append(acc)
            acc += durs[i]
        else:
            offset = max(0.0, acc - tdur)
            fc.append(f"{cur}[n{i}]xfade=transition={xf}:duration={tdur:.3f}:"
                      f"offset={offset:.3f}{out}")
            starts.append(acc - tdur)
            acc += durs[i] - tdur
        cur = out
    video_label = cur
    timeline_dur = acc

    # ---- audio ----
    audio = edl.get("audio", {})
    a_src = abspath(audio["src"]) if audio.get("src") else None
    fin = float(audio.get("fade_in", 0.4))
    fout = float(audio.get("fade_out", 1.2))
    a_start = float(audio.get("start", 0.0)) + audio_offset

    audio_labels = []
    next_idx = len(clip_files)

    if a_src and os.path.exists(a_src):
        inputs += ["-ss", f"{a_start:.3f}", "-i", a_src]
        music_i = next_idx; next_idx += 1
        music_af = [f"atrim=0:{timeline_dur:.3f}", "asetpts=PTS-STARTPTS"]
        # ducking under a voice-over
        duck = audio.get("duck_with")
        if duck and os.path.exists(abspath(duck)):
            inputs += ["-i", abspath(duck)]
            vo_i = next_idx; next_idx += 1
            fc.append(f"[{music_i}:a]" + ",".join(music_af) + f"[mus{music_i}]")
            fc.append(f"[mus{music_i}][{vo_i}:a]sidechaincompress=threshold=0.03:"
                      f"ratio=8:attack=20:release=300[ducked]")
            audio_labels.append("[ducked]")
            audio_labels.append(f"[{vo_i}:a]")
        else:
            fc.append(f"[{music_i}:a]" + ",".join(music_af) + f"[mus{music_i}]")
            audio_labels.append(f"[mus{music_i}]")

    # per-clip kept audio, placed on the timeline
    for i, cf in enumerate(clip_files):
        if has_audio[i]:
            delay = int(starts[i] * 1000)
            fc.append(f"[{i}:a]adelay={delay}|{delay}[ca{i}]")
            audio_labels.append(f"[ca{i}]")

    # sfx events
    for i, clip in enumerate(clips[:len(clip_files)]):
        for j, ev in enumerate(clip.get("sfx", []) or []):
            sp = abspath(ev["src"])
            if not os.path.exists(sp):
                print(f"[render] ~ sfx not found, skipping: {ev['src']}")
                continue
            inputs += ["-i", sp]
            si = next_idx; next_idx += 1
            at = float(ev.get("at", 0.0))
            delay = int((starts[i] + at) * 1000)
            gain = float(ev.get("gain_db", 0.0))
            fc.append(f"[{si}:a]adelay={delay}|{delay},volume={gain}dB[sfx{si}]")
            audio_labels.append(f"[sfx{si}]")

    have_audio = bool(audio_labels)
    if have_audio:
        if len(audio_labels) > 1:
            fc.append("".join(audio_labels) +
                      f"amix=inputs={len(audio_labels)}:normalize=0:"
                      f"duration=first[amixed]")
            amix_label = "[amixed]"
        else:
            amix_label = audio_labels[0]
        # fades
        fc.append(f"{amix_label}afade=t=in:st=0:d={fin},"
                  f"afade=t=out:st={max(0.0, timeline_dur - fout):.3f}:d={fout},"
                  f"aresample=48000[aout]")

    # ---- encode (atomic: render to .tmp then rename) ----
    crf = rcfg.get("preview_crf", 30) if preview else rcfg.get("final_crf", 18)
    preset = "veryfast" if preview else "slow"
    enc = ["-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", "yuv420p"]
    map_args = ["-map", video_label]
    if have_audio:
        map_args += ["-map", "[aout]", "-c:a", "aac",
                     "-b:a", rcfg.get("audio_bitrate", "320k")]
    enc += ["-t", f"{timeline_dur:.3f}", "-movflags", "+faststart"]

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp.mp4"
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fc),
           *map_args, *enc, tmp]
    run(cmd, "assemble timeline")

    # two-pass loudnorm for finals (measure the mixed track, re-apply linearly).
    # Previews skip it to stay fast — they're only for sign-off.
    did_final = False
    if have_audio and not preview and audio.get("loudnorm", True):
        meas = measure_loudness(tmp)
        if meas:
            ln = (f"loudnorm=I={rcfg.get('loudnorm_I', -14)}:"
                  f"TP={rcfg.get('loudnorm_TP', -1.5)}:LRA={rcfg.get('loudnorm_LRA', 11)}:"
                  f"measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:"
                  f"measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:"
                  f"offset={meas['target_offset']}:linear=true:print_format=summary,"
                  f"aresample=48000")
            tmp2 = out_path + ".tmp2.mp4"
            run(["ffmpeg", "-y", "-i", tmp, "-af", ln, "-c:v", "copy",
                 "-c:a", "aac", "-b:a", rcfg.get("audio_bitrate", "320k"),
                 "-movflags", "+faststart", tmp2], "two-pass loudnorm")
            os.replace(tmp2, out_path)
            os.remove(tmp)
            did_final = True
    if not did_final:
        # preview or no-audio: keep the single-pass render as-is
        os.replace(tmp, out_path)
    return timeline_dur


# ------------------------- check (strict) -------------------------

def nearest_beat(t, beats):
    if not beats:
        return None, None
    b = min(beats, key=lambda x: abs(x - t))
    return b, round(t - b, 3)


def check(edl, cfg, presets):
    print("[check] validating EDL (v2, strict) ...")
    errors, warns = [], []

    ver = edl.get("edl_version")
    if ver is None:
        warns.append("no edl_version; assuming current. Add \"edl_version\": 2.")
    elif ver > EDL_VERSION:
        errors.append(f"edl_version {ver} newer than supported {EDL_VERSION}")

    for k in edl:
        if k not in VALID_TOP_KEYS:
            errors.append(f"unknown top-level key: {k!r}")

    fmt = cfg.get("format", {})
    fps = edl.get("meta", {}).get("fps", fmt.get("fps", 30))
    beatsp = os.path.join(ROOT, "work", "beats.json")
    beatsj = load_json(beatsp) if os.path.exists(beatsp) else {}
    beats = beatsj.get("beats", [])
    song_analyzed = beatsj.get("duration")
    a_start = float(edl.get("audio", {}).get("start", 0.0))

    clips = edl.get("clips", [])
    if not clips:
        print("  ! no clips in EDL"); return False

    valid_grades = set(presets["grades"])
    valid_trans = set(presets["transitions"]) | {"cut"}

    acc = 0.0
    cum_cuts = []
    for i, c in enumerate(clips):
        for k in c:
            if k not in VALID_CLIP_KEYS:
                errors.append(f"clip {i}: unknown key {k!r} (typo? feature not supported)")
        src = abspath(c.get("src", ""))
        if not c.get("src"):
            errors.append(f"clip {i}: missing 'src'"); continue
        if not os.path.exists(src):
            errors.append(f"clip {i}: missing file {c.get('src')}"); continue

        # grade
        g = c.get("grade")
        if g and g not in valid_grades and "=" not in g:
            errors.append(f"clip {i}: unknown grade {g!r} (not a preset; not inline)")
        # transition
        t = c.get("transition", {"type": "cut"})
        tt = t.get("type", "cut")
        if tt not in valid_trans:
            errors.append(f"clip {i}: unknown transition {tt!r}")
        # motion
        m = c.get("motion")
        if isinstance(m, dict):
            mk = m.get("kind", "none")
            if mk not in VALID_MOTION_KINDS:
                errors.append(f"clip {i}: unknown motion kind {mk!r}")
        elif isinstance(m, str) and m not in presets["motion"]:
            errors.append(f"clip {i}: unknown motion preset {m!r}")
        # framing
        fr = c.get("framing", "auto")
        if fr not in VALID_FRAMING:
            errors.append(f"clip {i}: unknown framing {fr!r}")
        # speed
        sp = c.get("speed", 1.0)
        if sp is not None and float(sp) < 0:
            errors.append(f"clip {i}: negative speed {sp}")
        # cutout / overlay / sfx file existence
        if c.get("cutout") and not os.path.exists(abspath(c["cutout"])):
            errors.append(f"clip {i}: cutout file missing {c['cutout']}")
        if c.get("overlay") and c["overlay"].get("src") \
                and not os.path.exists(abspath(c["overlay"]["src"])):
            errors.append(f"clip {i}: overlay file missing {c['overlay']['src']}")
        for ev in c.get("sfx", []) or []:
            if not os.path.exists(abspath(ev.get("src", ""))):
                errors.append(f"clip {i}: sfx file missing {ev.get('src')}")

        info = probe(src)
        img = is_image(src)
        speed = float(c.get("speed", 1.0)) or 1.0
        if not img and c.get("out") is not None and info["dur"]:
            if float(c["out"]) > info["dur"] + 0.05:
                errors.append(f"clip {i}: out {c['out']}s exceeds source {info['dur']:.2f}s")
        dur = clip_duration(c, info)
        tdur = 0.0
        if tt != "cut":
            tp = presets["transitions"].get(tt, {})
            tdur = float(t.get("dur", tp.get("dur", 0.5)))
        cut_time = acc + dur
        acc = acc + dur - (tdur if i < len(clips) - 1 else 0)
        if i < len(clips) - 1:
            cum_cuts.append((cut_time - tdur / 2, tdur))  # (midpoint, transition dur)

    print(f"  clips: {len(clips)}  |  timeline: {acc:.2f}s  |  fps: {fps}")
    tmin = cfg.get("length", {}).get("target_min_seconds", 0)
    tmax = cfg.get("length", {}).get("target_max_seconds", 9999)
    if not (tmin <= acc <= tmax):
        warns.append(f"duration {acc:.1f}s outside target {tmin}-{tmax}s")

    # song length vs timeline
    if song_analyzed and (a_start + acc) > song_analyzed + 0.1:
        warns.append(f"edit needs {a_start + acc:.1f}s of song but it's only "
                     f"{song_analyzed:.1f}s — video will truncate. Lower audio.start "
                     f"or shorten the edit.")

    # beat alignment
    if beats:
        tol_frames = cfg.get("beats", {}).get("snap_tolerance_frames", 1.5)
        tol = tol_frames / fps
        # A cut is "on beat" if the beat falls within tolerance of the cut, OR
        # (for a dissolve) anywhere within the transition span — a beat landing
        # during a dissolve reads as on-beat.
        onbeat = off_beat = 0
        worst = 0.0
        for mid, td in cum_cuts:
            off = abs(nearest_beat(a_start + mid, beats)[1] or 0)
            eff = max(0.0, off - td / 2)          # distance beyond the transition span
            worst = max(worst, eff)
            if eff <= tol:
                onbeat += 1
            else:
                off_beat += 1
        print(f"  beat alignment: {onbeat}/{len(cum_cuts)} cuts on-beat "
              f"(within {tol_frames}f, dissolves count if beat is inside them); "
              f"worst {worst * 1000:.0f} ms off")
        if off_beat:
            warns.append(f"{off_beat} cut(s) off-beat; snap clip durations to beats.")
    else:
        warns.append("no work/beats.json — run beat-map for beat-alignment check.")

    for w_ in warns:
        print(f"  ~ {w_}")
    for e in errors:
        print(f"  ! {e}")
    ok = not errors
    print("[check] OK" if ok else f"[check] FAILED — {len(errors)} error(s)")
    return ok


# ------------------------- main -------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edl")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--clip", type=int, default=None)
    ap.add_argument("--from", dest="frm", type=int, default=None)
    ap.add_argument("--to", type=int, default=None)
    args = ap.parse_args()

    edl = load_json(abspath(args.edl))
    cfg, presets = load_config()
    meta = edl.get("meta", {})
    if meta:
        cfg.setdefault("format", {})
        for k in ("width", "height", "fps"):
            if k in meta:
                cfg["format"][k] = meta[k]

    if args.check:
        sys.exit(0 if check(edl, cfg, presets) else 2)

    # validate before rendering too (fail fast)
    if not check(edl, cfg, presets):
        print("[render] refusing to render an invalid EDL (see ! errors above).",
              file=sys.stderr)
        sys.exit(2)

    clips = edl["clips"]
    preview = args.preview and not args.final

    lo = args.frm if args.frm is not None else (args.clip if args.clip is not None else 0)
    hi = args.to if args.to is not None else (args.clip if args.clip is not None else len(clips) - 1)
    subset = args.clip is not None or args.frm is not None or args.to is not None

    print(f"[render] normalizing clips {lo}..{hi} ({'preview' if preview else 'final'}) ...")
    clip_files, durs, hasaud = [], [], []
    cached_n = 0
    for i in range(lo, hi + 1):
        # content-hash cache: skip re-normalizing a clip whose inputs are unchanged
        key = clip_cache_key(clips[i], cfg, presets, preview)
        outp = os.path.join(ROOT, "work", "clips",
                            f"{'pv' if preview else 'f'}_{key}.mp4")
        if os.path.exists(outp):
            d = clip_duration(clips[i], probe(abspath(clips[i]["src"])))
            ha = keep_audio_flag(clips[i])
            cached_n += 1
            print(f"  clip {i}: {d:.2f}s (cached) -> {rel(outp)}")
        else:
            d, ha = normalize_clip(clips[i], i, cfg, presets, outp, preview=preview)
            print(f"  clip {i}: {d:.2f}s{' +audio' if ha else ''} -> {rel(outp)}")
        clip_files.append(outp); durs.append(d); hasaud.append(ha)
    if cached_n:
        print(f"[render] reused {cached_n}/{len(clip_files)} cached clips "
              f"(delete work/clips/* to force full re-render).")

    # single clip spot-check (copy, so the cache entry survives)
    if args.clip is not None and lo == hi:
        import shutil
        dst = os.path.join(ROOT, "work", "cache", f"clip_{lo:03d}.mp4")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(clip_files[0], dst)
        print(f"[render] single clip -> {rel(dst)}")
        return

    title = meta.get("title") or cfg.get("title", "edit")
    # subset assemblies go to work/cache (never masquerade as the deliverable)
    if subset:
        out_path = os.path.join(ROOT, "work", "cache", f"subset_{lo}_{hi}_{title}.mp4")
    elif preview:
        out_path = os.path.join(ROOT, "work", "previews", f"preview_{title}.mp4")
    else:
        out_path = os.path.join(ROOT, "out", f"{title}.mp4")

    # audio offset so a subset plays the correct part of the song
    audio_offset = sum(clip_duration(clips[i], probe(abspath(clips[i]["src"])))
                       for i in range(0, lo)) if lo > 0 else 0.0

    sub_edl = dict(edl); sub_edl["clips"] = clips[lo:hi + 1]
    total = assemble(clip_files, durs, hasaud, sub_edl, cfg, presets, out_path,
                     preview=preview, audio_offset=audio_offset)

    size = os.path.getsize(out_path) / 1e6
    print(f"\n[render] DONE -> {rel(out_path)}")
    print(f"[render] {total:.2f}s | {size:.1f} MB | "
          f"{cfg['format']['width']}x{cfg['format']['height']}@{cfg['format']['fps']}")
    if preview:
        print("[render] PREVIEW — show it, get sign-off, then render without --preview.")


if __name__ == "__main__":
    main()
