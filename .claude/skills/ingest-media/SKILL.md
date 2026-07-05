---
name: ingest-media
description: Catalog and probe raw media dropped in assets/raw. Use at the start of a project or whenever new photos/videos are added, to build work/manifest.json (type, resolution, orientation, duration, fps, rotation) that every later stage relies on.
---

# ingest-media

**Goal:** turn a pile of files in `assets/raw/` into a structured `work/manifest.json`.

## When to use
- New media has been added to `assets/raw/`.
- The manifest is missing/stale, or the edit-plan needs to know what footage exists.

## Run it
```powershell
$PY = "C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe"
& $PY bin/probe_media.py                 # scans assets/raw
& $PY bin/probe_media.py --dir path\to\dir  # scan a different folder
```

## Output — `work/manifest.json` + thumbnails
Scans **recursively** and logs any skipped non-media files. Each entry:
```jsonc
{ "path": "assets/raw/clip01.mp4", "type": "video", "w": 1920, "h": 1080,
  "dur": 18.4, "fps": 29.97, "rotation": 0, "orientation": "landscape",
  "codec": "hevc", "pix_fmt": "yuv420p10le", "hdr": true, "has_audio": true,
  "thumbs": ["work/thumbs/..._2.jpg", ...],
  "metrics": { "luma": 0.42, "blur": 0.031, "focus": {"x":0.55,"y":0.40} },
  "scene_cuts": [4.2, 9.8] }
```
Also writes **`work/thumbs/contact_sheet.jpg`** — a labeled grid of one thumb per
asset (path also in `manifest.contact_sheet`).

> **Read the contact sheet** (`Read work/thumbs/contact_sheet.jpg`) before choosing
> shots — you can see the footage, not just its dimensions. `--no-thumbs` skips
> thumbnail/metric extraction if you only need metadata.

## What to do with it
- **Read the contact sheet** to pick shots by content.
- Use **`metrics.blur`** to avoid soft/out-of-focus takes; **`metrics.luma`** feeds
  exposure matching (`match_exposure.py`); **`metrics.focus`** seeds each clip's
  `focus` point so framing:auto crops toward the subject.
- Use **`scene_cuts`** to split long clips into distinct shots.
- **HDR** (`hdr:true`, usually iPhone/Android): render tonemaps it to bt709
  automatically — no action needed, just expect correct (not washed) colour.
- Note **clip durations** so edit-plan never requests an out-point past EOF.

## Next
→ `beat-map` skill (analyze the song), then `edit-plan`.
