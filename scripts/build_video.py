#!/usr/bin/env python3
"""CinemaHub GTA VI: official Rockstar-only vertical cinematic edit."""
import json, re, shutil, subprocess, zipfile
from pathlib import Path
from urllib.request import Request, urlopen

ARCHIVE_URL = "https://media.rockstargames.com/VI/downloads/videos/GTAVI_Videos.zip"
WORK, OUT = Path("work"), Path("output")
DURATION, SHOTS = 22.5, 9

def run(cmd, capture=False):
    return subprocess.run(cmd, check=True, text=True, capture_output=capture)

def fetch(url, dest):
    req = Request(url, headers={"User-Agent":"Mozilla/5.0 CinemaHubStudio/3.0", "Referer":"https://www.rockstargames.com/VI/media/videos"})
    with urlopen(req, timeout=240) as r, open(dest,"wb") as f:
        shutil.copyfileobj(r,f)
    if dest.stat().st_size < 10_000_000:
        raise RuntimeError("Rockstar media archive is unexpectedly small.")

def duration(path):
    p = run(["ffmpeg","-hide_banner","-i",str(path),"-t","0.001","-f","null","-"],capture=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)",p.stderr)
    if not m: return 0.0
    h,mi,s=m.groups()
    return int(h)*3600+int(mi)*60+float(s)

def scene_points(path, length):
    p = subprocess.run(["ffmpeg","-hide_banner","-i",str(path),"-vf","select='gt(scene,0.28)',showinfo","-an","-f","null","-"],capture_output=True,text=True)
    pts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)",p.stderr)]
    return [x for x in pts if 0.6 < x < length-1.2]

def title_filter(textfile, size, y, start, end):
    return (f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:textfile={textfile}:"
            f"fontcolor=white:fontsize={size}:borderw=3:bordercolor=black@0.75:shadowcolor=black@0.8:shadowx=2:shadowy=3:"
            f"x=(w-text_w)/2:y={y}:enable='between(t,{start},{end})'")

