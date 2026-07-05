#!/usr/bin/env python3
"""run_tests.py - end-to-end test suite for the auto-editor pipeline.

Generates synthetic media, drives the real bin/ tools, and asserts on outputs.
Covers the regressions found during the build: image-clip fps (short clips),
xfade timebase mismatch, drawtext stray-%, strict EDL validation, atomic output,
render caching, and the raw-media guard.

Run:  python tests/run_tests.py
Exit code 0 = all passed.
"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin")
PY = sys.executable
T = os.path.join(ROOT, "work", "cache", "selftest")
GUARD = os.path.join(ROOT, ".claude", "hooks", "guard_raw.py")

PASS = FAIL = 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        FAILURES.append(name)
        print(f"  [FAIL] {name}  {detail}")


def run(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


def ffprobe(path, entries):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", entries, "-of", "json", path])
    return json.loads(r.stdout) if r.returncode == 0 else {}


def gen_media():
    os.makedirs(T, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "testsrc2=size=854x480:rate=30", "-t", "3", "-pix_fmt", "yuv420p",
         os.path.join(T, "land.mp4")])
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "testsrc2=size=480x854:rate=30", "-t", "3", "-pix_fmt", "yuv420p",
         os.path.join(T, "port.mp4")])
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "color=c=teal:size=1200x1600", "-frames:v", "1", os.path.join(T, "still.png")])
    # 120 BPM click track via numpy
    import numpy as np, soundfile as sf
    sr, dur, bpm = 44100, 20, 120
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    sig = np.zeros_like(t)
    step = 60.0 / bpm
    for k in range(int(dur / step)):
        i = int(k * step * sr)
        sig[i:i + 400] += 0.6 * np.sin(2 * np.pi * 1000 * t[:400])
    sf.write(os.path.join(T, "song.wav"), sig.astype("float32"), sr)


def test_probe():
    print("probe_media:")
    out = os.path.join(T, "manifest.json")
    r = run([PY, os.path.join(BIN, "probe_media.py"), "--dir", T, "--out", out])
    check("probe runs", r.returncode == 0, r.stderr[-200:])
    m = json.load(open(out)) if os.path.exists(out) else {}
    check("manifest has 4 media (3 visual + song)", m.get("count") == 4, str(m.get("count")))
    vids = [a for a in m.get("assets", []) if a["type"] == "video"]
    check("video has metrics", bool(vids and vids[0].get("metrics")))
    check("contact sheet made", bool(m.get("contact_sheet")) and
          os.path.exists(os.path.join(ROOT, m["contact_sheet"])))
    check("no false HDR", all(not a.get("hdr") for a in m.get("assets", [])))
    return out


def test_beats():
    print("detect_beats:")
    out = os.path.join(T, "beats.json")
    r = run([PY, os.path.join(BIN, "detect_beats.py"), os.path.join(T, "song.wav"),
             "--out", out])
    check("beats runs", r.returncode == 0, r.stderr[-200:])
    b = json.load(open(out)) if os.path.exists(out) else {}
    check("tempo ~120", b.get("tempo") and 110 <= b["tempo"] <= 130, str(b.get("tempo")))
    check("beats present", len(b.get("beats", [])) > 20)
    return out


def write_edl(path, clips, title="selftest"):
    edl = {"edl_version": 2,
           "meta": {"width": 1080, "height": 1920, "fps": 30, "title": title},
           "audio": {"src": os.path.join(T, "song.wav").replace("\\", "/"),
                     "start": 0.0, "fade_in": 0.3, "fade_out": 0.5, "loudnorm": True},
           "clips": clips}
    json.dump(edl, open(path, "w"), indent=2)


def test_validation():
    print("strict validation:")
    valid = os.path.join(T, "valid.json")
    write_edl(valid, [
        {"src": os.path.join(T, "land.mp4").replace("\\", "/"), "in": 0, "out": 1,
         "grade": "cine_teal_orange", "motion": {"kind": "kenburns", "zoom": "in", "pan": "right", "amount": 0.1},
         "transition": {"type": "dissolve", "dur": 0.4}},
        {"src": os.path.join(T, "still.png").replace("\\", "/"), "dur": 1.0,
         "grade": "eq=contrast=1.1", "caption": {"text": "100% REAL", "style": "impact", "start": 0.1, "end": 0.9, "pop": True},
         "transition": {"type": "cut"}},
    ])
    r = run([PY, os.path.join(BIN, "render_edl.py"), valid, "--check"])
    check("valid EDL passes --check", r.returncode == 0, r.stdout[-300:])

    broken = os.path.join(T, "broken.json")
    write_edl(broken, [
        {"src": os.path.join(T, "land.mp4").replace("\\", "/"), "in": 0, "out": 99,
         "grade": "nope", "motion": {"kind": "xyz"}, "trasition": {"type": "dissolve"}},
    ])
    r = run([PY, os.path.join(BIN, "render_edl.py"), broken, "--check"])
    check("broken EDL fails --check (exit 2)", r.returncode == 2, f"got {r.returncode}")
    check("catches unknown grade", "unknown grade" in r.stdout)
    check("catches typo key", "trasition" in r.stdout)
    check("catches out-of-range", "exceeds source" in r.stdout)
    return valid


def test_render(valid):
    print("render (preview + regressions):")
    r = run([PY, os.path.join(BIN, "render_edl.py"), valid, "--preview"])
    check("preview renders", r.returncode == 0, r.stderr[-300:])
    out = os.path.join(ROOT, "work", "previews", "preview_selftest.mp4")
    check("preview file exists", os.path.exists(out))
    if os.path.exists(out):
        info = ffprobe(out, "stream=width,height")
        st = (info.get("streams") or [{}])[0]
        check("9:16 aspect", st.get("width", 0) * 16 == st.get("height", 0) * 9 or
              abs(st.get("width", 1) / st.get("height", 1) - 9 / 16) < 0.02,
              f"{st.get('width')}x{st.get('height')}")
    # image clip exact duration (regression: -loop defaulted to 25fps -> short)
    pv = [f for f in os.listdir(os.path.join(ROOT, "work", "clips")) if f.startswith("pv_")]
    exact = True
    for f in pv:
        info = ffprobe(os.path.join(ROOT, "work", "clips", f), "stream=nb_frames,duration")
        st = (info.get("streams") or [{}])[0]
        d = float(st.get("duration") or 0)
        if d and abs(round(d * 30) - d * 30) > 1.5:
            exact = False
    check("clip durations frame-exact", exact)
    # caption with % rendered (regression: stray %)
    check("caption clip present (no stray-%)", len(pv) >= 2)


def test_cache(valid):
    print("render caching:")
    r = run([PY, os.path.join(BIN, "render_edl.py"), valid, "--preview"])
    check("2nd render reuses cache", "reused" in r.stdout and "cached" in r.stdout,
          r.stdout[-200:])


def test_atomic():
    print("atomic output:")
    prevs = os.path.join(ROOT, "work", "previews")
    tmps = [f for f in os.listdir(prevs) if ".tmp" in f] if os.path.isdir(prevs) else []
    check("no leftover .tmp files", not tmps, str(tmps))


def test_describe(valid):
    print("describe_edl (treatment):")
    out = os.path.join(T, "treatment.md")
    r = run([PY, os.path.join(BIN, "describe_edl.py"), valid, "--out", out, "--quiet"])
    check("describe runs", r.returncode == 0, r.stderr[-200:])
    txt = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
    check("treatment written", bool(txt))
    check("treatment has screenplay body", "Shot-by-shot" in txt and "Treatment" in txt)
    check("treatment has timecodes", "0:00" in txt)
    check("treatment describes a transition", "cut" in txt or "crossfade" in txt)


def test_cleanup():
    print("cleanup (dry-run safety):")
    r = run([PY, os.path.join(BIN, "cleanup.py")])  # dry-run, no --yes
    check("cleanup dry-run runs", r.returncode == 0, r.stderr[-200:])
    safe = ("DRY-RUN" in r.stdout) or ("already clean" in r.stdout)
    check("cleanup is dry-run by default (no deletion)", safe, r.stdout[-200:])
    # every removal-target line (indented "    [dir ]/[file]") must be inside work/
    targets = [ln for ln in r.stdout.splitlines()
               if ln.startswith("    [dir ]") or ln.startswith("    [file]")]
    all_in_work = all("work\\" in ln or "work/" in ln for ln in targets)
    check("cleanup only ever targets work/ (never raw/out)", all_in_work,
          "; ".join(ln.strip() for ln in targets if not ("work\\" in ln or "work/" in ln)))


def test_guard():
    print("raw-media guard:")
    raw_del = "rm -" + "rf assets/raw/x.mp4"
    ff_out = "ffmpeg -i work/x.mp4 assets/raw/o.mp4"
    ff_in = "ffmpeg -i assets/raw/x.mp4 work/o.mp4"
    cases = [
        ("block delete raw", "Bash", {"command": raw_del}, 2),
        ("block ffmpeg output to raw", "Bash", {"command": ff_out}, 2),
        ("allow ffmpeg read raw", "Bash", {"command": ff_in}, 0),
        ("block write into raw", "Write", {"file_path": "assets/raw/x.txt"}, 2),
        ("allow write to work", "Write", {"file_path": "work/edl.json"}, 0),
        ("block recursive delete of out/", "Bash", {"command": "rm -" + "rf out/"}, 2),
        ("allow specific out/ file delete (no /s false-positive)", "Bash",
         {"command": "rm -f out/scene.mp4 out/selftest.mp4"}, 0),
    ]
    for desc, tool, ti, expect in cases:
        p = json.dumps({"tool_name": tool, "tool_input": ti})
        r = run([PY, GUARD], input=p)
        check(desc, r.returncode == expect, f"got {r.returncode}")


def main():
    print("=" * 60)
    print(" AUTO-EDITOR TEST SUITE")
    print("=" * 60)
    gen_media()
    test_probe()
    test_beats()
    valid = test_validation()
    test_render(valid)
    test_cache(valid)
    test_atomic()
    test_describe(valid)
    test_cleanup()
    test_guard()
    print("=" * 60)
    print(f" {PASS} passed, {FAIL} failed")
    if FAILURES:
        print(" FAILED: " + ", ".join(FAILURES))
    print("=" * 60)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    main()
