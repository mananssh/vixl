# AGENTS.md — Operating Manual for the Auto-Editor Repo

> **This is the single source of truth for how to work in this repo.**
> If you are an AI agent (Claude Code or otherwise) and you have just started
> a session or been through a context compaction, **read this file first**, then
> run the status skill (`/status` idea → `python bin/status.py`) to see where the
> current project stands. Everything you need to produce a professional-grade,
> beat-synced music-video edit lives here or is linked from here.

---

## 0. What this repo is

An **agentic video-editing studio**. You are handed a folder of raw media
(photos + video clips) and a background song, and you produce a polished,
professional-looking short-form video — the kind a top human editor
(think *Chipfat* editing for the *Sidemen*, or *Sam Kolder*-style travel
cinematics) would cut by hand.

The whole point of this repo is that **the craft is encoded here** — in the
skills, the docs, the presets and the scripts — so that we don't burn chat
context re-deriving technique every session. When in doubt, the knowledge is on
disk, not in the conversation.

The toolchain is **all CLI / local** (no cloud editors):

| Tool | Role |
|---|---|
| `ffmpeg` / `ffprobe` | The engine — cutting, grading, transitions, motion, compositing, audio |
| `librosa` (Python) | Beat / tempo / section detection |
| `rembg` (Python) | Subject cutout (background removal) |
| `ImageMagick` (`magick`) | Still-image processing, overlays, thumbnails |
| `sox` | Audio sweetening (EQ, reverb, sfx shaping) |
| `yt-dlp` | Pulling reference footage / sourcing overlays if needed |

Environment specifics (paths, gotchas) → **[docs/PIPELINE.md](docs/PIPELINE.md)**.

---

## 1. Golden rules (read every time)

1. **Never modify or delete anything in `assets/raw/`.** That is the user's
   irreplaceable source media. Read from it; write derivatives elsewhere. A hook
   enforces this, but treat `raw/` as read-only regardless.
2. **All intermediates go in `work/`; all deliverables go in `out/`.** Both are
   safe to wipe and regenerate. `work/` is gitignored.
