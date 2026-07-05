---
name: transitions
description: Choose and wire transitions between shots (hard cut, dissolve, whip-pan, zoom, luma/gradient wipe) using ffmpeg xfade, timed so the transition midpoint lands on a beat. Use when deciding how shots connect. Every transition must be motivated.
---

# transitions

**Goal:** connect shots so the joins feel intentional and land on the music.
**Rule:** every transition must be motivated (EDITING_STYLE §1.3). Default to hard
cuts; reach for a transition only when it adds meaning or hides motion.

## Presets — `config/presets/transitions.json`
Named presets referenced by the EDL clip's `transition.type`:
- `cut` — hard cut (the default; no xfade).
- `dissolve` — 0.4–0.8s cross-dissolve; "time passed / same mood".
- `whip_left` / `whip_right` — fast smoothleft/right (0.2–0.3s); needs existing pan.
- `zoom` — zoomin transition; needs a continuing push-in.
- `luma_wipe` — elegant gradient wipe for scene changes.
- `dip_black` / `dip_white` — fadeblack/fadewhite for section breaks or the ending.

## How timing works
`xfade` overlaps clip A and clip B by `duration`, starting at `offset`. To land the
**midpoint on a beat**, the transition should start `duration/2` before that beat.
`render_edl.py` computes offsets automatically from each clip's `dur` and the
`transition.dur` — you just choose the type and duration in the EDL.

```jsonc
"transition": { "type": "dissolve", "dur": 0.5 }   // into the NEXT clip
"transition": { "type": "cut" }                     // hard cut (dur ignored)
```

## Choosing (cinematic default)
- Mostly **hard cuts** on beats.
- **Dissolves** between locations/moods (sparingly).
- **Whip/zoom** only on shots with matching motion, midpoint on the beat.
- **Luma wipe** for a graceful scene change.
- **Match cuts** (shape/motion/colour continuity) are hard cuts that feel magic —
  plan these in edit-plan by ordering compatible shots adjacently.

## High-energy mode
Fast whip-pans and zoom transitions between bits, each on the beat; see
EDITING_STYLE §5 and the `sfx-overlays` skill to pair with a whoosh sfx.

## Reference
Full `xfade` transition list + audio crossfade + N-clip chaining caveat:
FFMPEG_COOKBOOK §6. Don't hand-chain >3 clips — let `render_edl.py` do the offset math.
