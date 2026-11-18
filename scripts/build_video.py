#!/usr/bin/env python3
"""CinemaHub GTA VI: cinematic vertical edit from Rockstar's direct 4K Extended Look."""
import re, shutil, subprocess
from pathlib import Path

WORK, OUT = Path("work"), Path("output")
DURATION, SHOTS = 22.5, 12
SOURCE = "https://media-rockstargames-com.akamaized.net/VI/downloads/videos/GTAVI_An_Extended_Look/GTAVI_An_Extended_Look.mp4"
# Spread excerpts through the official 26-minute in-game showcase.
TIMES = [501, 540, 688, 790, 840, 1037, 1045, 1061, 1093, 1128, 1402, 1511]

def run(cmd):
    subprocess.run(cmd,check=True)

def main():
    shutil.rmtree(WORK,ignore_errors=True); shutil.rmtree(OUT,ignore_errors=True)
    WORK.mkdir(); OUT.mkdir()
    clips=[]
    shot_len=DURATION/SHOTS
    headers="Referer: https://www.rockstargames.com/\r\nOrigin: https://www.rockstargames.com\r\nUser-Agent: Mozilla/5.0 CinemaHubStudio/3.0\r\n"
    for i,start in enumerate(TIMES):
        out=WORK/f"shot_{i:02d}.mp4"
        # Preserve the complete 16:9 gameplay frame; use a soft enlarged duplicate as the vertical canvas.
        vf=("[0:v]split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            "boxblur=28:12,eq=brightness=-0.16:saturation=0.72[back];"
            "[fg]scale=1080:-2:flags=lanczos,"
            "eq=contrast=1.07:saturation=1.12:brightness=0.012:gamma=1.06,"
            "unsharp=5:5:0.30:3:3:0[front];"
            "[back][front]overlay=(W-w)/2:(H-h)/2,fps=30,format=yuv420p[v]")
        print(f"Extracting official 4K scene {i+1}/{SHOTS} at {start}s")
        run(["ffmpeg","-hide_banner","-loglevel","warning","-rw_timeout","60000000","-headers",headers,
             "-ss",str(start),"-i",SOURCE,"-t",f"{shot_len:.3f}","-filter_complex",vf,"-map","[v]","-an",
             "-c:v","libx264","-preset","medium","-crf","16","-r","30","-pix_fmt","yuv420p",
             "-movflags","+faststart",str(out)])
        if not out.exists() or out.stat().st_size<100_000: raise RuntimeError(f"Failed to extract scene {i+1}")
        clips.append(out)
    concat=WORK/"concat.txt"
    concat.write_text(chr(10).join("file "+chr(39)+str(p.resolve())+chr(39) for p in clips)+chr(10))
    silent=WORK/"montage.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(concat),"-t",str(DURATION),
         "-vf","fps=30,format=yuv420p","-c:v","libx264","-preset","medium","-crf","16","-an","-movflags","+faststart",str(silent)])
    hook=WORK/"hook.txt"; hook.write_text("VICE CITY. БЕЗ ПРАВИЛ.",encoding="utf-8")
    end=WORK/"end.txt"; end.write_text("19.11.2026",encoding="utf-8")
    font=__import__("os").getenv("FONT_FILE","/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    vf=",".join([
        f"drawtext=fontfile={font}:textfile={hook.as_posix()}:fontcolor=white:fontsize=54:borderw=3:bordercolor=black@0.75:shadowcolor=black@0.8:shadowx=2:shadowy=3:x=(w-text_w)/2:y=h*0.12:enable='between(t,0.12,1.65)'",
        f"drawtext=fontfile={font}:textfile={end.as_posix()}:fontcolor=white:fontsize=70:borderw=3:bordercolor=black@0.75:shadowcolor=black@0.8:shadowx=2:shadowy=3:x=(w-text_w)/2:y=h*0.79:enable='between(t,20.7,22.35)'"
    ])
    final=OUT/"cinemahub-gta6.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(silent),"-vf",vf,"-c:v","libx264","-preset","medium","-crf","16","-pix_fmt","yuv420p","-r","30","-an","-movflags","+faststart",str(final)])
    cover=OUT/"cover.jpg"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-ss","15.5","-i",str(final),"-frames:v","1","-q:v","2",str(cover)])
    (OUT/"publication-pack.txt").write_text(
        "TITLE: VICE CITY — НИКАКИХ ПРАВИЛ\nDURATION: 22.5s\nFORMAT: 1080x1920, 30 fps, H.264\n"
        "EDIT: 12 curated excerpts from Rockstar's official 4K in-game Extended Look; full gameplay frame preserved inside a blurred 9:16 canvas, no center crop.\n"
        "AUDIO: No music embedded. Add a rising GTA / cinematic sound from TikTok's in-app library.\n\n"
        "DESCRIPTION: Завтра начинается новая глава. Добро пожаловать в Vice City. 🌴🔥\n"
        "HASHTAGS: #GTA6 #GTAVI #ViceCity #Gaming #CinemaHub\n\n"
        "SOURCE: Rockstar Games official media page: https://www.rockstargames.com/VI/media/videos\n"
        "NOTE: Follow Rockstar's current fan-content policy and TikTok's copyright rules.\n",encoding="utf-8")
    if final.stat().st_size<5_000_000: raise RuntimeError("Rendered MP4 is unexpectedly small.")
    print(f"SUCCESS: {final} ({final.stat().st_size} bytes)")
if __name__=="__main__": main()
