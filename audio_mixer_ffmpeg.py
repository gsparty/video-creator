# audio_mixer_ffmpeg.py
"""
FFmpeg-backed audio mixer. Does ducking by reducing SFX volume when mixing.
Requires ffmpeg available on PATH.
"""
import shutil
import subprocess
import os
from typing import List, Tuple

def _ffmpeg_exists() -> bool:
    return shutil.which("ffmpeg") is not None

def duck_and_mix(tts_path: str, sfx_items: List[Tuple[str, float]], out_path="final_mix.wav"):
    """
    Mix TTS (speech) and sfx using ffmpeg.
    sfx_items: list of (sfx_path, start_seconds)
    Produces out_path as PCM WAV (pcm_s16le).
    """
    if not os.path.exists(tts_path):
        raise FileNotFoundError(f"TTS file not found: {tts_path}")
    if not _ffmpeg_exists():
        raise RuntimeError("ffmpeg not found on PATH. Install ffmpeg and ensure it's on PATH.")

    inputs = ["-y", "-i", tts_path]
    # add inputs for each sfx
    for sfx, _ in sfx_items:
        inputs += ["-i", sfx]

    # Build filter_complex:
    # For each sfx input index i (starting at 1), make an adelay and small volume
    parts = []
    sfx_labels = []
    for idx, (_, offset) in enumerate(sfx_items, start=1):
        # convert seconds -> ms
        ms = int(offset * 1000)
        label = f"[s{idx}]"
        sfx_labels.append(label)
        # adelay: need to specify per-channel delays; use 0|0 which works for mono/stereo typical files
        # volume reduce e.g. 0.25 (roughly -12 dB)
        parts.append(f"[{idx}:a]adelay={ms}|{ms},volume=0.25{label}")

    # base speech label is [0:a]
    # combine all streams into amix: inputs = 1 + len(sfx_items)
    amix_inputs = 1 + len(sfx_items)
    # prepare list of inputs to amix: [0:a][s1][s2]... -> then amix
    mix_chain = "[0:a]" + "".join(sfx_labels) + f"amix=inputs={amix_inputs}:duration=longest:dropout_transition=0[mixout]"

    filter_complex = ";".join(parts + [mix_chain]) if parts else f"[0:a]anull[mixout]"

    cmd = ["ffmpeg"] + inputs + ["-filter_complex", filter_complex, "-map", "[mixout]", "-c:a", "pcm_s16le", out_path]

    # Run ffmpeg
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg mixing failed: {proc.stderr.decode(errors='replace')}")
    return out_path
