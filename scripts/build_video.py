#!/usr/bin/env python3
"""CinemaHub GTA VI cinematic TikTok edit from official Rockstar trailers."""
import re, shutil, subprocess
from pathlib import Path

WORK, OUT = Path("work"), Path("output")
DURATION, SHOT_COUNT = 22.5, 12
SOURCES = [
    ("trailer2", "https://www.youtube.com/watch?v=VQRLujxTm3c"),
    ("trailer1", "https://www.youtube.com/watch?v=QdBZY2fkU-0"),
]

def run(cmd, capture=False):
    return subprocess.run(cmd, check=True, text=True, capture_output=capture)

def probe_duration(path):
    p = run(["ffmpeg","-hide_banner","-i",str(path),"-frames:v","1","-f","null","-"],capture=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)",p.stderr)
    if not m: raise RuntimeError(f"Cannot read duration: {path.name}")
    h,mi,s=m.groups()
    return int(h)*3600+int(mi)*60+float(s)

def scene_points(path, length):
    p = subprocess.run(["ffmpeg","-hide_banner","-i",str(path),"-vf","select='gt(scene,0.22)',showinfo","-an","-f","null","-"],capture_output=True,text=True)
    points=[float(x) for x in re.findall(r"pts_time:([0-9.]+)",p.stderr)]
    points=[x for x in points if 0.7 < x < length-2.0]
    # Keep scene candidates at least 1.8 seconds apart.
    clean=[]
    for x in points:
        if not clean or x-clean[-1]>=1.8: clean.append(x)
    return clean

def main():
    shutil.rmtree(WORK,ignore_errors=True); shutil.rmtree(OUT,ignore_errors=True)
    WORK.mkdir(); OUT.mkdir()
    sources=[]
    for name,url in SOURCES:
        target=WORK/f"{name}.mp4"
        print("Downloading official Rockstar trailer:",name)
        run(["python3","-m","yt_dlp","--no-playlist","--no-warnings","-f","bv*[height>=1080]+ba/b","--merge-output-format","mp4","-o",str(target),url])
        if not target.exists() or target.stat().st_size<5_000_000:
            raise RuntimeError(f"Official source download failed or was too small: {name}")
        d=probe_duration(target)
        points=scene_points(target,d)
        if len(points)<4: raise RuntimeError(f"Not enough scene changes detected in {name}")
        sources.append((target,d,points))
        print(f"Validated {name}: {d:.1f}s, {len(points)} usable scene changes")
    # Distribute the edit across both trailers, avoiding adjacent repeated scenes.
    allocation=[6,6]
    selected=[]
    for (path,d,points),count in zip(sources,allocation):
        if len(points)<count: raise RuntimeError(f"Not enough distinct shots in {path.name}")
        indices=[round(i*(len(points)-1)/(count-1)) for i in range(count)]
        for idx in indices:
            selected.append((path,max(0.0,min(d-1.95,points[idx]-0.45))))
    shot_len=DURATION/SHOT_COUNT
    clips=[]
    for i,(src,start) in enumerate(selected):
        out=WORK/f"shot_{i:02d}.mp4"
        # Fill the vertical screen with a deliberate center crop; preserve full HD output.
        vf=("scale=2160:3840:force_original_aspect_ratio=increase,"
            "crop=1215:2160:x='(iw-ow)*0.50':y=(ih-oh)/2,"
            "scale=1080:1920,fps=30,"
            "eq=contrast=1.10:saturation=1.14:brightness=-0.006,"
            "unsharp=5:5:0.30:3:3:0,format=yuv420p")
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-ss",f"{start:.3f}","-i",str(src),"-t",f"{shot_len:.3f}",
             "-vf",vf,"-an","-c:v","libx264","-preset","medium","-crf","16","-r","30","-pix_fmt","yuv420p","-movflags","+faststart",str(out)])
        clips.append(out)
        print(f"Shot {i+1:02d}/{SHOT_COUNT}: {src.stem} @ {start:.2f}s")
    concat=WORK/"concat.txt"
    concat.write_text(chr(10).join("file "+chr(39)+str(p.resolve())+chr(39) for p in clips)+chr(10))
    silent=WORK/"montage.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(concat),"-t",str(DURATION),
         "-vf","fps=30,format=yuv420p","-c:v","libx264","-preset","medium","-crf","16","-an","-movflags","+faststart",str(silent)])
    hook=WORK/"hook.txt"; hook.write_text("VICE CITY. ТВОЯ ИСТОРИЯ НАЧИНАЕТСЯ.",encoding="utf-8")
    end=WORK/"end.txt"; end.write_text("19.11.2026",encoding="utf-8")
    font=__import__("os").getenv("FONT_FILE","/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    vf=",".join([
        f"drawtext=fontfile={font}:textfile={hook.as_posix()}:fontcolor=white:fontsize=46:borderw=3:bordercolor=black@0.75:shadowcolor=black@0.8:shadowx=2:shadowy=3:x=(w-text_w)/2:y=h*0.12:enable='between(t,0.12,1.65)'",
        f"drawtext=fontfile={font}:textfile={end.as_posix()}:fontcolor=white:fontsize=70:borderw=3:bordercolor=black@0.75:shadowcolor=black@0.8:shadowx=2:shadowy=3:x=(w-text_w)/2:y=h*0.79:enable='between(t,20.7,22.35)'"
    ])
    final=OUT/"cinemahub-gta6.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(silent),"-vf",vf,"-c:v","libx264","-preset","medium","-crf","16","-pix_fmt","yuv420p","-r","30","-an","-movflags","+faststart",str(final)])
    cover=OUT/"cover.jpg"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-ss","4.0","-i",str(final),"-frames:v","1","-q:v","2",str(cover)])
    (OUT/"publication-pack.txt").write_text(
        "TITLE: VICE CITY — ТВОЯ ИСТОРИЯ НАЧИНАЕТСЯ\nDURATION: 22.5s\nFORMAT: 1080x1920, 30 fps, H.264\n"
        "EDIT: 12 distinct cinematic cuts from official Rockstar GTA VI trailers; no unrelated city footage.\n"
        "AUDIO: No music embedded. Add a rising GTA / cinematic sound from TikTok's in-app library and align the first bass hit with the first cut.\n\n"
        "DESCRIPTION: Завтра начинается новая глава. Добро пожаловать в Vice City. 🌴🔥\n"
        "HASHTAGS: #GTA6 #GTAVI #ViceCity #Gaming #CinemaHub\n\n"
        "SOURCE: Rockstar Games official trailers: https://www.rockstargames.com/VI/media/videos\n"
        "NOTE: Use footage in accordance with Rockstar's fan-content policy and TikTok's copyright rules.\n",encoding="utf-8")
    if final.stat().st_size<5_000_000: raise RuntimeError("Rendered MP4 is unexpectedly small.")
    print(f"SUCCESS: {final} ({final.stat().st_size} bytes)")

if __name__=="__main__": main()
