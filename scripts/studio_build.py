#!/usr/bin/env python3
"""CinemaHub Studio: assemble user-supplied, rights-cleared clips into a vertical edit."""
import os, shutil, subprocess
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path("work/studio")
OUT = Path("output")
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}

def run(cmd):
    subprocess.run(cmd, check=True)

def download(url, dest):
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS media URLs are accepted.")
    req = Request(url, headers={"User-Agent": "CinemaHubStudio/1.0"})
    with urlopen(req, timeout=90) as response, open(dest, "wb") as f:
        shutil.copyfileobj(response, f)
    if dest.stat().st_size < 100_000:
        raise RuntimeError(f"Downloaded file is too small to be valid media: {dest.name}")

def probe(path):
    p = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)], capture_output=True, text=True)
    try: return float(p.stdout.strip())
    except: return 0.0

def main():
    title = os.getenv("PROJECT_TITLE", "CinemaHub video").strip()
    category = os.getenv("CATEGORY", "games").strip()
    duration = int(os.getenv("DURATION", "22"))
    urls = [u.strip() for u in os.getenv("SOURCE_URLS", "").splitlines() if u.strip()]
    if not urls:
        raise RuntimeError("No source URLs provided. Supply direct HTTPS links to media you may lawfully use.")
    if len(urls) > 20:
        raise RuntimeError("Maximum 20 source clips per build.")
    ROOT.mkdir(parents=True, exist_ok=True); OUT.mkdir(exist_ok=True)
    clips, clip_lengths = [], []
    for i, url in enumerate(urls):
        ext = Path(url.split("?")[0]).suffix.lower()
        if ext not in VIDEO_EXTS:
            raise RuntimeError(f"Unsupported media extension for source {i+1}: {ext or 'unknown'} (use MP4/MOV/M4V/WebM direct links).")
        src = ROOT / f"source_{i:02d}{ext}"
        download(url, src)
        length = probe(src)
        if length < 0.8:
            raise RuntimeError(f"Source {i+1} is not a readable video.")
        target = ROOT / f"clip_{i:02d}.mp4"
        clip_len = min(length, max(2.0, duration/len(urls)))
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(src),"-t",f"{clip_len:.2f}",
             "-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
             "-an","-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p","-movflags","+faststart",str(target)])
        clips.append(target); clip_lengths.append(clip_len)
    # Repeat the selected montage if source footage is shorter than the requested output.
    playlist, total = list(clips), sum(clip_lengths)
    while total < duration:
        playlist.extend(clips)
        total += sum(clip_lengths)
    concat = ROOT / "concat.txt"
    concat.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in playlist))
    silent = ROOT / "silent.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(concat),"-t",str(duration),
         "-vf","fps=30,format=yuv420p","-c:v","libx264","-preset","veryfast","-crf","19","-an","-movflags","+faststart",str(silent)])
    music_url = os.getenv("MUSIC_URL","").strip()
    narration = os.getenv("NARRATION_TEXT","").strip()
    voice = os.getenv("VOICE","ru-RU-DmitryNeural").strip()
    final = OUT / "cinemahub-video.mp4"
    audio_inputs = []
    if narration:
        voice_file = ROOT / "voiceover.mp3"
        run(["python3","-m","edge_tts","--voice",voice,"--text",narration,"--write-media",str(voice_file)])
        if not voice_file.exists() or voice_file.stat().st_size < 1000:
            raise RuntimeError("Text-to-speech did not produce a valid voiceover.")
        audio_inputs.append(voice_file)
    if music_url:
        music = ROOT / "music.mp3"
        download(music_url, music)
        audio_inputs.append(music)
    if not audio_inputs:
        shutil.copy2(silent, final)
    elif len(audio_inputs) == 1:
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(silent),"-i",str(audio_inputs[0]),"-t",str(duration),"-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(final)])
    else:
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(silent),"-i",str(audio_inputs[0]),"-stream_loop","-1","-i",str(audio_inputs[1]),"-filter_complex","[1:a]volume=1.0[voice];[2:a]volume=0.16[music];[voice][music]amix=inputs=2:duration=longest:dropout_transition=2[a]","-t",str(duration),"-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(final)])
    cover = OUT / "cover.jpg"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-ss","1","-i",str(final),"-frames:v","1","-q:v","2",str(cover)])
    hashtags = os.getenv("HASHTAGS", "#CinemaHub").strip()
    description = os.getenv("DESCRIPTION","").strip()
    safe_title = title.replace("\n"," ").strip()
    (OUT / "publication-pack.txt").write_text(
        f"TITLE: {safe_title}\nCATEGORY: {category}\nDURATION: {duration}s\n\nDESCRIPTION:\n{description}\n\nHASHTAGS:\n{hashtags}\n\n"
        "NOTE: Verify music and footage usage rights before publishing. If no music was supplied, add a sound from TikTok's in-app library.\n"
    )
    print(f"SUCCESS: {final} ({final.stat().st_size} bytes)")
    print(f"Sources processed: {len(clips)} | duration: {duration}s | music: {'included' if music_url else 'not included'}")

if __name__ == "__main__":
    main()
