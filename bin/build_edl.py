#!/usr/bin/env python3
"""build_edl.py - scaffold a first-draft work/edl.json (EDL v2) from manifest+beats.

Produces a VALID, RENDERABLE starting point that snaps clips onto beats, pads
dissolves so cuts don't drift off the beat, applies the default grade, and carries
per-clip focus points from ingest. The agent then refines shot choice/order/effects
(edit-plan skill + docs/EDITING_STYLE.md). This draft only rotates through assets in
order - it is a skeleton, not the finished edit.

Usage:
    python bin/build_edl.py [--section drop] [--target 45] [--beats-per-cut 2] [--force]
"""
import argparse, json, os, sys, time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=os.path.join(ROOT, "work", "manifest.json"))
    ap.add_argument("--beats", default=os.path.join(ROOT, "work", "beats.json"))
    ap.add_argument("--project", default=os.path.join(ROOT, "config", "project.json"))
    ap.add_argument("--brief", default=os.path.join(ROOT, "work", "brief.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "work", "edl.json"))
    ap.add_argument("--section", default=None)
    ap.add_argument("--target", type=float, default=None)
    ap.add_argument("--beats-per-cut", type=int, default=2)
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing edl.json (a backup is always written)")
    args = ap.parse_args()

    for p in (args.manifest, args.beats, args.project):
        if not os.path.exists(p):
            print(f"[build_edl] missing {p} - run ingest-media and beat-map first.",
                  file=sys.stderr)
            sys.exit(1)

    # never clobber a hand-refined edit silently
    if os.path.exists(args.out):
        bak = args.out + ".bak." + time.strftime("%Y%m%d_%H%M%S")
        try:
            import shutil
            shutil.copy2(args.out, bak)
        except Exception:
            bak = None
        if not args.force:
            print(f"[build_edl] {os.path.relpath(args.out, ROOT)} already exists. "
                  f"Refusing to overwrite a possibly hand-refined edit.\n"
                  f"           Backup written: {os.path.relpath(bak, ROOT) if bak else 'FAILED'}\n"
                  f"           Re-run with --force to regenerate from scratch.",
                  file=sys.stderr)
            sys.exit(2)
        elif bak:
            print(f"[build_edl] backed up existing edit -> {os.path.relpath(bak, ROOT)}")

    manifest = load(args.manifest)
    beats = load(args.beats)
    proj = load(args.project)
    fmt = proj["format"]
    brief = load(args.brief) if os.path.exists(args.brief) else {}
    if brief:
        print(f"[build_edl] using work/brief.json (title={brief.get('title')!r}).")

    assets = [a for a in manifest["assets"] if a["type"] in ("video", "image")]
    if not assets:
        print("[build_edl] no visual assets in manifest.", file=sys.stderr)
        sys.exit(1)

    # optionally drop clearly out-of-focus shots if we have metrics and enough spares
    sharp = [a for a in assets if (a.get("metrics") or {}).get("blur", 1) >= 0.0008]
    if len(sharp) >= max(4, len(assets) // 2):
        dropped = len(assets) - len(sharp)
        if dropped:
            print(f"[build_edl] skipped {dropped} likely-soft/low-detail shot(s) by blur metric.")
        assets = sharp

    all_beats = beats["beats"]
    downbeats = set(beats.get("downbeats", all_beats))
    target = (args.target or brief.get("target_seconds")
              or proj["length"]["target_max_seconds"])

    secs = beats.get("sections", [])
    section = None
    want_section = args.section or brief.get("song_section")
    if want_section and want_section not in ("full",):
        section = next((s for s in secs if s.get("label") == want_section), None)
    if not section:
        hi = [s for s in secs if s.get("energy") == "high"]
        section = max(hi, key=lambda s: s["end"] - s["start"]) if hi else None

    start = section["start"] if section else (all_beats[0] if all_beats else 0.0)
    db_after = [d for d in sorted(downbeats) if d >= start - 0.05]
    audio_start = db_after[0] if db_after else start

    win = [b for b in all_beats if audio_start - 0.01 <= b <= audio_start + target + 0.01]
    if len(win) < 2:
        win = all_beats[:]
        audio_start = win[0] if win else 0.0

    bpc = max(1, args.beats_per_cut)
    cut_beats = win[::bpc]

    grade = proj["look"]["default_grade"]
    clips = []
    ai = 0
    timeline = 0.0
    for i in range(len(cut_beats) - 1):
        gap = round(cut_beats[i + 1] - cut_beats[i], 3)
        if gap <= 0.05:
            continue
        a = assets[ai % len(assets)]
        ai += 1
        # dissolve occasionally on downbeats; PAD the clip by the transition dur so
        # the beat grid (and every later cut) does not drift early.
        use_dissolve = (cut_beats[i + 1] in downbeats and i % 4 == 3
                        and i < len(cut_beats) - 2)
        td = 0.4 if use_dissolve else 0.0
        dur = round(gap + td, 3)

        clip = {"src": a["path"], "grade": grade, "framing": "auto",
                "focus": a.get("focus") or {"x": 0.5, "y": 0.5}, "speed": 1.0,
                "motion": {"kind": "kenburns", "zoom": "in", "pan": "none", "amount": 0.10},
                "transition": {"type": "dissolve", "dur": td} if td else {"type": "cut"},
                "caption": None, "overlay": None, "cutout": None}
        if a["type"] == "image":
            clip["dur"] = dur
        else:
            src_dur = a.get("dur") or (dur + 1.0)
            tin = round(min(max(0.0, src_dur * 0.2), max(0.0, src_dur - dur)), 3)
            clip["in"] = tin
            clip["out"] = round(min(tin + dur, src_dur), 3)
            clip["dur"] = round(clip["out"] - tin, 3)
        clips.append(clip)
        timeline += clip["dur"] - td
        if timeline >= target:
            break

    song = next((a["path"] for a in manifest["assets"] if a["type"] == "audio"),
                beats.get("song", "assets/raw/song.mp3"))

    edl = {
        "edl_version": 2,
        "meta": {"width": fmt["width"], "height": fmt["height"],
                 "fps": fmt["fps"],
                 "title": brief.get("title") or proj.get("title", "edit")},
        "audio": {"src": song, "start": round(audio_start, 3),
                  "fade_in": 0.4, "fade_out": 1.2, "loudnorm": True, "duck_with": None},
        "clips": clips,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(edl, f, indent=2)

    print(f"[build_edl] drafted {len(clips)} clips | ~{timeline:.1f}s | "
          f"audio.start={audio_start:.2f}s | section={section['label'] if section else 'n/a'}")
    print(f"[build_edl] -> {os.path.relpath(args.out, ROOT)}")

    # auto-generate the human-readable treatment/screenplay for review
    try:
        import subprocess
        subprocess.run([sys.executable, os.path.join(ROOT, "bin", "describe_edl.py"),
                        args.out, "--quiet"], check=False)
        print("[build_edl] wrote work/treatment.md (human-readable screenplay) - "
              "review/edit it BEFORE rendering.")
    except Exception as e:
        print(f"[build_edl] (treatment skipped: {e})", file=sys.stderr)

    print("[build_edl] NOW REFINE: shot choice/order (Read work/thumbs/contact_sheet.jpg), "
          "hero cutouts, transitions, captions. Then re-run describe_edl.py, "
          "then render_edl.py --check.")


if __name__ == "__main__":
    main()
