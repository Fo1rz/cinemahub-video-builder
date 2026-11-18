# CinemaHub Video Builder

Free GitHub Actions workflow to assemble a vertical GTA VI fan edit from Rockstar Games' official media archive using FFmpeg (no generative AI).

## Run

Open **Actions → Build GTA VI TikTok → Run workflow**. The MP4 is uploaded as an artifact named `cinemahub-gta6-video`.

The workflow discovers the official downloadable ZIP from Rockstar's GTA VI media page. It stops if the archive cannot be downloaded or contains no usable footage; it never substitutes placeholder clips.

**Music:** To avoid copyright claims, the first build leaves the audio track out. Add a track licensed for reuse as `assets/music.mp3`, or add a sound from TikTok's own music library after downloading the MP4.

Use the edit in accordance with Rockstar's fan-content policy and TikTok's copyright rules.
