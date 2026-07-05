---
name: subject-cutout
description: Pop a person/subject off their background using rembg, for hero-shot moments and overlays. Use on a few select stills/shots only (hero policy) — it's slow and quality varies on video. Produces RGBA PNG (stills) or alpha MOV (video) in work/cutouts, composited via the EDL.
---

# subject-cutout

**Goal:** isolate the subject for a signature moment — e.g. freeze on the hero,
cut them out, push in over a blurred/darkened copy of the same frame with a soft
rim glow. Used once or twice it's stunning; on every clip it's tacky
(EDITING_STYLE §4). Respect `config.cutouts.max_cutout_clips`.

## Run it
```powershell
$PY = "C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe"
# still image → transparent PNG
& $PY bin/cutout.py assets/raw/hero.jpg -o work/cutouts/hero.png
# a single frame grabbed at time T from a video
& $PY bin/cutout.py assets/raw/hero.mp4 --frame 3.2 -o work/cutouts/hero.png
# full video → RGBA (QuickTime RLE, keeps alpha; large + slow)
& $PY bin/cutout.py assets/raw/hero.mp4 -o work/cutouts/hero.mov
```

The u2net model is pre-cached at `C:\Users\manan\.u2net\u2net.onnx`. If a model
download is ever needed and fails inside Python (DNS gotcha), fetch via
PowerShell `Invoke-WebRequest` — see PIPELINE.md.

## Use it in the EDL
Reference the result on a clip:
```jsonc
{ "src": "assets/raw/hero.mp4", "in": 3.0, "out": 5.0,
  "cutout": "work/cutouts/hero.png",
  "motion": { "kind": "kenburns", "to": "in", "amount": 0.18 } }
```
`render_edl.py` composites the cutout over a treated background (by default a
blurred, darkened version of the same source) with an optional push-in.

## Quality tips
- **Stills >> video** for clean edges. Prefer a freeze-frame cutout to per-frame
  video matting whenever the moment allows.
- Choose frames with good subject/background separation and even lighting.
- Add a subtle rim glow / drop shadow when compositing so the subject doesn't look
  pasted (see compositing recipe, FFMPEG_COOKBOOK §7).
- If edges are rough on a video clip, **don't ship it** — fall back to a graded
  full-frame shot and note it. Rough matte lines scream amateur.

## Alternate models
`bin/cutout.py --model u2net_human_seg` (people-tuned) or `isnet-general-use`
(often crisper). These download on first use — pre-fetch if DNS is flaky.
