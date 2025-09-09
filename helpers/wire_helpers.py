# helpers/wire_helpers.py
"""
Simple orchestrator to turn a script file into a short video using the helper modules:
 - script_marker_parser.py
 - tts_utils.py
 - audio_mixer.py
 - visual_templates.py

Usage (example):
  python helpers\wire_helpers.py --script-file sample_script.txt --out out.mp4 --sfx-dir assets/sounds

This script is intentionally conservative and meant for local testing first.
"""
import argparse
import os
import tempfile
from pathlib import Path
from moviepy.editor import concatenate_videoclips, AudioFileClip
import logging

# local helper modules (assumes run from repo root or PYTHONPATH includes repo)
from script_marker_parser import parse_script
import tts_utils
import audio_mixer
import visual_templates

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("wire_helpers")

DEFAULT_SFX_DIR = "assets/sounds"
DEFAULT_RES = (1280, 720)

def find_sfx_file(sfx_dir: str, name: str):
    # try common extensions
    for ext in (".wav", ".mp3", ".ogg", ".m4a"):
        p = Path(sfx_dir) / (name + ext)
        if p.exists():
            return str(p)
    return None

def produce_from_script(script_text: str, out_path: str, sfx_dir: str = DEFAULT_SFX_DIR, voice: str = None, size=(1280,720), tmpdir=None):
    tmpdir = tmpdir or tempfile.mkdtemp(prefix="avagent_")
    LOG.info("Using tmpdir %s", tmpdir)
    segments = parse_script(script_text)
    clips = []

    for i, seg in enumerate(segments):
        LOG.info("Segment %d: %s", i, seg["text"][:60])
        # 1) Synthesize TTS for this segment
        seg_tts_path = os.path.join(tmpdir, f"seg_{i}_tts.wav")
        try:
            tts_utils.synthesize_text(seg["text"], out_path=seg_tts_path, preferred_voice=voice, lang="en-US")
        except Exception as e:
            LOG.error("TTS failed for segment %d: %s", i, e)
            raise

        # 2) build sfx list for this segment (map names to files and offsets)
        sfx_items = []
        for name, offset in seg["sfx"]:
            p = find_sfx_file(sfx_dir, name)
            if p:
                sfx_items.append((p, offset))
            else:
                LOG.warning("SFX %s not found in %s (skipping)", name, sfx_dir)

        # 3) mix audio
        seg_mix_path = os.path.join(tmpdir, f"seg_{i}_mix.wav")
        audio_mixer.duck_and_mix(seg_tts_path, sfx_items, out_path=seg_mix_path)

        # 4) create video clip for this segment (use estimate_duration)
        dur = seg.get("estimate_duration", 2.5)
        # Choose template: if has_hit => pop_text; else text slide
        if seg.get("has_hit"):
            clip = visual_templates.make_pop_text(seg["text"], duration=dur, size=size)
        else:
            clip = visual_templates.make_text_slide(seg["text"], duration=dur, size=size)
        # attach audio
        try:
            clip_audio = AudioFileClip(seg_mix_path)
            clip = clip.set_audio(clip_audio).set_duration(clip_audio.duration)
        except Exception:
            # fallback: leave clip with its estimated duration
            LOG.exception("Failed to attach audio for seg %d; using silent clip", i)
        clips.append(clip)

    # 5) concatenate
    final = concatenate_videoclips(clips, method="compose")
    final = final.set_fps(24)
    final.write_videofile(out_path, codec="libx264", audio_codec="aac", threads=2, logger=None)
    LOG.info("Wrote final video to %s", out_path)
    return out_path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--script-file", required=True, help="Plain text script file (one caption per line).")
    p.add_argument("--out", required=True, help="Output mp4 path")
    p.add_argument("--sfx-dir", default=DEFAULT_SFX_DIR, help="SFX folder")
    p.add_argument("--voice", default=None, help="preferred TTS voice name")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    args = p.parse_args()

    if not os.path.exists(args.script_file):
        raise SystemExit("script file missing: " + args.script_file)
    with open(args.script_file, "r", encoding="utf-8") as f:
        script_text = f.read()

    produce_from_script(script_text, out_path=args.out, sfx_dir=args.sfx_dir, voice=args.voice, size=(args.width, args.height))

if __name__ == "__main__":
    main()
