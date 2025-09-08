# pexels_fetch.py
# pip: you already have requests via gTTS install; otherwise `pip install requests`
import os
import pathlib
import sys
import time
import urllib.parse

import requests

API_KEY = os.environ.get("PEXELS_API_KEY", "")  # set env var first
if not API_KEY:
    print("Set PEXELS_API_KEY env var (get it from https://www.pexels.com/api/)")
    sys.exit(1)

HEADERS = {"Authorization": API_KEY}
OUT = pathlib.Path("stock")
OUT.mkdir(exist_ok=True)

TOPICS = [
    "Top lifehack",
    "3-second kitchen trick",
    "Mind-blowing sports highlight",
    "Tiny gadget",
    "Quick fitness tip",
    "before after transformation",
    "Hidden phone feature",
    "weird food combo",
    "DIY home improvement",
    "travel hack",
]


def safe_name(s):
    return (
        "".join(c if c.isalnum() or c in " -_" else "_" for c in s)
        .strip()
        .replace(" ", "-")
    )


def fetch_videos_for_topic(topic, per_topic=3):
    q = topic + " vertical"
    params = {"query": q, "per_page": 15, "orientation": "portrait"}  # try portrait
    r = requests.get(
        "https://api.pexels.com/videos/search",
        params=params,
        headers=HEADERS,
        timeout=15,
    )
    if r.status_code != 200:
        print("Pexels error", r.status_code, r.text)
        return []
    data = r.json()
    videos = data.get("videos", [])
    out_dir = OUT / safe_name(topic)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for v in videos[:per_topic]:
        # choose the smallest vertical file that still is mp4
        files = v.get("video_files", [])
        # prefer 720x1280 or >=720 width
        candidate = None
        for f in sorted(
            files, key=lambda x: (x.get("width", 9999), x.get("height", 9999))
        ):
            if f.get("file_type") == "video/mp4":
                candidate = f
                break
        if not candidate:
            candidate = files[0] if files else None
        if not candidate:
            continue
        url = candidate["link"]
        fname = out_dir / (pathlib.Path(urllib.parse.urlparse(url).path).name)
        if fname.exists():
            saved.append(str(fname))
            continue
        try:
            print("Downloading", url)
            rr = requests.get(url, stream=True, timeout=60)
            rr.raise_for_status()
            with open(fname, "wb") as fh:
                for chunk in rr.iter_content(8192):
                    fh.write(chunk)
            saved.append(str(fname))
            time.sleep(0.5)
        except Exception as e:
            print("Failed to download", e)
    return saved


if __name__ == "__main__":
    for t in TOPICS:
        out = fetch_videos_for_topic(t, per_topic=3)
        print(t, "->", len(out), "files")
