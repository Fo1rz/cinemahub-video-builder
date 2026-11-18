# CinemaHub Studio

Free GitHub Actions-based video assembly studio for CinemaHub. It uses FFmpeg (no generative AI) to turn rights-cleared source clips into vertical TikTok-ready MP4s.

## Existing GTA VI workflow
The original Build GTA VI TikTok workflow is preserved. It downloads Rockstar's official GTA VI media archive and builds the original 22.5-second vertical edit.

## Universal studio
Open Actions → CinemaHub Studio → Run workflow and provide:
- Project title and category (games, movies, series, trailers)
- Direct HTTPS links to video files you have permission to use (one URL per line; MP4, MOV, M4V or WebM; up to 20 clips)
- Optional publication description and hashtags
- Optional Russian narration script with selectable male/female voice (Dmitry/Svetlana)
- Optional direct HTTPS music file only if you have the rights to use it; music is mixed quietly under narration
- Target duration (15, 22, 30, 45 or 60 seconds)

The workflow produces an MP4 (1080×1920, 30 fps), a JPG cover frame and a publication pack with title, description and hashtags. Optional Russian text-to-speech uses the free `edge-tts` package and requires internet access. The package is uploaded as a GitHub Actions artifact for 14 days.

## Important limitations
- This is an assembly studio, not a footage search engine or a TikTok uploader. You or the assistant must supply direct media-file URLs; ordinary YouTube/TikTok page URLs are not direct video files.
- Only use official press assets, public-domain/Creative Commons footage with compatible terms, or media for which you have permission. A public trailer is not automatically free to re-upload.
- Music is optional. If omitted, add a track from TikTok's in-app music library after downloading.
- The builder does not add AI-generated footage, fake engagement, or automatic posting.
- All source files are validated by FFprobe; failed or unsupported downloads stop the build rather than creating a misleading empty video.

## Output
- cinemahub-video.mp4
- cover.jpg
- publication-pack.txt
