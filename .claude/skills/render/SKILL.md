---
name: render
description: Render work/edl.json into a video — a fast low-res preview for sign-off, or the full-quality final export. Use to produce any deliverable. Always render a preview and get approval before the slow final render.
---

# render

**Goal:** turn the EDL into an actual video. Two-phase pipeline (normalize each
clip, then assemble with transitions + audio) — see PIPELINE.md §5.

## Workflow (do it in this order)
```powershell
$PY = "C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe"

# 1) validate the EDL (schema, files exist, durations, beat alignment) — no render
& $PY bin/render_edl.py work/edl.json --check

# 2) fast preview → work/previews/preview_<title>.mp4  (low-res, high CRF)
& $PY bin/render_edl.py work/edl.json --preview

#    → SHOW THE PREVIEW TO THE USER AND GET SIGN-OFF

# 3) full-quality final → out/<title>.mp4
& $PY bin/render_edl.py work/edl.json
```

Render always runs `--check` first and refuses to render an invalid EDL.
Normalized clips are **content-hash cached** in `work/clips/` — editing one clip
re-encodes only that clip (delete `work/clips/*` to force a full re-render).
Output is written atomically (`*.tmp.mp4` then rename), so a failed render never
leaves a truncated file masquerading as done.

## Options
- `--check` — validate only; strict (unknown keys/presets, bad ranges → exit 2);
  prints timeline duration, aggregate beat alignment, and song-too-short warnings.
- `--preview` — height from `config.render.preview_height` (default 640), CRF 30,
  `veryfast`. Seconds, not minutes.
- `--final` (default) — 1080×1920, CRF 18, `slow`, `+faststart`, loudnorm audio.
- `--clip N` — render just clip N to `work/cache/` for spot-checking one shot/effect.
- `--from N --to M` — render a range of clips (iterate on a section without a full render).

## Rules
- **Never skip the preview.** Full renders are slow; catch problems cheap.
- **Long finals:** run in the background and report when done — don't block.
- Output must be exactly 1080×1920, 30fps, yuv420p, loudness-normalized, clean
  fades, no black bars (Definition of Done, AGENTS.md §6).
- After a final render, tell the user the path, duration, and file size, and note
  anything dropped/capped.

## Troubleshooting
- **A/V drift or wrong length:** transitions overlap neighbours — the timeline is
  `sum(dur) - sum(transition.dur)`. Re-run `--check` to see the computed duration.
- **Soft footage after zoom:** ensure Ken Burns scales the source up first (motion-fx).
- **Colour mismatch between shots:** fix in `color-grade` (exposure/WB before style).
- **A clip errors out:** render it alone with `--clip N` to isolate the bad filter.
