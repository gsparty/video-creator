# sound_manager.py
"""
Sound manager for auto short generator.

Functions:
 - scan_and_prepare_beds()   # analyze + standardize files in assets/sounds -> assets/sounds/processed
 - select_bed_for_label(label, prefer=None) -> (bed_path, bed_vol, voice_vol)
 - mix_voice_and_bed(voice_wav, bed_path, out_mixed, target_sec, bed_vol, voice_vol, padding=1.0)

Usage (CLI):
  python sound_manager.py scan   # analyze and standardize beds
  python sound_manager.py pick sports
  python sound_manager.py mix <voice_wav> <label> <out_mixed.mp3>  (uses default target_sec based on voice)
"""

import subprocess
import shlex
import re
from pathlib import Path
import json
import sys

ASSETS_DIR = Path("assets")
SOUNDS_DIR = ASSETS_DIR / "sounds"
PROCESSED_DIR = SOUNDS_DIR / "processed"
STANDARD_SR = 44100
STANDARD_CH = 2

def _run(cmd):
    # Run and return stdout+stderr
    p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode, p.stdout

def ffprobe_volumedetect(path: Path):
    cmd = f'ffmpeg -v error -i "{path}" -af volumedetect -f null -'
    rc, out = _run(cmd)
    # parse mean_volume and max_volume
    mean = None
    maxv = None
    for line in out.splitlines():
        if "mean_volume" in line:
            m = re.search(r"mean_volume:\s*([-\d\.]+) dB", line)
            if m: mean = float(m.group(1))
        if "max_volume" in line:
            m = re.search(r"max_volume:\s*([-\d\.]+) dB", line)
            if m: maxv = float(m.group(1))
    return {"rc": rc, "out": out, "mean_volume": mean, "max_volume": maxv}

def ffprobe_duration(path: Path):
    cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{path}"'
    rc, out = _run(cmd)
    try:
        return float(out.strip())
    except:
        return None

def ensure_dirs():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def reencode_standard(in_path: Path, out_path: Path):
    # re-encode to mp3 44.1k stereo (consistent)
    cmd = (f'ffmpeg -y -i "{in_path}" -ar {STANDARD_SR} -ac {STANDARD_CH} '
           f'-b:a 192k "{out_path}"')
    rc, out = _run(cmd)
    return rc == 0, out

def normalize_to_target_max(in_path: Path, out_path: Path, target_max_db=-3.0):
    # estimate current max, then apply volume filter to reach target_max_db
    info = ffprobe_volumedetect(in_path)
    maxv = info.get("max_volume")
    if maxv is None:
        # fallback: copy
        return reencode_standard(in_path, out_path)
    delta = target_max_db - maxv
    # apply volume change in dB
    cmd = (f'ffmpeg -y -i "{in_path}" -af "volume={delta}dB" -ar {STANDARD_SR} -ac {STANDARD_CH} -b:a 192k "{out_path}"')
    rc, out = _run(cmd)
    return rc == 0, out

def scan_and_prepare_beds(target_max_db=-6.0):
    """
    Scans assets/sounds, re-encodes into assets/sounds/processed/
    and normalizes max_volume to ~target_max_db dB (not clipping).
    Produces a beds.json manifest in processed dir.
    """
    ensure_dirs()
    manifest = []
    for f in sorted(SOUNDS_DIR.glob("*")):
        if f.is_file() and f.parent == SOUNDS_DIR:
            try:
                stem = f.stem
                out = PROCESSED_DIR / f.name
                # reencode first into processed path (ensures consistent container)
                ok, msg = reencode_standard(f, out)
                if not ok:
                    print("reencode failed for", f, "->", msg)
                    continue
                info = ffprobe_volumedetect(out)
                dur = ffprobe_duration(out)
                manifest.append({
                    "orig": str(f),
                    "file": str(out),
                    "stem": stem,
                    "duration": dur,
                    "mean_volume": info.get("mean_volume"),
                    "max_volume": info.get("max_volume")
                })
                # normalize to target max if too loud/quiet
                norm_out = out.with_suffix(".norm.mp3")
                ok2, _ = normalize_to_target_max(out, norm_out, target_max_db)
                if ok2:
                    norm_info = ffprobe_volumedetect(norm_out)
                    manifest[-1].update({"normalized": str(norm_out),
                                         "normalized_max": norm_info.get("max_volume")})
                else:
                    manifest[-1].update({"normalized": None})
            except Exception as e:
                print("error processing", f, e)
    # write manifest
    manifest_path = PROCESSED_DIR / "beds_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest_path

