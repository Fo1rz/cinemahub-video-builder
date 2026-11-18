#!/usr/bin/env python3
import os, re, sys, zipfile, subprocess, shutil, random
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

PAGE = "https://www.rockstargames.com/VI/media/videos"
OFFICIAL_ZIP = "https://media-rockstargames-com.akamaized.net/VI/downloads/videos/GTAVI_Videos.zip"
WORK = Path("work")
OUT = Path("output")
ZIP_PATH = WORK / "rockstar-media.zip"
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}

def fetch(url, dest):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 CinemaHubVideoBuilder/1.0"})
    with urlopen(req, timeout=60) as response, open(dest, "wb") as f:
        shutil.copyfileobj(response, f)

def discover_zip():
    # Exact archive URL exposed by Rockstar's official Download All videos link.
    print(f"Using Rockstar official media archive: {OFFICIAL_ZIP}")
    return OFFICIAL_ZIP

def probe_duration(path):
    p = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)], capture_output=True, text=True)
    try: return float(p.stdout.strip())
    except: return 0.0

def run(cmd):
    subprocess.run(cmd, check=True)

def main():
    WORK.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
    print("Discovering official Rockstar ZIP...")
    zip_url = discover_zip()
    print("Downloading official media archive...")
    fetch(zip_url, ZIP_PATH)
    if ZIP_PATH.stat().st_size < 1_000_000:
        raise RuntimeError("Downloaded archive is unexpectedly small; refusing to build from incomplete media.")
    extract = WORK / "media"
    extract.mkdir(exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH) as z:
        z.extractall(extract)
    videos = sorted(p for p in extract.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    if not videos:
        raise RuntimeError("The Rockstar ZIP contained no supported video files.")
    print(f"Found {len(videos)} official video files.")
    # Spread the edit across different official clips; keep the output short and fast.
    selected = videos[:]
    if len(selected) > 9:
        indexes = [round(i * (len(selected)-1) / 8) for i in range(9)]
        selected = [selected[i] for i in indexes]
    else:
        selected = selected[:9]
    clip_dir = WORK / "clips"
    clip_dir.mkdir(exist_ok=True)
    clip_paths = []
    for i, src in enumerate(selected):
        duration = probe_duration(src)
        if duration < 2.7:
            continue
        # Pick a different point through each source clip, avoiding the opening slate.
        start = min(max(0.8, duration * (0.28 + (i % 3) * 0.12)), max(0, duration - 2.5))
        target = clip_dir / f"clip_{i:02d}.mp4"
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-ss",f"{start:.3f}","-i",str(src),"-t","2.5",
             "-an","-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
             "-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p","-movflags","+faststart",str(target)])
        clip_paths.append(target)
    if len(clip_paths) < 5:
        raise RuntimeError(f"Only {len(clip_paths)} usable clips; refusing to publish a weak/empty edit.")
    concat_file = clip_dir / "concat.txt"
    concat_file.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in clip_paths))
    final = OUT / "cinemahub-gta6.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(concat_file),
         "-t","22.5","-c:v","libx264","-preset","veryfast","-crf","19","-pix_fmt","yuv420p",
         "-r","30","-an","-movflags","+faststart",str(final)])
    print(f"SUCCESS: {final} ({final.stat().st_size} bytes)")
    print("NOTE: no music was embedded; add a properly licensed TikTok sound after download.")

if __name__ == "__main__":
    main()
