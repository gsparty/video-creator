# soundboard_map.py
# Map classifier labels to soundbed filenames and default volumes.
# Add your actual loops into assets/sounds/ with the names below.

from pathlib import Path

ASSETS_SOUNDS = Path("assets") / "sounds"

# Each entry: "label": ("filename.mp3", bed_volume (0..1), voice_volume (0..1))
# bed_volume is relative volume for the loop, voice_volume is applied to the voice track
DEFAULT_MAP = {
    "sports": ("stadium_cheer_loop.mp3", 0.20, 1.0),
    "music": ("pop_bed_loop.mp3", 0.25, 1.0),
    "tech": ("synth_loop.mp3", 0.18, 1.0),
    "politics": ("newsbed_loop.mp3", 0.15, 1.0),
    "celebrity": ("glam_loop.mp3", 0.20, 1.0),
    "lifestyle": ("acoustic_loop.mp3", 0.16, 1.0),
    "other": ("neutral_bg.mp3", 0.10, 1.0),
}

def get_soundbed_for_label(label: str):
    """
    Return (full_path:Path, bed_vol:float, voice_vol:float).
    Falls back to 'other' entry.
    """
    if not label:
        label = "other"
    entry = DEFAULT_MAP.get(label, DEFAULT_MAP.get("other"))
    filename, bed_v, voice_v = entry
    path = ASSETS_SOUNDS / filename
    return path, float(bed_v), float(voice_v)
