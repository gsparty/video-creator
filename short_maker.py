# short_maker.py
"""
Short maker: produce a single attention-grabbing MP4 from a topic headline.
Features:
 - edge-tts SSML (preferred). fallback: gTTS -> pyttsx3
 - ffmpeg-based loudnorm, compressor, reverb "flavor"
 - Create single-slide PNG (readable text) with wrapped text using ImageDraw.textbbox
 - Produce MP4 with zoompan and mapped audio (single final file)
 - Optional SFX overlay (list of (path, ms_position))
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import subprocess
import uuid
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

LOG = logging.getLogger("short_maker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [short_maker] %(message)s")

# Configure paths (adjust FFMPEG if needed)
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")

# default target vertical short resolution
TARGET_W, TARGET_H = 1080, 1920
FPS = 25

# default voice and sfx directory
DEFAULT_VOICE = "en-US-AriaNeural"


def run_cmd(cmd: List[str], capture=False, check=True, env=None):
    LOG.info("CMD> %s", " ".join(cmd))
    if capture:
        res = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
        )
        if check and res.returncode != 0:
            LOG.error(
                "Command failed. stdout:\n%s\nstderr:\n%s",
                res.stdout.decode(errors="ignore"),
                res.stderr.decode(errors="ignore"),
            )
            raise RuntimeError(f"Command failed: {cmd}")
        return res.stdout.decode(errors="ignore"), res.stderr.decode(errors="ignore")
    else:
        res = subprocess.run(cmd, env=env)
        if check and res.returncode != 0:
            raise RuntimeError(f"Command failed: {cmd}")
        return None


def safe_mkdir(path: str):
    os.makedirs(path, exist_ok=True)
    return path


def slugify(text: str) -> str:
    # basic slug suitable for filenames
    import re

    s = text.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-_]", "", s)
    if not s:
        s = uuid.uuid4().hex[:8]
    return s[:120]


def build_ssml_for_topic(
    topic: str, voice_name: str = DEFAULT_VOICE, style: str = "newscast-casual"
) -> str:
    """
    Build expressive SSML for Microsoft neural voices (edge-tts).
    """
    # minimal escape
    esc = topic.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    ssml = f"""
<speak xmlns="http://www.w3.org/2001/10/synthesis"
       xmlns:mstts="https://www.w3.org/2001/mstts"
       xml:lang="en-US">
  <voice name="{voice_name}">
    <mstts:express-as style="{style}">
      <prosody rate="+0%" pitch="+0%">
        Hey — <break time="220ms"/> here's what you should know about <emphasis level="moderate">{esc}</emphasis>.<break time="300ms"/>
        1. Quick context and why it matters. <break time="200ms"/>
        2. A short surprising fact. <break time="220ms"/>
        3. Finally — comment your opinion below. <break time="180ms"/>
      </prosody>
    </mstts:express-as>
  </voice>
