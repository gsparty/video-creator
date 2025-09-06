# run_all.py
"""
Run the video_builder for multiple topics (generate N videos).
If GOOGLE_OAUTH_CLIENT_SECRETS (client_secrets.json) exists and you consent, uploads to YouTube using upload_youtube.py.
"""

import os, sys, json, subprocess, shutil
from pathlib import Path
import argparse
import time
import hashlib

ROOT = Path.cwd()
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True)

def slugify(s):
    return "".join(c if c.isalnum() else "-" for c in s).strip("-")[:60]

def generate_topics(count=10):
    # If OPENAI_API_KEY is available, generate topics via ChatGPT
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            import openai
            openai.api_key = api_key
            prompt = (
                "Give me a list of {} short trending topic headlines for short vertical videos. "
                "Return as a JSON array of strings only."
            ).format(count)
            resp = openai.ChatCompletion.create(
                model="gpt-4o-mini" if hasattr(openai, "ChatCompletion") else "gpt-4o-mini",
                messages=[{"role":"user","content":prompt}],
                max_tokens=600,
            )
            txt = resp["choices"][0]["message"]["content"]
            arr = json.loads(txt)
            if isinstance(arr, list) and arr:
                return arr[:count]
        except Exception:
            # fallback to builtin list
            pass

    # Fallback list (simple seed topics)
    seeds = [
        "Top lifehack you must know",
        "3-second kitchen trick",
        "Mind-blowing sports highlight",
        "Tiny gadget that changed my life",
        "Quick fitness tip for busy people",
        "Insane before/after transformation",
        "Hidden feature in your phone",
        "Weird food combo that works",
        "One-minute DIY home improvement",
        "Unexpected travel hack",
        "Pet reaction compilation idea",
    ]
    return seeds[:count]

def build_video_for_topic(topic, index, resolution=None):
    # call video_builder.py as subprocess with JSON arg format used earlier
    arg_json = json.dumps({"trends":[topic]})
    cmd = [sys.executable, str(ROOT / "video_builder.py"), arg_json]
    print(f"[run_all] Calling video_builder for topic #{index+1}: {topic}")
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    # video_builder writes autonomous_video.mp4 (per your current setup)
    src = ROOT / "autonomous_video.mp4"
    if not src.exists():
        raise FileNotFoundError("autonomous_video.mp4 not created by video_builder")
    slug = slugify(topic) or f"clip{index+1}"
    out_name = OUT_DIR / f"{index+1:02d}_{slug}.mp4"
    shutil.move(str(src), str(out_name))
    print(f"[run_all] Moved video to {out_name}")
    return out_name

def maybe_upload_to_youtube(video_path, title, desc, privacy="private"):
    # optional: only uploads if upload_youtube.py is present and client_secrets.json exists
    upload_script = ROOT / "upload_youtube.py"
    client = ROOT / "client_secrets.json"
    if not upload_script.exists() or not client.exists():
        print("[run_all] YouTube upload skipped (upload_youtube.py or client_secrets.json missing).")
        return False
    cmd = [sys.executable, str(upload_script), str(video_path), title, desc, privacy]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(proc.stdout)
    return proc.returncode == 0

def main(args):
    topics = generate_topics(args.count)
    print("[run_all] Topics:", topics)
    results = []
    for i, t in enumerate(topics):
        try:
            out = build_video_for_topic(t, i, resolution=args.resolution)
            results.append((t, out))
            if args.upload and args.youtube:
                title = t
                desc = f"Auto-generated video for: {t}"
                maybe_upload_to_youtube(out, title, desc, privacy=args.privacy)
        except Exception as e:
            print("[run_all] ERROR building topic:", t, e)
    print("[run_all] Done. Outputs in", OUT_DIR)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=10, help="How many videos to create")
    p.add_argument("--resolution", type=str, default=None, help="WxH e.g. 540x960 (not enforced by video_builder)")
    p.add_argument("--upload", action="store_true", help="Attempt YouTube upload if upload script + client_secrets.json are present")
    p.add_argument("--youtube", action="store_true", help="Also pass flag to call YouTube uploader (requires client_secrets.json)")
    p.add_argument("--privacy", type=str, default="private", help="YouTube privacy: public/private/unlisted")
    args = p.parse_args()
    main(args)
