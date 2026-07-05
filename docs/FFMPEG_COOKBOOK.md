# FFMPEG_COOKBOOK.md — recipes

Battle-tested ffmpeg/sox snippets the skills and `render_edl.py` are built on.
Project target: **1080×1920, 30fps, yuv420p**. Windows shell examples use
`^`-free single lines; wrap as needed. `$PY` = the full python path.

> These are the *primitives*. For the actual deliverable, drive them through the
> EDL + `render_edl.py` so the edit is reproducible.

---

## 1. Probe

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,duration:stream_tags=rotate -show_entries format=duration -of json input.mp4
```

---

## 2. Frame a source into 9:16 (1080×1920)

**Portrait source — scale to fill, crop overflow (no bars):**
```bash
ffmpeg -i in.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" -r 30 out.mp4
```

**Landscape source — blurred-fill background (keeps whole frame, fills the sides):**
```bash
ffmpeg -i in.mp4 -filter_complex \
"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:20,eq=brightness=-0.15[bg]; \
 [0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg]; \
 [bg][fg]overlay=(W-w)/2:(H-h)/2" -r 30 out.mp4
```

**Still image → 5s clip, correct aspect:**
```bash
ffmpeg -loop 1 -t 5 -i img.jpg -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p" -r 30 out.mp4
```

---

## 3. Trim (frame-accurate)

```bash
# re-encode (accurate): put -ss/-to AFTER -i
ffmpeg -i in.mp4 -ss 12.30 -to 14.10 -c:v libx264 -crf 18 -an seg.mp4
```

---

## 4. Colour grade

**Quick cinematic teal-orange (eq + curves + colorbalance):**
```bash
ffmpeg -i in.mp4 -vf \
"curves=preset=medium_contrast, \
 eq=contrast=1.06:saturation=1.05:gamma=0.98, \
 colorbalance=rs=-0.06:gs=-0.02:bs=0.06:rh=0.06:gh=0.02:bh=-0.06, \
 vignette=PI/5" out.mp4
```

**Apply a .cube LUT:**
```bash
ffmpeg -i in.mp4 -vf "lut3d=config/luts/teal_orange.cube" out.mp4
```

**Film grain + subtle bloom + vignette (cinematic finish):**
```bash
ffmpeg -i in.mp4 -vf \
"split[a][b];[b]gblur=sigma=8,curves=all='0/0 0.5/0.4 1/1'[bl];[a][bl]blend=all_mode=screen:all_opacity=0.15, \
 noise=alls=6:allf=t, vignette=PI/5" out.mp4
