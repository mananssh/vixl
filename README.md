# 🎬 Auto-Editor — an agentic video-editing studio

Drop in a folder of raw photos/videos and a song. Get back a professional-grade,
beat-synced, colour-graded short-form video — cut the way a top human editor would
do it, but driven entirely by local CLI tools and an AI agent.

> **Cinematic by default, high-energy on demand.** Ships with a "cinematic/moody"
> look and also knows the fast, punchy, meme-driven *Chipfat/Sidemen* style.

## How it works

```
raw media + song ──► ingest ──► beat-map ──► edit-plan (EDL) ──► render ──► out/final.mp4
                                                  ▲
                        colour-grade · motion-fx · cutout · sfx/overlays · audio-post
```

Everything the agent needs to know lives on disk, so sessions stay cheap and
survive context resets:

- **[AGENTS.md](AGENTS.md)** — the operating manual (start here).
- **[CLAUDE.md](CLAUDE.md)** — Claude Code–specific notes.
- **[docs/PIPELINE.md](docs/PIPELINE.md)** — end-to-end technical walkthrough + env setup.
- **[docs/EDITING_STYLE.md](docs/EDITING_STYLE.md)** — the creative playbook (how a pro decides).
- **[docs/FFMPEG_COOKBOOK.md](docs/FFMPEG_COOKBOOK.md)** — copy-paste ffmpeg recipes.
- **[.claude/skills/](.claude/skills/)** — one skill per pipeline stage.

## Quick start

1. Put your media in `assets/raw/` and your song there too.
2. Let the agent run the pipeline (or drive it yourself):
   ```powershell
   $PY = "C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe"
   & $PY bin/probe_media.py            # → work/manifest.json
   & $PY bin/detect_beats.py assets/raw/song.mp3   # → work/beats.json
   # agent designs work/edl.json (see edit-plan skill)
   & $PY bin/render_edl.py work/edl.json --preview # → work/previews/
   & $PY bin/render_edl.py work/edl.json           # → out/final.mp4
   ```
3. Check status any time: `& $PY bin/status.py`.

## Layout

```
AGENTS.md CLAUDE.md README.md
.claude/
  settings.json      hooks + permissions
  skills/            one folder per pipeline stage (SKILL.md each)
  hooks/             session-status + raw-asset guard
bin/                 the tools: probe, beats, cutout, render, status
config/
  project.json       locked project settings (aspect/fps/length/vibe)
  presets/           grade + transition + motion presets (JSON)
  luts/              .cube colour LUTs
assets/
  raw/               ← YOUR source media + song (read-only, never touched)
  sfx/ overlays/ fonts/   effect assets
work/                intermediates (gitignored): manifest, beats, edl, clips, previews
out/                 final deliverables
docs/                pipeline + style + cookbook
```

## Requirements

ffmpeg/ffprobe, Python 3.12 + `librosa` + `rembg`+`onnxruntime`, ImageMagick, sox,
yt-dlp. All already installed on this machine — see [docs/PIPELINE.md](docs/PIPELINE.md).

## License

Copyright (c) 2026 Manan (mananssh). All Rights Reserved. This is proprietary,
source-available code — no license is granted to copy, modify, or redistribute
it. See [LICENSE](LICENSE) for the full notice.
