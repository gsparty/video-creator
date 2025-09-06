#!/usr/bin/env python3
"""
auto_short_generator.py
Create a vertical short from an input video + three assets:
 - background music (looped)
 - whoosh SFX (placed once)
 - ending music (placed near end)

No pydub used (avoids audioop issues). Uses moviepy only.
"""

import argparse
from pathlib import Path
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
import moviepy.audio.fx.all as afx

def build_short(
    input_video: Path,
    output_video: Path,
    background: Path,
    whoosh: Path,
    ending: Path,
    whoosh_at: float = 1.0,
    ending_fade_len: float = 0.6,
    bg_volume: float = 0.15,
    whoosh_vol: float = 0.7,
    ending_vol: float = 0.9,
):
    assert input_video.exists(), f"Input video not found: {input_video}"
    print("Loading video:", input_video)
    video = VideoFileClip(str(input_video))

    duration = video.duration
    print(f"Video duration: {duration:.2f}s")

    audio_clips = []
    # keep original video audio if present
    if video.audio is not None:
        print("Using original video audio (if any).")
        audio_clips.append(video.audio)

    # background music: loop it to the full duration
    if background and Path(background).exists():
        print("Loading background music:", background)
        bg = AudioFileClip(str(background)).volumex(bg_volume)
        # loop to duration
        bg = bg.fx(afx.audio_loop, duration=duration)
        audio_clips.append(bg)
    else:
        print("No background found / skipping background.")

    # whoosh SFX: place once at whoosh_at (only if exists)
    if whoosh and Path(whoosh).exists():
        print(f"Loading whoosh SFX: {whoosh} at {whoosh_at}s")
        who = AudioFileClip(str(whoosh)).volumex(whoosh_vol).set_start(max(0, min(whoosh_at, duration)))
        audio_clips.append(who)
    else:
        print("No whoosh found / skipping whoosh.")

    # ending music: place to start so it finishes exactly at the end (or start near end)
    if ending and Path(ending).exists():
        print("Loading ending music:", ending)
        ending_clip = AudioFileClip(str(ending)).volumex(ending_vol)
        # place it so it ends at video.duration (or if longer, trim)
        start_for_ending = max(0, duration - ending_clip.duration)
        # If the ending is longer than desired we can instead place it a few seconds before the end:
        if start_for_ending < 0:
            # fallback: place at duration - 2s (so it overlaps)
            start_for_ending = max(0, duration - 2.0)
        ending_final = ending_clip.set_start(start_for_ending)
        audio_clips.append(ending_final)
    else:
        print("No ending found / skipping ending.")

    if not audio_clips:
        raise RuntimeError("No audio tracks available to produce final audio.")

    # Composite them into final audio
    print("Compositing audio tracks...")
    final_audio = CompositeAudioClip(audio_clips).set_duration(duration)

    # Attach audio and export
    print("Setting final audio to video and exporting:", output_video)
    final = video.set_audio(final_audio)

    # Ensure vertical dimensions (scale/pad) if input is not 1080x1920
    # We'll keep original aspect but force vertical (1080x1920) output by scaling/padding via ffmpeg params
    # MoviePy's write_videofile supports resizing with .resize, but we keep it simple here:
    final.write_videofile(
        str(output_video),
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp-audio.m4a",
        remove_temp=True,
        threads=4,
        fps=25,
    )
    print("Done:", output_video)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("input", help="Input video file (mp4)")
    p.add_argument("output", help="Output mp4 path")
    p.add_argument("--background", default="background.mp3", help="Background bed music (looped)")
    p.add_argument("--whoosh", default="whoosh.wav", help="Short whoosh SFX")
    p.add_argument("--ending", default="ending.mp3", help="Ending sound (placed near end)")
    p.add_argument("--whoosh-at", type=float, default=1.0, help="Seconds into video to play whoosh")
    p.add_argument("--bg-vol", type=float, default=0.15, help="Background volume multiplier")
    p.add_argument("--whoosh-vol", type=float, default=0.7, help="Whoosh volume multiplier")
    p.add_argument("--ending-vol", type=float, default=0.9, help="Ending volume multiplier")
    args = p.parse_args()

    build_short(
        Path(args.input),
        Path(args.output),
        Path(args.background),
        Path(args.whoosh),
        Path(args.ending),
        whoosh_at=args.whoosh_at,
        bg_volume=args.bg_vol,
        whoosh_vol=args.whoosh_vol,
        ending_vol=args.ending_vol,
    )
