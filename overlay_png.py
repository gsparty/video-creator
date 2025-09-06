# overlay_png.py
# Usage: python overlay_png.py "Headline text" out.png width height fontsize
from PIL import Image, ImageDraw, ImageFont
import sys
import os

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

def make_overlay(text, outpath, w=1080, h=1920, fontsize=120):
    hw, hh = max(1, w//2), max(1, h//2)  # half res render (fast)
    font = _load_font(max(8, int(fontsize//2)))
    img = Image.new("RGBA", (hw, hh), (0,0,0,0))
    draw = ImageDraw.Draw(img)

    # wrap text into lines to fit width
    def wrap(draw, text, font, max_w):
        words = text.split()
        lines = []
        line = ""
        for w0 in words:
            cand = (line + " " + w0).strip()
            if draw.textlength(cand, font=font) <= max_w:
                line = cand
            else:
                if line:
                    lines.append(line)
                line = w0
        if line:
            lines.append(line)
        return lines

    maxw = int(hw * 0.9)
    lines = wrap(draw, text, font, maxw)
    try:
        line_h = font.size + int(font.size * 0.3)
    except Exception:
        line_h = int(hh * 0.05)
    total_h = line_h * len(lines)
    y = max(0, (hh - total_h)//2)

    # background box
    if lines:
        max_w_line = max(int(draw.textlength(ln, font=font)) for ln in lines)
        pad_x = max(8, int(hw * 0.03))
        pad_y = max(4, int(line_h * 0.4))
        box_w = max_w_line + pad_x*2
        box_h = total_h + pad_y*2
        box_x = max(0, (hw - box_w)//2)
        box_y = max(0, y - pad_y)
        draw.rectangle([box_x, box_y, box_x+box_w, box_y+box_h], fill=(0,0,0,200))

    # draw lines centered
    for ln in lines:
        line_w = int(draw.textlength(ln, font=font))
        x = max(0, (hw - line_w)//2)
        draw.text((x, y), ln, font=font, fill=(255,255,255,255))
        y += line_h

    # scale to target size
    img = img.resize((w, h), resample=Image.Resampling.LANCZOS if hasattr(Image,'Resampling') else Image.LANCZOS)
    img.save(outpath)

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python overlay_png.py \"Headline text\" out.png width height [fontsize]")
        sys.exit(1)
    text = sys.argv[1]
    out = sys.argv[2]
    w = int(sys.argv[3])
    h = int(sys.argv[4])
    fs = int(sys.argv[5]) if len(sys.argv) >= 6 else 120
    make_overlay(text, out, w, h, fs)
    print("Wrote", out)
