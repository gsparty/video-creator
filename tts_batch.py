# tts_batch.py
# Usage: python tts_batch.py outputs_dir
import pathlib
import sys

from gtts import gTTS


def find_script_for_video(video_path):
    p = pathlib.Path(video_path)
    txt_candidates = [p.with_suffix(".txt"), p.parent / (p.stem + ".txt")]
    for t in txt_candidates:
        if t.exists():
            return t.read_text(encoding="utf8").strip()
    # fallback: use slug/filename as text
    return p.stem.replace("_", " ").replace("-", " ")


def main(outputs_dir):
    p = pathlib.Path(outputs_dir)
    mp4s = sorted(p.glob("*.mp4"))
    if not mp4s:
        print("No mp4 files found in", outputs_dir)
        return
    for v in mp4s:
        script = find_script_for_video(v)
        out_mp3 = v.with_suffix(".tts.mp3")
        if out_mp3.exists():
            print("Skipping (exists):", out_mp3.name)
            continue
        print("TTS for", v.name)
        try:
            tts = gTTS(script, lang="en")
            tts.save(str(out_mp3))
            print("Wrote", out_mp3.name)
        except Exception as e:
            print("TTS error for", v.name, ":", e)


if __name__ == "__main__":
    outdir = sys.argv[1] if len(sys.argv) > 1 else "outputs"
    main(outdir)
