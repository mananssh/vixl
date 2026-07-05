#!/usr/bin/env python3
"""describe_edl.py - render work/edl.json as a human-readable treatment/screenplay.

The EDL is machine-precise but hard to picture. This turns it into prose the user
can read like a shot list / screenplay BEFORE any clips are processed, so they can
approve or hand back suggestions cheaply. Think "Claude plan mode" for the edit.

Writes work/treatment.md and prints it. Regenerate any time the EDL changes.

Usage:
    python bin/describe_edl.py [work/edl.json] [--out work/treatment.md]
"""
import argparse, json, os, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def maybe(p):
    return load(p) if os.path.exists(p) else None


def tc(s):
    """seconds -> m:ss.t timecode"""
    s = max(0.0, float(s))
    m = int(s // 60)
    return f"{m}:{s - m * 60:04.1f}"


def basename(path):
    return os.path.basename(str(path or "")).strip()


def describe_motion(m):
    if not m:
        return "locked-off (no camera move)"
    kind = m.get("kind", "none")
    if kind in (None, "none"):
        return "locked-off (no camera move)"
    if kind == "kenburns":
        zoom = m.get("zoom", "in")
        pan = m.get("pan", "none")
        amt = m.get("amount", 0.1)
        move = "slow push-in" if zoom == "in" else "slow pull-back"
        if pan and pan != "none":
            move += f", drifting {pan}"
        strength = "gentle" if amt < 0.08 else ("strong" if amt > 0.14 else "measured")
        return f"Ken Burns {move} ({strength})"
    if kind == "zoompunch":
        return f"punch-in zoom snapping on the beat (+{m.get('amount', 0.1):.0%})"
    if kind == "speedramp":
        return "speed ramp"
    if kind == "shake":
        return "handheld camera shake"
    if kind == "rgbsplit":
        return "RGB split / chromatic aberration hit"
    return kind


def describe_transition(t):
    """transition INTO the next clip"""
    if not t:
        return "hard cut"
    typ = t.get("type", "cut")
    dur = t.get("dur")
    tail = f" ({dur:g}s)" if dur else ""
    return {
        "cut": "hard cut",
        "dissolve": f"crossfade{tail}",
        "fade": f"crossfade{tail}",
        "whip_left": f"whip-pan left{tail}",
        "whip_right": f"whip-pan right{tail}",
        "zoom": f"zoom transition{tail}",
        "luma_wipe": f"gradient/luma wipe{tail}",
        "dip_black": f"dip to black{tail}",
        "dip_white": f"dip to white{tail}",
    }.get(typ, f"{typ}{tail}")


def describe_speed(sp):
    if sp is None or abs(sp - 1.0) < 1e-3:
        return None
    if sp == 0:
        return "frozen (freeze-frame)"
    if sp < 1:
        return f"slow-mo ({sp:g}x)"
    return f"sped up ({sp:g}x)"


def clip_duration(c):
    if c.get("dur") is not None:
        return float(c["dur"])
    if c.get("in") is not None and c.get("out") is not None:
        sp = c.get("speed") or 1.0
        raw = float(c["out"]) - float(c["in"])
        return raw / sp if sp else raw
    return 0.0


def build(edl, brief):
    meta = edl.get("meta", {})
    audio = edl.get("audio", {})
    clips = edl.get("clips", [])

    # timeline positions accounting for transition overlaps
    starts, t = [], 0.0
    for c in clips:
        starts.append(t)
        d = clip_duration(c)
        td = (c.get("transition") or {}).get("dur", 0) or 0
        t += d - td
    total = t + ((clips[-1].get("transition") or {}).get("dur", 0) or 0) if clips else 0.0

    L = []
    title = meta.get("title", "untitled")
    L.append(f"# Treatment — {title}")
    L.append("")
    L.append("> Human-readable screenplay of the current edit "
             "(`work/edl.json`). **Read it, mark it up, tell me what to change** — "
             "editing here is free; re-rendering clips is not. When it reads right, "
             "I lock the EDL and render.")
    L.append("")

    if brief:
        theme = brief.get("theme") or brief.get("about")
        tone = brief.get("tone") or brief.get("vibe")
        if theme:
            L.append(f"**About:** {theme}  ")
        if tone:
            L.append(f"**Tone:** {tone}  ")
        must = brief.get("must_include") or []
        if must:
            L.append(f"**Must include:** {', '.join(must)}  ")
        avoid = brief.get("avoid") or []
        if avoid:
            L.append(f"**Avoid:** {', '.join(avoid)}  ")
        L.append("")

    L.append(f"- **Format:** {meta.get('width')}x{meta.get('height')} @ "
             f"{meta.get('fps')}fps (9:16 vertical)")
    L.append(f"- **Runtime:** ~{total:.1f}s across {len(clips)} shots")
    L.append(f"- **Song:** `{basename(audio.get('src'))}` from {tc(audio.get('start', 0))} "
             f"(fade in {audio.get('fade_in', 0):g}s / out {audio.get('fade_out', 0):g}s"
             f"{', loudness-normalized' if audio.get('loudnorm') else ''})")
    if audio.get("duck_with"):
        L.append(f"- **Voice-over:** `{basename(audio['duck_with'])}` (music ducks under it)")
    grades = {c.get("grade") for c in clips if c.get("grade")}
    if len(grades) == 1:
        L.append(f"- **Look:** {grades.pop()} across every shot")
    elif grades:
        L.append(f"- **Look:** mixed — {', '.join(sorted(str(g) for g in grades))}")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Shot-by-shot")
    L.append("")

    for i, c in enumerate(clips):
        s = starts[i]
        d = clip_duration(c)
        head = f"**{i + 1}. [{tc(s)}–{tc(s + d)}]** ({d:.1f}s) — `{basename(c.get('src'))}`"
        tags = []
        if c.get("cutout"):
            tags.append("HERO CUTOUT")
        if c.get("caption"):
            tags.append("caption")
        if c.get("overlay"):
            tags.append("overlay")
        if c.get("sfx"):
            tags.append(f"{len(c['sfx'])} sfx")
        if tags:
            head += "  _(" + ", ".join(tags) + ")_"
        L.append(head)

        note = (c.get("notes") or "").strip()
        if note:
            L.append(f"    {note}")

        # the craft line
        bits = [describe_motion(c.get("motion"))]
        sp = describe_speed(c.get("speed"))
        if sp:
            bits.append(sp)
        fr = c.get("framing")
        if fr == "blurpad":
            bits.append("blurred-fill background")
        if c.get("cutout"):
            bits.append(f"subject cut out and composited (`{basename(c['cutout'])}`)")
        if c.get("caption"):
            cap = c["caption"]
            bits.append(f'caption "{cap.get("text", "")}" ({cap.get("style", "default")}'
                        f'{", pop-in" if cap.get("pop") else ""})')
        if c.get("overlay"):
            ov = c["overlay"]
            bits.append(f"{ov.get('mode', 'overlay')} overlay `{basename(ov.get('src'))}`")
        bits.append(f"→ {describe_transition(c.get('transition'))} into next")
        L.append(f"    *{'; '.join(bits)}.*")
        L.append("")

    L.append("---")
    L.append("")
    L.append("## How to change it")
    L.append("- Tell me in plain words (\"drop shot 4\", \"hold the trophy longer\", "
             "\"warmer\", \"no captions\", \"whip-pan into the goal\") — I edit `work/edl.json`.")
    L.append("- Or edit `work/edl.json` yourself and re-run "
             "`python bin/describe_edl.py` to refresh this file.")
    L.append("- When it reads right: `python bin/render_edl.py work/edl.json --preview` "
             "for sign-off, then the final.")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edl", nargs="?", default=os.path.join(ROOT, "work", "edl.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "work", "treatment.md"))
    ap.add_argument("--brief", default=os.path.join(ROOT, "work", "brief.json"))
    ap.add_argument("--quiet", action="store_true", help="write the file but don't print it")
    args = ap.parse_args()

    if not os.path.exists(args.edl):
        print(f"[describe_edl] no EDL at {args.edl} - build one first "
              f"(build_edl.py / edit-plan).", file=sys.stderr)
        sys.exit(1)

    edl = load(args.edl)
    brief = maybe(args.brief)
    text = build(edl, brief)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)

    if not args.quiet:
        print(text)
    print(f"[describe_edl] -> {os.path.relpath(args.out, ROOT)}", file=sys.stderr)


if __name__ == "__main__":
    main()
