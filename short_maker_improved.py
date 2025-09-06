# short_maker_improved.py
"""
Autonomous short generator (improved):
  - create short mp4 from topic text
  - script generation: small template (replaceable)
  - TTS (edge-tts preferred, falls back to gTTS)
  - mix voice + selected bed (voice padded BEFORE mixing)
  - create image with Pillow (title, subtitle, label baked in)
  - ffmpeg -> final mp4
Usage:
  python short_maker_improved.py --topic "Huge football upset..." --sec 25
"""
import os
import subprocess
import textwrap
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from sound_selector import select_bed, select_sfx

ROOT = Path.cwd()
ASSETS_DIR = ROOT / "assets"
SOUNDS_DIR = ASSETS_DIR / "sounds"
OUT_ROOT = ROOT / "shorts"

VOICE = "en-US-AriaNeural"
DEFAULT_TARGET_SEC = 25
WIDTH, HEIGHT = 1080, 1920

def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def _run_list(cmd_list):
    print("CMD>", " ".join(cmd_list))
    p = subprocess.run(cmd_list, capture_output=True, text=True)
    if p.returncode != 0:
        print("ERROR (stderr):", p.stderr[:2000])
        raise RuntimeError(f"Command failed: {' '.join(cmd_list)}\n{p.stderr}")
    return p.stdout

# ----------------------------
# Script generation (simple)
# ----------------------------
def generate_script(topic: str) -> str:
    # Replace with OpenAI call if you have API; keep fallback concise.
    topic = topic.strip()
    fallback = (
        f"{topic}. Quick recap: what happened and why it matters now. "
        "One surprising stat or quote to hook viewers. Call to action: comment your take."
    )
    # Minimal deterministic template - easy to replace with LLM.
    return fallback

# ----------------------------
# TTS helpers
# ----------------------------
def has_edge_tts():
    try:
        subprocess.run(["edge-tts", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def tts_to_wav_edge(text: str, out_wav: Path) -> Path:
    # Uses edge-tts CLI to produce WAV (modern MS voice)
    cmd = [
        "edge-tts",
        "--voice", VOICE,
        "--text", text,
        "--write-media", str(out_wav)
    ]
    _run_list(cmd)
    return out_wav

def tts_to_wav_gtts(text: str, out_wav: Path) -> Path:
    from gtts import gTTS
    tmp_mp3 = out_wav.with_suffix(".tmp.mp3")
    tts = gTTS(text=text, lang="en")
    tts.save(str(tmp_mp3))
    # convert to wav pcm
    cmd = ["ffmpeg", "-y", "-i", str(tmp_mp3), "-ar", "44100", "-ac", "2", str(out_wav)]
    _run_list(cmd)
    tmp_mp3.unlink(missing_ok=True)
    return out_wav

def make_voice_tts(text: str, out_wav: Path) -> Path:
    _ensure_dir(out_wav.parent)
    if has_edge_tts():
        try:
            return tts_to_wav_edge(text, out_wav)
        except Exception as e:
            print("edge-tts failed:", e)
    return tts_to_wav_gtts(text, out_wav)

# ----------------------------
# Audio mixing: pad voice THEN mix
# ----------------------------
def mix_voice_and_bed(voice_wav: Path, bed_path: Optional[Path], target_sec: int, out_mixed: Path,
                      bed_vol=0.18, voice_vol=1.0):
    """
    Steps:
      1) convert voice wav -> mp3 temp
      2) pad voice to target_sec (apad) -> voice_padded.mp3
      3) if bed_path: stream_loop -1 bed and mix with voice_padded using amix=inputs=2:duration=first
         (voice_padded is first, so the result will be the padded length)
      4) if no bed, just write voice_padded -> out_mixed
    """
    out_mixed.parent.mkdir(parents=True, exist_ok=True)
    tmp_voice_mp3 = out_mixed.with_suffix(".voice.tmp.mp3")
    tmp_voice_padded = out_mixed.with_suffix(".voice.padded.mp3")

    # 1) convert
    _run_list(["ffmpeg", "-y", "-i", str(voice_wav), "-ar", "44100", "-ac", "2", str(tmp_voice_mp3)])

    # 2) pad voice to target length
    _run_list([
        "ffmpeg", "-y", "-i", str(tmp_voice_mp3),
        "-af", f"apad=pad_dur={int(target_sec)}",
        "-t", str(int(target_sec)),
        "-ar", "44100", "-ac", "2", str(tmp_voice_padded)
    ])

    if not bed_path:
        # finalize
        _run_list(["ffmpeg", "-y", "-i", str(tmp_voice_padded), "-ar", "44100", "-ac", "2",
                   "-c:a", "libmp3lame", "-b:a", "192k", str(out_mixed)])
        tmp_voice_mp3.unlink(missing_ok=True)
        tmp_voice_padded.unlink(missing_ok=True)
        return out_mixed

    # 3) mix: ensure voice is second input so we can use [1:a] as voice (but use duration=first)
    # We will use the padded voice as the "first" input in filter_complex so amix=duration=first keeps target length.
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(bed_path),
        "-i", str(tmp_voice_padded),
        "-filter_complex",
        f"[1:a]volume={voice_vol}[voice];[0:a]volume={bed_vol}[bed];[voice][bed]amix=inputs=2:duration=first:dropout_transition=2[aout]",
        "-map", "[aout]",
        "-t", str(int(target_sec)),
        "-ar", "44100", "-ac", "2",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_mixed)
    ]
    _run_list(cmd)
    tmp_voice_mp3.unlink(missing_ok=True)
    tmp_voice_padded.unlink(missing_ok=True)
    return out_mixed

