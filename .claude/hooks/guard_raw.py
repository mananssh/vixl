#!/usr/bin/env python3
"""guard_raw.py - PreToolUse hook: protect irreplaceable source media.

Blocks operations that could delete or overwrite anything under assets/raw/:
  - Write/Edit/NotebookEdit into assets/raw/
  - shell deletes/moves targeting assets/raw/ (rm, del, move, Remove-Item, ...)
  - ffmpeg/tool OUTPUT written into assets/raw/ (overwrite via -y etc.)
  - shell redirects / Set-Content / Out-File / tee into assets/raw/
  - `git clean -x/-X/-fdx` (would delete gitignored raw media)
  - recursive deletes of the out/ deliverables tree

Reads the hook JSON on stdin (bytes -> utf-8-sig, so a BOM is fine); exit code 2
blocks the call and shows the stderr message to the agent. Fail-open on any
internal error so it can never wedge a session. See AGENTS.md golden rule #1.
"""
import json, re, sys

PROTECT = ("assets/raw", "assets\\raw")
DELETE_VERBS = re.compile(
    r"\b(rm|rmdir|rd|del|erase|remove-item|ri|move|mv|move-item|mi)\b", re.IGNORECASE)
WRITE_CMDLETS = re.compile(
    r"\b(set-content|add-content|out-file|tee-object|tee|clear-content)\b", re.IGNORECASE)


def blocked(reason):
    print(reason, file=sys.stderr)
    sys.exit(2)


def touches_raw(text):
    low = text.replace("\\", "/").lower()
    return any(p.replace("\\", "/") in low for p in PROTECT)


def main():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8-sig", errors="replace").strip()
    except Exception:
        raw = sys.stdin.read().strip()
    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        sys.exit(0)

    tool = data.get("tool_name") or data.get("toolName") or ""
    ti = data.get("tool_input") or data.get("toolInput") or {}

    # File-writing tools -> block writes into assets/raw
    if tool in ("Write", "Edit", "NotebookEdit", "MultiEdit"):
        path = (ti.get("file_path") or ti.get("path") or "").replace("\\", "/")
        if "assets/raw/" in path.lower():
            blocked("BLOCKED by guard_raw: assets/raw/ is read-only source media. "
                    "Write derivatives to work/ or out/ instead. (AGENTS.md rule #1)")
        sys.exit(0)

    # Shell tools
    if tool in ("Bash", "PowerShell"):
        cmd = ti.get("command", "")
        low = cmd.replace("\\", "/").lower()

        # git clean that removes ignored/untracked files would nuke raw/
        if re.search(r"\bgit\s+clean\b", low) and re.search(r"-[a-z]*x", low):
            blocked("BLOCKED by guard_raw: `git clean -x/-X` would delete gitignored "
                    "source media in assets/raw/. Clean specific paths manually if needed.")

        # deletes / moves that mention a protected path
        if DELETE_VERBS.search(cmd) and touches_raw(cmd):
            blocked("BLOCKED by guard_raw: refusing to delete/move anything under "
                    "assets/raw/ (irreplaceable source media). Operate on work/ or out/. "
                    "(AGENTS.md rule #1)")

        # redirects / write-cmdlets / tee into assets/raw
        if touches_raw(cmd):
            # any '>' redirect whose target region mentions raw
            if re.search(r">>?\s*[^|]*assets/raw", low):
                blocked("BLOCKED by guard_raw: redirecting output into assets/raw/. "
                        "Write to work/ or out/ instead.")
            if WRITE_CMDLETS.search(cmd) and "assets/raw" in low:
                blocked("BLOCKED by guard_raw: writing into assets/raw/ via a cmdlet. "
                        "Write to work/ or out/ instead.")
            # ffmpeg (or any tool) OUTPUT into raw: last non-flag token is the output
            if re.search(r"\bffmpeg\b", low):
                toks = cmd.split()
                # find output tokens = tokens that look like paths under raw and are
                # NOT the argument to -i (inputs are allowed to read from raw)
                for j, tk in enumerate(toks):
                    tnorm = tk.replace("\\", "/").lower().strip('"\'')
                    if "assets/raw" in tnorm:
                        prev = toks[j - 1].lower() if j > 0 else ""
                        if prev != "-i":
                            blocked("BLOCKED by guard_raw: ffmpeg output path is under "
                                    "assets/raw/ (would overwrite source). Send output to "
                                    "work/ or out/. Reading from raw with -i is fine.")

        # recursive delete of the deliverables tree (match recursion FLAGS only,
        # not a literal "/s" inside a path like out/scene.mp4)
        recursive = re.search(r"\b(rm|remove-item|rd|rmdir)\b", low) and (
            re.search(r"\s-\w*r\w*\b", low) or re.search(r"\s/s\b", low)
            or "-recurse" in low)
        if recursive and "out/" in low:
            blocked("BLOCKED by guard_raw: recursive delete of out/. Delete specific files.")

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)  # never break a session on a guard error
