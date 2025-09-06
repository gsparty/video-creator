# assemble_video.py
import subprocess, pathlib, sys, shutil, os, tempfile
from pathlib import Path

def run(cmd):
    print("RUN:", " ".join(cmd))
    subprocess.check_call(cmd)

def normalize_clip(infile, outfile, duration=4):
    # ensure vertical, 1080x1920, loop if shorter
    # -vf scale and crop/pad to 1080x1920 center
    cmd = [
        "ffmpeg", "-y", "-i", str(infile),
        "-vf", "scale=w=1080:h=1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "veryfast", "-t", str(duration),
        "-pix_fmt", "yuv420p", str(outfile)
    ]
    run(cmd)

def concat_clips(clip_files, out_concat):
    # create file list for concat demuxer
    listf = out_concat.with_suffix(".txt")
    with open(listf, "w", encoding="utf-8") as fh:
        for f in clip_files:
            fh.write(f"file '{str(Path(f).resolve()).replace('' ,'')}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listf), "-c", "copy", str(out_concat)]
    run(cmd)

def add_audio_and_overlay(video, audio, overlay_png, out_final):
    # map video + audio; overlay PNG centered third from top
    overlay_pos = "(main_w-overlay_w)/2:(main_h-overlay_h)/6"
    cmd = [
        "ffmpeg", "-y", "-i", str(video), "-i", str(audio), "-i", str(overlay_png),
        "-filter_complex", f"[0:v][2:v]overlay={overlay_pos}:format=auto,format=yuv420p",
        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-shortest", str(out_final)
    ]
    run(cmd)

def main(topic_folder, audiofile, overlay_png, outpath):
    p = Path(topic_folder)
    tmp = Path(tempfile.mkdtemp(prefix="assemble_"))
    try:
        # pick up to 3 clips from topic folder
        clips = sorted(p.glob("*.mp4"))[:3]
        if not clips:
            print("No clips found in", topic_folder)
            return
        norm_clips = []
        for i,c in enumerate(clips, start=1):
            out = tmp / f"{i:02d}.mp4"
            normalize_clip(c, out, duration=5)  # each segment 5s
            norm_clips.append(str(out))
        concat = tmp / "concat.mp4"
        concat_clips(norm_clips, concat)
        add_audio_and_overlay(concat, audiofile, overlay_png, outpath)
        print("Final:", outpath)
    finally:
        shutil.rmtree(tmp)

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: assemble_video.py <topic_folder> <audio.mp3> <overlay.png> <output.mp4>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
