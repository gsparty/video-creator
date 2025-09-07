

import hashlib
from pathlib import Path
from tempfile import gettempdir

import numpy as np
from moviepy.editor import ImageClip
from PIL import Image, ImageDraw, ImageFont

# text_overlay.py â€” file-backed overlay generator (half-res -> cached PNG -> ImageClip)

FONT_PATHS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    r"C:\Windows\Fonts\Tahoma.ttf",
]

def _load_font(size):
    for fp in FONT_PATHS:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()

def _wrap_lines(draw, text, font, max_w):
    words = text.split()
    lines = []
    line = ""
    for w in words:
        cand = (line + " " + w).strip()
        if draw.textlength(cand, font=font) <= max_w:
            line = cand
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines

def _overlay_cache_path(headline, size, bg_box):
    key = f"{headline}|{size[0]}x{size[1]}|{int(bg_box)}"
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()
    tmpdir = Path(gettempdir()) / "auto_video_overlays"
    tmpdir.mkdir(parents=True, exist_ok=True)
    return tmpdir / f"{h}.png"

def make_text_clip(text, fontsize=64, color="white", size=(1080,1920), align="center", duration=5, bg_box=True):
    """
    Render text to a small PNG (half-resolution) and return a MoviePy ImageClip created from the file.
    Avoids large in-memory numpy arrays and caches identical overlays.
    """

    w, h = int(size[0]), int(size[1])
    hw, hh = max(1, w // 2), max(1, h // 2)

    outpath = _overlay_cache_path(text, (w,h), bg_box)
    if outpath.exists():
        return ImageClip(str(outpath)).set_duration(duration).resize(newsize=(w,h))

    font = _load_font(max(8, int(fontsize // 2)))
    img = Image.new("RGBA", (hw, hh), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    max_text_w = int(hw * 0.9)
    lines = _wrap_lines(draw, text, font, max_text_w)

    try:
        line_h = font.size + int(font.size * 0.3)
    except Exception:
        line_h = int(hh * 0.05)
    total_h = line_h * len(lines)
    y = max(0, (hh - total_h) // 2)

    if bg_box and lines:
        max_w_line = max(int(draw.textlength(ln, font=font)) for ln in lines)
        pad_x = max(8, int(hw * 0.03))
        pad_y = max(4, int(line_h * 0.4))
        box_w = max_w_line + pad_x * 2
        box_h = total_h + pad_y * 2
        box_x = max(0, (hw - box_w) // 2)
        box_y = max(0, y - pad_y)
        draw.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], fill=(0,0,0,200))

    for ln in lines:
        line_w = int(draw.textlength(ln, font=font))
        x = max(0, (hw - line_w) // 2)
        draw.text((x, y), ln, font=font, fill=color)
        y += line_h

    arr = np.array(img).astype(np.uint8)
    Image.fromarray(arr).save(outpath, format="PNG")

    return ImageClip(str(outpath)).set_duration(duration).resize(newsize=(w,h))

