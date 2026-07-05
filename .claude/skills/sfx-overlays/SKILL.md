---
name: sfx-overlays
description: Add captions, meme/reaction overlays, sound effects, light leaks/grain, and emphasis hits — the Chipfat/Sidemen comedy vocabulary, plus tasteful cinematic overlays. Use for punch-ins with sfx, bold pop-in captions, reaction images, whooshes on transitions, and texture overlays.
---

# sfx-overlays

**Goal:** punctuation and texture. In cinematic mode this is light (a whoosh on a
whip, a light leak between scenes, a subtle title). In comedy mode it's the whole
personality (EDITING_STYLE §5). Serve the moment — effects aren't the content.

## Asset libraries
- `assets/sfx/` — sound effects (vine-boom, airhorn, boing, whoosh, record-scratch,
  bass-drop, "bruh", cash-register, sad-violin…). Add your own `.wav`/`.mp3`.
- `assets/overlays/` — light leaks, film grain, dust, bokeh, lens flares (video/PNG).
- `assets/fonts/` — caption fonts (e.g. Montserrat-Black / Impact for comedy).

> These folders ship empty. Pull royalty-free assets with `yt-dlp`/download into
> them as needed, or point the EDL at any path you have. Log what you add.

## Captions (EDL `caption`)
```jsonc
"caption": { "text": "LET IT GO", "style": "impact", "start": 1.0, "end": 2.2,
             "y": 0.72, "pop": true }
```
- `style` → a preset in `config/presets/captions.json`: `impact`, `bold`,
  `cinematic_title`, `lower_third` (real fonts shipped in `assets/fonts/`).
  `pop:true` adds an overshoot scale-in. Literal `%` and punctuation are safe.
- Cinematic: minimal, elegant, lower-third or centered title on a downbeat.
- Comedy: thick white + heavy black outline, pop-in with a tiny overshoot/shake,
  timed to the spoken word.
- `render_edl.py` uses `drawtext` (FFMPEG_COOKBOOK §7).

## Image / reaction overlays (EDL `overlay`)
```jsonc
"overlay": { "src": "assets/overlays/lightleak.mp4", "mode": "screen", "opacity": 0.4 }
"overlay": { "src": "assets/overlays/reaction.png", "mode": "over",
             "scale": 0.5, "pos": "top-right", "start": 1.2, "end": 2.0 }
```
- `mode`: `screen` (leaks/grain/flares), `over` (reaction images/arrows/circles).
- Freeze-frame + zoom + red-circle highlight on the mocked thing is a classic
  comedy beat — combine `speed:0`/held frame + a circle PNG overlay + `zoompunch`.

## Sound effects (paired with emphasis)
Add an sfx hit alongside a motion emphasis. SFX are mixed in `audio-post`, but you
declare them in the EDL as timeline events:
```jsonc
"sfx": [ { "src": "assets/sfx/vine_boom.wav", "at": 1.05, "gain_db": -2 } ]
```
Pair conventions: zoompunch → vine-boom/bass-drop; whip transition → whoosh;
freeze reaction → record-scratch; fail → sad-violin; win → airhorn.

## Restraint
Land the joke *then* the sfx. Don't stack five effects on a line that isn't funny.
In cinematic mode, if in doubt, leave it out.
