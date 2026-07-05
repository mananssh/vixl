#!/usr/bin/env python3
"""cutout.py - subject background removal via rembg.

Usage:
    python bin/cutout.py in.jpg -o work/cutouts/hero.png
    python bin/cutout.py in.mp4 --frame 3.2 -o work/cutouts/hero.png   # cut one grabbed frame
    python bin/cutout.py in.mp4 -o work/cutouts/hero.mov               # whole video (slow)
    python bin/cutout.py in.mp4 --start 3.0 --end 6.0 -o work/cutouts/hero.mov
    python bin/cutout.py in.jpg -o out.png --model u2net_human_seg

Part of the subject-cutout skill. Hero shots only (config.cutouts). Prefer stills
or --frame over whole-video matting (cleaner edges, far faster). See docs/PIPELINE.md
for the DNS gotcha if a model download fails.
"""
import argparse, os, shutil, subprocess, sys, tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".avif"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def cut_image(inp, outp, session):
    from rembg import remove
    from PIL import Image
    img = Image.open(inp).convert("RGB")
    out = remove(img, session=session)
    os.makedirs(os.path.dirname(outp) or ".", exist_ok=True)
    out.save(outp)
    print(f"[cutout] {os.path.basename(inp)} -> {os.path.relpath(outp, ROOT)}  "
          f"({out.size[0]}x{out.size[1]} RGBA)")


def grab_frame(video, t, dest):
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", video,
                        "-frames:v", "1", dest], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(dest):
        print(f"[cutout] failed to grab frame at {t}s\n{r.stderr[-400:]}", file=sys.stderr)
        sys.exit(1)


def cut_video(inp, outp, session, start=None, end=None, codec="qtrle"):
    """Per-frame matte -> RGBA video. Slow; hero use only. Temp dir auto-cleaned."""
    from rembg import remove
    from PIL import Image

    fps = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", inp],
        capture_output=True, text=True).stdout.strip() or "30"

    tmp = tempfile.mkdtemp(prefix="cutout_")
    try:
        frames_dir = os.path.join(tmp, "f"); os.makedirs(frames_dir)
        extract = ["ffmpeg", "-y", "-v", "error"]
        if start is not None:
            extract += ["-ss", str(start)]
        if end is not None:
            extract += ["-to", str(end)] if start is None else ["-t", str(end - start)]
        extract += ["-i", inp, os.path.join(frames_dir, "%05d.png")]
        print("[cutout] extracting frames" + (f" ({start}-{end}s)" if start is not None else "") + " ...")
        subprocess.run(extract, capture_output=True, text=True)
        frames = sorted(os.listdir(frames_dir))
        if not frames:
            print("[cutout] no frames extracted", file=sys.stderr); sys.exit(1)

        out_dir = os.path.join(tmp, "o"); os.makedirs(out_dir)
        print(f"[cutout] matting {len(frames)} frames (slow) ...")
        for i, fn in enumerate(frames):
            img = Image.open(os.path.join(frames_dir, fn)).convert("RGB")
            remove(img, session=session).save(os.path.join(out_dir, fn))
            if (i + 1) % 20 == 0:
                print(f"  {i+1}/{len(frames)}")

        os.makedirs(os.path.dirname(outp) or ".", exist_ok=True)
        # qtrle=widely compatible lossless alpha; prores4444 also supported
        vcodec = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"] \
            if codec == "prores" else ["-c:v", "qtrle", "-pix_fmt", "argb"]
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", fps,
                        "-i", os.path.join(out_dir, "%05d.png"), *vcodec, outp],
                       capture_output=True, text=True)
        print(f"[cutout] -> {os.path.relpath(outp, ROOT)} (RGBA video, {len(frames)} frames)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--frame", type=float, default=None,
                    help="video: grab this timestamp (s) and cut a single still")
    ap.add_argument("--start", type=float, default=None, help="video: matte from this second")
    ap.add_argument("--end", type=float, default=None, help="video: matte until this second")
    ap.add_argument("--codec", choices=["qtrle", "prores"], default="qtrle")
    ap.add_argument("--model", default="u2net",
                    help="rembg model: u2net | u2net_human_seg | isnet-general-use")
    args = ap.parse_args()

    inp = args.input if os.path.isabs(args.input) else os.path.join(ROOT, args.input)
    outp = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    if not os.path.isfile(inp):
        print(f"[cutout] not found: {inp}", file=sys.stderr); sys.exit(1)

    from rembg import new_session
    session = new_session(args.model)

    ext = os.path.splitext(inp)[1].lower()
    if ext in IMAGE_EXT:
        cut_image(inp, outp, session)
    elif ext in VIDEO_EXT:
        if args.frame is not None:
            with tempfile.TemporaryDirectory() as td:
                still = os.path.join(td, "frame.png")
                grab_frame(inp, args.frame, still)
                cut_image(still, outp, session)
        else:
            cut_video(inp, outp, session, start=args.start, end=args.end, codec=args.codec)
    else:
        print(f"[cutout] unsupported input type: {ext}", file=sys.stderr); sys.exit(1)


if __name__ == "__main__":
    main()
