# generate_base_videos.py
# Creates simple placeholder vertical videos (image -> looped mp4) for a list of topics.
import pathlib
import subprocess
import sys

from PIL import Image, ImageDraw

FONT_PATHS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    r"C:\Windows\Fonts\Tahoma.ttf",
]


def load_font(size):
    from PIL import ImageFont

    for fp in FONT_PATHS:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


def make_image(text, outpath, w=1080, h=1920, fontsize=140, bg=(10, 10, 10)):
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    font = load_font(fontsize)
    # wrap text
    maxw = int(w * 0.9)
    words = text.split()
    lines = []
    line = ""
    for w0 in words:
        cand = (line + " " + w0).strip()
        if draw.textlength(cand, font=font) <= maxw:
            line = cand
        else:
            if line:
                lines.append(line)
            line = w0
    if line:
        lines.append(line)
    # compute text block
    line_h = getattr(font, "size", 30) + int(getattr(font, "size", 30) * 0.2)
    total_h = line_h * len(lines)
    y = max(0, (h - total_h) // 2)
    for ln in lines:
        tw = int(draw.textlength(ln, font=font))
        x = (w - tw) // 2
        draw.text((x, y), ln, font=font, fill=(255, 255, 255))
        y += line_h
    img.save(outpath)


def image_to_mp4(imgpath, outmp4, duration=10, fps=25):
    # create a short mp4 by repeating the image
    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(imgpath),
        "-c:v",
        "libx264",
        "-t",
        str(duration),
        "-pix_fmt",
        "yuv420p",
        "-vf",
        "scale=1080:1920",
        "-r",
        str(fps),
        str(outmp4),
    ]
    subprocess.run(cmd, check=True)


def main(outdir="outputs", topics=None):
    p = pathlib.Path(outdir)
    p.mkdir(parents=True, exist_ok=True)
    if topics is None:
        topics = [
            "Top lifehack you must know",
            "3-second kitchen trick",
            "Mind-blowing sports highlight",
            "Tiny gadget that changed my life",
            "Quick fitness tip for busy people",
            "Insane before/after transformation",
            "Hidden feature in your phone",
            "Weird food combo that works",
            "One-minute DIY home improvement",
            "Unexpected travel hack",
        ]
    for i, t in enumerate(topics, start=1):
        safe = f"{i:02d}_" + "".join(
            c if c.isalnum() or c in " -_" else "_" for c in t
        ).strip().replace(" ", "-")
        img = p / (safe + ".png")
        mp4 = p / (safe + ".mp4")
        if mp4.exists():
            print("Skipping", mp4.name)
            continue
        print("Make", img.name)
        make_image(t, img, 1080, 1920, fontsize=120, bg=(18, 18, 18))
        print("Render", mp4.name)
        image_to_mp4(img, mp4, duration=8)
    print("Done; base videos in", p)


if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "outputs"
    main(outdir)
