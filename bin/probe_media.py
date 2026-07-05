#!/usr/bin/env python3
"""probe_media.py - catalog assets/raw into work/manifest.json (v2, with eyes).

For every media file (recursively) records: type, dimensions, duration, fps,
rotation, orientation, codec, pix_fmt, HDR color metadata, and has_audio.
Also EXTRACTS THUMBNAILS + a contact sheet (so the agent can actually SEE the
footage), detects scene cuts in videos, and computes blur / exposure / suggested
subject-focus metrics used by edit-plan and match_exposure.

Usage:
    python bin/probe_media.py                 # scan assets/raw recursively
    python bin/probe_media.py --dir some/dir
    python bin/probe_media.py --no-thumbs     # metadata only, skip thumbnails/metrics

Part of the ingest-media skill. See docs/PIPELINE.md.
"""
import argparse, json, os, subprocess, sys
from fractions import Fraction

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THUMBS = os.path.join(ROOT, "work", "thumbs")
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv", ".flv"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp", ".tif", ".tiff"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}


def classify(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in VIDEO_EXT: return "video"
    if ext in IMAGE_EXT: return "image"
    if ext in AUDIO_EXT: return "audio"
    return None


def ffprobe(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", path],
        capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def orientation(w, h):
    if not w or not h: return "unknown"
    return "landscape" if w > h else ("portrait" if h > w else "square")


def is_hdr(transfer, primaries):
    t = (transfer or "").lower(); p = (primaries or "").lower()
    return t in ("smpte2084", "arib-std-b67") or p == "bt2020"


def grab_frame(src, t, dest, width=240):
    args = ["ffmpeg", "-y", "-v", "error"]
    if t is not None:
        args += ["-ss", f"{t:.3f}"]
    args += ["-i", src, "-frames:v", "1", "-vf", f"scale={width}:-1", dest]
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode == 0 and os.path.exists(dest)


def scene_cuts(src, threshold=0.4):
    """Return list of scene-change timestamps (seconds) within a video."""
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", src, "-vf",
         f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True)
    times = []
    for line in r.stderr.splitlines():
        if "pts_time:" in line and "showinfo" in line:
            try:
                seg = line.split("pts_time:")[1].split()[0]
                times.append(round(float(seg), 3))
            except (IndexError, ValueError):
                pass
    return times


def frame_metrics(thumb_path):
    """mean luma (0-1), blur (variance of Laplacian), suggested focus (x,y)."""
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        return {}
    try:
        im = Image.open(thumb_path).convert("L")
        a = np.asarray(im, dtype="float32") / 255.0
    except Exception:
        return {}
    mean_luma = float(a.mean())
    # Laplacian (edge) map
    lap = (-4 * a
           + np.roll(a, 1, 0) + np.roll(a, -1, 0)
           + np.roll(a, 1, 1) + np.roll(a, -1, 1))
    blur = float(lap.var())
    # focus suggestion = center of mass of edge energy, clamped away from edges
    e = np.abs(lap)
    if e.sum() > 1e-6:
        ys, xs = np.nonzero(e >= 0)  # all
        w = e.flatten()
        h_, w_ = a.shape
        yy = (np.arange(h_)[:, None] * e).sum() / e.sum() / h_
        xx = (np.arange(w_)[None, :] * e).sum() / e.sum() / w_
        fx = float(min(0.85, max(0.15, xx)))
        fy = float(min(0.85, max(0.15, yy)))
    else:
        fx = fy = 0.5
    return {"luma": round(mean_luma, 3), "blur": round(blur, 5),
            "focus": {"x": round(fx, 3), "y": round(fy, 3)}}


def probe_one(path, do_thumbs=True):
    kind = classify(path)
    if kind is None:
        return None
    relp = os.path.relpath(path, ROOT).replace("\\", "/")
    e = {"path": relp, "type": kind, "w": None, "h": None, "dur": None,
         "fps": None, "rotation": 0, "orientation": "unknown", "codec": None,
         "pix_fmt": None, "hdr": False, "has_audio": False}
    info = ffprobe(path)
    if not info:
        e["error"] = "ffprobe failed"; return e
    fmt = info.get("format", {})
    if fmt.get("duration"):
        try: e["dur"] = round(float(fmt["duration"]), 3)
        except ValueError: pass
    vs = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if any(s.get("codec_type") == "audio" for s in info.get("streams", [])):
        e["has_audio"] = True
    if vs:
        e["w"], e["h"] = vs.get("width"), vs.get("height")
        e["codec"] = vs.get("codec_name")
        e["pix_fmt"] = vs.get("pix_fmt")
        e["transfer"] = vs.get("color_transfer")
        e["primaries"] = vs.get("color_primaries")
        e["hdr"] = is_hdr(vs.get("color_transfer"), vs.get("color_primaries"))
        rate = vs.get("avg_frame_rate") or vs.get("r_frame_rate")
        if rate and rate != "0/0":
            try: e["fps"] = round(float(Fraction(rate)), 3)
            except (ZeroDivisionError, ValueError): pass
        rot = 0
        tags = vs.get("tags", {}) or {}
        if "rotate" in tags:
            try: rot = int(tags["rotate"]) % 360
            except ValueError: rot = 0
        for sd in vs.get("side_data_list", []) or []:
            if "rotation" in sd:
                try: rot = int(sd["rotation"]) % 360
                except (ValueError, TypeError): pass
        e["rotation"] = rot
        w, h = e["w"], e["h"]
        if rot in (90, 270): w, h = h, w
        e["orientation"] = orientation(w, h)
    if kind == "audio":
        e["orientation"] = "n/a"

    if do_thumbs and kind in ("video", "image"):
        os.makedirs(THUMBS, exist_ok=True)
        stem = relp.replace("/", "__").rsplit(".", 1)[0]
        if kind == "video" and e["dur"]:
            fracs = [0.1, 0.3, 0.5, 0.7, 0.9]
            thumbs = []
            for i, fr in enumerate(fracs):
                dst = os.path.join(THUMBS, f"{stem}_{i}.jpg")
                if grab_frame(path, e["dur"] * fr, dst):
                    thumbs.append(os.path.relpath(dst, ROOT).replace("\\", "/"))
            e["thumbs"] = thumbs
            mid = os.path.join(THUMBS, f"{stem}_2.jpg")
            if os.path.exists(mid):
                e["metrics"] = frame_metrics(mid)
                e["focus"] = e["metrics"].get("focus")
            cuts = scene_cuts(path)
            if cuts:
                e["scene_cuts"] = cuts
        else:  # image
            dst = os.path.join(THUMBS, f"{stem}.jpg")
            if grab_frame(path, None, dst):
                e["thumbs"] = [os.path.relpath(dst, ROOT).replace("\\", "/")]
                e["metrics"] = frame_metrics(dst)
                e["focus"] = e["metrics"].get("focus")
    return e


def build_contact_sheet(entries):
    """Tile one representative thumb per visual asset into a labeled sheet."""
    try:
        import numpy as np  # noqa
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None
    thumbs = []
    for i, e in enumerate(entries):
        t = (e.get("thumbs") or [None])[0]
        if t and os.path.exists(abs_(t)):
            thumbs.append((i, e, abs_(t)))
    if not thumbs:
        return None
    cols = min(5, len(thumbs))
    tw, th = 240, 180
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (18, 18, 20))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(os.path.join(ROOT, "assets", "fonts", "Arial-Bold.ttf"), 20)
    except Exception:
        font = ImageFont.load_default()
    for n, (idx, e, tp) in enumerate(thumbs):
        try:
            im = Image.open(tp).convert("RGB")
            im.thumbnail((tw, th))
        except Exception:
            continue
        cx, cy = (n % cols) * tw, (n // cols) * th
        sheet.paste(im, (cx + (tw - im.width) // 2, cy + (th - im.height) // 2))
        label = f"#{idx} {os.path.basename(e['path'])[:22]}"
        draw.rectangle([cx, cy, cx + tw, cy + 18], fill=(0, 0, 0))
        draw.text((cx + 3, cy + 1), label, fill=(255, 235, 120), font=font)
    out = os.path.join(THUMBS, "contact_sheet.jpg")
    sheet.save(out, quality=85)
    return os.path.relpath(out, ROOT).replace("\\", "/")


def abs_(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(ROOT, "assets", "raw"))
    ap.add_argument("--out", default=os.path.join(ROOT, "work", "manifest.json"))
    ap.add_argument("--no-thumbs", action="store_true")
    args = ap.parse_args()

    scan_dir = args.dir if os.path.isabs(args.dir) else os.path.join(ROOT, args.dir)
    if not os.path.isdir(scan_dir):
        print(f"[probe] directory not found: {scan_dir}", file=sys.stderr); sys.exit(1)

    files, skipped = [], []
    for root, _dirs, names in os.walk(scan_dir):
        for name in sorted(names):
            if name == ".gitkeep":
                continue
            p = os.path.join(root, name)
            if classify(p):
                files.append(p)
            else:
                skipped.append(os.path.relpath(p, ROOT).replace("\\", "/"))
    files.sort()

    entries = []
    for p in files:
        e = probe_one(p, do_thumbs=not args.no_thumbs)
        if e:
            entries.append(e)
            flags = []
            if e.get("hdr"): flags.append("HDR")
            if e.get("scene_cuts"): flags.append(f"{len(e['scene_cuts'])} scene-cuts")
            m = e.get("metrics") or {}
            mstr = f" luma={m.get('luma')} blur={m.get('blur')}" if m else ""
            dims = f"{e['w']}x{e['h']}" if e.get("w") else "-"
            print(f"  #{len(entries)-1} {e['type']:5} {dims:11} "
                  f"{e['orientation']:9}{mstr} {' '.join(flags)}  {e['path']}")

    sheet = None
    if not args.no_thumbs:
        sheet = build_contact_sheet([e for e in entries if e["type"] in ("video", "image")])

    manifest = {"count": len(entries), "contact_sheet": sheet,
                "skipped": skipped, "assets": entries}
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    nv = sum(1 for e in entries if e["type"] == "video")
    ni = sum(1 for e in entries if e["type"] == "image")
    na = sum(1 for e in entries if e["type"] == "audio")
    nhdr = sum(1 for e in entries if e.get("hdr"))
    print(f"\n[probe] {len(entries)} assets ({nv} video, {ni} image, {na} audio"
          + (f", {nhdr} HDR" if nhdr else "") + f") -> {os.path.relpath(args.out, ROOT)}")
    if sheet:
        print(f"[probe] contact sheet -> {sheet}  (open/Read it to choose shots)")
    if skipped:
        print(f"[probe] skipped {len(skipped)} non-media file(s): "
              + ", ".join(skipped[:5]) + (" ..." if len(skipped) > 5 else ""))
    if na == 0:
        print("[probe] note: no audio file found - add the song for beat-map.")


if __name__ == "__main__":
    main()
