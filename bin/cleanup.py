#!/usr/bin/env python3
"""cleanup.py - remove intermediary artifacts, leaving only input and output.

MANUAL ONLY. Never run as part of the pipeline. Wipes derivatives under work/
(thumbnails, normalized clips, cutouts, previews, cache, backups) so the project
is back to just:  assets/raw/ (input)  +  out/ (deliverables).

Safe by design:
- NEVER touches assets/raw/ or out/ (input + output are sacred).
- Only ever deletes inside work/ (paths are resolved and re-checked).
- Dry-run by DEFAULT: prints what it would remove. Pass --yes to actually delete.
- --keep-edit preserves the small, reproducible edit definition
  (edl.json, beats.json, manifest.json, brief.json, treatment.md) while still
  clearing the heavy intermediates.

Usage:
    python bin/cleanup.py                # dry-run: show what would be removed
    python bin/cleanup.py --yes          # remove ALL of work/ (input+output only)
    python bin/cleanup.py --yes --keep-edit   # keep the edit definition, drop heavy stuff
"""
import argparse, os, shutil, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")

# small files that ARE the reproducible edit - kept under --keep-edit
EDIT_DEFN = {"edl.json", "beats.json", "manifest.json", "brief.json", "treatment.md"}


def _inside_work(path):
    """True only if path is strictly within work/ (guards against symlink/.. escapes)."""
    rp = os.path.realpath(path)
    rw = os.path.realpath(WORK)
    return rp == rw or rp.startswith(rw + os.sep)


def _size(path):
    total = 0
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    for dp, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def _human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="actually delete (default: dry-run)")
    ap.add_argument("--keep-edit", action="store_true",
                    help="keep edl/beats/manifest/brief/treatment; drop heavy intermediates")
    args = ap.parse_args()

    if not os.path.isdir(WORK):
        print("[cleanup] nothing to do - work/ does not exist.")
        return

    targets = []
    for name in sorted(os.listdir(WORK)):
        p = os.path.join(WORK, name)
        if name == ".gitkeep":
            continue
        if args.keep_edit and name in EDIT_DEFN:
            continue
        if not _inside_work(p):  # refuse anything that resolves outside work/
            print(f"[cleanup] SKIP (outside work/): {name}", file=sys.stderr)
            continue
        targets.append(p)

    if not targets:
        print("[cleanup] work/ already clean (nothing to remove).")
        return

    total = sum(_size(p) for p in targets)
    mode = "WOULD REMOVE (dry-run)" if not args.yes else "REMOVING"
    print(f"[cleanup] {mode} {len(targets)} item(s) from work/  (~{_human(total)}):")
    for p in targets:
        kind = "dir " if os.path.isdir(p) else "file"
        print(f"    [{kind}] {os.path.relpath(p, ROOT)}  ({_human(_size(p))})")

    if args.keep_edit:
        kept = [n for n in EDIT_DEFN if os.path.exists(os.path.join(WORK, n))]
        if kept:
            print(f"[cleanup] keeping edit definition: {', '.join(sorted(kept))}")

    print("[cleanup] assets/raw/ (input) and out/ (output) are never touched.")

    if not args.yes:
        print("\n[cleanup] DRY-RUN — nothing deleted. Re-run with --yes to remove.")
        return

    removed = 0
    for p in targets:
        if not _inside_work(p):  # re-check right before deleting
            continue
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
            removed += 1
        except OSError as e:
            print(f"[cleanup] could not remove {os.path.relpath(p, ROOT)}: {e}",
                  file=sys.stderr)
    print(f"\n[cleanup] removed {removed} item(s), freed ~{_human(total)}.")


if __name__ == "__main__":
    main()