</speak>
"""
    return ssml.strip()


# ----- TTS handling -----
def edge_tts_available() -> bool:
    try:
        return True
    except Exception:
        return False


async def _edge_tts_save(ssml: str, out_wav: str, voice: str = DEFAULT_VOICE):
    import edge_tts  # type: ignore

    # edge_tts.Communicate(text, voice=voice).save(path)
    com = edge_tts.Communicate(ssml, voice=voice)
    await com.save(out_wav)


def try_edge_tts_sync(ssml: str, out_wav: str, voice: str = DEFAULT_VOICE) -> bool:
    try:
        # run async save synchronously
        asyncio.run(_edge_tts_save(ssml, out_wav, voice=voice))
        LOG.info("edge-tts produced: %s", out_wav)
        return True
    except Exception as e:
        LOG.warning("edge-tts SSML failed: %s", e)
        return False


def try_gtts_text_to_mp3(text: str, out_mp3: str, lang="en"):
    # lightweight fallback using gTTS
    try:
        from gtts import gTTS

        t = gTTS(text, lang=lang)
        tmp = out_mp3 + ".tmp.mp3"
        t.save(tmp)
        # ensure proper sample rate / channels via ffmpeg
        run_cmd([FFMPEG, "-y", "-i", tmp, "-ar", "44100", "-ac", "2", out_mp3])
        os.remove(tmp)
        LOG.info("gTTS produced: %s", out_mp3)
        return True
    except Exception as e:
        LOG.warning("gTTS failed: %s", e)
        return False


def try_pyttsx3_text_to_wav(text: str, out_wav: str):
    try:
        import pyttsx3

        engine = pyttsx3.init()
        # Windows voices often produce WAV by save_to_file
        engine.save_to_file(text, out_wav)
        engine.runAndWait()
        LOG.info("pyttsx3 produced: %s", out_wav)
        return True
    except Exception as e:
        LOG.warning("pyttsx3 failed: %s", e)
        return False


def get_audio_duration(path: str) -> float:
    try:
        out, err = run_cmd(
            [
                FFPROBE,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture=True,
        )
        out = out.strip()
        return float(out)
    except Exception:
        LOG.warning("ffprobe failed for %s; defaulting to 20s", path)
        return 20.0


def flavor_audio_broadcast(in_mp3: str, out_mp3: str):
    # gentle highpass + compressor + small reverb + normalize already applied beforehand
    af = "highpass=f=80,lowpass=f=15000,acompressor=threshold=0.05:ratio=4:attack=5:release=100,aecho=0.0007:0.0009:0.6:0.35"
    run_cmd(
        [FFMPEG, "-y", "-i", in_mp3, "-af", af, "-ar", "44100", "-ac", "2", out_mp3]
    )
    return out_mp3


def pad_audio_to_duration(in_mp3: str, out_mp3: str, duration: float):
    # pad using apad
    run_cmd(
        [
            FFMPEG,
            "-y",
            "-i",
            in_mp3,
            "-af",
            f"apad=pad_dur={max(0, duration)}",
            "-ar",
            "44100",
            "-ac",
            "2",
            out_mp3,
        ]
    )
    return out_mp3


# ----- image/slide generation -----
def wrap_text_to_lines(
    text: str, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont, max_w: int
) -> List[str]:
    # robust wrapper: use textbbox for measurement
    words = text.strip().split()
    if not words:
        return []
    lines = []
    cur = words[0]
    for w in words[1:]:
        trial = cur + " " + w
        bbox = draw.textbbox((0, 0), trial, font=font)
        w_px = bbox[2] - bbox[0]
        if w_px <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def create_slide_png(
    out_path: str, title: str, width: int = TARGET_W, height: int = TARGET_H
):
    # simple gradient + centered title + big readable font
    img = Image.new("RGB", (width, height), color=(20, 20, 20))
    draw = ImageDraw.Draw(img)

    # gradient
    for i in range(height):
        # subtle vertical gradient
        ratio = i / (height - 1)
        r = int(24 + ratio * 40)
        g = int(24 + ratio * 10)
        b = int(24 + ratio * 60)
        draw.line([(0, i), (width, i)], fill=(r, g, b))

    # load font: prefer a TTF if available, else load_default
    font = None
    try:
        # common fallback fonts:
        for f in [
            "arial.ttf",
            "DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]:
            try:
                font = ImageFont.truetype(f, size=72)
                break
            except Exception:
                font = None
        if font is None:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    # title wrapping
    max_text_w = int(width * 0.85)
    lines = wrap_text_to_lines(title, draw, font, max_text_w)
    # adjust font size to fit if too many lines
    if len(lines) > 6:
        # try smaller font
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=48)
            lines = wrap_text_to_lines(title, draw, font, max_text_w)
        except Exception:
            font = ImageFont.load_default()
            lines = wrap_text_to_lines(title, draw, font, max_text_w)

    # compute block height
    line_h = (
        draw.textbbox((0, 0), "Ay", font=font)[3]
        - draw.textbbox((0, 0), "Ay", font=font)[1]
    )
    block_h = line_h * len(lines)
    y0 = (height - block_h) // 2

    # draw text with stroke for readability
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        w_line = bbox[2] - bbox[0]
        x = (width - w_line) // 2
        y = y0 + i * line_h
        # draw outline by drawing text multiple times
        outline_color = (0, 0, 0)
        for ox, oy in [(-2, -2), (-2, 2), (2, -2), (2, 2), (0, -2), (0, 2)]:
            draw.text((x + ox, y + oy), line, font=font, fill=outline_color)
        draw.text((x, y), line, font=font, fill=(255, 255, 255))

    # small footer call-to-action
    try:
        foot_font = ImageFont.truetype("DejaVuSans.ttf", size=28)
    except Exception:
        foot_font = ImageFont.load_default()
    footer = "Watch more • Comment below"
    fbbox = draw.textbbox((0, 0), footer, font=foot_font)
    draw.text(
        (width - fbbox[2] - 20, height - fbbox[3] - 20),
        footer,
        font=foot_font,
        fill=(220, 220, 220),
    )

    img.save(out_path, format="PNG")
    LOG.info("Saved slide image: %s", out_path)
    return out_path


# ----- final MP4 creation -----
def create_mp4_from_image_and_audio(
    image_png: str,
    audio_mp3: str,
    out_mp4: str,
    fps: int = FPS,
    extra_zoom: float = 0.0009,
):
    # compute duration
    dur = get_audio_duration(audio_mp3)
    frames = max(1, int(math.ceil(dur * fps)))
    # zoompan d value controls frames; ensure integer
    d_val = frames
    # ffmpeg zoompan expects expressions; using the same filter as previous pipeline
    filter_complex = f"[0:v]scale={TARGET_W}:{TARGET_H},zoompan=z='zoom+{extra_zoom}':d={d_val}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',fps={fps},format=yuv420p[v]"
    cmd = [
        FFMPEG,
        "-y",
        "-loop",
        "1",
        "-i",
        image_png,
        "-i",
        audio_mp3,
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-map",
        "1:a",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        out_mp4,
    ]
    run_cmd(cmd)
    LOG.info("Created video: %s", out_mp4)
    return out_mp4


# ----- orchestration: main generate_short -----
def generate_short(
    topic: str,
    out_root: str = "shorts",
    voice: str = DEFAULT_VOICE,
    sfx_timing: Optional[List[Tuple[str, int]]] = None,
    force_use_gtts: bool = False,
) -> str:
    """
    Generate a single final mp4 for `topic`.
    sfx_timing: list of tuples (sfx_path, ms_offset) to overlay on final audio (optional).
    Returns path to final mp4.
    """
    slug = slugify(topic or "topic")
    out_dir = safe_mkdir(os.path.join(out_root, slug))
    LOG.info("generate_short called: %s -> %s", topic, out_dir)

    tmp_wav = os.path.join(out_dir, f"{slug}.tts.raw.wav")
    tmp_mp3 = os.path.join(out_dir, f"{slug}.tts.raw.mp3")
    norm_mp3 = os.path.join(out_dir, f"{slug}.tts.norm.mp3")
    flavored_mp3 = os.path.join(out_dir, f"{slug}.tts.flavored.mp3")
    final_mp3 = os.path.join(out_dir, f"{slug}.final.mp3")
    base_png = os.path.join(out_dir, f"{slug}_base.png")
    final_mp4 = os.path.join(out_dir, f"{slug}.mp4")

    # compose speech text (short hook + list)
    tts_text = f"{topic} — here's what you should know. 1. Quick context and why it matters. 2. A short surprising fact. 3. Comment your opinion below!"
    LOG.info("TTS text: %s", tts_text)

    # 1) Try edge-tts SSML (if available and not forced to use fallback)
    ssml = build_ssml_for_topic(topic, voice_name=voice)
    success = False
    if not force_use_gtts and edge_tts_available():
        LOG.info("Using edge-tts SSML voice: %s", voice)
        success = try_edge_tts_sync(ssml, tmp_wav, voice=voice)
        # convert wav to mp3
        if success and os.path.exists(tmp_wav):
            run_cmd([FFMPEG, "-y", "-i", tmp_wav, "-ar", "44100", "-ac", "2", tmp_mp3])
    # 2) if edge-tts failed, try gTTS (gtts writes mp3)
    if (not success) and (not force_use_gtts):
        LOG.info("Attempting gTTS fallback")
        success = try_gtts_text_to_mp3(tts_text, tmp_mp3)
    # 3) final fallback: pyttsx3 -> wav -> mp3
    if not success:
        LOG.info("Attempting pyttsx3 fallback (WAV)")
        ok = try_pyttsx3_text_to_wav(tts_text, tmp_wav)
        if ok and os.path.exists(tmp_wav):
            run_cmd([FFMPEG, "-y", "-i", tmp_wav, "-ar", "44100", "-ac", "2", tmp_mp3])
            success = True

    if not success or not os.path.exists(tmp_mp3):
        raise RuntimeError("All TTS attempts failed")

    # 4) Normalize loudness (loudnorm) - create norm_mp3
    run_cmd(
        [
            FFMPEG,
            "-y",
            "-i",
            tmp_mp3,
            "-vn",
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11,dynaudnorm=f=150:g=15",
            "-ar",
            "44100",
            "-ac",
            "2",
            norm_mp3,
        ]
    )

    # 5) Flavor audio (compress + subtle reverb)
    flavor_audio_broadcast(norm_mp3, flavored_mp3)

    # 6) pad to at least 20s (or keep actual duration whichever larger)
    dur = get_audio_duration(flavored_mp3)
    target_dur = max(20.0, dur)
    pad_audio_to_duration(flavored_mp3, final_mp3, target_dur)

    # 7) Optional SFX overlay (if provided) - simple overlay
    if sfx_timing:
        # build filter_complex overlay by delaying SFX then amix
        inputs = [final_mp3] + [p for p, _ in sfx_timing]
        cmd = [FFMPEG, "-y"]
        for p in inputs:
            cmd += ["-i", p]
        # adelay for each sfx (index start 1)
        delay_filters = []
        for idx, (_, ms) in enumerate(sfx_timing, start=1):
            # input index is idx (0=voice, 1..n sfx)
            delay_filters.append(f"[{idx}:a]adelay={ms}|{ms}[s{idx}]")
        mix_inputs = "[0:a]" + "".join(f"[s{i}]" for i in range(1, len(sfx_timing) + 1))
        af = (
            ";".join(delay_filters)
            + ";"
            + f"{mix_inputs}amix=inputs={1+len(sfx_timing)}:duration=first:dropout_transition=2[aout]"
        )
        cmd += [
            "-filter_complex",
            af,
            "-map",
            "[aout]",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            final_mp3 + ".sfx.mp4",
        ]
        try:
            run_cmd(cmd)
            # after mixing, replace final_mp3 with the mixed audio (we used mp4 container)
            # extract audio (mp3) back (or simply use that mp4 as audio input)
            tmp_mixed = final_mp3 + ".sfx.mp4"
            final_mp3 = final_mp3 + ".mixed.mp3"
            run_cmd(
                [
                    FFMPEG,
                    "-y",
                    "-i",
                    tmp_mixed,
                    "-vn",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    final_mp3,
                ]
            )
        except Exception as e:
            LOG.warning("SFX mixing failed: %s", e)

    # 8) create slide PNG
    create_slide_png(base_png, title=topic, width=TARGET_W, height=TARGET_H)

    # 9) create final mp4 from single image + audio
    # ensure final_mp3 exists
    if not os.path.exists(final_mp3):
        raise RuntimeError("final audio missing: " + str(final_mp3))
    create_mp4_from_image_and_audio(base_png, final_mp3, final_mp4)

    LOG.info("generate_short finished: %s", final_mp4)
    return final_mp4


# If run as script for quick test
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "topic", nargs="?", default="Test Trend Headline: Amazing news today"
    )
    parser.add_argument("--out", default="shorts")
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument(
        "--sfx",
        nargs="*",
        help="pairs sfxPath:msOffset (e.g. sfx/whoosh.mp3:600 )",
        default=[],
    )
    args = parser.parse_args()

    sfx_list = []
    for s in args.sfx:
        if ":" in s:
            p, m = s.split(":", 1)
            try:
                sfx_list.append((p, int(m)))
            except Exception:
                pass
    path = generate_short(
        args.topic, out_root=args.out, voice=args.voice, sfx_timing=sfx_list
    )
    print("Done ->", path)
