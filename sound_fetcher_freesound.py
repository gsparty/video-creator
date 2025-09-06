# sound_fetcher_freesound.py
"""
Fetch beds/sfx from Freesound using the v2 API.
Usage examples:
  # immediate (pass API key directly)
  python sound_fetcher_freesound.py --api-key "YOUR_KEY" --keywords "stadium crowd cheer" --label sports --mode beds --limit 6

  # or using .env (create a file named .env with FREESOUND_API_KEY=...)
  python sound_fetcher_freesound.py --keywords "stadium crowd cheer" --label sports --mode beds --limit 6

Requirements:
  pip install requests python-dotenv
"""
import os
import time
import argparse
from pathlib import Path
import requests
import subprocess

# optional: load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()  # loads .env into environment if exists
except Exception:
    pass

def ffprobe_ok(p: Path) -> bool:
    cmd = ["ffprobe", "-v", "error",
           "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(p)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())

def search_and_download(query: str, label: str, api_key: str, mode="beds", limit=6, min_dur=5.0, max_dur=300.0):
    endpoint = "https://freesound.org/apiv2/search/text/"
    headers = {"Authorization": f"Token {api_key}"}
    params = {
        "query": query,
        "filter": f"duration:[{min_dur} TO {max_dur}]",
        "page_size": 20,
        "fields": "id,name,previews,duration",
    }
    ROOT = Path.cwd()
    out_dir = ROOT / "assets" / "sounds" / label / ("beds" if mode == "beds" else "sfx")
    out_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    page = 1
    while downloaded < limit:
        params["page"] = page
        try:
            r = requests.get(endpoint, headers=headers, params=params, timeout=20)
            r.raise_for_status()
        except Exception as e:
            print("Freesound request failed:", e)
            return
        j = r.json()
        results = j.get("results", [])
        if not results:
            print("No results returned from Freesound. Try different keywords or expand duration range.")
            break
        for item in results:
            if downloaded >= limit:
                break
            previews = item.get("previews", {})
            mp3_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
            if not mp3_url:
                continue
            # safe filename
            safe_name = f"{label}-{item['id']}-{Path(item['name']).stem}".replace(" ", "_")
            out_path = out_dir / f"{safe_name}.mp3"
            if out_path.exists():
                print("Already have", out_path, "-> skipping")
                downloaded += 1
                continue
            try:
                print("Downloading", mp3_url)
                with requests.get(mp3_url, stream=True, timeout=30) as rr:
                    rr.raise_for_status()
                    with open(out_path, "wb") as fh:
                        for chunk in rr.iter_content(8192):
                            if chunk:
                                fh.write(chunk)
                # quick validate
                if not ffprobe_ok(out_path):
                    print("Downloaded file failed ffprobe, removing:", out_path)
                    out_path.unlink(missing_ok=True)
                    continue
                print("Saved:", out_path)
                downloaded += 1
            except Exception as e:
                print("Download/validate failed for", mp3_url, ":", e)
        if not j.get("next"):
            break
        page += 1
        time.sleep(1.0)
    print("Downloaded total:", downloaded, "to", out_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", required=True)
    parser.add_argument("--label", default="default")
    parser.add_argument("--mode", choices=["beds", "sfx"], default="beds")
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--min-dur", type=float, default=5.0)
    parser.add_argument("--max-dur", type=float, default=300.0)
    parser.add_argument("--api-key", type=str, default=None, help="Freesound API key (optional). If not given, reads FREESOUND_API_KEY from env or .env")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("FREESOUND_API_KEY")
    if not api_key:
        print("Set FREESOUND_API_KEY in your environment or pass --api-key. Exiting.")
        raise SystemExit(1)

    search_and_download(args.keywords, args.label, api_key, mode=args.mode, limit=args.limit, min_dur=args.min_dur, max_dur=args.max_dur)
