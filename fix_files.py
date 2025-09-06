# fix_files.py — one-shot fixer to patch Pillow/MoviePy issues and bad backticks
import io, os, sys
from pathlib import Path

ROOT = Path.cwd()
print("Working in", ROOT)

# 1) write pil_compat.py
pil_code = r'''
# pil_compat.py -- small shim so MoviePy's use of PIL.Image.ANTIALIAS works
try:
    from PIL import Image
except Exception:
    raise

# Add legacy alias ANTIALIAS if missing
if not hasattr(Image, "ANTIALIAS"):
    # modern Pillow uses Image.LANCZOS or Image.Resampling.LANCZOS
    if hasattr(Image, "LANCZOS"):
        Image.ANTIALIAS = Image.LANCZOS
    else:
        try:
            Image.ANTIALIAS = Image.Resampling.LANCZOS
        except Exception:
            if hasattr(Image, "BICUBIC"):
                Image.ANTIALIAS = Image.BICUBIC
            else:
                Image.ANTIALIAS = None

# ensure Resampling.LANCZOS exists when possible
try:
    if hasattr(Image, "Resampling") and not hasattr(Image.Resampling, "LANCZOS") and hasattr(Image, "LANCZOS"):
        Image.Resampling.LANCZOS = Image.LANCZOS
except Exception:
    pass
'''
(Path(ROOT) / "pil_compat.py").write_text(pil_code, encoding="utf-8")
print("Wrote pil_compat.py")

# 2) repair literal backtick-n characters in video_builder.py if present
vb = Path(ROOT / "video_builder.py")
if vb.exists():
    s = vb.read_text(encoding="utf-8")
    if "`n" in s:
        s2 = s.replace("`n", "\n")
        vb.write_text(s2, encoding="utf-8")
        print("Replaced literal `n sequences in video_builder.py")
    else:
        print("No `n corruption found in video_builder.py")
else:
    print("video_builder.py not found — skipping backtick repair")

# 3) ensure import pil_compat at the top of text_overlay.py and video_builder.py
def ensure_import(path):
    p = Path(path)
    if not p.exists():
        print(f"{path} not found; skipping")
        return
    s = p.read_text(encoding="utf-8")
    if "import pil_compat" in s:
        print(f"pil_compat import already present in {path}")
        return
    # Insert import at top before any moviepy or PIL imports
    lines = s.splitlines()
    insert_at = 0
    # try to find first non-shebang/non-comment line
    for i, L in enumerate(lines):
        if L.strip().startswith("#!") or L.strip().startswith("#"):
            continue
        insert_at = i
        break
    lines.insert(insert_at, "import pil_compat")
    p.write_text("\n".join(lines), encoding="utf-8")
    print(f"Inserted import pil_compat into {path}")

ensure_import(ROOT / "text_overlay.py")
ensure_import(ROOT / "video_builder.py")

# 4) ensure text_overlay.py content matches the robust, file-backed overlay we designed
text_overlay_expected = r'''
# text_overlay.py — file-backed overlay generator (half-res -> cached PNG -> ImageClip)
import hashlib
from pathlib import Path
from tempfile import gettempdir
from PIL import Image, ImageDraw, ImageFont
import numpy as np

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
    from moviepy.editor import ImageClip

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
'''
tpath = ROOT / "text_overlay.py"
if tpath.exists():
    # if current differs substantially we will overwrite with the robust version
    cur = tpath.read_text(encoding="utf-8")
    if "file-backed overlay" not in cur:
        print("Overwriting text_overlay.py with robust version")
        tpath.write_text(text_overlay_expected.strip() + "\n", encoding="utf-8")
    else:
        print("text_overlay.py already appears robust")
else:
    print("text_overlay.py missing — writing robust version")
    tpath.write_text(text_overlay_expected.strip() + "\n", encoding="utf-8")

print("Patching done. Please run the overlay test next.")
