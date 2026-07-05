---
name: color-grade
description: Choose and apply a consistent colour look across all clips — exposure/white-balance matching first, then a stylistic grade (cinematic teal-orange, warm, punchy, B&W) via ffmpeg eq/curves/colorbalance or a .cube LUT. Use when deciding the look or when clips don't match each other.
---

# color-grade

**Goal:** every shot looks like it came from one camera on one day, then wears a
deliberate look. Cohesion first, style second (EDITING_STYLE §6).

## Presets — `config/presets/grades.json`
Grades are named presets referenced by the EDL's `grade` field. Built-in keys:
- `cine_teal_orange` — project default: filmic contrast, teal shadows, warm skin,
  slight desaturation, vignette.
- `warm_film` — nostalgic warm pastel, soft contrast, light grain.
- `punchy` — high saturation/contrast for energetic edits.
- `bw_contrast` — cinematic black & white.
- `neutral` — exposure/WB match only, no style (use as a base or for problem clips).

Each preset is an ffmpeg filter string. To tweak the look globally, edit the
preset once — every clip using it updates.

## Apply (normally via the EDL)
Set `"grade": "cine_teal_orange"` on clips; `render_edl.py` injects the preset's
filter chain. To preview a look on one clip manually:
```powershell
ffmpeg -i assets/raw/clip01.mp4 -vf "curves=preset=medium_contrast,eq=contrast=1.06:saturation=1.05,colorbalance=rs=-0.06:bs=0.06:rh=0.06:bh=-0.06,vignette=PI/5" -t 4 work/cache/grade_test.mp4
```

## LUTs
Drop `.cube` files in `config/luts/` and reference via a preset that uses
`lut3d=config/luts/<name>.cube`. LUTs give a filmic look in one step; still do
exposure/WB matching *before* the LUT.

## Matching workflow (when clips don't match) — cohesion step zero
1. **Automatic:** run `python bin/match_exposure.py` — it reads ingest luma
   metrics and writes a per-clip `correct` (brightness/gamma nudge toward the
   median) into the EDL. `correct` is applied BEFORE the grade, so the shared
   preset then lands consistently across shots. Use `--dry-run` to preview.
2. **Manual tweak:** set a clip's `correct` (e.g. `{"brightness":0.04,"gamma":0.98}`)
   or use an **inline grade string** (any value containing `=`, e.g.
   `"grade": "eq=brightness=0.03:gamma_b=1.03"`) — both are really applied.
3. Look at `work/thumbs/contact_sheet.jpg` and re-check skin tones across shots.

## Tips
- Keep it subtle — a good grade is felt, not seen.
- Grade the *normalized* clip (after scale/crop) so vignette/edges align to 9:16.
- See FFMPEG_COOKBOOK §4 for the exact filter recipes.
