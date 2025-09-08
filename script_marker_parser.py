# script_marker_parser.py
"""
Lightweight parser for script markers.
Markers supported:
  [SFX=name,offset]   -> sound effect named 'name' played offset seconds into that caption
  [HIT]               -> emphasis marker (useful for placing a short whoosh)

Returns a list of segments: each segment is dict with:
  { "text": str, "sfx": [(name, offset_seconds), ...], "has_hit": bool, "estimate_duration": float }

Duration estimate uses a simple words-per-second model (default 150 wpm).
"""
import re
from typing import List, Dict, Tuple

SFX_RE = re.compile(r"\[SFX=([^,\]]+)(?:,([0-9.]+))?\]")
HIT_RE = re.compile(r"\[HIT\]")

def estimate_duration_seconds(text: str, wpm: int = 150) -> float:
    # 150 wpm -> 2.5 words per second
    words = len(text.split())
    if wpm <= 0:
        wpm = 150
    words_per_sec = wpm / 60.0
    return max(0.5, words / words_per_sec)

def parse_script(script_text: str) -> List[Dict]:
    """
    script_text: multiline string, each caption on its own line (blank lines allowed).
    Returns a list of segment dicts.
    """
    segments = []
    for raw in script_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        sfxs: List[Tuple[str, float]] = []
        # extract SFX markers
        for m in SFX_RE.finditer(line):
            name = m.group(1).strip()
            offset = float(m.group(2)) if m.group(2) else 0.0
            sfxs.append((name, offset))
        has_hit = bool(HIT_RE.search(line))
        # remove markers from visible text
        clean = SFX_RE.sub("", line)
        clean = HIT_RE.sub("", clean).strip()
        dur = estimate_duration_seconds(clean)
        segments.append({"text": clean, "sfx": sfxs, "has_hit": has_hit, "estimate_duration": dur})
    return segments

if __name__ == "__main__":
    sample = """Top lifehack: Put a rubber band around a jar lid. [SFX=whoosh,0.12]
It gives you extra grip and makes opening jars easier. [HIT]"""
    print(parse_script(sample))
