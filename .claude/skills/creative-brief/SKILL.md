---
name: creative-brief
description: Kick off a new video. INTERVIEW the user about the video before any editing — what it's about, what must be in it, the tone/energy, pacing, captions, title text, things to avoid, target length — and capture the answers in work/brief.json so every later stage (shot selection, grade, captions) is steered by intent, not guesswork. Use this FIRST, before ingest/beat-map/edit-plan, whenever starting a fresh edit.
---

# creative-brief

**Goal:** turn a vague "make me a video" into a concrete brief the rest of the
pipeline can execute against. This is the *intake interview*. Do it **first**, so
`edit-plan` isn't guessing at intent. The output is `work/brief.json`.

## Process
1. **Confirm the media is (or will be) in `assets/raw/`.** If it's already there,
   run `ingest-media` first so you can reference actual footage while asking.
2. **Interview the user.** Ask the questions below with the `AskUserQuestion` tool
   (batch related ones; offer sensible defaults from `config/project.json` so they
   can one-click). Keep it short — 4–8 questions, not an interrogation. Skip any a
   locked project default already answers unless the user wants to change it.
3. **Write `work/brief.json`** (schema below).
4. **Confirm back** a one-paragraph summary of what you understood, then proceed to
   `ingest-media` → `beat-map` → `edit-plan`.

## Questions to cover
- **About / subject** — what is this video of? What's the story or throughline?
- **Must-include** — specific shots/moments/people that HAVE to be in it.
- **Avoid** — anything to leave out (a person, a blurry clip, a moment).
- **Tone / vibe** — cinematic & moody? hype/high-energy (Chipfat/Sidemen)?
  nostalgic? clean & corporate? (Maps to grade + pacing + transition palette.)
- **Captions / text** — none, minimal titles, or bold pop-in captions? Any exact
  title text (e.g. an opener/closer line)?
- **Hero moment** — the single shot to build the climax around (for a cutout / the
  drop / the ending).
- **Length & song section** — target seconds and which part of the song to build on
  (drop/chorus vs. full).
- **Anything else** — pace ("fast cuts" vs "let shots breathe"), references, a
  specific ending.

## `work/brief.json` schema
```jsonc
{
  "title": "wc2022-final",           // used as meta.title / output filename
  "about": "The 2022 WC final, Argentina vs France, as a 45s hype recap",
  "tone": "cinematic_moody",         // free text or a grade key; steers look + pacing
  "energy": "high",                  // low | medium | high — cut pacing
  "must_include": ["Messi lifting the trophy", "Mbappe hat-trick"],
  "avoid": ["the blurry crowd pan", "any France celebration as the ending"],
  "captions": "minimal",             // none | minimal | bold
  "title_text": "THE FINAL",         // optional on-screen opener (null if none)
  "ending_text": "CAMPEONES DEL MUNDO",  // optional closer (null if none)
  "hero_moment": "Messi kisses the trophy",
  "target_seconds": 45,              // within config length window
  "song_section": "drop",            // drop | chorus | full | a section label
  "notes": "let the ending breathe; everything before the shootout is fast"
}
```
All fields optional except `title`. Anything omitted falls back to
`config/project.json`. This file is **advisory** — `edit-plan` reads it to make
choices; it doesn't override the locked format/aspect in `config/project.json`.

## How the brief flows downstream
- `build_edl.py` reads it for `title`, `target_seconds`, and `song_section`.
- **You** (during `edit-plan`) use `must_include` / `avoid` / `hero_moment` /
  `captions` to select and treat shots — read the contact sheet with the brief open.
- `describe_edl.py` surfaces the brief at the top of `work/treatment.md` so the
  user can check the edit against their own ask.

## Next
→ `ingest-media` (if not done) → `beat-map` → `edit-plan` → **review the treatment**
(`work/treatment.md`) → `render`.
