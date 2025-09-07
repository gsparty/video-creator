#!/usr/bin/env python3
"""
auto_short_ffmpeg.py

Mix background bed, whoosh SFX and ending into an input video's audio and produce a final short mp4.
No moviepy or pydub needed — uses ffmpeg/ffprobe via subprocess.

Usage example:
  python auto_short_ffmpeg.py input.mp4 output_short.mp4 --background background.mp3 --whoosh whoosh.wav --ending ending.mp3 --whoosh-at 1.2 --target-sec 25

Behavior:
 - Extracts original audio from input (if any) and mixes it with:
   * background (looped to video duration, reduced volume)
   * whoosh (placed at --whoosh-at seconds)
   * ending (placed so it ends at the video end)
 - Final audio is encoded as AAC and merged back into a new mp4 (video re-encoded to h264).
"""

import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd, check=True):
    print("CMD>", cmd)
    res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = res.stdout.decode(errors="replace")
    if res.returncode != 0 and check:
        raise RuntimeError(f"Command failed (rc={res.returncode}):\n{cmd}\n\n{out}")
    return out

def ffprobe_duration(path: Path) -> float:
    cmd = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{path}"'
    out = run(cmd)
    try:
        return float(out.strip())
    except Exception:
        return 0.0

def create_bed_loop(background: Path, duration: float, out_path: Path, vol=0.15):
    # loop background using stream_loop, trim with -t, set volume
    cmd = f'ffmpeg -y -stream_loop -1 -i "{background}" -t {duration:.3f} -af "volume={vol}" -ar 44100 -ac 2 "{out_path}"'
    run(cmd)

def place_sfx_at(sfx: Path, start_sec: float, out_path: Path, vol=1.0):
    # adelay expects milliseconds per channel, here we use mono->stereo safe pattern
    ms = int(round(max(0.0, start_sec) * 1000))
    # adelay: "ms|ms" for two channels; if input has >1 channel ffmpeg will handle.
    cmd = f'ffmpeg -y -i "{sfx}" -af "adelay={ms}|{ms},volume={vol}" -ar 44100 -ac 2 "{out_path}"'
    run(cmd)

def mix_tracks(track_paths, out_path: Path):
    # track_paths: list of audio file paths to amix together
    # Build filter that sets each input as-is then amix them
    inputs = " ".join(f'-i "{p}"' for p in track_paths)
    inputs_count = len(track_paths)
    # Lower chance of clipping: use -filter_complex "[0:a][1:a]...amix=inputs=N:duration=longest:dropout_transition=2"
    amix_filter_inputs = "".join(f'[{i}:a]' for i in range(inputs_count))
    filter_complex = f'{amix_filter_inputs}amix=inputs={inputs_count}:duration=first:dropout_transition=2,volume=1'
    cmd = f'ffmpeg -y {inputs} -filter_complex "{filter_complex}" -ar 44100 -ac 2 "{out_path}"'
    run(cmd)

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("input_video")
    p.add_argument("output_video")
    p.add_argument("--background", default="background.mp3", help="background bed (looped)")
    p.add_argument("--whoosh", default="whoosh.wav", help="whoosh SFX (short)")
    p.add_argument("--ending", default="ending.mp3", help="ending track")
    p.add_argument("--whoosh-at", type=float, default=1.0, help="seconds into video to play whoosh")
    p.add_argument("--bg-vol", type=float, default=0.15, help="background volume multiplier when generating bed")
    p.add_argument("--whoosh-vol", type=float, default=0.9, help="whoosh volume multiplier")
    p.add_argument("--ending-vol", type=float, default=0.9, help="ending volume multiplier")
    p.add_argument("--target-sec", type=float, default=0.0, help="If >0 override output duration (will trim/extend audio).")
    args = p.parse_args()

    inp = Path(args.input_video)
    out = Path(args.output_video)
    bg = Path(args.background)
    whoosh = Path(args.whoosh)
    ending = Path(args.ending)

    if not inp.exists():
        print("Input video not found:", inp)
        sys.exit(2)

    # get input duration
    # ffprobe can get duration of video container
    duration = ffprobe_duration(inp)
    if args.target_sec > 0:
        duration = args.target_sec
    print(f"Video duration -> {duration:.3f}s")

    tmpdir = Path(tempfile.mkdtemp(prefix="shorttmp_"))
    try:
        # 1) extract original audio (if any) -- produce wav for best mixing compatibility
        orig_audio = tmpdir / "orig_audio.wav"
        run(f'ffmpeg -y -i "{inp}" -vn -ar 44100 -ac 2 -c:a pcm_s16le "{orig_audio}" || echo "no-audio"')

        # If orig_audio was not created or its duration is 0, create silent audio of duration
        has_orig = orig_audio.exists() and ffprobe_duration(orig_audio) > 0.01
        if not has_orig:
            print("No original audio found — generating silent base audio")
            run(f'ffmpeg -y -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -t {duration:.3f} -ar 44100 -ac 2 "{orig_audio}"')

        # 2) create bed loop file
        bed_wav = tmpdir / "bed.wav"
        if bg.exists():
            create_bed_loop(bg, duration, bed_wav, vol=args.bg_vol)
        else:
            # create silent bed if missing
            run(f'ffmpeg -y -f lavfi -i anullsrc=r=44100:cl=stereo -t {duration:.3f} "{bed_wav}"')

        # 3) place whoosh at whoosh-at
        whoosh_placed = tmpdir / "whoosh_placed.wav"
        if whoosh.exists():
            place_sfx_at(whoosh, args.whoosh_at, whoosh_placed, vol=args.whoosh_vol)
        else:
            run(f'ffmpeg -y -f lavfi -i anullsrc=cl=stereo:r=44100 -t {duration:.3f} "{whoosh_placed}"')

        # 4) place ending so it ends at video end
        ending_placed = tmpdir / "ending_placed.wav"
        if ending.exists():
            ending_dur = ffprobe_duration(ending)
            start_for_ending = max(0.0, duration - ending_dur)
            place_sfx_at(ending, start_for_ending, ending_placed, vol=args.ending_vol)
        else:
            run(f'ffmpeg -y -f lavfi -i anullsrc=cl=stereo:r=44100 -t {duration:.3f} "{ending_placed}"')

        # 5) mix bed + whoosh + ending -> bed_mix.wav
        bed_mix = tmpdir / "bed_mix.wav"
        mix_tracks([bed_wav, whoosh_placed, ending_placed], bed_mix)

        # 6) mix original audio (voice) + bed_mix -> final_audio.wav
        final_audio = tmpdir / "final_audio.wav"
        # we keep voice at full, bed_mix will already have lower volume because we applied vol earlier
        mix_tracks([orig_audio, bed_mix], final_audio)

        # 7) attach final_audio to video (re-encode video to h264 + aac)
        # Trim/pad audio to exact duration to avoid mismatch
        run(f'ffmpeg -y -i "{inp}" -i "{final_audio}" -map 0:v -map 1:a -c:v libx264 -preset fast -crf 20 -c:a aac -b:a 192k -shortest "{out}"')
        print("Created:", out)

    finally:
        # don't remove tmpdir automatically in case user wants debug — print path
        print("Temporary files in:", tmpdir)
        print("If you want them removed, delete this folder when done.")

if __name__ == "__main__":
    main()
