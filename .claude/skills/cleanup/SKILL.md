---
name: cleanup
description: Manually reset the project to just input and output — delete all intermediary artifacts under work/ (thumbnails, normalized clips, cutouts, previews, render cache, backups). NEVER touches assets/raw/ (input) or out/ (deliverables). Use only when the user explicitly asks to clean up / free space / reset; never as part of a render.
---

# cleanup

**Goal:** on explicit request, wipe the working intermediates so the project is
back to **input (`assets/raw/`) + output (`out/`)** only. Everything under `work/`
is regenerable from the raw media + the EDL, so it's safe to discard.

**Do not run this automatically.** It's a manual, user-initiated action —
intermediates make re-renders cheap (the render cache alone saves re-encoding
unchanged clips), so only clear them when the user asks.

## Usage
```powershell
$PY = "C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe"

# 1) DRY-RUN first (default) — shows exactly what would be deleted + sizes
& $PY bin/cleanup.py

# 2) full clean — leaves only assets/raw/ (input) and out/ (output)
& $PY bin/cleanup.py --yes

# keep the small, reproducible edit definition (edl/beats/manifest/brief/treatment)
# so you can re-render later without redoing ingest/beat-map/planning:
& $PY bin/cleanup.py --yes --keep-edit
```

## What it removes / keeps
- **Removes** (inside `work/` only): `thumbs/`, `clips/`, `cutouts/`, `previews/`,
  `cache/`, `*.bak.*` backups — and, without `--keep-edit`, the JSON/markdown
  definition files too.
- **`--keep-edit`** preserves `edl.json`, `beats.json`, `manifest.json`,
  `brief.json`, `treatment.md` (tiny; lets you re-render without re-ingesting).
- **Never touches** `assets/raw/` or `out/`. The tool re-checks that every deletion
  path resolves inside `work/` before removing it.

## Rules
- **Always dry-run first** and show the user what will go (and the space freed)
  before passing `--yes`.
- If the user wants to keep the finished edit reproducible, use `--keep-edit`.
- Confirm the final render is safely in `out/` (and delivered) before a full clean —
  once `work/` is gone, re-rendering means re-ingesting + re-planning unless you
  kept the edit definition.
