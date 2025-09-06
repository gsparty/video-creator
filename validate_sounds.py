# validate_sounds.py
"""
Scan assets/sounds/<label> and verify files are valid audio.
Deletes any file that is clearly broken (size too small or ffprobe can't read).
Prints volumedetect output for each valid file for debugging.
Usage:
    python validate_sounds.py
"""
import subprocess
from pathlib import Path

ROOT = Path.cwd()
SOUNDS_DIR = ROOT / "assets" / "sounds"

def ffprobe_info(path: Path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def volumedetect(path: Path):
    # capture stderr where volumedetect outputs
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    # volumedetect outputs on stderr
    return p.returncode, p.stdout.strip(), p.stderr.strip()

def validate_all():
    if not SOUNDS_DIR.exists():
        print("No sounds dir:", SOUNDS_DIR)
        return
    for label_dir in sorted(SOUNDS_DIR.iterdir()):
        if not label_dir.is_dir():
            continue
        print("===", label_dir.name, "===")
        for f in sorted(label_dir.glob("*.*")):
            size = f.stat().st_size
            print(f.name, "size:", size)
            if size < 2048:
                print("  -> too small, deleting", f)
                try:
                    f.unlink()
                except Exception as e:
                    print("   unlink failed:", e)
                continue
            rc, out, err = ffprobe_info(f)
            if rc != 0 or (not out and not err):
                print("  -> ffprobe failed or returned nothing. stderr:", err[:200])
                print("  -> deleting", f)
                try:
                    f.unlink()
                except Exception as e:
                    print("   unlink failed:", e)
                continue
            print("  duration (s):", out)
            # run volumedetect (may print to stderr)
            rc2, out2, err2 = volumedetect(f)
            combined = (err2 or out2).strip()
            if "mean_volume" in combined:
                # parse mean_volume
                import re
                m = re.search(r"mean_volume:\s*(-?\d+(\.\d+)?)\s*dB", combined)
                mval = float(m.group(1)) if m else None
                print("  mean_volume (dB):", mval)
            else:
                print("  volumedetect produced no mean_volume; ffmpeg output snippet:")
                print(combined[:1000])  # print first chunk for debugging
            print("")

if __name__ == "__main__":
    validate_all()
