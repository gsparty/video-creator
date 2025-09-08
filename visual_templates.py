# visual_templates.py
"""
Small MoviePy helpers for simple on-screen text animations.
These produce short clips (fit for concatenation).
"""
from moviepy.editor import TextClip, CompositeVideoClip, ColorClip
from moviepy.video.fx.all import fadein, fadeout
from typing import Tuple

def make_text_slide(text: str, duration: float = 3.0, size: Tuple[int, int] = (1280, 720), fontsize: int = 64, bg_color=(0,0,0)):
    w, h = size
    bg = ColorClip((w, h), color=bg_color).set_duration(duration)
    txt = TextClip(text, fontsize=fontsize, color="white", font="Arial", method="caption", size=(int(w*0.9), None)).set_duration(duration)
    txt = txt.set_pos(("center", "center"))
    return CompositeVideoClip([bg, txt]).set_duration(duration)

def make_pop_text(text: str, duration: float = 2.2, size: Tuple[int, int] = (1280, 720), fontsize: int = 72, bg_color=(0,0,0)):
    w, h = size
    bg = ColorClip((w, h), color=bg_color).set_duration(duration)
    txt = TextClip(text, fontsize=fontsize, color="white", font="Arial", method="caption", size=(int(w*0.9), None)).set_duration(duration)
    txt = txt.resize(lambda t: 0.7 + 0.3 * min(1, t / 0.2)).set_pos("center")
    txt = fadein(txt, 0.08).fx(fadeout, 0.08)
    return CompositeVideoClip([bg, txt]).set_duration(duration)
