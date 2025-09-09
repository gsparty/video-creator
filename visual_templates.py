# visual_templates.py
"""
PIL-backed visual templates for short clips.
Renders text to images with Pillow (uses ImageDraw.textbbox for measurement).
Returns MoviePy ImageClip objects so MoviePy does not require ImageMagick/TextClip.
"""

from typing import Tuple
from moviepy.editor import ImageClip
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import textwrap
import os

# Typical font locations; adjust if you want a custom font path
DEFAULT_FONT_PATHS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
]

def _get_font(fontsize: int):
    # Try common font files. Fall back to load_default() if none present.
    for p in DEFAULT_FONT_PATHS:
        try:
            if os.path.exists(p):
                return ImageFont.truetype(p, size=fontsize)
        except Exception:
            continue
    return ImageFont.load_default()

def _render_text_image(text: str, size: Tuple[int, int], fontsize: int, bg_color=(0, 0, 0)):
    w, h = size
    img = Image.new("RGB", (w, h), color=bg_color)
    draw = ImageDraw.Draw(img)
    font = _get_font(fontsize)

    # Wrap to roughly 82% of width in characters
    max_line_px = int(w * 0.82)

    # Estimate average char width using textbbox on single char
    try:
        x0, y0, x1, y1 = draw.textbbox((0, 0), "X", font=font)
        avg_char_w = max(1, x1 - x0)
    except Exception:
        avg_char_w = max(6, fontsize // 2)

    chars_per_line = max(10, max_line_px // avg_char_w)

    # Split into wrapped lines while preserving existing paragraph breaks
    lines = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")  # preserve blank line
            continue
        wrapped = textwrap.fill(paragraph, width=chars_per_line)
        lines.extend(wrapped.splitlines())

    # Determine line height using textbbox (robust)
    try:
        bx0, by0, bx1, by1 = draw.textbbox((0, 0), "Ay", font=font)
        line_h = (by1 - by0) + 6
    except Exception:
        line_h = fontsize + 8

    text_h = line_h * len(lines)
    y_start = max(10, (h - text_h) // 2)

    # Render each line centered horizontally
    for i, line in enumerate(lines):
        if line == "":
            # skip drawing but preserve vertical space
            continue
        try:
            lx0, ly0, lx1, ly1 = draw.textbbox((0, 0), line, font=font)
            line_w = lx1 - lx0
        except Exception:
            line_w = len(line) * avg_char_w
        x = int((w - line_w) // 2)
        y = int(y_start + i * line_h)
        draw.text((x, y), line, font=font, fill=(255, 255, 255))

    return img

def make_text_slide(text: str, duration: float = 3.0, size: Tuple[int, int] = (1280, 720), fontsize: int = 64, bg_color=(0,0,0)):
    """
    Standard text slide: centered, wrapped, white-on-dark.
    Returns a MoviePy ImageClip set to the requested duration.
    """
    img = _render_text_image(text, size, fontsize, bg_color)
    clip = ImageClip(np.array(img)).set_duration(duration)
    return clip

def make_pop_text(text: str, duration: float = 2.2, size: Tuple[int, int] = (1280, 720), fontsize: int = 72, bg_color=(0,0,0)):
    """
    Pop text: same rendering, but adds a simple resize "pop" effect.
    """
    img = _render_text_image(text, size, fontsize, bg_color)
    clip = ImageClip(np.array(img)).set_duration(duration)
    # gentle pop (MoviePy will interpolate)
    clip = clip.resize(lambda t: 0.8 + 0.2 * min(1, t / 0.12))
    return clip

