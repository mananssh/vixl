---
name: motion-fx
description: Add movement to shots — Ken Burns push/pan on stills, zoom punch-in on beats, speed ramps and slow-mo, camera shake, RGB split/chromatic aberration. Use to keep static shots alive and to add emphasis. Match motion direction across cuts.
---

# motion-fx

**Goal:** no dead shots. Give almost every shot motion, and match motion direction
across cuts (EDITING_STYLE §1.4). Motion is set per-clip in the EDL `motion` field.

## Presets — `config/presets/motion.json`
Referenced by `motion.kind` (preset defaults merge with per-clip overrides):
- `kenburns` — smooth push/pan (real start→end interpolation on a 2× prescaled
  frame, so no jitter). Params: `zoom` ∈ `in|out`, `pan` ∈ `none|left|right|up|down`,
  `amount` (zoom fraction, e.g. 0.12).
- `zoompunch` — hard, sudden scale-up (110–140%) for N frames on a beat; emphasis.
- `speedramp` — smooth accelerate/decelerate. Params: `from_speed`,`to_speed`
  (video only; implemented as a log-PTS ramp).
- `shake` — camera shake on impact (pair with an sfx hit in comedy mode).
- `rgbsplit` — chromatic aberration hit for the biggest moments.
- `none` — no added motion (only for shots with strong real camera movement).

## EDL usage
```jsonc
"motion": { "kind": "kenburns", "zoom": "in", "pan": "right", "amount": 0.12 }
"motion": { "kind": "zoompunch", "amount": 0.25, "at": 0.0, "hold": 0.4 }
"motion": { "kind": "speedramp", "from_speed": 1.0, "to_speed": 0.4 }
"speed": 0.5     // constant slow-mo; "speed": 0 = freeze-frame at "in"
```

## Craft notes
- **Ken Burns:** scale the source up (~2×) before zoompan so the push doesn't
  soften the image. Keep cinematic pushes gentle (5–12% over the shot).
- **Zoom punch** lands on the beat/punchline; hold briefly; then cut. In cinematic
  mode use rarely; in comedy mode it's a staple.
- **Speed ramps** should ease (not linear) and the cut should fall on the beat.
- **Smooth slow-mo** needs `minterpolate` (slow to render) — see FFMPEG_COOKBOOK §5.
- **Shake / RGB split** are emphasis only — never on a non-moment.
- **Match direction:** if a subject exits left, have the next shot enter from the
  right or continue the push — set complementary `from`/`to` across adjacent clips.

## Reference
Exact zoompan / setpts / minterpolate / crop-shake / rgbashift recipes:
FFMPEG_COOKBOOK §5.
