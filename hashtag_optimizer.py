# hashtag_optimizer.py
import csv
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config import GOOGLE_SERVICE_ACCOUNT_JSON, SHEET_ID, SHEET_NAME, TOKENS_DIR

import re
import sys

# Simple hashtag optimizer
def optimize_hashtags(text: str, max_tags: int = 8):
    # Split words, clean, lowercase
    words = re.findall(r"\w+", text.lower())
    unique = list(dict.fromkeys(words))  # preserve order, dedupe
    tags = [f"#{w}" for w in unique if len(w) > 2]  # skip tiny words
    # Always add shorts + trending
    tags.extend(["#shorts", "#trending"])
    return tags[:max_tags]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python hashtag_optimizer.py 'your text here'")
    else:
        text = " ".join(sys.argv[1:])
        tags = optimize_hashtags(text)
        print("Optimized hashtags:", " ".join(tags))

# Scopes and constants
SCOPES_SHEETS = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
TOKENS_PATH = Path(TOKENS_DIR) / "youtube_token.json"

def open_sheet():
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError("SERVICE_ACCOUNT_FILE/GOOGLE_SERVICE_ACCOUNT_JSON not set")
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SERVICE_ACCOUNT_JSON, SCOPES_SHEETS)
    gc = gspread.authorize(creds)
    if SHEET_ID:
        sh = gc.open_by_key(SHEET_ID)
    else:
        sh = gc.open(SHEET_NAME)
    ws = sh.sheet1
    return ws

def parse_rows(ws):
    rows = ws.get_all_records()
    return rows

def extract_video_id(url: str) -> str:
    if not url:
        return ""
    # Common patterns
    m = re.search(r"(?:v=|youtu\.be/|/embed/)([A-Za-z0-9_-]{6,})", url)
    if m:
        return m.group(1)
    # fallback: last path segment
    parts = url.rstrip("/").split("/")
    if parts:
        candidate = parts[-1]
        if len(candidate) >= 6:
            return candidate
    return ""

def yt_client_from_token():
    if not TOKENS_PATH.exists():
        raise RuntimeError("YouTube token not found. Run an authenticated upload once to create tokens/youtube_token.json")
    creds = Credentials.from_authorized_user_file(str(TOKENS_PATH), scopes=["https://www.googleapis.com/auth/youtube.readonly"])
    return build("youtube", "v3", credentials=creds)

def fetch_view_counts_for_ids(youtube, ids: List[str]) -> Dict[str, int]:
    out = {}
    # YouTube API allows up to 50 ids per request
    for i in range(0, len(ids), 50):
        batch = ids[i:i+50]
        resp = youtube.videos().list(part="statistics", id=",".join(batch)).execute()
        for item in resp.get("items", []):
            vid = item.get("id")
            stats = item.get("statistics", {})
            views = int(stats.get("viewCount", 0))
            out[vid] = views
        time.sleep(0.1)
    return out

def aggregate_hashtags(rows) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Return:
      - tag_to_videoids: map hashtag -> list of video ids (from YouTubeURL column)
      - tag_to_rows: map hashtag -> list of row timestamps or topics (for debugging)
    """
    tag_to_vids = defaultdict(list)
    tag_to_rows = defaultdict(list)
    for r in rows:
        caption = r.get("Caption") or r.get("caption") or r.get("Caption ") or ""
        yt = r.get("YouTubeURL") or r.get("YouTube Url") or ""
        vid = extract_video_id(yt)
        tags = re.findall(r"#(\w+)", caption)
        for t in tags:
            if vid:
                tag_to_vids[t.lower()].append(vid)
            tag_to_rows[t.lower()].append(r.get("Topic") or r.get("topic") or "")
    return tag_to_vids, tag_to_rows

def compute_stats(tag_to_vids: Dict[str, List[str]], youtube) -> List[Tuple[str,int,int,float]]:
    """
    For each tag, compute (tag, count_videos, total_views, avg_views)
    """
    all_vids = sorted({vid for vids in tag_to_vids.values() for vid in vids})
    if not all_vids:
        return []
    views_map = fetch_view_counts_for_ids(youtube, all_vids)
    results = []
    for tag, vids in tag_to_vids.items():
        counts = len(vids)
        total = sum(views_map.get(v, 0) for v in vids)
        avg = total / counts if counts else 0
        results.append((tag, counts, total, avg))
    results.sort(key=lambda x: (x[3], x[1]), reverse=True)  # sort by avg_views desc, then count
    return results

def write_csv(out_path: Path, rows):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["hashtag", "count_videos", "total_views", "avg_views"])
        for tag, cnt, total, avg in rows:
            w.writerow([tag, cnt, total, round(avg,2)])

def recommend_for_topic(topic: str, top_n: int = 10):
    ws = open_sheet()
    rows = parse_rows(ws)
    tag_to_vids, tag_to_rows = aggregate_hashtags(rows)
    youtube = yt_client_from_token()
    stats = compute_stats(tag_to_vids, youtube)
    out_path = Path("hashtag_scores.csv")
    write_csv(out_path, stats)
    print("Wrote", out_path)
    # Print top N
    print("Top hashtags overall:")
    for row in stats[:top_n]:
        tag, cnt, total, avg = row
        print(f"#{tag} — avg_views={avg:.1f} count={cnt}")
    # Very simple similarity: prefer tags that share tokens with topic
    topic_toks = set(re.findall(r"[A-Za-z0-9]+", topic.lower()))
    scored = []
    for tag, cnt, total, avg in stats:
        score = 0
        if any(tok in tag for tok in topic_toks):
            score += 10
        score += avg / 1000.0  # small weight for popularity
        scored.append((tag, cnt, total, avg, score))
    scored.sort(key=lambda x: x[4], reverse=True)
    print("\nRecommended hashtags for topic:", topic)
    for tag, cnt, total, avg, score in scored[:top_n]:
        print(f"#{tag} (avg={avg:.0f}, count={cnt})")
    return stats
