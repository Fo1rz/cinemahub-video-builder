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
    self_test = os.getenv("CINEMAHUB_SELF_TEST") == "1"
    urls = [u.strip() for u in os.getenv("SOURCE_URLS", "").splitlines() if u.strip()]
    drive_folder_url = os.getenv("DRIVE_FOLDER_URL", "").strip()
    if not self_test and not urls and not drive_folder_url:
        raise RuntimeError("Provide a shared Google Drive folder URL or direct HTTPS media URLs.")
    if len(urls) > 20:
        raise RuntimeError("Maximum 20 source clips per build.")
    if self_test:
        duration = 15
        shutil.rmtree(ROOT, ignore_errors=True)
        shutil.rmtree(OUT, ignore_errors=True)
    ROOT.mkdir(parents=True, exist_ok=True); OUT.mkdir(exist_ok=True)
    pace = os.getenv("PACE", "fast").strip().lower()
    pace_seconds = {"fast": 1.6, "balanced": 2.4, "cinematic": 3.6}
    if pace not in pace_seconds:
        raise RuntimeError("PACE must be fast, balanced, or cinematic.")
    sources = []
    if self_test:
        # Synthetic footage exercises the real FFmpeg montage path without external media.
        for i, color in enumerate(("0x182848", "0x8f2438")):
            src = ROOT / f"self_test_{i:02d}.mp4"
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-f", "lavfi", "-i", f"color=c={color}:s=540x960:r=30:d=5",
                 "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(src)])
            sources.append((src, probe(src)))
    else:
        source_paths = []
        if drive_folder_url:
            import gdown
            drive_dir = ROOT / "google_drive"
            shutil.rmtree(drive_dir, ignore_errors=True)
            drive_dir.mkdir(parents=True, exist_ok=True)
            print("Downloading shared Google Drive folder...")
            downloaded = gdown.download_folder(
                url=drive_folder_url, output=str(drive_dir),
                quiet=False, use_cookies=False, remaining_ok=True
            )
            if not downloaded:
                raise RuntimeError("Google Drive folder download returned no files. Check that the folder is shared as 'Anyone with the link — Viewer'.")
            source_paths.extend(
                x for x in drive_dir.rglob("*")
                if x.is_file() and x.suffix.lower() in VIDEO_EXTS
            )
            print(f"Google Drive files downloaded: {len(downloaded)}; video files found: {len(source_paths)}")
        for i, url in enumerate(urls):
            ext = Path(url.split("?")[0]).suffix.lower()
            if ext not in VIDEO_EXTS:
                raise RuntimeError(f"Unsupported media extension for source {i+1}: {ext or 'unknown'} (use MP4/MOV/M4V/WebM direct links).")
            src = ROOT / f"source_url_{i:02d}{ext}"
            download(url, src)
            source_paths.append(src)
        if not source_paths:
            raise RuntimeError("No MP4/MOV/M4V/WebM videos found in the shared folder or direct URLs.")
        source_paths = sorted(source_paths, key=lambda x: x.name.lower())[:20]
        for i, src in enumerate(source_paths):
            length = probe(src)
            if length < 0.8:
                print(f"Skipping unreadable/short source: {src.name}")
                continue
            sources.append((src, length))
        if not sources:
            raise RuntimeError("No readable video sources were found.")
    # Build a paced montage from short excerpts distributed across the supplied sources.
    segment_count = max(1, int((duration + pace_seconds[pace] - 0.001) // pace_seconds[pace]))
    visits = [0] * len(sources)
    visit_totals = [sum(1 for k in range(segment_count) if k % len(sources) == i) for i in range(len(sources))]
    clips, clip_lengths = [], []
    for k in range(segment_count):
        src, source_length = sources[k % len(sources)]
        source_index = k % len(sources)
        seg_len = min(pace_seconds[pace], source_length)
        slots = max(1, visit_totals[source_index] - 1)
        offset = 0.0 if visit_totals[source_index] <= 1 else (visits[source_index] * max(0.0, source_length - seg_len) / slots)
        visits[source_index] += 1
        target = ROOT / f"segment_{k:03d}.mp4"
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-ss",f"{offset:.3f}","-i",str(src),"-t",f"{seg_len:.2f}",
             "-filter_complex","[0:v]split=2[bg][fg];[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=28:12,eq=brightness=-0.16:saturation=0.72[back];[fg]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos[front];[back][front]overlay=(W-w)/2:(H-h)/2,fps=30,setsar=1,format=yuv420p[v]",
             "-map","[v]","-an","-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p","-movflags","+faststart",str(target)])
        clips.append(target); clip_lengths.append(seg_len)
    # Repeat the paced sequence only when the selected excerpts do not fill the requested duration.
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
    hook_text = os.getenv("HOOK_TEXT","").strip()
    if self_test:
        hook_text = "CINEMAHUB SELF-TEST"
    voice = os.getenv("VOICE","ru-RU-DmitryNeural").strip()
    if duration not in {15, 22, 30, 45, 60}:
        raise RuntimeError("Duration must be one of: 15, 22, 30, 45, 60 seconds.")
    if voice not in {"ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural"}:
        raise RuntimeError("Unsupported voice. Choose Dmitry or Svetlana.")
    if len(narration) > 2000:
        raise RuntimeError("Narration is too long (maximum 2000 characters).")
    if len(hook_text) > 120:
        raise RuntimeError("Hook text is too long (maximum 120 characters).")
    final = OUT / "cinemahub-video.mp4"
    audio_inputs = []
    if hook_text:
        hook_file = ROOT / "hook.txt"
        hook_file.write_text(hook_text, encoding="utf-8")
        hooked = ROOT / "hooked.mp4"
        hook_filter = (
            "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"textfile={hook_file.as_posix()}:fontcolor=white:fontsize=62:"
            "borderw=4:bordercolor=black:box=1:boxcolor=black@0.48:boxborderw=24:"
            "x=(w-text_w)/2:y=h*0.13:enable='between(t,0,2.8)'"
        )
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(silent),
             "-vf",hook_filter,"-c:v","libx264","-preset","veryfast","-crf","19",
             "-pix_fmt","yuv420p","-an","-movflags","+faststart",str(hooked)])
        silent = hooked
    if narration:
        voice_file = ROOT / "voiceover.mp3"
        subtitles_file = ROOT / "voiceover.vtt"
        run(["python3","-m","edge_tts","--voice",voice,"--text",narration,"--write-media",str(voice_file),"--write-subtitles",str(subtitles_file)])
        if not voice_file.exists() or voice_file.stat().st_size < 1000 or not subtitles_file.exists():
            raise RuntimeError("Text-to-speech did not produce valid audio and subtitle files.")
        speech_duration = probe(voice_file)
        if speech_duration > duration:
            raise RuntimeError(f"Voiceover is {speech_duration:.1f}s but the video is {duration}s. Shorten the narration script.")
        audio_inputs.append(voice_file)
        # Burn readable Russian captions into the video and keep separate subtitle/audio assets.
        captioned = ROOT / "captioned.mp4"
        subtitle_filter = f"subtitles=filename='{subtitles_file.as_posix()}':force_style='FontName=DejaVu Sans,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00101010,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=150'"
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(silent),"-vf",subtitle_filter,"-c:v","libx264","-preset","veryfast","-crf","19","-pix_fmt","yuv420p","-an","-movflags","+faststart",str(captioned)])
        shutil.copy2(subtitles_file, OUT / "voiceover.vtt")
        shutil.copy2(voice_file, OUT / "voiceover.mp3")
        silent = captioned
    if music_url:
        music = ROOT / "music.mp3"
        download(music_url, music)
        audio_inputs.append(music)
    if not audio_inputs:
        shutil.copy2(silent, final)
    elif len(audio_inputs) == 1:
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(silent),"-i",str(audio_inputs[0]),"-t",str(duration),"-map","0:v:0","-map","1:a:0","-af","apad","-c:v","copy","-c:a","aac","-b:a","192k","-movflags","+faststart",str(final)])
    else:
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(silent),"-i",str(audio_inputs[0]),"-stream_loop","-1","-i",str(audio_inputs[1]),"-filter_complex","[1:a]volume=1.0[voice];[2:a]volume=0.16[music];[voice][music]amix=inputs=2:duration=longest:dropout_transition=2[a]","-t",str(duration),"-map","0:v:0","-map","[a]","-c:v","copy","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(final)])
    cover = OUT / "cover.jpg"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-ss","1","-i",str(final),"-frames:v","1","-q:v","2",str(cover)])
    hashtags = os.getenv("HASHTAGS", "#CinemaHub").strip()
    description = os.getenv("DESCRIPTION","").strip()
    safe_title = title.replace("\n"," ").strip()
    (OUT / "publication-pack.txt").write_text(
        f"TITLE: {safe_title}\nCATEGORY: {category}\nDURATION: {duration}s\n\nDESCRIPTION:\n{description}\n\nHASHTAGS:\n{hashtags}\n\n"
        f"HOOK: {'included in first 2.8 seconds' if hook_text else 'not included'}\nVOICEOVER: {'included' if narration else 'not included'}\nCAPTIONS: {'burned into video; VTT also included' if narration else 'not included'}\n"
        "NOTE: Verify music and footage usage rights before publishing. If no music was supplied, add a sound from TikTok's in-app library.\n"
    )
    print(f"SUCCESS: {final} ({final.stat().st_size} bytes)")
    print(f"Sources processed: {len(clips)} | duration: {duration}s | pace: {pace} | hook: {'included' if hook_text else 'off'} | voiceover: {'included' if narration else 'not included'} | captions: {'burned in' if narration else 'off'} | music: {'included' if music_url else 'not included'}")
    if self_test:
        check = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate", "-of", "csv=p=0", str(final)],
            capture_output=True, text=True, check=True).stdout.strip()
        if check != "1080,1920,30/1":
            raise RuntimeError(f"Self-test failed: unexpected video format: {check}")
        if not cover.exists() or cover.stat().st_size < 1000 or not (OUT / "publication-pack.txt").exists():
            raise RuntimeError("Self-test failed: cover or publication pack is missing.")
        print("SELF-TEST PASSED: MP4 format, cover and publication pack verified.")

if __name__ == "__main__":
    main()
