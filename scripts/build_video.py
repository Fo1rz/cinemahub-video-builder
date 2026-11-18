#!/usr/bin/env python3
# GTA VI pre-launch edit: timed Russian hype title cards and creator pack.
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
    clip_durations = []
    for i, src in enumerate(selected):
        duration = probe_duration(src)
        print(f"Source {src.name}: {duration:.3f}s")
        if duration < 0.6:
            print(f"Skipping very short/unreadable source: {src.name}")
            continue
        # Use up to 2.5 seconds from each official source, including short clips.
        clip_len = min(2.5, duration)
        start = max(0.0, (duration - clip_len) * (0.35 + (i % 3) * 0.15))
        target = clip_dir / f"clip_{i:02d}.mp4"
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-ss",f"{start:.3f}","-i",str(src),"-t",f"{clip_len:.3f}",
             "-an","-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
             "-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p","-movflags","+faststart",str(target)])
        clip_paths.append(target)
        clip_durations.append(clip_len)
    if len(clip_paths) < 5:
        raise RuntimeError(f"Only {len(clip_paths)} usable clips; refusing to publish a weak/empty edit.")
    # Repeat the official montage sequence if the source clips are collectively shorter than 20 seconds.
    total_duration = sum(clip_durations)
    while total_duration < 22.5 and len(clip_paths) >= 5:
        clip_paths.extend(clip_paths[:])
        clip_durations.extend(clip_durations[:])
        total_duration = sum(clip_durations)
        concat_file = clip_dir / "concat.txt"
    concat_file.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in clip_paths))
    final = OUT / "cinemahub-gta6.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(concat_file),
         "-t","22.5","-c:v","libx264","-preset","veryfast","-crf","19","-pix_fmt","yuv420p",
         "-r","30","-an","-movflags","+faststart",str(final)])

    # Add a four-beat Russian hype sequence. Text is kept in UTF-8 files so
    # FFmpeg handles Cyrillic reliably; all footage remains official Rockstar media.
    title_cards = [
        ("13 ЛЕТ МЫ ЖДАЛИ...", 0.0, 3.5),
        ("И ВОТ ЭТОТ МОМЕНТ НАСТАЛ", 5.0, 9.0),
        ("VICE CITY • 19.11.2026", 11.5, 16.5),
        ("ТЫ ГОТОВ?", 18.0, 22.5),
    ]
    filters = []
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    for i, (label, start, end) in enumerate(title_cards):
        text_path = WORK / f"title_{i}.txt"
        text_path.write_text(label, encoding="utf-8")
        filters.append(
            "drawtext="
            f"fontfile={font}:textfile={text_path.as_posix()}:"
            "fontcolor=white:fontsize=58:borderw=4:bordercolor=black:"
            "box=1:boxcolor=black@0.55:boxborderw=24:"
            "x=(w-text_w)/2:y=h*0.14:"
            f"enable='between(t,{start},{end})'"
        )
    titled = OUT / "cinemahub-gta6-titled.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(final),
         "-vf", ",".join(filters), "-c:v","libx264","-preset","veryfast","-crf","19",
         "-pix_fmt","yuv420p","-r","30","-an","-movflags","+faststart",str(titled)])
    titled.replace(final)

    cover = OUT / "cover.jpg"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-ss","1","-i",str(final),
         "-frames:v","1","-q:v","2",str(cover)])
    (OUT / "publication-pack.txt").write_text(
        "TITLE: Последняя ночь перед GTA VI\\n"
        "DURATION: 22.5s\\n"
        "FORMAT: 1080x1920, 30 fps\\n"
        "MUSIC: Add a currently available sound from TikTok's in-app library.\\n\\n"
        "DESCRIPTION: 13 лет ожидания. И вот этот момент почти настал… 🌴🔥 "
        "Vice City, мы возвращаемся! Ты готов к GTA VI?\\n\\n"
        "HASHTAGS: #GTA6 #GTAVI #ViceCity #Gaming #CinemaHub\\n\\n"
        "SOURCE: Official Rockstar Games media archive.\\n"
        "NOTE: This edit contains official promotional footage. Check Rockstar's current "
        "fan-content policy before monetizing or using it to promote a product/service."
    , encoding="utf-8")
    print(f"SUCCESS: {final} ({final.stat().st_size} bytes)")
    print(f"Cover created: {cover} ({cover.stat().st_size} bytes)")
    print("NOTE: no music was embedded; add a suitable TikTok in-app sound after download.")

if __name__ == "__main__":
    main()
