"""Motion-ranked highlight selection for raw gameplay recordings."""
import subprocess
import numpy as np

def select_segments(sources, duration, seg_len):
    candidates = []
    for source_index, (src, source_length) in enumerate(sources):
        cmd = ["ffmpeg","-hide_banner","-loglevel","error","-i",str(src),
               "-vf","fps=2,scale=128:72:flags=fast_bilinear,format=gray",
               "-f","rawvideo","-pix_fmt","gray","pipe:1"]
        raw = subprocess.run(cmd, check=True, stdout=subprocess.PIPE).stdout
        frame_size = 128 * 72
        count = len(raw) // frame_size
        if count < 4:
            continue
        frames = np.frombuffer(raw[:count*frame_size], dtype=np.uint8).reshape(count,72,128).astype(np.int16)
        # Motion energy between adjacent frames, plus a small detail/contrast bonus.
        diffs = np.abs(np.diff(frames, axis=0)).mean(axis=(1,2))
        brightness = frames.mean(axis=(1,2))
        contrast = frames.std(axis=(1,2))
        step = 2.0
        win = max(3, int(round(seg_len / step)) + 1)
        for start in range(0, max(1, count-win+1), 2):
            end = min(count-1, start+win-1)
            if end-start < 2:
                continue
            motion = float(diffs[start:end].mean())
            light = float(brightness[start:end+1].mean())
            detail = float(contrast[start:end+1].mean())
            if light < 22 or detail < 12:
                continue
            # Avoid dead/static footage; motion dominates, detail prevents muddy frames.
            score = motion + min(detail, 55)*0.10
            candidates.append((score, source_index, start*step, min(seg_len, source_length-start*step)))
    if not candidates:
        raise RuntimeError("Could not find usable moving gameplay highlights in the source videos.")
    # Greedy quality-first selection with temporal spacing to prevent repeated nearby frames.
    candidates.sort(reverse=True)
    wanted = max(1, int(round(duration / seg_len)))
    chosen = []
    min_gap = max(3.5, seg_len*1.8)
    for gap in (min_gap, 2.0, 0.0):
        for score, si, offset, length in candidates:
            if len(chosen) >= wanted:
                break
            if any(si == c[1] and abs(offset-c[2]) < gap for c in chosen):
                continue
            chosen.append((score,si,offset,length))
        if len(chosen) >= wanted:
            break
    if len(chosen) < wanted:
        # Reuse only as a last resort, and never pad with a single repeated excerpt.
        for item in candidates:
            chosen.append(item)
            if len(chosen) >= wanted:
                break
    # Strongest moment opens; remaining clips are interleaved across source files.
    chosen.sort(key=lambda x: x[0], reverse=True)
    result = [(sources[si][0], offset, length) for _,si,offset,length in chosen[:wanted]]
    return result