# ----------------------------
# Pillow: robust text wrapping & drawing (works across PIL versions)
# ----------------------------
def _get_text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont):
    # Prefer draw.textbbox if available
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        return w, h
    except Exception:
        try:
            return font.getsize(text)
        except Exception:
            return draw.textsize(text, font=font)  # last resort

def make_base_image(out_png: Path, title: str, subtitle: Optional[str], label: Optional[str]):
    W, H = WIDTH, HEIGHT
    img = Image.new("RGB", (W, H), (12, 12, 16))
    draw = ImageDraw.Draw(img)

    # load fonts
    font_path_candidates = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    font_big = font_med = font_small = None
    for p in font_path_candidates:
        try:
            if Path(p).exists():
                font_big = ImageFont.truetype(p, 72)
                font_med = ImageFont.truetype(p, 46)
                font_small = ImageFont.truetype(p, 36)
                break
        except Exception:
            continue
    if font_big is None:
        font_big = ImageFont.load_default()
        font_med = font_big
        font_small = font_big

    # Title wrap
    max_w = W - 140
    words = title.split()
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        tw, th = _get_text_size(draw, test, font_big)
        if tw <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    y = H // 6
    for i, line in enumerate(lines[:5]):
        tw, th = _get_text_size(draw, line, font_big)
        draw.text(((W - tw) // 2, y), line, font=font_big, fill=(255, 255, 255))
        y += th + 12

    # subtitle
    if subtitle:
        sub_lines = textwrap.wrap(subtitle, width=30)
        y += 8
        for sl in sub_lines[:4]:
            tw, th = _get_text_size(draw, sl, font_med)
            draw.text(((W - tw) // 2, y), sl, font=font_med, fill=(220, 220, 220))
            y += th + 8

    # label (top-left)
    if label:
        lab = label.upper()
        tw, th = _get_text_size(draw, lab, font_small)
        padding = 12
        rect_w = tw + padding * 2
        rect_h = th + padding
        box = (40, 40, 40 + rect_w, 40 + rect_h)
        draw.rectangle(box, fill=(240, 80, 40))
        draw.text((40 + padding, 40 + (padding//2)), lab, font=font_small, fill=(0, 0, 0))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_png))
    print("[short_maker] Saved slide image:", out_png)
    return out_png

# ----------------------------
# High-level short creation
# ----------------------------
def classify_topic(topic: str) -> str:
    t = topic.lower()
    if any(w in t for w in ("football", "soccer", "goal", "fifa", "match")):
        return "sports"
    if any(w in t for w in ("president", "senate", "election", "parliament")):
        return "news"
    if any(w in t for w in ("ai", "openai", "google", "apple", "microsoft", "startup")):
        return "tech"
    return "default"

def create_short(topic: str, target_sec: int = DEFAULT_TARGET_SEC):
    safe = "".join(c if c.isalnum() or c in (" ", "-", "_") else "-" for c in topic)[:120].strip()
    out_dir = OUT_ROOT / safe.replace(" ", "-")
    _ensure_dir(out_dir)

    script = generate_script(topic)
    label = classify_topic(topic)
    print("[short_maker] topic label:", label)

    # pick a bed
    bed = select_bed(label, target_sec)
    print("[short_maker] selected bed:", bed)

    # TTS -> wav
    voice_wav = out_dir / "tts.raw.wav"
    make_voice_tts(script, voice_wav)

    # mix voice + bed
    mixed = out_dir / "final_audio.mixed.mp3"
    mix_voice_and_bed(voice_wav, bed, target_sec, mixed)

    # create base image baked with text
    subtitle = script.split(".")[0] if "." in script else script
    base_png = out_dir / f"{safe}_base.png"
    make_base_image(base_png, title=topic, subtitle=subtitle, label=label)

    # ffmpeg combine image (loop) + mixed audio -> mp4
    out_mp4 = out_dir / f"{safe}.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(base_png),
        "-i", str(mixed),
        "-c:v", "libx264",
        "-t", str(int(target_sec)),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_mp4)
    ]
    _run_list(cmd)
    print("[short_maker] Created video:", out_mp4)
    return str(out_mp4)

# CLI
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--sec", type=int, default=DEFAULT_TARGET_SEC)
    args = parser.parse_args()
    mp4 = create_short(args.topic, target_sec=args.sec)
    print("DONE ->", mp4)
