# EDITING_STYLE.md — the editor's playbook

This is how a **professional editor decides** — the taste, not the toolage. When
the `edit-plan` skill builds an EDL, it reasons from this document. Read it before
sequencing any edit. Two modes are covered:

- **Cinematic / moody** (this project's default) — Kolder/Teo-style travel-film craft.
- **High-energy comedy** (*Chipfat*-for-*Sidemen* style) — fast, punchy, meme-driven.

Most of the *principles* (cut on beats, motivate every transition, grade for
cohesion) apply to both; the *dials* differ.

---

## 1. First principles (both modes)

1. **The song is the edit.** Structure the video to the music, not the other way
   round. Map the song's sections first (intro → build → drop → breakdown → outro),
   then assign footage energy to match. Cut speed should *rise and fall with the
   music*, never stay flat.
2. **Cut on the beat, land impact on the downbeat.** Small cuts fall on beats;
   the biggest moments (the best shot, the hardest transition, a title) land on a
   **downbeat** or the drop. A cut that's 2 frames off the beat *feels* wrong even
   to people who can't say why.
3. **Every transition must be motivated.** Don't sprinkle transitions. A whip-pan
   needs motion to hide in; a zoom transition needs a push-in that continues; a
   dissolve says "time passed / same mood." An unmotivated star-wipe screams amateur.
4. **Motion in, motion out.** A static shot next to a static shot is dead air.
   Give almost every shot *some* movement (real camera motion, a speed ramp, or a
   Ken Burns push) and try to **match motion direction across a cut** (subject
   exits left → next shot enters from the right, or continues the push).
5. **Grade for cohesion first, style second.** The #1 tell of amateur editing is
   shots that don't match. Balance exposure/white-balance across clips *before*
   applying a stylistic look, so the whole piece feels shot on one camera, one day.
6. **Hold your best shot.** Resist cutting your strongest frame too fast. Let the
   hero shot breathe over a musical swell, then cut hard on the drop.
7. **Start strong, end clean.** Open on a hook within the first ~1.5s. End on a
   resolved musical phrase with a clean out (fade or a held final frame), never
   mid-phrase.

---

## 2. Rhythm & pacing (how long to hold a shot)

Quantise every shot length to beats. At a given BPM, one beat = `60/BPM` seconds.

| Song energy | Typical shot length | Feel |
|---|---|---|
| Intro / ambient | 2–4 beats (or a long held hero shot) | Establish, breathe |
| Build | 2 beats, tightening to 1 | Momentum |
| Drop / chorus | 1 beat, or ½-beat bursts | Relentless, exciting |
| Breakdown | 2–4 beats | Release the tension |
| Outro | lengthening back out | Resolution |

**Rules of thumb**
- Never hold a *non-hero* shot longer than the energy warrants — boredom is death.
- On the drop, a burst of ½-beat cuts (4–8 in a row) is a classic energy spike;
  use the best, most different-looking frames so it reads as deliberate, not a glitch.
- Vary shot length even within a section — perfectly even cutting feels robotic.
  Think in phrases (e.g. 3 short + 1 long), not metronomic sameness.
- **Don't cut on every single beat for the whole video** — that's exhausting.
  Cut on beats, but *choose* which beats.

---

## 3. Shot selection & ordering

- **Cull ruthlessly.** Better to use 15 great seconds than 60 mediocre ones.
- **Sequence for contrast:** alternate wide↔close, static↔moving, light↔dark,
  so consecutive shots don't blur together. Two similar shots back-to-back look
  like a mistake.
- **Group by location/subject** into mini-phrases, then transition between groups
  on downbeats.
- **Save a "money shot"** for the drop and another for the ending.
- **Establish → detail → payoff:** wide to set the scene, closer for texture,
  then the hero moment. This micro-arc reads as intentional storytelling.
- **Continuity of energy over continuity of time** — for a montage, emotional/energy
  flow beats chronological order.

---

## 4. Cinematic / moody mode (this project's default)

**Grade:** `cine_teal_orange` — lift shadows toward teal, push skin/highlights
toward warm orange, gentle S-curve for filmic contrast, slightly desaturated
except skin, soft vignette (~0.25), fine grain (~0.06), optional halation/bloom
on highlights. Keep it *subtle* — a good grade is felt, not seen.

**Cuts & transitions:**
- Primarily **hard cuts on the beat** + occasional **slow cross-dissolves**
  (0.4–0.8s) between locations/moods.
- **Zoom / whip transitions** sparingly, always motivated by an existing push or
  pan, timed so the midpoint hits the beat.
- **Luma / gradient wipes** for elegant scene changes.
- **Match cuts** (shape/motion/colour continuity across a cut) whenever the
  footage allows — the most impressive "how did they do that" moment.
- **Speed ramps** into transitions: ramp up to the cut, cut on the beat, ease out.

**Motion:** slow Ken Burns pushes (5–12% over the shot), gentle drifts. Avoid
frantic movement. Stills get a slow push/parallax so they don't feel dead.

**Extras:** subtle light leaks between scenes; 2.39 letterbox is optional (off by
default in 9:16 since it eats vertical space); film grain + very light gate-weave
for texture.

**Cutouts (hero only):** pop the subject off the background on 1–3 signature
shots — e.g. freeze on the hero, cut them out, push in on the cutout over a
blurred/darkened version of the same frame, add a soft rim glow. Used once or
twice it's stunning; on every shot it's tacky.

---

## 5. High-energy comedy mode (Chipfat / Sidemen) — on demand

Not this project's default, but fully supported. The vocabulary that defines the style:

- **Zoom punch-in on the punchline:** hard, sudden scale-up (110–140%) exactly on
  the funny word/beat, hold ~½s, cut. Often stacked with a **camera shake** and a
  **sfx hit** (vine boom / bass drop).
- **Sound effects as punctuation:** boing, airhorn, record-scratch, vine-boom,
  "bruh", quack, cash-register, sad-violin. Each emphasis gesture pairs with an
  sfx (see `sfx-overlays` skill + `assets/sfx/`). *The sfx sells the joke.*
- **Reaction / meme overlays:** cut-out reaction images, arrows, circles, "😐"
  emojis, freeze-frame + zoom + red-circle highlight on the thing being mocked.
- **Bold captions:** thick sans (Impact/Montserrat-Black), white fill + heavy
  black outline, pop-in with a tiny overshoot/shake, timed to the word. Great for
  emphasis and for the deaf-scroll audience.
- **Speed for comedy:** speed-up mundane bits (with rising pitch), slam to slow-mo
  on the reaction. Freeze-frames on reactions.
- **RGB split / chromatic aberration + zoom blur** on the biggest hits.
- **Fast whip-pan and zoom transitions** between bits.
- **Rapid-fire cutting** during a rant, each cut on the beat or on speech stress.

Restraint still matters: even Chipfat lands the joke *then* the sfx; effects serve
the comedy, they aren't the comedy. Don't stack five effects on a line that isn't
funny.

---

## 6. Colour cohesion checklist

Before styling, normalize across all clips:
1. **Exposure** — match mid-tone brightness so no clip is visibly darker/brighter.
2. **White balance** — neutralize colour casts so whites match shot-to-shot.
3. **Contrast/saturation** baseline — a common starting point.
4. *Then* apply the stylistic grade/LUT uniformly.
5. Spot-check skin tones — they must stay natural/consistent; the eye forgives a
   lot but never bad skin.

---

## 7. Audio craft

- **Beat-match is king** — see §1–2.
- **Fade in/out** the music (no hard starts/stops). Short fade-in (~0.4s), longer
  tail (~1–1.5s).
- **Loudness-normalize** to ~-14 LUFS (social) so it isn't quiet or clipped.
- **Duck** the music under any voice-over/dialogue (sidechain compression).
- **SFX** sit slightly above the music in the moment, then get out of the way.
- **Silence is a tool** — a beat of near-silence before the drop makes the drop hit harder.

---

## 8. Common amateur tells to avoid (a checklist)

- ❌ Cuts slightly off the beat.
- ❌ Shots that don't colour-match.
- ❌ Every shot the same length (metronomic) or every shot too long (boring).
- ❌ Unmotivated / overused transitions (default cross-dissolve on everything, star-wipes).
- ❌ Black bars / squished footage from lazy aspect handling.
- ❌ Music that starts/stops abruptly or is too quiet/too loud.
- ❌ Effects with no purpose (zoom/shake/RGB-split on a non-moment).
- ❌ Ending mid-phrase or on an ugly frame.
- ❌ Two visually similar shots back to back.

If the edit avoids all of these and nails §1, it will already read as professional.
