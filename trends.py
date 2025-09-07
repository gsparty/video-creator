# trends.py
from typing import List

import requests

from config import TRENDS_URL


def fetch_trends() -> List[str]:
    """
    Fetch top trends from the configured scraper function.
    Accepts multiple JSON shapes and returns a cleaned list of strings.
    """
    try:
        r = requests.get(TRENDS_URL, timeout=20)
        print(f"DEBUG: fetched trends URL {TRENDS_URL} -> HTTP {r.status_code}")
        raw = r.text[:2000] if r.text else ""
        print("DEBUG: raw body (first 2000 chars):", raw)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("ERROR: could not fetch trends:", e)
        return []

    # Accept many possible shapes:
    topics = []
    if isinstance(data, list):
        topics = data
    elif isinstance(data, dict):
        # common names
        for key in ("trends", "topics", "results", "data"):
            v = data.get(key)
            if v:
                topics = v
                break
        # fallback: maybe direct dict of index->value
        if not topics:
            # try to find the first list inside the dict
            for v in data.values():
                if isinstance(v, list):
                    topics = v
                    break
    else:
        print("DEBUG: unexpected trends JSON shape:", type(data))

    # Normalize items to strings, de-dupe while preserving order
    clean = []
    seen = set()
    for t in topics or []:
        if not t:
            continue
        s = str(t).strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        clean.append(s)
    if not clean:
        print("DEBUG: parsed no topics from response.")
    else:
        print(f"DEBUG: parsed {len(clean)} trends: {clean[:10]}")
    return clean[:10]