```

**Neutralize before styling (exposure/WB match):**
```bash
# nudge exposure and white balance
ffmpeg -i in.mp4 -vf "eq=brightness=0.03:gamma_r=0.98:gamma_b=1.03" out.mp4
```

---

## 5. Motion

**Ken Burns slow push on a still (zoompan), 5s @30fps:**
```bash
ffmpeg -loop 1 -t 5 -i img.jpg -vf \
"scale=2160:3840,zoompan=z='min(zoom+0.0009,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1080x1920:fps=30,format=yuv420p" out.mp4
```
*Tip: scale up first so the zoom doesn't soften. Vary x/y expressions to pan.*

**Zoom punch-in on video (hard 120% hit for N frames):**
```bash
ffmpeg -i in.mp4 -vf "scale=1080:1920,zoompan=z='if(lt(on,3),1.2,1)':d=1:s=1080x1920:fps=30" out.mp4
```

**Speed change (2× faster / 0.5× slow-mo):**
```bash
ffmpeg -i in.mp4 -vf "setpts=0.5*PTS" -af "atempo=2.0" fast.mp4
ffmpeg -i in.mp4 -vf "setpts=2.0*PTS" slow.mp4          # visual only
```

**Smooth slow-mo (frame interpolation — slow to render):**
```bash
ffmpeg -i in.mp4 -vf "minterpolate=fps=60,setpts=2.0*PTS" -r 30 slowmo.mp4
```

**Camera shake (on impact):**
```bash
ffmpeg -i in.mp4 -vf "crop=in_w-20:in_h-20:'10*sin(n/2)':'10*cos(n/3)'" out.mp4
```

**RGB split / chromatic aberration (emphasis hit):**
```bash
ffmpeg -i in.mp4 -vf "rgbashift=rh=6:bh=-6" out.mp4
```

---

## 6. Transitions (xfade)

**Two clips, 0.5s dissolve. Offset = (durationA - transition):**
```bash
ffmpeg -i a.mp4 -i b.mp4 -filter_complex \
"[0][1]xfade=transition=fade:duration=0.5:offset=2.5" -c:v libx264 -crf 18 out.mp4
```

Useful `transition=` values:
`fade, dissolve, wipeleft, wiperight, wipeup, wipedown, slideleft, slideright,
smoothleft, smoothright, circleopen, circleclose, radial, zoomin, pixelize,
hlslice, hrslice, diagtl, diagbr, fadeblack, fadewhite, distance, wipetl, squeezeh`.

**Whip-pan feel:** `transition=smoothleft` (or slideleft) with a short 0.2–0.3s
duration on shots that already contain a pan.
**Zoom transition:** `transition=zoomin`, midpoint on the beat.

**Chaining N clips** requires cumulative offsets (each xfade overlaps the previous
result). `render_edl.py` computes these automatically — see that script rather than
hand-chaining more than ~3 clips.

**Audio crossfade to match:**
```bash
ffmpeg -i a.mp4 -i b.mp4 -filter_complex "[0:a][1:a]acrossfade=d=0.5" out.mp4
```

---

## 7. Compositing (cutouts, overlays, captions)

**Composite an RGBA cutout over a background clip, with a push-in:**
```bash
ffmpeg -i bg.mp4 -i cutout.png -filter_complex \
"[1]scale=iw*1.0:-1[c];[0][c]overlay=(W-w)/2:(H-h)/2:format=auto" out.mp4
```

**Overlay a screen-blended light leak / grain video:**
```bash
ffmpeg -i base.mp4 -i assets/overlays/lightleak.mp4 -filter_complex \
"[1]scale=1080:1920,format=yuv420p[o];[0][o]blend=all_mode=screen:all_opacity=0.4" out.mp4
```

**Burn-in caption (drawtext), pop-in near a beat:**
```bash
ffmpeg -i in.mp4 -vf \
"drawtext=fontfile='assets/fonts/Montserrat-Black.ttf':text='LET IT GO':fontcolor=white:fontsize=90:borderw=6:bordercolor=black:x=(w-text_w)/2:y=h*0.72:enable='between(t,1.0,2.2)'" out.mp4
```

---

## 8. Cutouts via rembg (Python, not ffmpeg)

Still image:
```powershell
& $PY bin/cutout.py assets/raw/hero.jpg -o work/cutouts/hero.png
```
Video → RGBA (QuickTime RLE keeps alpha; big files):
```powershell
& $PY bin/cutout.py assets/raw/hero.mp4 -o work/cutouts/hero.mov
```
Compose the result per §7.

---

## 9. Final assembly & audio

**Concatenate identically-encoded segments (no transition):**
```bash
# files.txt: lines of  file 'work/clips/001.mp4'
ffmpeg -f concat -safe 0 -i files.txt -c copy joined.mp4
```

**Mux song with fades + loudnorm, cut to video length:**
```bash
ffmpeg -i video.mp4 -ss 41 -i assets/raw/song.mp3 -filter_complex \
"[1:a]afade=t=in:st=0:d=0.4,afade=t=out:st=39:d=1.2,loudnorm=I=-14:TP=-1.5:LRA=11[a]" \
-map 0:v -map "[a]" -shortest -c:v copy -c:a aac -b:a 320k final.mp4
```

**Duck music under a voice-over (sidechain):**
```bash
ffmpeg -i music.wav -i vo.wav -filter_complex \
"[0:a][1:a]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[m];[m][1:a]amix=inputs=2" ducked.wav
```

---

## 10. sox audio sweetening

```bash
sox in.wav out.wav gain -n -3            # normalize to -3dB
sox in.wav out.wav bass +3 treble +2     # tone shaping
sox in.wav out.wav reverb 40             # add space to an sfx
sox in.wav out.wav pitch 300             # +3 semitones (comedy speed-up)
```

---

## 11. Encoding defaults

| Purpose | Args |
|---|---|
| Preview | `-c:v libx264 -crf 30 -preset veryfast -vf scale=-2:640` |
| Final | `-c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p` |
| Audio | `-c:a aac -b:a 320k` |
| Web-friendly | add `-movflags +faststart` |

Always end final videos with `-movflags +faststart` for smooth playback/upload.
