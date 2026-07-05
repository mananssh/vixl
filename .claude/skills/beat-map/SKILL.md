---
name: beat-map
description: Analyze the background song with librosa to extract tempo, beat times, downbeats, and energy sections into work/beats.json. Use before designing the edit so every cut can be snapped to the music. Also use to pick which song section to build a short edit around.
---

# beat-map

**Goal:** produce `work/beats.json` — the rhythmic skeleton the whole edit hangs on.

## When to use
- You have the song and are about to design the edit.
- You need to choose the strongest ~30–60s section for a short edit.

## Run it
```powershell
$PY = "C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe"
& $PY bin/detect_beats.py assets/raw/song.mp3
# focus on a section and set bar length:
& $PY bin/detect_beats.py assets/raw/song.mp3 --start 40 --end 75 --beats-per-bar 4
```

## Output — `work/beats.json`
```jsonc
{
  "tempo": 122.0,
  "duration": 194.3,
  "beats": [0.51, 1.02, 1.53, ...],       // seconds
  "downbeats": [0.51, 2.53, 4.55, ...],   // every Nth beat (bar starts)
  "sections": [                            // coarse energy segmentation
    { "start": 0.0, "end": 16.0, "energy": "low",  "label": "intro" },
    { "start": 41.0, "end": 73.0, "energy": "high", "label": "drop" }
  ]
}
```

## How to use it in the edit
- **Snap cuts to `beats`.** Convert to frames with `round(t * fps)`.
- **Land big transitions/titles on `downbeats`** (bar starts feel like "arrivals").
- **Match cut speed to `sections`** — see EDITING_STYLE §2 (intro=slow, drop=fast).
- For a short edit, pick the highest-energy section (often labeled `drop`/`chorus`)
  and set the EDL's `audio.start` to its start; end on the next downbeat after your
  target length.

## Notes
- librosa's tempo can land on a half/double (e.g. 61 vs 122 BPM). If shot pacing
  feels off by 2×, re-check tempo and adjust beat subdivision.
- Downbeat detection here is heuristic (every `beats-per-bar` beats from the first
  strong beat). Nudge `--beats-per-bar` if bars feel misaligned.

## Next
→ `edit-plan` skill (design `work/edl.json`).
