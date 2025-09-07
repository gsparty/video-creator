# overlay_all.py
# Usage: python overlay_all.py outputs_dir
import pathlib
import subprocess
import sys

PYTHON_EXE = None  # leave None to use system 'python' command; set to venv path if desired

def run(cmd):
    print("RUN:", " ".join(cmd))
    subprocess.run(cmd, check=True)

def make_overlay_for(video_path, headline, w=1080, h=1920, fontsize=120):
    vp = pathlib.Path(video_path)
    overlay_png = vp.with_name(vp.stem + "_overlay.png")
    py = PYTHON_EXE or (sys.executable)
    run([py, str(pathlib.Path(__file__).parent / "overlay_png.py"),
         headline, str(overlay_png), str(w), str(h), str(fontsize)])
    return overlay_png

def attach_audio(video_path, audio_path):
    vp = pathlib.Path(video_path)
    out = vp.with_name(vp.stem + "_with_audio.mp4")
    cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
           "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)]
    run(cmd)
    return out

def composite(video_path, overlay_png):
    vp = pathlib.Path(video_path)
    final = vp.with_name(vp.stem + "_final.mp4")
    cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(overlay_png),
           "-filter_complex", "overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/6",
           "-c:v", "libx264", "-crf", "23", "-preset", "medium", "-c:a", "aac", str(final)]
    run(cmd)
    return final

def main(outputs_dir):
    p = pathlib.Path(outputs_dir)
    mp4s = sorted(p.glob("*.mp4"))
    for v in mp4s:
        # skip already-final files
        if v.stem.endswith("_final") or v.stem.endswith("_with_audio"):
            continue
        print("Processing:", v.name)
        # pick headline: try .txt, else use filename
        txt = v.with_suffix(".txt")
        if txt.exists():
            headline = txt.read_text(encoding='utf8').strip().splitlines()[0][:200]
        else:
            headline = v.stem.replace('_',' ').replace('-', ' ')
        # 1) attach audio if tts exists
        tts = v.with_suffix(".tts.mp3")
        working_video = v
        if tts.exists():
            print("Attaching audio", tts.name)
            working_video = attach_audio(v, tts)
        # 2) make overlay PNG
        overlay = make_overlay_for(working_video, headline)
        # 3) composite
        final = composite(working_video, overlay)
        print("Final:", final)
    print("Done.")

if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv)>1 else "outputs"
    main(outdir)
