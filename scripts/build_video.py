#!/usr/bin/env python3
"""CinemaHub GTA VI: fast, varied, cinematic vertical montage from Rockstar's official media archive."""
import shutil
import subprocess
import zipfile
import random
from pathlib import Path
from urllib.request import Request, urlopen

OFFICIAL_ZIP = "https://media-rockstargames-com.akamaized.net/VI/downloads/videos/GTAVI_Videos.zip"
WORK = Path("work")
OUT = Path("output")
ZIP_PATH = WORK / "rockstar-media.zip"
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
DURATION = 22.5
SHOT_COUNT = 18
SHOT_LEN = DURATION / SHOT_COUNT

def run(cmd):
    subprocess.run(cmd, check=True)

def fetch(url, dest):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 CinemaHubStudio/2.0"})
    with urlopen(req, timeout=90) as response, open(dest, "wb") as f:
        shutil.copyfileobj(response, f)

def probe_duration(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return 0.0

def drawtext(label, start, end, size, y):
    text_path = WORK / f"text_{int(start * 100):04d}.txt"
    text_path.write_text(label, encoding="utf-8")
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    return (
        "drawtext=fontfile=" + font + ":textfile=" + text_path.as_posix() +
        f":fontcolor=white:fontsize={size}:borderw=4:bordercolor=black:"
        "box=1:boxcolor=black@0.42:boxborderw=18:"
        f"x=(w-text_w)/2:y={y}:enable='between(t,{start:.3f},{end:.3f})'"
    )

def main():
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(OUT, ignore_errors=True)
    WORK.mkdir(parents=True)
    OUT.mkdir(parents=True)
    media = WORK / "media"
    media.mkdir()

    print("Downloading Rockstar Games official GTA VI media archive...")
    fetch(OFFICIAL_ZIP, ZIP_PATH)
    if ZIP_PATH.stat().st_size < 1_000_000:
        raise RuntimeError("Rockstar archive is unexpectedly small; stopping rather than making an incomplete edit.")
    with zipfile.ZipFile(ZIP_PATH) as archive:
        archive.extractall(media)

    sources = sorted(p for p in media.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTS)
    # Optional supplemental sources: user-owned gameplay, licensed stock footage, or CC media.
    extra_urls = [u.strip() for u in __import__("os").getenv("EXTRA_SOURCE_URLS", "").splitlines() if u.strip()]
    if len(extra_urls) > 12:
        raise RuntimeError("Maximum 12 supplemental sources.")
    for i, url in enumerate(extra_urls):
        if not url.startswith("https://"):
            raise RuntimeError("Supplemental sources must be direct HTTPS media URLs.")
        ext = Path(url.split("?")[0]).suffix.lower()
        if ext not in VIDEO_EXTS:
            raise RuntimeError(f"Supplemental source {i+1} must be a direct MP4/MOV/M4V/WebM file URL.")
        dest = media / f"supplemental_{i:02d}{ext}"
        print(f"Downloading supplemental source {i+1}/{len(extra_urls)}...")
        fetch(url, dest)
        sources.append(dest)
    usable = [(p, probe_duration(p)) for p in sources]
    usable = [(p, d) for p, d in usable if d >= 2.0]
    if len(usable) < 3:
        raise RuntimeError(f"Only {len(usable)} usable official videos found; need at least three distinct sources.")
    print(f"Found {len(usable)} usable videos across official and supplemental sources.")

    # Deterministic shuffle gives a different editorial order from alphabetical archive order.
    rng = random.Random(6172026)
    rng.shuffle(usable)
    clips_dir = WORK / "shots"
    clips_dir.mkdir()
    playlist = []
    for i in range(SHOT_COUNT):
        src, src_duration = usable[i % len(usable)]
        shot_duration = SHOT_LEN
        max_start = max(0.0, src_duration - shot_duration - 0.05)
        # Spread repeated visits to a source across its timeline instead of always taking its opening.
        visit = i // len(usable)
        visits = (SHOT_COUNT + len(usable) - 1) // len(usable)
        fraction = (visit + rng.uniform(0.08, 0.92)) / max(1, visits)
        start = max_start * min(1.0, fraction)
        crop_bias = rng.choice([0.22, 0.32, 0.42, 0.50, 0.58, 0.68, 0.78])
        speed = rng.choice([0.90, 0.96, 1.00, 1.06, 1.12])
        # Alternating crop, speed and grade creates a visibly edited sequence, not a repeated slideshow.
        vf = (
            "scale=1200:2134:force_original_aspect_ratio=increase,"
            f"crop=1080:1920:x='(iw-ow)*{crop_bias}':y=(ih-oh)/2,"
            f"setpts={1.0/speed:.5f}*PTS,tpad=stop_mode=clone:stop_duration=0.35,fps=30,"
            f"eq=contrast={rng.uniform(1.04,1.12):.3f}:saturation={rng.uniform(1.10,1.28):.3f}:brightness={rng.uniform(-0.015,0.012):.3f},"
            "unsharp=5:5:0.45:3:3:0.0,format=yuv420p"
        )
        target = clips_dir / f"shot_{i:02d}.mp4"
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{shot_duration:.3f}",
            "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "19", "-pix_fmt", "yuv420p", "-r", "30",
            "-movflags", "+faststart", str(target)
        ])
        playlist.append(target)
        print(f"Shot {i+1:02d}/{SHOT_COUNT}: {src.name} @ {start:.1f}s, speed {speed:.2f}x")

    concat = clips_dir / "concat.txt"
    concat.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in playlist))
    silent = WORK / "montage.mp4"
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat), "-t", str(DURATION),
        "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "18", "-an", "-movflags", "+faststart", str(silent)
    ])

    # Keep typography deliberately sparse: one opening hook and one closing punchline.
    filters = [
        drawtext("VICE CITY НЕ БУДЕТ ПРЕЖНИМ", 0.15, 1.75, 49, "h*0.13"),
        drawtext("ТЫ В ИГРЕ?", 20.55, 22.35, 64, "h*0.78"),
    ]
    final = OUT / "cinemahub-gta6.mp4"
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent),
        "-vf", ",".join(filters), "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", "-an",
        "-movflags", "+faststart", str(final)
    ])

    cover = OUT / "cover.jpg"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "3.2",
         "-i", str(final), "-frames:v", "1", "-q:v", "2", str(cover)])
    (OUT / "publication-pack.txt").write_text(
        "TITLE: Vice City не будет прежним\n"
        "DURATION: 22.5s\nFORMAT: 1080x1920, 30 fps\n"
        "EDIT: 18-shot fast cinematic montage, varied source moments, speed changes and color grading\n"
        "MUSIC: Add a currently trending, suitable sound from TikTok's in-app library.\n\n"
        "DESCRIPTION: Это уже не просто GTA. Это Vice City. 🌴🔥 Какой момент из трейлеров зацепил тебя больше всего?\n\n"
        "HASHTAGS: #GTA6 #GTAVI #ViceCity #Gaming #CinemaHub\n\n"
        "SOURCE: Official Rockstar Games promotional media archive.\n"
        "NOTE: Check Rockstar's current fan-content policy before monetizing or using promotional footage commercially.\n",
        encoding="utf-8"
    )
    print(f"SUCCESS: {final} ({final.stat().st_size} bytes)")
    print(f"Cover: {cover} ({cover.stat().st_size} bytes)")
    print("No music embedded; add a suitable sound from TikTok's in-app library.")

if __name__ == "__main__":
    main()