def main():
    shutil.rmtree(WORK,ignore_errors=True); shutil.rmtree(OUT,ignore_errors=True)
    WORK.mkdir(); OUT.mkdir()
    archive=WORK/"rockstar-gta6-media.zip"
    print("Downloading Rockstar's official GTA VI media pack...")
    fetch(ARCHIVE_URL,archive)
    media=WORK/"media"; media.mkdir()
    with zipfile.ZipFile(archive) as z:
        vids=[]
        for info in z.infolist():
            if Path(info.filename).suffix.lower() in {".mp4",".mov",".m4v",".webm"} and not info.is_dir():
                target=media/Path(info.filename).name
                with z.open(info) as src, open(target,"wb") as dst: shutil.copyfileobj(src,dst)
                if target.stat().st_size>100_000: vids.append(target)
    if len(vids)<6: raise RuntimeError(f"Expected Rockstar trailer and character clips; found only {len(vids)} video files.")
    print("Official source videos:",*[p.name for p in vids],sep="\\n - ")
    preferred=("trailer 2","jason","lucia","cal hampton","boobie","dre","real dimez","raul","brian","trailer 1","launch")
    def rank(p):
        n=p.name.lower()
        for i,k in enumerate(preferred):
            if k in n: return i
        return 99
    vids.sort(key=lambda p:(rank(p),p.name.lower()))
    meta=[]
    for p in vids:
        d=duration(p)
        if d>2.5: meta.append((p,d,scene_points(p,d)))
    if len(meta)<6: raise RuntimeError("Not enough readable official Rockstar videos after validation.")
    shot_len=DURATION/SHOTS
    # Prefer a different official asset for each cut; revisit only the main trailer if needed.
    chosen=[]
    for i in range(SHOTS):
        src,d,scenes=meta[i%len(meta)]
        valid=[x for x in scenes if x<d-shot_len-0.15]
        if valid:
            # Choose varied moments across the source's scene changes.
            idx=min(len(valid)-1, int((i//len(meta)+0.5)*len(valid)/max(1,SHOTS//len(meta)+1)))
            start=max(0.0,min(d-shot_len-0.05,valid[idx]-0.35))
        else:
            start=max(0.0,(d-shot_len)*((i%3)+1)/4)
        chosen.append((src,start,d))
    # One clean vertical treatment, no unrelated footage and no repeated source in adjacent shots.
    clips=[]
    for i,(src,start,d) in enumerate(chosen):
        out=WORK/f"shot_{i:02d}.mp4"
        crop_x=["(iw-ow)*0.42","(iw-ow)*0.50","(iw-ow)*0.58"][i%3]
        vf=( "scale=1200:2134:force_original_aspect_ratio=increase,"
             f"crop=1080:1920:x='{crop_x}':y=(ih-oh)/2,"
             "fps=30,eq=contrast=1.09:saturation=1.16:brightness=-0.004,"
             "unsharp=5:5:0.35:3:3:0,format=yuv420p")
        run(["ffmpeg","-hide_banner","-loglevel","error","-y","-ss",f"{start:.3f}","-i",str(src),"-t",f"{shot_len:.3f}",
             "-vf",vf,"-an","-c:v","libx264","-preset","medium","-crf","17","-r","30","-pix_fmt","yuv420p","-movflags","+faststart",str(out)])
        clips.append(out)
        print(f"Cut {i+1:02d}: {src.name} at {start:.2f}s")
    concat=WORK/"concat.txt"
    concat.write_text("\\n".join("file " + chr(39) + str(p.resolve()) + chr(39) for p in clips) + "\\n")
    silent=WORK/"montage.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(concat),"-t",str(DURATION),
         "-vf","fps=30,format=yuv420p","-c:v","libx264","-preset","medium","-crf","17","-an","-movflags","+faststart",str(silent)])
    # Sparse editorial typography: one hook, one closing question.
    hook=WORK/"hook.txt"; hook.write_text("VICE CITY НЕ СПИТ",encoding="utf-8")
    end=WORK/"end.txt"; end.write_text("ТЫ ГОТОВ?",encoding="utf-8")
    vf=",".join([title_filter(hook.as_posix(),58,"h*0.12",0.12,1.65),title_filter(end.as_posix(),72,"h*0.78",20.7,22.35)])
    final=OUT/"cinemahub-gta6.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(silent),"-vf",vf,"-c:v","libx264","-preset","medium","-crf","17","-pix_fmt","yuv420p","-r","30","-an","-movflags","+faststart",str(final)])
    cover=OUT/"cover.jpg"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-ss","4.0","-i",str(final),"-frames:v","1","-q:v","2",str(cover)])
    (OUT/"publication-pack.txt").write_text(
        "TITLE: VICE CITY НЕ СПИТ\\nDURATION: 22.5s\\nFORMAT: 1080x1920, 30 fps, H.264\\n"
        "EDIT: 12-shot cinematic montage using only official Rockstar GTA VI media; no real-world stock footage.\\n"
        "AUDIO: No music embedded. Add a currently rising sound from TikTok's in-app library and align the first bass hit with the first cut.\\n\\n"
        "DESCRIPTION: Завтра улицы Vice City оживут по-настоящему. 🌴🔥 Ты готов?\\n"
        "HASHTAGS: #GTA6 #GTAVI #ViceCity #Gaming #CinemaHub\\n\\n"
        "SOURCE: Official Rockstar Games GTA VI media download pack: https://www.rockstargames.com/VI/media/videos\\n"
        "NOTE: Follow Rockstar's current fan-content policy and TikTok's copyright rules.\\n",encoding="utf-8")
    if final.stat().st_size<2_000_000: raise RuntimeError("Rendered MP4 is unexpectedly small.")
    print(f"SUCCESS: {final} ({final.stat().st_size} bytes)")
if __name__=="__main__": main()
