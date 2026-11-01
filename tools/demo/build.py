"""Turn the recorded reels into MP4s, a sizzle reel and README GIFs; run by record.sh.
   build.py <demo-out dir>   (needs ffmpeg, pdftoppm and Pillow)"""
import json, os, subprocess, sys
import cards

D = sys.argv[1]; OUT = f"{D}/final"
for d in (OUT, f"{D}/seg", f"{D}/cards"):
    os.makedirs(d, exist_ok=True)
BG = "0xF2F3F1"
X264 = ["-c:v", "libx264", "-preset", "slow", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an"]
def ff(*a): subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)
cards.main(f"{D}/cards")

# the PDF export, from the demo server's real PDF: page one scrolls, then page two
subprocess.run(["pdftoppm", "-png", "-r", "110", "-f", "1", "-l", "2", f"{D}/demo.pdf", f"{D}/pdfpage"], check=True)
ff("-f", "lavfi", "-i", "color=c=0xE9EAE7:s=1280x800:r=30:d=13", "-loop", "1", "-i", f"{D}/pdfpage-1.png", "-loop", "1", "-i", f"{D}/pdfpage-2.png",
   "-loop", "1", "-i", f"{D}/cards/cap-export-1.png", "-loop", "1", "-i", f"{D}/cards/cap-export-2.png", "-filter_complex",
   "[1]scale=820:-1[p1];[2]scale=820:-1[p2];"
   "[0][p1]overlay=x=230:y='if(lt(t,1.5),40,if(lt(t,8.5),40-(t-1.5)*(h-760)/7,800-h-40))':enable='lt(t,9)':shortest=1[a];"
   "[a][p2]overlay=x=230:y='if(lt(t,10),40,40-(t-10)*(h-760)/3)':enable='gte(t,9)':shortest=1[b];"
   "[b][3]overlay=0:0:enable='lt(t,6)':shortest=1[c];[c][4]overlay=0:0:enable='gte(t,6)':shortest=1[v]",
   "-map", "[v]", "-t", "13", *X264, f"{D}/export.mp4")

# each reel on its own, without the blank first second
for n in ("plate", "summary", "log", "manage", "settings", "phone"):
    ff("-ss", "1.2", "-i", f"{D}/{n}.webm", "-vf", "fps=30", *X264, f"{OUT}/{n}.mp4")
ff("-i", f"{D}/export.mp4", *X264, f"{OUT}/export.mp4")

# the sizzle: cards and the key moments, cut at the captions (index, offset in seconds), a little faster,
# each sliding in from the right over the one before
marks = {n: [m["t"] for m in json.load(open(f"{D}/{n}.json"))] for n in ("plate", "summary", "log", "manage", "settings", "phone")}
marks["export"] = [0.3, 12.5]
CUTS = [("card", "title", 3.2), ("card", "plate", 1.4), ("plate", (2, -.4), (5, 0), 1.35),
        ("card", "summary", 1.4), ("summary", (0, -.2), (1, -.1), 1.3), ("summary", (3, -.7), (4, 0), 1.2), ("summary", (5, -.4), (6, -.2), 1.2),
        ("card", "log", 1.4), ("log", (0, -.2), (1, -1.7), 1.4), ("log", (2, -.2), (3, 4.6), 1.4), ("log", (4, -.2), (5, -.1), 1.4),
        ("card", "manage", 1.4), ("manage", (0, -.1), (1, -.3), 1.4), ("manage", (2, -.2), (2, 6.4), 1.4),
        ("card", "export", 1.4), ("export", (0, 0), (1, 0), 1.6),
        ("card", "settings", 1.4), ("settings", (1, -.2), (2, -.1), 1.4),
        ("card", "phone", 1.4), ("phone", (0, -.3), (3, -.3), 1.6), ("card", "end", 4.5)]
parts = []
for i, c in enumerate(CUTS):
    seg = f"{D}/seg/{i:02d}.mp4"
    if c[0] == "card":
        d = c[2]
        ff("-loop", "1", "-t", str(d), "-i", f"{D}/cards/card-{c[1]}.png",
           "-vf", "fps=30,format=yuv420p", *X264, seg)
    else:
        n, (i0, o0), (i1, o1), speed = c
        a, b = marks[n][i0] + o0, marks[n][i1] + o1; d = (b - a) / speed
        fit = f"scale=-2:800,pad=1280:800:(ow-iw)/2:0:color={BG}" if n == "phone" else "scale=1280:800"
        ff("-ss", f"{a:.2f}", "-t", f"{b - a:.2f}", "-i", f"{D}/export.mp4" if n == "export" else f"{D}/{n}.webm", "-vf",
           f"setpts=PTS/{speed},{fit},fps=30,format=yuv420p", *X264, seg)
    parts.append((seg, float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", seg],
                                            capture_output=True, text=True, check=True).stdout)))
SWIPE = 0.45
chain, last, t = [], "0:v", 0.0
for k in range(1, len(parts)):
    t += parts[k - 1][1] - SWIPE   # the next clip starts sliding in this long before the last one ends
    chain.append(f"[{last}][{k}:v]xfade=transition=slideleft:duration={SWIPE}:offset={t:.3f}[x{k}]"); last = f"x{k}"
ff(*[a for seg, _ in parts for a in ("-i", seg)], "-filter_complex", ";".join(chain), "-map", f"[{last}]", *X264, f"{OUT}/sizzle.mp4")

# GIFs for the README: GitHub plays GIFs inline, MP4s only as links
def gif(src, dst, width, fps, colors=128):
    ff("-i", src, "-vf", f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors={colors}:stats_mode=diff[p];"
       "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle", dst)
gif(f"{OUT}/sizzle.mp4", f"{OUT}/sizzle.gif", 720, 8, 96)
for n in ("plate", "summary", "log", "manage", "export", "settings"):
    gif(f"{OUT}/{n}.mp4", f"{OUT}/{n}.gif", 640, 8)
gif(f"{OUT}/phone.mp4", f"{OUT}/phone.gif", 300, 8)
print("built", OUT)