def pick_bed_for_label(label: str, prefer=None):
    """
    Picks the best bed in processed dir matching label prefix.
    Returns (bed_path, bed_volume_factor, voice_volume_factor)
    bed_volume_factor & voice_volume_factor are floats used in ffmpeg volume= filters.
    """
    manifest_path = PROCESSED_DIR / "beds_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError("No beds manifest found. Run scan_and_prepare_beds() first.")
    import json
    manifest = json.loads(manifest_path.read_text())
    # prefer exact label files first
    label = label.lower()
    candidates = [m for m in manifest if m["stem"].lower().startswith(label + "__")]
    if not candidates:
        # fallback: look for any file with label in name
        candidates = [m for m in manifest if label in m["stem"].lower()]
    if not candidates:
        # fallback to neutral
        candidates = [m for m in manifest if m["stem"].lower().startswith("neutral__")]
    if not candidates and manifest:
        candidates = [manifest[0]]
    if not candidates:
        return None, 0.2, 1.0
    # choose longest normalized candidate
    candidates = [c for c in candidates if c.get("normalized")]
    if not candidates:
        c = manifest[0]
        return Path(c["file"]), 0.2, 1.0
    c = max(candidates, key=lambda x: (x.get("duration") or 0))
    bed_path = Path(c.get("normalized") or c.get("file"))
    # default volumes: bed quieter than voice
    # If bed is very soft (max < -30dB) raise bed_vol
    maxv = c.get("normalized_max") or c.get("max_volume") or -40
    bed_vol = 0.18
    if maxv < -30:
        bed_vol = 0.45
    if "stadium" in c["stem"].lower():
        bed_vol = 0.18
    voice_vol = 1.0
    return bed_path, bed_vol, voice_vol

def mix_voice_and_bed(voice_wav: Path, bed_path: Path, out_mixed: Path,
                      target_sec: float = None, bed_vol: float = 0.18, voice_vol: float = 1.0, padding=1.0):
    """
    Mixes voice WAV with bed (loops bed if needed) -> out_mixed mp3
    target_sec: final desired duration (if None, use voice duration + padding)
    Returns True on success.
    """
    voice_dur = ffprobe_duration(voice_wav)
    if voice_dur is None:
        raise RuntimeError("Cannot determine voice duration for " + str(voice_wav))
    if target_sec is None:
        target = voice_dur + padding
    else:
        target = target_sec

    # Use stream_loop for bed and amix; we create an intermediate bed_looped.mp3 trimmed to target
    looped_bed = PROCESSED_DIR / (bed_path.stem + ".looped.mp3")
    cmd_loop = f'ffmpeg -y -stream_loop -1 -i "{bed_path}" -t {target} -ar {STANDARD_SR} -ac {STANDARD_CH} -b:a 192k "{looped_bed}"'
    rc, out = _run(cmd_loop)
    if rc != 0:
        print("looping bed failed:", out)
        return False

    # mix voice + bed with volumes
    # voice first input, bed second input
    # use amix to combine (duration=first so voice duration controls)
    out_mixed_tmp = out_mixed.with_suffix(".tmp.mp3")
    cmd_mix = (f'ffmpeg -y -i "{voice_wav}" -i "{looped_bed}" -filter_complex '
               f'"[0:a]volume={voice_vol}[voice];[1:a]volume={bed_vol}[bed];'
               f'[voice][bed]amix=inputs=2:duration=first:dropout_transition=2[aout]" '
               f'-map "[aout]" -t {target} -ar {STANDARD_SR} -ac {STANDARD_CH} -b:a 192k "{out_mixed_tmp}"')
    rc, out = _run(cmd_mix)
    if rc != 0:
        print("mix failed:", out)
        return False

    # final pass normalize loudness to target LUFS (-14) optionally:
    final = out_mixed
    cmd_norm = f'ffmpeg -y -i "{out_mixed_tmp}" -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar {STANDARD_SR} -ac {STANDARD_CH} -b:a 192k "{final}"'
    rc, out = _run(cmd_norm)
    if rc != 0:
        print("final normalize failed:", out)
        # fallback to tmp
        out_mixed_tmp.replace(final)
    return True

# CLI support
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: sound_manager.py scan | pick <label> | mix <voice_wav> <label> <out_mixed.mp3>")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "scan":
        p = scan_and_prepare_beds()
        print("manifest at", p)
    elif cmd == "pick":
        label = sys.argv[2] if len(sys.argv) > 2 else "neutral"
        bed_path, bed_vol, voice_vol = pick_bed_for_label(label)
        print("picked:", bed_path, bed_vol, voice_vol)
    elif cmd == "mix":
        if len(sys.argv) < 5:
            print("mix requires: mix <voice_wav> <label> <out_mixed.mp3>")
            sys.exit(2)
        voice = Path(sys.argv[2])
        label = sys.argv[3]
        outp = Path(sys.argv[4])
        bed, bed_vol, voice_vol = pick_bed_for_label(label)
        print("mixing with:", bed, bed_vol, voice_vol)
        ok = mix_voice_and_bed(voice, bed, outp, bed_vol=bed_vol, voice_vol=voice_vol)
        print("ok:", ok)
    else:
        print("unknown command", cmd)