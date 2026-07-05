#!/usr/bin/env python3
"""detect_beats.py - librosa beat/tempo/section analysis -> work/beats.json.

Usage:
    python bin/detect_beats.py assets/raw/song.mp3
    python bin/detect_beats.py song.mp3 --start 40 --end 75 --beats-per-bar 4

Part of the beat-map skill. See docs/PIPELINE.md.
"""
import argparse, json, os, sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    ap.add_argument("--out", default=os.path.join(ROOT, "work", "beats.json"))
    ap.add_argument("--start", type=float, default=None, help="analyze from this second")
    ap.add_argument("--end", type=float, default=None, help="analyze until this second")
    ap.add_argument("--beats-per-bar", type=int, default=4)
    args = ap.parse_args()

    song = args.song if os.path.isabs(args.song) else os.path.join(ROOT, args.song)
    if not os.path.isfile(song):
        print(f"[beats] file not found: {song}", file=sys.stderr)
        sys.exit(1)

    import numpy as np
    import librosa

    print(f"[beats] loading {os.path.basename(song)} ...")
    y, sr = librosa.load(song, sr=None, mono=True)
    full_dur = float(len(y) / sr)

    # optional windowing
    off = args.start or 0.0
    if args.start is not None or args.end is not None:
        s = int((args.start or 0.0) * sr)
        e = int((args.end or full_dur) * sr)
        y = y[s:e]

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, trim=False)
    tempo = float(np.atleast_1d(tempo)[0])
    beat_times = (librosa.frames_to_time(beat_frames, sr=sr) + off).tolist()
    beat_times = [round(t, 3) for t in beat_times]

    # downbeats: every Nth beat starting from the strongest early beat
    bpb = max(1, args.beats_per_bar)
    # choose phase = index of the max-onset-strength beat within the first bar
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    beat_strength = onset_env[np.clip(beat_frames, 0, len(onset_env) - 1)] if len(beat_frames) else np.array([])
    phase = int(np.argmax(beat_strength[:bpb])) if len(beat_strength) >= 1 else 0
    downbeats = [beat_times[i] for i in range(phase, len(beat_times), bpb)]

    # coarse energy sections via RMS thresholding over fixed windows
    sections = _sections(y, sr, off)

    duration = full_dur
    result = {
        "song": os.path.relpath(song, ROOT).replace("\\", "/"),
        "tempo": round(tempo, 2),
        "duration": round(duration, 3),
        "analyzed_window": [off, round(off + len(y) / sr, 3)],
        "beats_per_bar": bpb,
        "beats": beat_times,
        "downbeats": [round(t, 3) for t in downbeats],
        "sections": sections,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"[beats] tempo ~{result['tempo']} BPM | {len(beat_times)} beats | "
          f"{len(downbeats)} downbeats | {len(sections)} sections")
    hi = [s for s in sections if s["energy"] == "high"]
    if hi:
        best = max(hi, key=lambda s: s["end"] - s["start"])
        print(f"[beats] strongest high-energy section: {best['start']}s-{best['end']}s "
              f"({best['label']}) - good candidate for a short edit's audio.start")
    print(f"[beats] -> {os.path.relpath(args.out, ROOT)}")


def _sections(y, sr, off):
    import numpy as np
    import librosa
    hop = 512
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    if rms.size == 0:
        return []
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop) + off
    # normalize and bucket into ~2s windows
    win = max(1, int(2.0 * sr / hop))
    buckets = []
    for i in range(0, len(rms), win):
        seg = rms[i:i + win]
        if seg.size:
            buckets.append((round(float(times[i]), 2),
                            round(float(times[min(i + win, len(times) - 1)]), 2),
                            float(np.mean(seg))))
    if not buckets:
        return []
    energies = np.array([b[2] for b in buckets])
    lo, hi = np.percentile(energies, 33), np.percentile(energies, 66)

    def lvl(e):
        return "low" if e < lo else ("high" if e > hi else "mid")

    # merge consecutive same-level buckets
    sections = []
    cs, ce, cl = buckets[0][0], buckets[0][1], lvl(buckets[0][2])
    for s, e, en in buckets[1:]:
        l = lvl(en)
        if l == cl:
            ce = e
        else:
            sections.append({"start": cs, "end": ce, "energy": cl})
            cs, ce, cl = s, e, l
    sections.append({"start": cs, "end": ce, "energy": cl})

    # heuristic labels
    for idx, sec in enumerate(sections):
        if idx == 0 and sec["energy"] != "high":
            sec["label"] = "intro"
        elif idx == len(sections) - 1 and sec["energy"] != "high":
            sec["label"] = "outro"
        elif sec["energy"] == "high":
            sec["label"] = "drop"
        elif sec["energy"] == "mid":
            sec["label"] = "build"
        else:
            sec["label"] = "breakdown"
    return sections


if __name__ == "__main__":
    main()
