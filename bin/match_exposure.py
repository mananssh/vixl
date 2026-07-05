#!/usr/bin/env python3
"""match_exposure.py - auto-match exposure across an EDL's clips (cohesion step zero).

Reads work/manifest.json luma metrics (from ingest) and, for every clip in
work/edl.json, computes a per-clip 'correct' (brightness/gamma nudge) toward a
common reference (the median luma of the clips used). Writes the corrections into
the EDL's clip.correct fields so render applies them BEFORE the stylistic grade -
the single biggest step toward "shot on one camera" cohesion (EDITING_STYLE.md §6).

Usage:
    python bin/match_exposure.py                 # in-place edit work/edl.json (backup written)
    python bin/match_exposure.py --dry-run       # print suggestions, don't write
    python bin/match_exposure.py --strength 0.7  # 0..1, how strongly to pull to the reference
"""
import argparse, json, os, statistics, sys, time

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
    ap.add_argument("--edl", default=os.path.join(ROOT, "work", "edl.json"))
    ap.add_argument("--manifest", default=os.path.join(ROOT, "work", "manifest.json"))
    ap.add_argument("--strength", type=float, default=0.7)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for p in (args.edl, args.manifest):
        if not os.path.exists(p):
            print(f"[match] missing {p} - run ingest-media + build the EDL first.",
                  file=sys.stderr)
            sys.exit(1)

    edl = load(args.edl)
    manifest = load(args.manifest)
    luma_by_path = {a["path"]: (a.get("metrics") or {}).get("luma")
                    for a in manifest.get("assets", [])}

    lumas = []
    for c in edl.get("clips", []):
        l = luma_by_path.get(c.get("src"))
        if l is not None:
            lumas.append(l)
    if not lumas:
        print("[match] no luma metrics in manifest (re-run probe_media.py with thumbnails).",
              file=sys.stderr)
        sys.exit(1)

    ref = statistics.median(lumas)
    print(f"[match] reference luma (median) = {ref:.3f} across {len(lumas)} clips; "
          f"strength={args.strength}")

    changed = 0
    for i, c in enumerate(edl.get("clips", [])):
        l = luma_by_path.get(c.get("src"))
        if l is None:
            continue
        delta = (ref - l) * args.strength
        # clamp to a sane, subtle range; eq.brightness is roughly additive on 0..1
        delta = max(-0.25, min(0.25, round(delta, 3)))
        if abs(delta) < 0.01:
            continue
        correct = dict(c.get("correct") or {})
        correct["brightness"] = delta
        # gentle gamma nudge in the same direction for a more natural match
        correct["gamma"] = round(max(0.85, min(1.15, 1.0 - delta * 0.5)), 3)
        c["correct"] = correct
        changed += 1
        print(f"  clip {i}: luma {l:.3f} -> brightness {delta:+.3f}, gamma {correct['gamma']}  "
              f"({os.path.basename(c.get('src',''))})")

    if args.dry_run:
        print(f"[match] dry-run: would adjust {changed} clip(s). No file written.")
        return

    bak = args.edl + ".bak." + time.strftime("%Y%m%d_%H%M%S")
    try:
        import shutil
        shutil.copy2(args.edl, bak)
    except Exception:
        bak = None
    with open(args.edl, "w", encoding="utf-8") as f:
        json.dump(edl, f, indent=2)
    print(f"[match] adjusted {changed} clip(s) -> {os.path.relpath(args.edl, ROOT)}"
          + (f" (backup {os.path.relpath(bak, ROOT)})" if bak else ""))
    print("[match] re-run render_edl.py --check, then --preview.")


if __name__ == "__main__":
    main()
