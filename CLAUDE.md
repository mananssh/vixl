# CLAUDE.md

**Read [AGENTS.md](AGENTS.md) first — it is the operating manual.** This file
only adds Claude Code–specific operational notes. Do not duplicate content;
AGENTS.md is the source of truth.

## Session bootstrap (do this at the start of every session / after a compaction)
1. Read `AGENTS.md`.
2. Run `python bin/status.py` (a SessionStart hook also prints this automatically).
3. Read `work/edl.json` if it exists — it *is* the current edit.

## Environment (Windows)
- **Python:** always call by full path —
  `C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe`.
  In PowerShell set `$PY = "C:\Users\manan\AppData\Local\Programs\Python\Python312\python.exe"` first.
- **CLI tools on PATH (new terminals):** `ffmpeg`, `ffprobe`, `yt-dlp`, `magick`, `sox`.
- **rembg model** is pre-cached at `C:\Users\manan\.u2net\u2net.onnx`.
- **Gotcha:** Python's own downloads (pooch/requests) sometimes hit a transient
  DNS failure for github.com even though PowerShell resolves fine. If a model/asset
  download fails inside Python, fetch it with PowerShell `Invoke-WebRequest` into
  the expected cache path instead.

## Working style in this repo
- **Prefer the skills** in `.claude/skills/` over ad-hoc commands. Each maps to a
  pipeline stage (see AGENTS.md §3).
- **The edit is the EDL.** Change `work/edl.json` and re-render; don't hand-roll
  irreproducible ffmpeg one-liners for the actual deliverable. One-off ffmpeg is
  fine for *probing/experiments*, not for the final edit.
- **Never touch `assets/raw/`** (source media). Derivatives → `work/`, deliverables → `out/`.
- **Preview → sign-off → final.** Full renders are slow; don't skip the preview.
- **Long renders:** run in the background and report when done rather than blocking.

## Permissions
`.claude/settings.json` pre-allows the media tools and project scripts so you
aren't prompted for every `ffmpeg`/`ffprobe`/`python bin/*` call. If you add a new
routine command, add it there (or use `/fewer-permission-prompts`).

## Don't
- Don't commit unless the user asks.
- Don't delete `assets/raw/`, `out/`, or the user's song under any circumstance.
- Don't invent skills/paths — if it's not in `.claude/skills/`, it doesn't exist yet;
  create it properly (folder + `SKILL.md` frontmatter) rather than faking it.
