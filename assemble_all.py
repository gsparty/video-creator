# assemble_all.py
"""
Batch assemble: for every topic index in outputs/ (NN_Title.mp4),
look for stock/<safe-topic>/ . If clips exist, call assemble_video.py to create
<NN>_..._enhanced.mp4. Otherwise fallback to placeholder base mp4.
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(".").resolve()
OUT = ROOT / "outputs"
STOCK = ROOT / "stock"


def safe_topic_from_filename(name):
    # remove prefix like "01_" and extension
    base = pathlib.Path(name).stem
    # base may be "01_Top-lifehack-you-must-know"
    return base


def call_assemble(topic_folder, audiofile, overlay_png, out_final):
    cmd = [
        sys.executable,
        str(ROOT / "assemble_video.py"),
        str(topic_folder),
        str(audiofile),
        str(overlay_png),
        str(out_final),
    ]
    try:
        print("CALL:", " ".join(cmd))
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError as e:
        print("assemble failed:", e)
        return False


def main():
    mp4s = sorted(OUT.glob("[0-9][0-9]_*.mp4"))
    summary = []
    for mp in mp4s:
        topic = safe_topic_from_filename(mp.name)
        mp.name.split("_", 1)[0]
        print("Processing:", mp.name)
        # audio and overlay naming conventions used in your outputs
        audio = OUT / f"{mp.stem}.tts.mp3"
        overlay = OUT / f"{mp.stem}_with_audio_overlay.png"
        out_enh = OUT / f"{mp.stem}_enhanced.mp4"

        topic_stock_dir = STOCK / topic
        use_stock = topic_stock_dir.exists() and any(topic_stock_dir.glob("*.mp4"))

        if use_stock:
            print("Found stock clips:", topic_stock_dir)
            src_folder = topic_stock_dir
        else:
            print(
                "No stock clips for", topic, "- falling back to placeholder clip:", mp
            )
            # create a tiny "stock" folder with single placeholder so assemble_video can work
            tmp_folder = OUT / f"tmp_stock_for_{topic}"
            tmp_folder.mkdir(exist_ok=True)
            # copy placeholder to tmp folder as 01_placeholder.mp4
            tmp_pl = tmp_folder / "placeholder.mp4"
            if not tmp_pl.exists():
                # copy original placeholder mp (the base mp)
                src = mp
                import shutil

                shutil.copyfile(src, tmp_pl)
            src_folder = tmp_folder

        if not audio.exists():
            print(
                "WARNING: audio not found, will use placeholder silent audio if needed"
            )
            # assemble_video expects a real audio file — you can create a short silent mp3 or skip
            # For now, fail-safe: create a 1s silent mp3 via ffmpeg if missing
            sil = OUT / f"{mp.stem}.tts.mp3"
            if not sil.exists():
                print("Creating 1s silent audio:", sil)
                subprocess.check_call(
                    [
                        "ffmpeg",
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=channel_layout=stereo:sample_rate=44100",
                        "-t",
                        "1",
                        "-q:a",
                        "9",
                        "-acodec",
                        "libmp3lame",
                        str(sil),
                    ]
                )
            audio = sil

        if not overlay.exists():
            print(
                "Overlay PNG not found, creating a simple one from title text using overlay_png.py"
            )
            # Attempt to create overlay via overlay_png.py (if present)
            title = mp.stem.split("_", 1)[1] if "_" in mp.stem else mp.stem
            try:
                subprocess.check_call(
                    [
                        sys.executable,
                        str(ROOT / "overlay_png.py"),
                        title,
                        str(OUT / f"{mp.stem}_with_audio_overlay.png"),
                        "1080",
                        "1920",
                        "120",
                    ]
                )
                overlay = OUT / f"{mp.stem}_with_audio_overlay.png"
            except Exception as e:
                print("Could not create overlay PNG:", e)

        ok = call_assemble(src_folder, audio, overlay, out_enh)
        summary.append(
            (
                mp.name,
                "stock" if use_stock else "placeholder",
                str(out_enh) if ok else "FAILED",
            )
        )

    print("\nSummary:")
    for s in summary:
        print(*s)


if __name__ == "__main__":
    main()
