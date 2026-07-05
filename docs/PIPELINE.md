# PIPELINE.md — end-to-end technical walkthrough

This is the "how the machine works" doc. For *creative* decisions see
[EDITING_STYLE.md](EDITING_STYLE.md); for raw command recipes see
[FFMPEG_COOKBOOK.md](FFMPEG_COOKBOOK.md).

---

## Environment

| Thing | Value |
|---|---|
| Python | `C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe` (call by full path; refer to as `$PY`) |
| ffmpeg / ffprobe | on PATH (`C:\ffmpeg\bin\`) |
| yt-dlp, magick, sox | on PATH (winget installs; new terminals) |
| rembg model cache | `C:\Users\manan\.u2net\u2net.onnx` (pre-downloaded) |
| Python libs | `librosa`, `soundfile`, `rembg`, `onnxruntime`, `numpy`, `Pillow` |

**PowerShell preamble** used throughout:
```powershell
$PY = "C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe"
```

**Known gotcha:** Python's `requests`/`pooch` downloads occasionally fail DNS
(`getaddrinfo failed`) for github.com even though the network is fine. Workaround:
download with PowerShell `Invoke-WebRequest` into the expected cache path.

---

## Stage 1 — Ingest (`ingest-media` skill → `bin/probe_media.py`)

Probes `assets/raw/` **recursively** with ffprobe and writes `work/manifest.json`:
type, dimensions, duration, fps, rotation, orientation, codec, pix_fmt, **HDR
colour metadata**, has_audio. It also **extracts thumbnails + a labeled
`work/thumbs/contact_sheet.jpg`** (so the agent can see the footage), detects
**scene cuts** in videos, and computes **blur / exposure / suggested-focus
metrics** per asset. Skipped non-media files are logged.

```powershell
& $PY bin/probe_media.py                 # scans assets/raw
& $PY bin/probe_media.py --dir some/dir  # scan elsewhere
```

Why it matters: the edit-plan stage needs to know what raw material exists, its
orientation (for 9:16 framing decisions), and clip lengths (so it doesn't ask for
an out-point past the end of a file).

---

## Stage 2 — Beat map (`beat-map` skill → `bin/detect_beats.py`)

librosa analysis of the song → `work/beats.json`:
- `tempo` (BPM),
- `beats` — every beat time (seconds),
- `downbeats` — estimated bar starts (every 4th beat by default),
- `duration`, and
- `sections` — coarse energy segmentation (intro / build / drop / outro) so the
  edit can escalate cut speed with the music.

```powershell
& $PY bin/detect_beats.py assets/raw/song.mp3
& $PY bin/detect_beats.py assets/raw/song.mp3 --beats-per-bar 4 --start 40 --end 75
```

The EDL's cut points are chosen from this file. **Cuts snap to `beats`; big
transitions prefer `downbeats`.**

---

## Stage 3 — Edit plan (`edit-plan` skill → `work/edl.json`)

This is the agent's job (the "editor's brain"), informed by
[EDITING_STYLE.md](EDITING_STYLE.md). Inputs: `manifest.json` + `beats.json` +
`config/project.json`. Output: `work/edl.json` (schema in the edit-plan skill).

The plan decides: which shots, in what order, how long each is held (quantised to
beats), the grade, the per-clip motion, the transition into the next clip,
captions/overlays, and where hero cutouts go. `bin/build_edl.py` can scaffold a
first-draft EDL automatically that the agent then refines.

---

## Stage 4 — Per-clip treatment (referenced by the EDL, applied at render)

These aren't separate render passes you run by hand — they're **fields in the
EDL** that `render_edl.py` turns into ffmpeg filter chains:
- `grade` → a preset from `config/presets/grades.json` (see `color-grade` skill).
- `motion` → Ken Burns / zoom-punch / speed ramp (see `motion-fx` skill).
- `caption` / `overlay` → text + image comps (see `sfx-overlays` skill).
- `cutout` → a pre-rendered RGBA from `subject-cutout` (see that skill), composited over a background.

Cutouts *are* a separate pre-pass (they're slow): run `bin/cutout.py` to produce
`work/cutouts/*.png|.mov`, then reference the result in the EDL clip's `cutout` field.

---

## Stage 5 — Render (`render` skill → `bin/render_edl.py`)

Two-phase, robust approach (not one monster filtergraph):

1. **Normalize each clip** to a uniform intermediate: trim to in/out, apply
   speed, scale+crop/pad to the exact project resolution (9:16 with a blurred
   fill for off-aspect sources), apply grade + motion + caption/overlay, force
   constant fps and pixel format. → `work/clips/NNN.mp4`.
2. **Assemble**: chain the normalized clips with `xfade` video transitions and
   `acrossfade`/concat, overlay the song, apply audio fades + `loudnorm`.
   → preview (`work/previews/`) or final (`out/`).

```powershell
& $PY bin/render_edl.py work/edl.json --preview   # fast, low-res, for sign-off
& $PY bin/render_edl.py work/edl.json             # full quality → out/
```

Long finals: run in the background and report when done.

---

## Stage 6 — Audio post (`audio-post` skill)

Handled inside render for the common case (fades + loudnorm). For anything richer
— ducking a music bed under a voice-over, EQ, reverb tails on sfx, stem
sweetening — use `sox` / ffmpeg `sidechaincompress` as described in the
`audio-post` skill, producing a mixed track that the EDL references as `audio.src`.

---

## Stage 4b — Exposure match (`color-grade` skill → `bin/match_exposure.py`)

Optional but recommended cohesion step: reads ingest luma metrics and writes a
per-clip `correct` (brightness/gamma toward the median) into the EDL, applied
*before* the stylistic grade so shots match. `--dry-run` to preview.

## Performance & safety notes

- **Render caching:** normalized clips are content-hash cached in `work/clips/`.
  Editing one clip re-encodes only that clip. Delete `work/clips/*` to force a
  full re-render. Intermediates are near-lossless (CRF 12) so the final CRF-18
  encode isn't a second generation loss.
- **Atomic output:** finals/previews render to `*.tmp.mp4` then rename on success.
- **HDR:** `render_edl.py` detects PQ/HLG/bt2020 sources and tonemaps to bt709
  (needs an ffmpeg with zscale+tonemap — this machine's build has libzimg).
- **Two-pass loudnorm** on finals (measure → apply linear), output at 48 kHz.

## Tests

`python tests/run_tests.py` generates synthetic media and exercises the whole
pipeline (probe, beats, validation, render, caching, atomic output, guard) with
assertions — run it after changing any tool.

## Data contracts (so stages stay decoupled)

- `work/manifest.json` — list of `{path, type, w, h, dur, fps, rotation, orientation}`.
- `work/beats.json` — `{tempo, duration, beats[], downbeats[], sections[]}`.
- `work/edl.json` — the timeline (see edit-plan skill for full schema).

As long as each stage honours these contracts, any stage can be re-run
independently. That's what keeps sessions cheap and compaction-safe.
