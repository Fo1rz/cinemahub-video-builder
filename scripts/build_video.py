#!/usr/bin/env python3
"""CinemaHub GTA VI: fast, varied, cinematic vertical montage from Rockstar's official media archive."""
import shutil
import subprocess
import zipfile
import random
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
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
COMMONS_FILES = [
    ("Une plage à Miami Beach (Floride) en février 2022.webm", "CC0 1.0", "Benoît Prieur"),
    ("Miami International Airport (MIA) June 2024 VID (0).webm", "CC BY 4.0", "FunctioningMemberOfSociety"),
    ("MIA Mover-01.webm", "Public domain dedication", "Priwo"),
]
def run(cmd):
    subprocess.run(cmd, check=True)

def fetch(url, dest, referer=None):
    headers = {"User-Agent": "CinemaHubStudio/2.3 (https://github.com/Fo1rz/cinemahub-video-builder)"}
    if referer:
        headers["Referer"] = referer
    req = Request(url, headers=headers)
    for attempt in range(6):
        try:
            with urlopen(req, timeout=120) as response, open(dest, "wb") as output:
                shutil.copyfileobj(response, output)
            return
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 5:
                raise
            delay = min(90, 10 * (2 ** attempt))
            print(f"Media host returned HTTP {exc.code}; retrying in {delay}s ({attempt+1}/5)...")
            time.sleep(delay)
        except (TimeoutError, URLError):
            if attempt == 5:
                raise
            delay = min(90, 10 * (2 ** attempt))
            print(f"Media download interrupted; retrying in {delay}s ({attempt+1}/5)...")
            time.sleep(delay)

def download_commons_file(filename, dest):
    params = urlencode({
        "action": "query",
        "titles": "File:" + filename,
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    })
    api = "https://commons.wikimedia.org/w/api.php?" + params
    req = Request(api, headers={"User-Agent": "CinemaHubStudio/2.2 (https://github.com/Fo1rz/cinemahub-video-builder)"})
    with urlopen(req, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    pages = payload.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    info = page.get("imageinfo", [])
    if not info or not info[0].get("url"):
        raise RuntimeError(f"Commons original media URL not found: {filename}")
    fetch(info[0]["url"], dest, referer="https://commons.wikimedia.org/")
    if dest.stat().st_size < 100_000:
        raise RuntimeError(f"Commons media unexpectedly small: {filename}")


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
    external_sources = []
    for i, (filename, license_name, author) in enumerate(COMMONS_FILES):
        ext = Path(filename).suffix.lower()
        dest = media / f"commons_miami_{i:02d}{ext}"
        print(f"Downloading Wikimedia Commons source {i+1}/{len(COMMONS_FILES)}: {filename}")
        download_commons_file(filename, dest)
        external_sources.append(dest)
        sources.append(dest)
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
        external_sources.append(dest)
        sources.append(dest)
    usable = [(p, probe_duration(p)) for p in sources]
    usable = [(p, d) for p, d in usable if d >= 2.0]
    official_usable = [(p, d) for p, d in usable if p not in external_sources]
    external_usable = [(p, d) for p, d in usable if p in external_sources]
    if len(official_usable) < 1 or len(external_usable) < 2:
        raise RuntimeError(f"Need at least 1 official and 2 external videos; found {len(official_usable)} and {len(external_usable)}.")
    print(f"Found {len(official_usable)} official and {len(external_usable)} external videos.")

    # Alternate real Miami and GTA VI footage; repeat source only with different timeline selections when needed.
    rng = random.Random(6172026)
    rng.shuffle(official_usable)
    rng.shuffle(external_usable)
    clips_dir = WORK / "shots"
    clips_dir.mkdir()
    playlist = []
    for i in range(SHOT_COUNT):
        pool = external_usable if i % 2 == 0 else official_usable
        src, src_duration = pool[(i // 2) % len(pool)]
        shot_duration = SHOT_LEN
        max_start = max(0.0, src_duration - shot_duration - 0.05)
        # Spread repeated visits to a source across its timeline instead of always taking its opening.
        visit = (i // 2) // len(pool)
        visits = (SHOT_COUNT // 2 + len(pool) - 1) // len(pool)
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
        drawtext("ЭТО МАЙАМИ ИЛИ VICE CITY?", 0.15, 1.75, 49, "h*0.13"),
        drawtext("ГДЕ РЕАЛЬНОСТЬ?", 20.55, 22.35, 64, "h*0.78"),
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
        "TITLE: Майами или Vice City?\n"
        "DURATION: 22.5s\nFORMAT: 1080x1920, 30 fps\n"
        "EDIT: 18-shot fast real-Miami-vs-Vice-City montage, alternating stock and game footage, speed changes and color grading\n"
        "MUSIC: Add a currently trending, suitable sound from TikTok's in-app library.\n\n"
        "DESCRIPTION: Сначала кажется, что это реальный Майами. А потом понимаешь — это Vice City. 🌴🔥 Какой кадр выглядит реалистичнее?\n\n"
        "HASHTAGS: #GTA6 #GTAVI #ViceCity #Gaming #CinemaHub\n\n"
        "SOURCE: Rockstar Games promotional media + Wikimedia Commons footage.\n"
        "COMMONS CREDITS: " + " | ".join(f"{name} — {author} ({license_name})" for name, license_name, author in COMMONS_FILES) + "\n"
        "NOTE: Check Rockstar's current fan-content policy before monetizing or using promotional footage commercially.\n",
        encoding="utf-8"
    )
    print(f"SUCCESS: {final} ({final.stat().st_size} bytes)")
    print(f"Cover: {cover} ({cover.stat().st_size} bytes)")
    print("No music embedded; add a suitable sound from TikTok's in-app library.")

if __name__ == "__main__":
    main()
