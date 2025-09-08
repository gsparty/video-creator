#!/usr/bin/env python3
"""
fetch_trends_to_scraped.py

Usage:
  python fetch_trends_to_scraped.py --endpoint "https://<your-service>/scrape" --out scraped --max 10

Saves files like scraped/20250826-153000-<slug>.json
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

import requests


def slugify(s):
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    return s[:80].strip("-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True, help="full /scrape endpoint URL")
    ap.add_argument(
        "--out", required=True, help="output directory to write scraped items"
    )
    ap.add_argument("--max", type=int, default=10, help="max trends to fetch")
    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    print("Fetching", args.endpoint)
    resp = requests.get(args.endpoint, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if not data or "trends" not in data:
        raise RuntimeError(f"Unexpected response: {data}")

    trends = data["trends"][: args.max]
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    for i, t in enumerate(trends):
        topic = (
            t.get("topic") or t.get("cleaned") or t.get("original") or f"topic-{i+1}"
        )
        safe = slugify(topic)
        filename = outdir / f"{timestamp}-{i+1:02d}-{safe}.json"
        item = {
            "topic": topic,
            "original": t.get("original"),
            "meta": t,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        }
        with open(filename, "w", encoding="utf-8") as fh:
            json.dump(item, fh, ensure_ascii=False, indent=2)
        print("Wrote", filename)
    print("Done. Wrote", len(trends), "items to", outdir)


if __name__ == "__main__":
    main()
