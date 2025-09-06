# sound_selector.py
"""
Select best bed and sfx files from assets/sounds.
Functions:
  - select_bed(label, target_sec) -> Path | None
  - select_sfx(label, max_count=3) -> list[Path]
Utility: uses ffprobe and ffmpeg volumedetect to compute duration/mean dB.
"""
from pathlib import Path
import subprocess
import re
from typing import Optional, List

ROOT = Path.cwd()
SOUNDS_DIR = ROOT / "assets" / "sounds"

def _ffprobe_duration(path: Path) -> Optional[float]:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return None
    try:
        return float(p.stdout.strip())
    except Exception:
        return None

def _volumedetect_mean_db(path: Path) -> Optional[float]:
    # runs volumedetect, returns mean_volume in dB if found
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = p.stderr or p.stdout or ""
    m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", out)
    if m:
        try:
            return float(m.group(1))
        except:
            return None
    return None

def _list_candidates(label: str, subfolder_names=("beds",)):
    paths = []
    label_dir = SOUNDS_DIR / label
    if not label_dir.exists():
        return []
    # check nested subfolders first
    for sub in subfolder_names:
        d = label_dir / sub
        if d.exists():
            for f in d.glob("*.mp3"):
                paths.append(f)
    # fallback: scan label_dir root mp3s
    for f in label_dir.glob("*.mp3"):
        paths.append(f)
    # dedupe
    seen = set()
    res = []
    for p in paths:
        if p.exists() and p not in seen:
            res.append(p)
            seen.add(p)
    return res

def select_bed(label: str, target_sec: int = 25,
               min_duration_ratio=0.5,
               prefer_mean_db_range=(-35, -8)) -> Optional[Path]:
    """
    Select a bed (long background) for a label.
    Strategy:
      - look in assets/sounds/<label>/beds/*.mp3 and assets/sounds/<label>/*.mp3
      - prefer duration >= target_sec*min_duration_ratio
      - prefer mean_volume inside prefer_mean_db_range (dB)
      - fallback to longest candidate
    """
    cand = _list_candidates(label, subfolder_names=("beds",))
    if not cand:
        return None
    scored = []
    for p in cand:
        dur = _ffprobe_duration(p) or 0.0
        mean_db = _volumedetect_mean_db(p)
        # score: prefer near target length and mean_db in range
        length_score = -abs(dur - target_sec)
        db_score = 0
        if mean_db is not None:
            low, high = prefer_mean_db_range
            if low <= mean_db <= high:
                db_score = 20  # preferred loudness
            else:
                db_score = -abs((mean_db - (low+high)/2))
        scored.append((length_score + db_score, p, dur, mean_db))
    # sort descending by score
    scored.sort(key=lambda x: x[0], reverse=True)
    # choose first candidate that's not too tiny
    for score, p, dur, mean_db in scored:
        if dur >= max(2.0, target_sec * min_duration_ratio):
            return p
    # fallback to longest one
    longest = max(scored, key=lambda x: x[2])
    return longest[1] if longest else None

def select_sfx(label: str, max_count: int = 4, max_duration=3.0) -> List[Path]:
    """
    Pick up to max_count short SFX from assets/sounds/<label>/sfx or label root.
    """
    sfx_dir = SOUNDS_DIR / label / "sfx"
    candidates = []
    if sfx_dir.exists():
        candidates.extend(sorted(sfx_dir.glob("*.mp3")))
    # fallback to any short files in label folder
    label_dir = SOUNDS_DIR / label
    if label_dir.exists():
        candidates.extend([p for p in label_dir.glob("*.mp3") if "bed" not in p.name.lower() and p not in candidates])
    chosen = []
    for p in candidates:
        dur = _ffprobe_duration(p) or 9999.0
        if dur <= max_duration:
            chosen.append((dur, p))
        if len(chosen) >= max_count:
            break
    # sort by duration ascending (shorter first)
    chosen.sort(key=lambda x: x[0])
    return [p for _, p in chosen]
