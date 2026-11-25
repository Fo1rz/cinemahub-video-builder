"""Motion and scene-change ranked gameplay highlight selector."""
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
        diffs = np.abs(np.diff(frames, axis=0)).mean(axis=(1,2))
        brightness = frames.mean(axis=(1,2))
        contrast = frames.std(axis=(1,2))
        # fps=2 means one sampled frame every 0.5 seconds.
        step = 0.5
        win = max(4, int(round(seg_len / step)) + 1)
        max_offset = max(0.0, source_length - seg_len - 0.05)
        last_start = min(count-win, int(max_offset / step))
        for start in range(0, max(0, last_start)+1, 2):
            end = min(count-1, start+win-1)
            if end-start < 2:
                continue
            offset = start * step
            if offset + seg_len > source_length + 0.02:
                continue
            motion = float(diffs[start:end].mean())
            light = float(brightness[start:end+1].mean())
            detail = float(contrast[start:end+1].mean())
            # Skip dark/flat screens and near-static traversal.
            if light < 22 or detail < 12 or motion < 2.5:
                continue
            # Motion + scene transitions + image detail. Avoid simply rewarding shaky camera.
            peak = float(np.percentile(diffs[start:end], 85))
            score = motion * 0.72 + peak * 0.18 + min(detail, 55)*0.10
            candidates.append((score, source_index, offset, seg_len))
    if not candidates:
        raise RuntimeError("No usable dynamic gameplay moments found in the source recordings.")
    candidates.sort(reverse=True)
    wanted = max(1, int(round(duration / seg_len)))
    chosen = []
    # Spread picks over the source timeline and across recordings.
    for gap in (max(3.5, seg_len*1.8), 2.0, 0.75, 0.0):
        for score, si, offset, length in candidates:
            if len(chosen) >= wanted:
                break
            if any(si == c[1] and abs(offset-c[2]) < gap for c in chosen):
                continue
            chosen.append((score,si,offset,length))
        if len(chosen) >= wanted:
            break
    if len(chosen) < wanted:
        raise RuntimeError(f"Only {len(chosen)} usable highlights found; refusing to pad the edit with weak/repeated footage.")
    # Highest-scoring moment opens, then maintain a varied sequence of clips.
    chosen.sort(key=lambda x: x[0], reverse=True)
    return [(sources[si][0], offset, length) for _,si,offset,length in chosen[:wanted]]
