# audio_mixer.py
"""
Simple audio mixer utilities using pydub.
Expect ffmpeg available on the machine running this.
"""
from pydub import AudioSegment
from typing import List, Tuple
import os

def normalize(seg: AudioSegment, target_dbfs=-20.0) -> AudioSegment:
    change = target_dbfs - seg.dBFS
    return seg.apply_gain(change)

def duck_and_mix(tts_path: str, sfx_items: List[Tuple[str, float]], out_path="final_mix.wav"):
    """
    Mix TTS (speech) and SFX into a single WAV.

    sfx_items: list of tuples (sfx_path, start_time_seconds)
    Simple ducking policy: lower SFX by ~10dB when overlaying on speech.
    """
    if not os.path.exists(tts_path):
        raise FileNotFoundError(f"TTS file not found: {tts_path}")

    tts = AudioSegment.from_file(tts_path)
    tts = normalize(tts, -20.0)
    length_ms = len(tts)
    out = AudioSegment.silent(duration=length_ms)
    # overlay speech first
    out = out.overlay(tts)

    for sfx_path, start_sec in sfx_items:
        if not os.path.exists(sfx_path):
            # skip missing SFX files
            continue
        sfx = AudioSegment.from_file(sfx_path)
        sfx = normalize(sfx, -12.0)
        # basic duck: reduce by 10 dB to keep speech clear
        ducked = sfx - 10.0
        start_ms = int(start_sec * 1000)
        out = out.overlay(ducked, position=start_ms)

    out.export(out_path, format="wav")
    return out_path
