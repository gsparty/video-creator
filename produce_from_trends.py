"""
produce_from_trends.py

Fetch /scrape from your local trends-scraper and produce short videos using short_maker.generate_short.

Usage (PowerShell):
  cd C:\auto_video_agent
  .\venv\Scripts\Activate.ps1
  python produce_from_trends.py --count 3

Assumptions:
 - Node server (http://127.0.0.1:8080) is running and /scrape returns JSON { trends: [...] }.
 - short_maker.py is importable and has generate_short(title) -> path (as in your tests).
 - Adjust PYTRENDS/Node host via --server if different.
"""

import requests
import time
import argparse
import logging
import os
from pathlib import Path

# Import your generate_short function (adjust if your short_maker API differs)
try:
    from short_maker import generate_short
except Exception as e:
    raise SystemExit("Cannot import generate_short from short_maker.py: " + str(e))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [produce] %(levelname)s %(message)s")

DEFAULT_SERVER = os.environ.get("SCRAPER_SERVER", "http://127.0.0.1:8080")

def fetch_trends(server=DEFAULT_SERVER, timeout=15):
    url = server.rstrip("/") + "/scrape"
    logging.info("Fetching trends from %s", url)
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        return data.get("trends", [])
    except Exception as e:
        logging.exception("Failed to fetch trends: %s", e)
        return []

def select_trends(trends, count=3, min_interest=5, min_spike=1.0, prefer_source=None):
    """
    Filter + sort trends for likely-viewable topics.
    - prefer entries with interest >= min_interest OR spike >= min_spike
    - then sort by tuned_score or interest+spike
    """
    # ensure each entry has numeric interest/spike and a score fallback
    prepared = []
    for t in trends:
        try:
            interest = float(t.get("interest") or 0)
        except Exception:
            interest = 0.0
        try:
            spike = float(t.get("spike") or 0)
        except Exception:
            spike = 0.0
        score = float(t.get("tuned_score") or t.get("baseScore") or (interest + spike*10) or 0)
        prepared.append((t, interest, spike, score))

    # prefer items that meet thresholds
    filtered = [p for p in prepared if (p[1] >= min_interest or p[2] >= min_spike)]
    if not filtered:
        # relax thresholds if nothing
        filtered = prepared

    # optionally prefer a source
    if prefer_source:
        filtered.sort(key=lambda x: (0 if x[0].get("source")==prefer_source else 1, -x[3], -x[1], -x[2]))
    else:
        filtered.sort(key=lambda x: (-x[3], -x[1], -x[2]))

    selected = [p[0] for p in filtered[:count]]
    return selected

def produce_shorts_for_trends(trends, delay_between=3, dry_run=False):
    results = []
    for t in trends:
        title = t.get("cleaned") or t.get("topic") or t.get("original") or ""
        if not title:
            logging.warning("Skipping trend with no usable title: %s", t)
            continue
        logging.info("Producing short for: %s", title)
        try:
            if dry_run:
                res = {"title": title, "status": "dry-run"}
            else:
                out = generate_short(title)
                res = {"title": title, "status": "ok", "output": out}
            results.append(res)
        except Exception as e:
            logging.exception("Failed to produce short for %s: %s", title, e)
            results.append({"title": title, "status": "error", "error": str(e)})
        logging.info("Sleeping %s seconds before next job", delay_between)
        time.sleep(delay_between)
    return results

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--server", default=DEFAULT_SERVER, help="Scraper server base url (default http://127.0.0.1:8080)")
    p.add_argument("--count", type=int, default=3, help="How many top trends to produce")
    p.add_argument("--min-interest", type=float, default=12.0, help="Filter: minimum interest to consider")
    p.add_argument("--min-spike", type=float, default=1.2, help="Filter: minimum spike to consider")
    p.add_argument("--delay", type=int, default=3, help="Seconds between jobs")
    p.add_argument("--dry-run", action="store_true", help="Don't call generate_short, just show")
    args = p.parse_args()

    trends = fetch_trends(server=args.server)
    if not trends:
        logging.error("No trends returned, exiting.")
        return

    selected = select_trends(trends, count=args.count, min_interest=args.min_interest, min_spike=args.min_spike)
    logging.info("Selected %d trends: %s", len(selected), [s.get("cleaned") or s.get("topic") for s in selected])

    results = produce_shorts_for_trends(selected, delay_between=args.delay, dry_run=args.dry_run)
    logging.info("Done. Results:\n%s", results)

if __name__ == "__main__":
    main()
