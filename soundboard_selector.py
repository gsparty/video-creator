# soundboard_selector.py
"""
Select a soundbed based on a simple label or topic heuristics.
Place your sound files in assets/sounds/, e.g.:
  assets/sounds/stadium_cheer_loop.mp3
  assets/sounds/news_sizzle_loop.mp3
  assets/sounds/dramatic_pulse_loop.mp3
  assets/sounds/calm_ambient_loop.mp3
"""

import random
from pathlib import Path

SOUNDS_DIR = Path("assets") / "sounds"

SOUND_MAP = {
    "sports": ["stadium_cheer_loop.mp3", "stadium_ambience.mp3"],
    "politics": ["news_sizzle_loop.mp3", "corporate_loop.mp3"],
    "tech": ["tech_pulse_loop.mp3", "calm_ambient_loop.mp3"],
    "entertainment": ["pop_bed_loop.mp3", "dramatic_pulse_loop.mp3"],
    "default": ["calm_ambient_loop.mp3"],
}


def select_bed_for_label(label: str):
    label = (label or "").lower()
    chosen_list = SOUND_MAP.get(label, SOUND_MAP.get("default"))
    for filename in chosen_list:
        path = SOUNDS_DIR / filename
        if path.exists():
            return str(path)
    # fallback: pick any mp3 in folder
    if SOUNDS_DIR.exists():
        mp3s = list(SOUNDS_DIR.glob("*.mp3"))
        if mp3s:
            return str(random.choice(mp3s))
    return None


if __name__ == "__main__":
    for lbl in ["sports", "politics", "tech", "entertainment", "weird"]:
        print(lbl, "->", select_bed_for_label(lbl))
