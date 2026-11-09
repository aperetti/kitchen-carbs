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

REELS = ("plate", "summary", "log", "after", "manage", "settings", "phone")
logs = {n: json.load(open(f"{D}/{n}.json")) for n in REELS}

# each reel on its own, from just before its first caption, at 30 fps
for n in REELS:
    first = min([c["t"] for c in logs[n]["caps"]] + [c["start"] for c in logs[n]["clips"].values()])
    ff("-ss", f"{max(0, first - .6):.2f}", "-i", f"{D}/{n}.webm", "-vf", f"fps=30", *X264, f"{OUT}/{n}.mp4")
ff("-i", f"{D}/export.mp4", *X264, f"{OUT}/export.mp4")

# The sizzle: section cards and named clips (reels.js marks where each starts and ends on a still frame), a little
# faster. A section card slides in; clips within a section cross-fade.
CARD_S, SPEED = 2.2, 1.3
CUTS = [("card", "title", 3.2),
        ("card", "plate", CARD_S), ("plate", "search"), ("plate", "portion"), ("plate", "weigh"),
        ("card", "summary", CARD_S), ("summary", "open"), ("summary", "bg"), ("summary", "given"),
        ("card", "log", CARD_S), ("log", "day"), ("log", "meal"), ("log", "edit"),
        ("card", "after", CARD_S), ("after", "after"),
        ("card", "manage", CARD_S), ("manage", "food"), ("manage", "photos"),
        ("card", "export", CARD_S), ("export", (0.3, 12.5)),
        ("card", "settings", CARD_S), ("settings", "settings"),
        ("phone", "phone"),
        ("card", "end", 4.5)]
parts = []
for i, c in enumerate(CUTS):
    seg = f"{D}/seg/{i:02d}.mp4"
    if c[0] == "card":
        ff("-loop", "1", "-t", str(c[2]), "-i", f"{D}/cards/card-{c[1]}.png", "-vf", "fps=30,format=yuv420p", *X264, seg)
    elif c[0] == "export":
        a, b = c[1]
        ff("-ss", f"{a:.2f}", "-t", f"{b - a:.2f}", "-i", f"{D}/export.mp4", "-vf", f"setpts=PTS/1.5,fps=30,format=yuv420p", *X264, seg)
    elif c[0] == "phone":   # the phone beside its title, not lost in the middle of a wide frame
        cl = logs["phone"]["clips"]["phone"]; a, b = cl["start"], cl["end"]
        ff("-ss", f"{a:.2f}", "-t", f"{b - a:.2f}", "-i", f"{D}/phone.webm", "-loop", "1", "-i", f"{D}/cards/phone-bg.png", "-filter_complex",
           f"[0]setpts=PTS/1.6,scale=-2:740:flags=lanczos,pad=iw+4:ih+4:2:2:color=0xC9CCC8[ph];[1][ph]overlay=x=840:y=28:shortest=1,fps=30,format=yuv420p", *X264, seg)
    else:
        n, name = c; cl = logs[n]["clips"][name]; a, b = cl["start"], cl["end"]
        ff("-ss", f"{a:.2f}", "-t", f"{b - a:.2f}", "-i", f"{D}/{n}.webm", "-vf",
           f"setpts=PTS/{SPEED},fps=30,format=yuv420p", *X264, seg)
    parts.append((seg, c[0] == "card", float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", seg],
                                                          capture_output=True, text=True, check=True).stdout)))
chain, last, t = [], "0:v", 0.0
for k in range(1, len(parts)):
    slide = parts[k][1] or parts[k - 1][1]
    d = 0.45 if slide else 0.3
    t += parts[k - 1][2] - d   # the next part starts this long before the last one ends
    chain.append(f"[{last}][{k}:v]xfade=transition={'slideleft' if slide else 'fade'}:duration={d}:offset={t:.3f}[x{k}]"); last = f"x{k}"
ff(*[a for seg, _, _ in parts for a in ("-i", seg)], "-filter_complex", ";".join(chain), "-map", f"[{last}]", *X264, f"{OUT}/sizzle.mp4")

# GIFs for the README: GitHub plays GIFs inline, MP4s only as links
def gif(src, dst, width, fps, colors=128):
    ff("-i", src, "-vf", f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors={colors}:stats_mode=diff[p];"
       "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle", dst)
gif(f"{OUT}/sizzle.mp4", f"{OUT}/sizzle.gif", 640, 8, 96)   # under GitHub's 10 MB inline limit
for n in ("plate", "summary", "log", "after", "manage", "export", "settings"):
    gif(f"{OUT}/{n}.mp4", f"{OUT}/{n}.gif", 640, 8)
gif(f"{OUT}/phone.mp4", f"{OUT}/phone.gif", 300, 8)
print("built", OUT)
