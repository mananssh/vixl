#!/usr/bin/env python3
"""status.py - print current project state and the recommended next step.

Used by the SessionStart hook (auto-prints each session / after compaction) and
runnable any time. Defensive: never raises, so it can't break a session.
"""
import json, os, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _load(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    return _safe(lambda: json.load(open(p, encoding="utf-8")))


def _count_raw():
    d = os.path.join(ROOT, "assets", "raw")
    exts = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v",
            ".jpg", ".jpeg", ".png", ".heic", ".webp", ".avif",
            ".mp3", ".wav", ".m4a", ".flac", ".aac"}
    if not os.path.isdir(d):
        return 0, 0, 0
    v = i = a = 0
    for f in os.listdir(d):
        e = os.path.splitext(f)[1].lower()
        if e in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}:
            v += 1
        elif e in {".jpg", ".jpeg", ".png", ".heic", ".webp", ".avif"}:
            i += 1
        elif e in {".mp3", ".wav", ".m4a", ".flac", ".aac"}:
            a += 1
    return v, i, a


def _latest(dirrel, exts=(".mp4",)):
    d = os.path.join(ROOT, dirrel)
    if not os.path.isdir(d):
        return None
    files = [os.path.join(d, f) for f in os.listdir(d)
             if os.path.splitext(f)[1].lower() in exts]
    if not files:
        return None
    f = max(files, key=lambda p: _safe(lambda: os.path.getmtime(p), 0))
    return os.path.relpath(f, ROOT).replace("\\", "/")


def main():
    print("=" * 64)
    print(" AUTO-EDITOR - PROJECT STATUS  (read AGENTS.md for the manual)")
    print("=" * 64)

    proj = _load("config/project.json") or {}
    look = proj.get("look", {})
    fmt = proj.get("format", {})
    length = proj.get("length", {})
    if fmt:
        print(f" Target: {fmt.get('width')}x{fmt.get('height')} @ {fmt.get('fps')}fps "
              f"| {length.get('target_min_seconds')}-{length.get('target_max_seconds')}s "
              f"| vibe: {look.get('vibe')} | cutouts: {proj.get('cutouts', {}).get('policy')}")

    v, i, a = _count_raw()
    print(f"\n RAW MEDIA (assets/raw): {v} video, {i} image, {a} audio")

    brief = _load("work/brief.json")
    manifest = _load("work/manifest.json")
    beats = _load("work/beats.json")
    edl = _load("work/edl.json")
    treatment = os.path.exists(os.path.join(ROOT, "work", "treatment.md"))
    preview = _latest("work/previews")
    final = _latest("out")

    def mark(x):
        return "x" if x else " "

    print("\n PIPELINE:")
    print(f"   [{mark(manifest)}] 1. ingest      "
          + (f"{manifest.get('count')} assets cataloged" if manifest else "not run — run ingest-media"))
    print(f"   [{mark(beats)}] 2. beat-map    "
          + (f"~{beats.get('tempo')} BPM, {len(beats.get('beats', []))} beats" if beats else "not run — run beat-map"))
    print(f"   [{mark(edl)}] 3. edit-plan   "
          + (f"{len(edl.get('clips', []))} clips in work/edl.json" if edl else "not built — run edit-plan"))
    print(f"   [{mark(treatment)}] 3b. treatment  "
          + ("work/treatment.md (review before render)" if treatment else "none yet — describe_edl.py"))
    print(f"   [{mark(preview)}] 4. preview     " + (preview or "none yet — render --preview"))
    print(f"   [{mark(final)}] 5. final       " + (final or "none yet — render (after sign-off)"))

    # recommend next step
    print("\n NEXT STEP:")
    if v == 0 and i == 0:
        nxt = "Add media + song to assets/raw/, then run ingest-media."
    elif not manifest:
        nxt = "Run ingest-media:  python bin/probe_media.py"
    elif a == 0 and not beats:
        nxt = "Add the song to assets/raw/, then run beat-map."
    elif not beats:
        nxt = "Run beat-map:  python bin/detect_beats.py assets/raw/<song>"
    elif not edl:
        nxt = "Design the edit (edit-plan). Draft:  python bin/build_edl.py  then refine."
    elif not treatment:
        nxt = "Write the treatment for review:  python bin/describe_edl.py  (then show the user)"
    elif not preview:
        nxt = "Get sign-off on work/treatment.md, then preview:  python bin/render_edl.py work/edl.json --preview"
    elif not final:
        nxt = "Get sign-off on the preview, then final:  python bin/render_edl.py work/edl.json"
    else:
        nxt = "Final exists. Iterate on work/edl.json and re-render, or you're done."
    print("   " + nxt)
    print("=" * 64)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[status] (non-fatal) {e}", file=sys.stderr)
        sys.exit(0)
