---
name: edit-plan
description: The editor's brain. Turn work/manifest.json + work/beats.json into work/edl.json — choosing shots, order, beat-quantised durations, per-clip grade/motion/transitions, captions/overlays, and hero cutouts. Use this to design or revise the actual edit. Read docs/EDITING_STYLE.md before planning.
---

# edit-plan

**Goal:** author `work/edl.json`, the reproducible description of the whole edit.
This is where taste happens. **Read [docs/EDITING_STYLE.md](../../../docs/EDITING_STYLE.md) first.**

## Inputs
- `work/manifest.json` (footage), `work/beats.json` (rhythm), `config/project.json` (locked settings).
- `work/brief.json` if it exists (the user's intent — from the `creative-brief`
  skill). Let it drive shot selection (`must_include`/`avoid`/`hero_moment`),
  captions, title text, tone and target length. If there's no brief and the ask is
  vague, run `creative-brief` first.

## Output for sign-off: the treatment (screenplay)
The EDL is precise but hard to picture. **Always emit a human-readable treatment
and get the user's OK on it before rendering clips** — editing prose is free,
re-encoding is not.
```powershell
$PY = "C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe"
& $PY bin/describe_edl.py            # work/edl.json -> work/treatment.md (+ prints it)
```
`build_edl.py` writes `work/treatment.md` automatically; re-run `describe_edl.py`
after every EDL change to refresh it. Show it to the user, take their notes, edit
the EDL, refresh, repeat — *then* render.

## Process (how a pro builds the timeline)
1. **Pick the song window.** From `beats.json.sections`, choose the strongest
   ~30–60s (usually the drop/chorus). Set `audio.start` there; plan to end on a downbeat.
2. **Budget the shots.** Given the section length and the target cut pacing per
   energy (EDITING_STYLE §2), you'll need roughly `length / avg_shot_len` shots.
3. **Select & order** from the manifest (EDITING_STYLE §3): cull hard, alternate
   wide/close & static/moving, group into location phrases, save a money shot for a
   drop and one for the end.
4. **Quantise durations to beats.** Each clip's on-screen length = an integer
   number of beats appropriate to its section. Accumulate and confirm cut times
   land on `beats` (transitions on `downbeats`).
5. **Assign treatment per clip:** `grade` (usually the project default),
   `motion` (Ken Burns on stills, subtle push on video), `transition` into the
   next clip (mostly hard cuts + occasional dissolves; motivated only).
6. **Place hero cutouts** (≤ `config.cutouts.max_cutout_clips`) — see subject-cutout.
7. **Optional captions/overlays** (cinematic: minimal; comedy: see sfx-overlays).
8. **Audio:** fades + loudnorm (audio-post for anything richer).

You can scaffold a first draft automatically, then refine by hand:
```powershell
$PY = "C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe"
& $PY bin/build_edl.py            # draft work/edl.json from manifest+beats+project
```
`build_edl.py` picks a section, lays clips onto beats, and applies the default
grade so you get a valid, renderable EDL immediately — then you improve shot
choice/order/effects.

## EDL schema — `work/edl.json` (edl_version 2)
Every field below is actually consumed by `render_edl.py` (no silent no-ops).
`render_edl.py --check` strictly validates this: unknown keys, unknown
grade/transition/motion names, negative speed, out-of-range in/out, and missing
files all FAIL the check (exit 2). It also fails before any render.
```jsonc
{
  "edl_version": 2,
  "meta":  { "width": 1080, "height": 1920, "fps": 30, "title": "project-0607" },
  "audio": {
    "src": "assets/raw/song.mp3",
    "start": 41.0,           // song offset where the edit begins
    "fade_in": 0.4, "fade_out": 1.2,
    "loudnorm": true,        // two-pass linear loudnorm on finals
    "duck_with": null        // optional path to a VO to sidechain-duck the music under
  },
  "clips": [
    {
      "src": "assets/raw/clip01.mp4",
      "in": 12.30, "out": 14.10,          // source in/out seconds (image: omit, use "dur")
      "dur": null,                         // on-screen duration; default (out-in)/speed
      "speed": 1.0,                        // 0.5 = slow-mo, 2 = fast, 0 = freeze-frame at "in"
      "grade": "cine_teal_orange",         // preset key OR an inline ffmpeg filter string (contains "=")
      "correct": null,                     // {brightness,gamma,saturation,...} exposure/WB fix, applied BEFORE grade (see match_exposure.py)
      "framing": "auto",                   // auto|fill|blurpad. auto=focus-aware fill (no black bars)
      "focus": { "x": 0.5, "y": 0.5 },     // crop focus point 0..1 (from ingest metrics); avoids decapitating subjects
      "motion": { "kind": "kenburns", "zoom": "in", "pan": "none", "amount": 0.12 },
      "transition": { "type": "dissolve", "dur": 0.5 },  // transition INTO next clip; {"type":"cut"} = hard cut
      "cutout":  null,                     // path to work/cutouts/xxx.png|.mov -> composited over a blurred/darkened bg
      "caption": { "text": "...", "style": "impact", "start": 1.0, "end": 2.2, "pop": true },
      "overlay": { "src": "assets/overlays/leak.mp4", "mode": "screen", "opacity": 0.4 },
      "audio":   null,                     // {"mode":"keep","volume_db":0} to keep this clip's own audio (comedy/VO)
      "sfx":     [ { "src": "assets/sfx/boom.wav", "at": 0.2, "gain_db": -2 } ],
      "notes":   null                      // free-text; ignored by render, for your own reference
    }
  ]
}
```

### Field notes
- **Duration math:** clip occupies `dur` seconds; timeline length =
  `sum(dur) - sum(transition.dur)` (transitions overlap neighbours).
  **When adding a dissolve, pad that clip's `dur` by the transition duration** so
  later cuts don't drift off the beat — `build_edl.py` does this automatically and
  `--check` reports beat alignment (a beat inside a dissolve counts as on-beat).
- **motion.kind:** `kenburns` | `zoompunch` | `shake` | `rgbsplit` | `speedramp` |
  `none`. Ken Burns: `zoom` ∈ `in|out`, `pan` ∈ `none|left|right|up|down`,
  `amount` = zoom fraction. Presets in `config/presets/motion.json` supply defaults.
- **grade** = a `grades.json` key OR an inline filter string (e.g.
  `"eq=contrast=1.1:saturation=1.2"`). **correct** is for exposure/WB matching and
  runs before the grade — usually set by `match_exposure.py`, not by hand.
- **framing `auto`** = focus-aware fill (crops toward `focus`, no black bars);
  `blurpad` = blurred-fill background for footage you don't want to crop.
- **caption.style / overlay.mode / transition.type / grade / motion** all resolve
  against `config/presets/`. Prefer keys so the look stays consistent and editable
  in one place.

### Before you plan: LOOK at the footage
`ingest-media` produces `work/thumbs/contact_sheet.jpg` (a labeled grid) plus
per-asset `metrics` (luma, blur, suggested `focus`) and `scene_cuts` in the
manifest. **Read the contact sheet** to choose shots by content, use `blur` to
avoid soft takes, and `scene_cuts` to split long clips into shots.

## Validate
```powershell
& $PY bin/render_edl.py work/edl.json --check   # validates schema + files + durations, no render
```

## Next
→ `subject-cutout` / `color-grade` / `motion-fx` / `sfx-overlays` as referenced,
→ refresh `work/treatment.md` (`describe_edl.py`) and get sign-off,
then `render` (preview first!).
