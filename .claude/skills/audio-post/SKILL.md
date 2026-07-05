---
name: audio-post
description: Build and sweeten the final audio — music fades, loudness normalization (~-14 LUFS), ducking a music bed under voice-over (sidechain), EQ/reverb on SFX via sox, and mixing SFX events into the track. Use when audio needs more than the default fades+loudnorm that render applies.
---

# audio-post

**Goal:** clean, punchy, correctly-loud audio. For the common case (music fades +
loudnorm) `render_edl.py` handles it from the EDL `audio` block — you only need
this skill for richer mixing.

## The default (already automatic)
EDL `audio`: `{ src, start, fade_in, fade_out, loudnorm:true }` → render applies
`afade` in/out and `loudnorm=I=-14:TP=-1.5:LRA=11`, cut to video length. Targets
match `config/project.json.render`.

## Ducking music under a voice-over
Set `audio.duck_with` to the VO path in the EDL, or build the bed manually:
```bash
ffmpeg -i music.wav -i vo.wav -filter_complex \
"[0:a][1:a]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[m];[m][1:a]amix=inputs=2:normalize=0" ducked.wav
```
Then point `audio.src` at `ducked.wav`.

## Mixing SFX events
EDL clip `sfx: [{src, at, gain_db}]` events are collected across the timeline and
mixed over the music at their timeline positions. To do it by hand, delay each sfx
and amix:
```bash
ffmpeg -i music.wav -i boom.wav -filter_complex \
"[1:a]adelay=1050|1050,volume=-2dB[s];[0:a][s]amix=inputs=2:normalize=0:duration=first" mixed.wav
```

## sox sweetening
```bash
sox boom.wav boom_big.wav gain -n -2 reverb 30      # normalize + space
sox vo.wav vo_clean.wav highpass 90 compand 0.02,0.20 -60,-40 -6  # clean voice
sox in.wav up.wav pitch 300 tempo 1.5               # comedy speed-up + pitch
```

## Craft (EDITING_STYLE §7)
- Always fade — no hard starts/stops. Short in (~0.4s), longer tail (~1–1.5s).
- Normalize to ~-14 LUFS for social.
- SFX pop above the music in the moment, then get out of the way.
- A beat of near-silence before the drop makes it hit harder.

## Reference
FFMPEG_COOKBOOK §9 (mux/duck) and §10 (sox).