3. **Call Python by its full path** (Scripts dir isn't on PATH in existing shells):
   `C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe`.
   The scripts refer to it as `$PY` — see [docs/PIPELINE.md](docs/PIPELINE.md).
4. **The edit is data, not vibes.** Every edit is described by an **EDL**
   (Edit Decision List) JSON at `work/edl.json`. Change the edit by editing the
   EDL and re-rendering — never by hand-crafting one-off ffmpeg commands you
   can't reproduce. See [§4](#4-the-edl-the-heart-of-the-repo).
5. **Preview before final.** Always render a fast low-res preview and get sign-off
   before committing to a full-quality render (which is slow). See the
   `render` skill.
6. **Cuts land on beats.** Unless deliberately doing a "float" (a held shot over
   a musical swell), every cut/transition midpoint should snap to a beat or
   downbeat from `work/beats.json`.
7. **Don't reinvent — reach for a skill.** The `.claude/skills/` directory covers
   every stage. If a task fits a skill, use it. Skills are listed in [§3](#3-the-skills).
8. **Log what you drop.** If you skip footage, cap a count, or bail on a cutout
   because quality was rough, say so in your summary. Silent truncation reads as
   "I used everything" when you didn't.

---

## 2. The pipeline at a glance

```
 assets/raw/  +  song
      │
      ▼
┌─────────────┐   probe every file → work/manifest.json
│ ingest-media│   (resolution, orientation, duration, fps, type)
└─────────────┘
      │
      ▼
┌─────────────┐   librosa → work/beats.json
│  beat-map   │   (tempo, beat times, downbeats, energy sections)
└─────────────┘
      │
      ▼
┌─────────────┐   the "editor's brain": pick + order shots, assign
│  edit-plan  │   durations to beats, choose transitions/effects/grade
└─────────────┘   → work/edl.json
      │
      ├──────────────┬───────────────┬──────────────┐
      ▼              ▼               ▼              ▼
┌───────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│color-grade│ │ motion-fx  │ │subject-cut │ │sfx-overlays│   (per-clip treatment,
└───────────┘ └────────────┘ └────────────┘ └────────────┘    referenced by the EDL)
      │              │               │              │
      └──────────────┴───────┬───────┴──────────────┘
                             ▼
                      ┌────────────┐  transitions + audio-post applied here
                      │   render   │  → work/previews/*.mp4  → out/final.mp4
                      └────────────┘
```

Read the full walkthrough in **[docs/PIPELINE.md](docs/PIPELINE.md)**.
Read the *creative* playbook (how a pro decides) in **[docs/EDITING_STYLE.md](docs/EDITING_STYLE.md)**.
Read the raw ffmpeg recipes in **[docs/FFMPEG_COOKBOOK.md](docs/FFMPEG_COOKBOOK.md)**.

---

## 3. The skills

Each is a directory under `.claude/skills/<name>/` with a `SKILL.md`. Invoke the
one that matches the stage; each SKILL.md is self-contained and tells you exactly
what to run.

| Skill | Use it when… |
|---|---|
| **ingest-media** | New media is dropped in `assets/raw/` and needs cataloging/probing. |
| **beat-map** | You have the song and need beat/tempo/section data to cut to. |
| **edit-plan** | You have the manifest + beat map and need to design the edit (build the EDL). This is the editor's brain. |
| **color-grade** | Choosing/applying a look (cinematic teal-orange, warm, punchy, B&W…). |
| **subject-cutout** | Popping a person off their background for a hero shot / overlay. |
| **transitions** | Choosing and wiring transitions between shots (dissolve, whip-pan, zoom, luma-wipe…). |
| **motion-fx** | Adding movement: Ken Burns, zoom punch-in, speed ramp, shake, RGB split. |
| **sfx-overlays** | Captions, meme/reaction overlays, sound effects, emphasis hits (Chipfat energy). |
| **audio-post** | Mixing the track, ducking under VO, EQ, fades, loudness normalization. |
| **render** | Producing the preview or the final export. |

---

## 4. The EDL — the heart of the repo

Everything renders from **`work/edl.json`**. This is what makes edits
reproducible, tweakable, and cheap on context: you don't re-explain the edit,
you diff the EDL.

Minimal shape (**full v2 schema + every field** in
[.claude/skills/edit-plan/SKILL.md](.claude/skills/edit-plan/SKILL.md)):

```jsonc
{
  "edl_version": 2,
  "meta": { "width": 1080, "height": 1920, "fps": 30, "title": "summer-2026" },
  "audio": {
    "src": "assets/raw/song.mp3",
    "start": 41.0,            // where in the song the edit begins (e.g. the drop)
    "fade_in": 0.4, "fade_out": 1.2, "loudnorm": true, "duck_with": null
  },
  "clips": [
    {
      "src": "assets/raw/clip01.mp4",
      "in": 12.3, "out": 14.1,        // source in/out (seconds)
      "grade": "cine_teal_orange",     // preset key OR inline "eq=..." filter
      "focus": { "x": 0.5, "y": 0.5 }, // crop focus (from ingest); framing:auto won't decapitate
      "motion": { "kind": "kenburns", "zoom": "in", "pan": "none", "amount": 0.12 },
      "speed": 1.0,                    // 0 = freeze-frame
      "transition": { "type": "dissolve", "dur": 0.5 },  // transition INTO next clip
      "correct": null, "caption": null, "overlay": null, "cutout": null, "sfx": []
    }
  ]
}
```

Everything above is really rendered (cutout/overlay/sfx/duck/correct/focus all
implemented). `python bin/render_edl.py work/edl.json --check` **strictly
validates** (unknown keys/presets, bad ranges → hard fail) and runs automatically
before every render. Render with the `render` skill → `--preview` then final.

---

## 5. Current project defaults (locked with the user)

- **Aspect / format:** 9:16 portrait — **1080×1920**, 30 fps.
- **Length:** short, **~30–60 s** (pick the strongest song section).
- **Vibe:** **cinematic / moody** — filmic teal-orange grade, elegant cuts,
  tasteful transitions, subtle grain + vignette. (The repo also supports the
  high-energy "Chipfat" mode — see EDITING_STYLE — but this project is cinematic.)
- **Cutouts:** **hero shots only** — a few select stills/shots, not every clip.

These live machine-readably in **[config/project.json](config/project.json)** —
that file wins if this list ever drifts.

---

## 6. Definition of done

A render is "done" when:
- [ ] Duration is within the target window and ends on a musical resolution
      (downbeat / phrase end), not mid-phrase.
- [ ] Every cut/transition midpoint sits on a beat (±1 frame) unless a
      deliberate float.
- [ ] Consistent grade across all shots (no clip looks like it wandered in from
      another video).
- [ ] Output is exactly 1080×1920, 30 fps, no black bars from bad scaling, audio
      loudness-normalized with clean fades.
- [ ] A preview was shown and signed off before the final render.
- [ ] Anything dropped/capped is reported to the user.

---

## 7. If you're lost after a compaction

1. Read this file (you're here).
2. `python bin/status.py` — prints exactly what exists and the next step.
3. Read `work/edl.json` if it exists — that's the current edit.
4. `Read work/thumbs/contact_sheet.jpg` to see the footage you're working with.
5. Check `out/` and `work/previews/` for the latest render.
6. Resume from the first incomplete pipeline stage in [§2](#2-the-pipeline-at-a-glance).

## 8. Tools & tests

Tools in `bin/`: `probe_media.py` (ingest+thumbnails+metrics), `detect_beats.py`,
`build_edl.py` (draft EDL — won't clobber an existing one without `--force`),
`match_exposure.py` (cohesion), `render_edl.py` (validate/preview/final, cached,
atomic), `cutout.py`, `status.py`.

**After changing any tool, run `python tests/run_tests.py`** — it generates
synthetic media and asserts the whole pipeline (probe, beats, strict validation,
render, frame-exact durations, caching, atomic output, raw-media guard). Keep it green.
