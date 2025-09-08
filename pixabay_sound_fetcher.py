# pixabay_sound_fetcher.py
"""
Simple (best-effort) Pixabay audio scraper/downloader.
Usage:
  pip install requests beautifulsoup4
  python pixabay_sound_fetcher.py --keywords "stadium crowd" --label sports --limit 6
Notes:
  - Scraping is fragile. Use an API key if available.
  - Downloads to: assets/sounds/<label>/
"""
import argparse
import re
import subprocess
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path.cwd()
OUT_ROOT = ROOT / "assets" / "sounds"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) python-sound-fetcher",
}


def safe_get(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text


def download_url(url, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=HEADERS, stream=True, timeout=30) as r:
        r.raise_for_status()
        total = 0
        with open(out_path, "wb") as fh:
            for chunk in r.iter_content(8192):
                if not chunk:
                    continue
                fh.write(chunk)
                total += len(chunk)
    return out_path, total


def find_sound_pages_for_query(query, max_pages=2):
    # Pixabay sound search URL (best-effort)
    query_enc = requests.utils.quote(query)
    found = []
    for page in range(1, max_pages + 1):
        url = f"https://pixabay.com/sounds/search/{query_enc}/?pagi={page}"
        try:
            html = safe_get(url)
        except Exception as e:
            print("Failed to fetch search page:", url, e)
            break
        soup = BeautifulSoup(html, "html.parser")
        # sound cards link to /sounds/<slug>/
        for a in soup.select("a[href^='/sounds/']"):
            href = a.get("href")
            if href and href.startswith("/sounds/"):
                full = "https://pixabay.com" + href
                if full not in found:
                    found.append(full)
        time.sleep(0.8)
    return found


def extract_mp3_url_from_sound_page(page_url):
    try:
        html = safe_get(page_url)
    except Exception as e:
        print("  page fetch failed:", e)
        return None
    soup = BeautifulSoup(html, "html.parser")
    # look for <audio> or direct link to .mp3
    # try <audio> tags:
    audio = soup.find("audio")
    if audio:
        src = audio.get("src")
        if src and src.endswith(".mp3"):
            if src.startswith("/"):
                return "https://pixabay.com" + src
            return src
    # try source tags:
    source = soup.find("source")
    if source:
        s = source.get("src")
        if s and s.endswith(".mp3"):
            if s.startswith("/"):
                return "https://pixabay.com" + s
            return s
    # fallback: search for .mp3 in page text
    m = re.search(r'https?://[^\s\'"]+\.mp3', html)
    if m:
        return m.group(0)
    return None


def ffprobe_ok(path: Path):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.returncode == 0 and p.stdout.strip()


def fetch(query, label="default", limit=6):
    pages = find_sound_pages_for_query(query)
    print("Found sound pages:", len(pages))
    out_dir = OUT_ROOT / label
    out_dir.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    for page_url in pages:
        if downloaded >= limit:
            break
        print("Visiting:", page_url)
        mp3 = extract_mp3_url_from_sound_page(page_url)
        if not mp3:
            print("  no mp3 url found on page")
            continue
        fname = page_url.rstrip("/").split("/")[-1]
        out_path = out_dir / f"{label}-{fname}.mp3"
        try:
            print("  downloading mp3:", mp3)
            download_url(mp3, out_path)
            print("  saved ->", out_path)
            # validate with ffprobe
            if not ffprobe_ok(out_path):
                print("  ffprobe can't read file, deleting")
                out_path.unlink(missing_ok=True)
                continue
            downloaded += 1
        except Exception as e:
            print("  download failed:", e)
        time.sleep(1.0)
    print("Downloaded:", downloaded, "files to", out_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", required=True)
    parser.add_argument("--label", default="default")
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    fetch(args.keywords, label=args.label, limit=args.limit)
