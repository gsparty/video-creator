#!/usr/bin/env python3
"""
auto_short_full.py

Processes scraped/*.json items (or a single input file) and generates one vertical 1080x1920 short each.

Usage:
  cd C:\auto_video_agent
  # fetch first (or run fetch separately)
  python fetch_trends_to_scraped.py --endpoint "https://trends-scraper-555677311817.us-central1.run.app/scrape" --out scraped --max 10

  # then generate shorts for every file in scraped/
  python auto_short_full.py --input-dir scraped --out shorts --background assets/sounds/background.mp3 --whoosh assets/sounds/whoosh.wav --ending assets/sounds/ending.mp3 --sec 25

Notes:
 - Requires ffmpeg and edge-tts (optional but preferred) in PATH.
 - Pillow is required for slide generation (pip install Pillow)
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---- Tweakable params ----
VOICE = "en-US-AriaNeural"        # edge-tts voice
SILENCE_MS_BETWEEN_SENTENCES = 120  # ms
WHOOSH_PRE_MS = 120               # place whoosh this many ms before sentence start
WHOOSH_VOL = 0.9                  # whoosh amplitude multiplier (0..1) — raise to hear it
BED_VOL = 0.25                    # background bed base volume (0..1) — lower = quieter bed
VOICE_VOL = 1.0
ENDING_PRE_SEC = 1.0
TARGET_SAMPLE_RATE = 44100
TARGET_CHANNELS = 2

# ---------------------------
def run(cmd_list, check=True):
    print("CMD>", " ".join(cmd_list))
    res = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = res.stdout.decode(errors="replace")
    if res.returncode != 0 and check:
        raise RuntimeError(f"Command failed (rc={res.returncode}):\n{' '.join(cmd_list)}\n\n{out}")
    return out

def slugify(s):
    s = (s or "").strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s).strip("-").lower()
    return s[:100]

def split_sentences(text):
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r'([.?!]\s+|\n+)', text)
    sentences = []
    cur = ""
    for p in parts:
        if re.match(r'([.?!]\s+|\n+)', p):
            cur += p.strip()
            if cur.strip():
                sentences.append(cur.strip())
            cur = ""
        else:
            cur += p
    if cur.strip():
        sentences.append(cur.strip())
    if len(sentences) == 1 and len(sentences[0].split()) > 40:
        words = sentences[0].split()
        chunked = []
        chunk = []
        for w in words:
            chunk.append(w)
            if len(chunk) >= 10:
                chunked.append(" ".join(chunk) + ".")
                chunk = []
        if chunk:
            chunked.append(" ".join(chunk) + ".")
        sentences = chunked
    return [s for s in sentences if s]

def has_edge_tts():
    try:
        subprocess.run(["edge-tts", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

def tts_sentence_edge(text, out_mp3_path):
    # use list args to avoid shell quoting issues
    cmd = ["edge-tts", "--voice", VOICE, "--text", text, "--write-media", str(out_mp3_path)]
    run(cmd)
    return out_mp3_path

def tts_sentence_gtts(text, out_mp3_path):
    try:
        from gtts import gTTS
    except Exception as e:
        raise RuntimeError("gTTS not available (and edge-tts not available)") from e
    t = gTTS(text=text, lang="en")
    t.save(str(out_mp3_path))
    return out_mp3_path

def mp3_to_wav_pcm(in_mp3, out_wav):
    cmd = ["ffmpeg", "-y", "-i", str(in_mp3), "-ar", str(TARGET_SAMPLE_RATE), "-ac", str(TARGET_CHANNELS), "-c:a", "pcm_s16le", str(out_wav)]
    run(cmd)

def flavor_audio(in_wav, out_wav):
    af = "loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=80,lowpass=f=15000,acompressor=threshold=0.05:ratio=4:attack=5:release=100"
    cmd = ["ffmpeg","-y","-i", str(in_wav), "-af", af, "-ar", str(TARGET_SAMPLE_RATE), "-ac", str(TARGET_CHANNELS), str(out_wav)]
    run(cmd)

def create_silence(duration_sec, out_wav):
    cmd = ["ffmpeg","-y","-f","lavfi","-i",f"anullsrc=cl=stereo:r={TARGET_SAMPLE_RATE}","-t",str(duration_sec),"-ar",str(TARGET_SAMPLE_RATE),"-ac",str(TARGET_CHANNELS),str(out_wav)]
    run(cmd)

def build_voice_from_sentences(sentences, tmpdir, use_edge):
    wav_files = []
    durations = []
    for i, s in enumerate(sentences):
        mp3_tmp = tmpdir / f"sent-{i:02d}.mp3"
        wav_tmp = tmpdir / f"sent-{i:02d}.wav"
        flav = tmpdir / f"sent-{i:02d}.flav.wav"
        if use_edge and has_edge_tts():
            tts_sentence_edge(s, mp3_tmp)
        else:
            tts_sentence_gtts(s, mp3_tmp)
        mp3_to_wav_pcm(mp3_tmp, wav_tmp)
        flavor_audio(wav_tmp, flav)
        wav_files.append(flav)
        # duration
        dur_out = run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", str(flav)], check=False)
        try:
            durations.append(float(dur_out.strip().splitlines()[0]))
        except Exception:
            durations.append(0.0)
    # build concatenated voice_full by alternating sentences and short silence
    seq = []
    silence_file = tmpdir / "sil.wav"
    create_silence(SILENCE_MS_BETWEEN_SENTENCES/1000.0, silence_file)
    for i,f in enumerate(wav_files):
        seq.append(str(f))
        if i != len(wav_files)-1:
            seq.append(str(silence_file))
    if not seq:
        # empty
        empty = tmpdir / "voice_empty.wav"
        create_silence(0.1, empty)
        return empty, []
    # Prepare ffmpeg arguments: add all inputs and a filter_complex concat
    inputs = []
    for p in seq:
        inputs += ["-i", p]
    n = len(seq)
    concat_filter = "".join([f"[{i}:a]" for i in range(n)]) + f"concat=n={n}:v=0:a=1[aout]"
    out_full = tmpdir / "voice_full.wav"
    cmd = ["ffmpeg","-y"] + inputs + ["-filter_complex", concat_filter, "-map", "[aout]", "-ar", str(TARGET_SAMPLE_RATE), "-ac", str(TARGET_CHANNELS), str(out_full)]
    run(cmd)
    return out_full, durations

def make_bed_loop(background_path, target_sec, out_wav):
    if background_path and Path(background_path).exists():
        cmd = ["ffmpeg","-y","-stream_loop","-1","-i", str(background_path), "-t", str(target_sec), "-ar", str(TARGET_SAMPLE_RATE), "-ac", str(TARGET_CHANNELS), str(out_wav)]
        run(cmd)
    else:
        create_silence(target_sec, out_wav)
    return out_wav

def build_whooshes_track(whoosh_path, sentence_starts, tmpdir, target_sec, whoosh_vol=WHOOSH_VOL, whoosh_pre_ms=WHOOSH_PRE_MS):
    if not whoosh_path or not Path(whoosh_path).exists() or not sentence_starts:
        silent = tmpdir / "whooshes_silent.wav"
        create_silence(target_sec, silent)
        return silent
    # For each start time prepare a -i whoosh and apply adelay to place it
    inputs = []
    adelay_parts = []
    for idx, st in enumerate(sentence_starts):
        inputs += ["-i", str(whoosh_path)]
        ms = int(max(0, (st * 1000.0) - whoosh_pre_ms))
        adelay_parts.append(f"[{idx}:a]adelay={ms}|{ms}:all=1,volume={whoosh_vol}[w{idx}]")
    wh_list = "".join([f"[w{idx}]" for idx in range(len(sentence_starts))])
    amix_part = f"{wh_list}amix=inputs={len(sentence_starts)}:duration=first:dropout_transition=0[whoosh_mix]"
    filter_complex = ";".join(adelay_parts + [amix_part])
    out_who = tmpdir / "whooshes_all.wav"
    cmd = ["ffmpeg","-y"] + inputs + ["-filter_complex", filter_complex, "-map", "[whoosh_mix]", "-t", str(target_sec), "-ar", str(TARGET_SAMPLE_RATE), "-ac", str(TARGET_CHANNELS), str(out_who)]
    run(cmd)
    return out_who

def mix_voice_whoosh_bed(voice_full, whooshes_all, bed_loop, out_final, target_sec):
    tmp_voice_with_sfx = out_final.with_suffix(".voice_with_sfx.wav")
    # mix voice+whoosh -> voice_with_sfx
    run(["ffmpeg","-y","-i", str(voice_full), "-i", str(whooshes_all),
         "-filter_complex", f"[0:a]volume={VOICE_VOL}[v];[1:a]volume=1.0[w];[v][w]amix=inputs=2:duration=first:dropout_transition=0[aout]",
         "-map","[aout]","-t",str(target_sec),"-ar",str(TARGET_SAMPLE_RATE),"-ac",str(TARGET_CHANNELS), str(tmp_voice_with_sfx)])
    # Duck bed using sidechaincompress (bed first, voice second)
    tmp_ducked = out_final.with_suffix(".ducked.tmp.wav")
    try:
        run(["ffmpeg","-y","-i", str(bed_loop), "-i", str(tmp_voice_with_sfx),
             "-filter_complex", f"[0:a]volume={BED_VOL}[bed];[bed][1:a]sidechaincompress=threshold=0.08:ratio=10:attack=5:release=200[bed_duck];[bed_duck][1:a]amix=inputs=2:duration=first:dropout_transition=0[aout]",
             "-map","[aout]","-t",str(target_sec),"-ar",str(TARGET_SAMPLE_RATE),"-ac",str(TARGET_CHANNELS), str(tmp_ducked)])
    except Exception as e:
        # fallback: simply reduce bed volume more strongly and mix
        print("[warning] sidechaincompress failed, falling back to simpler ducking:", e)
        run(["ffmpeg","-y","-i", str(bed_loop), "-i", str(tmp_voice_with_sfx),
             "-filter_complex", f"[0:a]volume={max(0.02, BED_VOL*0.35)}[bed];[1:a]volume=1.0[voice];[bed][voice]amix=inputs=2:duration=first:dropout_transition=0[aout]",
             "-map","[aout]","-t",str(target_sec),"-ar",str(TARGET_SAMPLE_RATE),"-ac",str(TARGET_CHANNELS), str(tmp_ducked)])
    # final loudness normalization
    run(["ffmpeg","-y","-i", str(tmp_ducked), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-t",str(target_sec), "-ar",str(TARGET_SAMPLE_RATE), "-ac",str(TARGET_CHANNELS), str(out_final)])
    return out_final

def text_size(draw, text, font):
    # cross-version Pillow safe text size using textbbox
    bbox = draw.textbbox((0,0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return w, h

def create_slide_image_pillow(out_png, title):
    W, H = 1080, 1920
    bg = Image.new("RGB", (W,H), (12,12,16))
    draw = ImageDraw.Draw(bg)
    # try some fonts
    font_paths = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ]
    font = None
    for p in font_paths:
        try:
            if Path(p).exists():
                font = ImageFont.truetype(p, 72)
                break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    # wrap title
    max_w = W - 140
    words = title.split()
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        tw, th = text_size(draw, test, font)
        if tw <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    # draw lines centered
    y = H//4
    for line in lines[:6]:
        tw, th = text_size(draw, line, font)
        draw.text(((W-tw)//2, y), line, font=font, fill=(255,255,255))
        y += th + 12
    out_png.parent.mkdir(parents=True, exist_ok=True)
    bg.save(str(out_png))
    return out_png

def render_final_video(input_video, final_audio, out_path, target_sec, title=None):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if input_video and Path(input_video).exists():
        # scale/pad to vertical 1080x1920 (fit & pad)
        vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1"
        cmd = ["ffmpeg","-y","-i", str(input_video), "-i", str(final_audio),
               "-map","0:v","-map","1:a","-c:v","libx264","-preset","fast","-crf","20","-vf", vf,
               "-c:a","aac","-b:a","192k","-shortest", str(out_path)]
        run(cmd)
    else:
        # create slide image and combine with audio
        tmp_img = out_path.with_suffix(".png")
        create_slide_image_pillow(tmp_img, title or "Short update")
        cmd1 = ["ffmpeg","-y","-loop","1","-i", str(tmp_img), "-i", str(final_audio),
                "-c:v","libx264","-t", str(target_sec), "-pix_fmt","yuv420p", "-c:a","aac","-b:a","192k","-shortest", str(out_path)]
        run(cmd1)

def process_one_item(item_json_path, out_dir, background, whoosh, ending, target_sec):
    tmpdir = Path(tempfile.mkdtemp(prefix="shorttmp_"))
    print("Temp dir:", tmpdir)
    tmpdir.mkdir(parents=True, exist_ok=True)

    data = json.loads(Path(item_json_path).read_text(encoding="utf-8"))
    title = data.get("title") or data.get("text") or Path(item_json_path).stem
    topic = title
    print("Topic/title:", topic)
    # generate script using script_generator if present
    try:
        import importlib
        sg = importlib.import_module("script_generator")
        if hasattr(sg, "generate_script"):
            script = sg.generate_script(topic)
        else:
            script = f"{topic}. Quick recap: What happened in one line. Why it matters right now — key consequence. Call to action: follow for more."
    except Exception:
        script = f"{topic}. Quick recap: What happened in one line. Why it matters right now — key consequence. Call to action: follow for more."

    print("Script:", script)
    sentences = split_sentences(script)
    print("Sentences:", sentences)
    if not sentences:
        sentences = [script]

    # TTS per sentence
    use_edge = has_edge_tts()
    voice_full, sent_durs = build_voice_from_sentences(sentences, tmpdir, use_edge=use_edge)
    # compute sentence start times
    starts = []
    cur = 0.0
    for d in sent_durs:
        starts.append(cur)
        cur += (d or 0.0) + (SILENCE_MS_BETWEEN_SENTENCES/1000.0)
    total_voice_dur = float(run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", str(voice_full)], check=False).strip() or 0.0)
    target = float(target_sec)
    if total_voice_dur > target:
        target = total_voice_dur + 0.5
        print("[note] voice > target, extended target to", target)

    # bed loop
    bed_loop = tmpdir / "bed_loop.wav"
    make_bed_loop(background, target, bed_loop)

    # whooshes placement
    whooshes_all = build_whooshes_track(Path(whoosh) if whoosh else None, starts, tmpdir, target, whoosh_vol=WHOOSH_VOL, whoosh_pre_ms=WHOOSH_PRE_MS)

    # ending placement
    ending_placed = tmpdir / "ending_placed.wav"
    if ending and Path(ending).exists():
        end_dur_out = run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", str(ending)], check=False)
        try:
            end_dur = float(end_dur_out.strip().splitlines()[0])
        except Exception:
            end_dur = 1.0
        place_at = max(0.0, target - end_dur - ENDING_PRE_SEC)
        delay_ms = int(place_at * 1000.0)
        # use adelay to place the ending and produce placed wav of length target
        run(["ffmpeg","-y","-i", str(ending), "-af", f"adelay={delay_ms}|{delay_ms},volume=1.0", "-t", str(target), "-ar", str(TARGET_SAMPLE_RATE), "-ac", str(TARGET_CHANNELS), str(ending_placed)])
    else:
        create_silence(target, ending_placed)

    # combine whooshes + ending into sfx_combined
    sfx_combined = tmpdir / "sfx_combined.wav"
    run(["ffmpeg","-y","-i", str(whooshes_all), "-i", str(ending_placed),
         "-filter_complex", "[0:a]volume=1.0[a0];[1:a]volume=1.0[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]",
         "-map","[aout]","-t",str(target), "-ar",str(TARGET_SAMPLE_RATE), "-ac",str(TARGET_CHANNELS), str(sfx_combined)])

    # mix voice + sfx + duck bed -> final_audio
    final_audio = Path(out_dir) / f"{int(time.time())}-{slugify(topic)}.final_audio.wav"
    mix_voice_whoosh_bed(voice_full, sfx_combined, bed_loop, final_audio, target)
    # render final video (no input video given in scraped items by default)
    out_mp4 = Path(out_dir) / f"{int(time.time())}-{slugify(topic)}.mp4"
    render_final_video(None, final_audio, out_mp4, target, title=topic)
    print("Created:", out_mp4)
    print("Temp dir (retain for debug):", tmpdir)
    return out_mp4

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", dest="input_dir", required=False, help="Directory with scraped JSON files")
    ap.add_argument("--input", dest="input", required=False, help="Single input JSON or video (optional)")
    ap.add_argument("--out", dest="out", required=True, help="Output dir for shorts")
    ap.add_argument("--background", dest="background", required=False, help="Background bed (mp3)")
    ap.add_argument("--whoosh", dest="whoosh", required=False, help="Whoosh sfx (wav/mp3)")
    ap.add_argument("--ending", dest="ending", required=False, help="Ending sfx (mp3)")
    ap.add_argument("--sec", dest="sec", type=float, default=25.0)
    args = ap.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    if args.input:
        # single file: accept JSON or direct video
        p = Path(args.input)
        if p.suffix.lower() == ".json":
            process_one_item(p, out_root, args.background, args.whoosh, args.ending, args.sec)
        else:
            # treat as single video file (wrap into slide/replace audio)
            fake = {"title": p.stem, "text": p.stem}
            tmp_json = Path(tempfile.mkdtemp()) / f"{int(time.time())}-{slugify(p.stem)}.json"
            tmp_json.write_text(json.dumps(fake, ensure_ascii=False), encoding="utf-8")
            process_one_item(tmp_json, out_root, args.background, args.whoosh, args.ending, args.sec)
    elif args.input_dir:
        d = Path(args.input_dir)
        if not d.exists():
            print("[error] --input-dir not found:", args.input_dir)
            sys.exit(1)
        files = sorted([p for p in d.glob("*.json")])
        if not files:
            print("[info] no json files in", d)
            return
        for f in files:
            try:
                process_one_item(f, out_root, args.background, args.whoosh, args.ending, args.sec)
                # move or rename processed file so we don't process again
                processed_dir = d / "processed"
                processed_dir.mkdir(exist_ok=True)
                f.rename(processed_dir / f.name)
            except Exception as e:
                print("Error processing", f, e)
    else:
        print("Please pass --input-dir or --input")
        sys.exit(1)

if __name__ == "__main__":
    main()
