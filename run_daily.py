#!/usr/bin/env python3
"""
run_daily.py

Fetch trends, filter to English (optional), generate shorts and optionally stage/upload.

Usage examples:
    python run_daily.py --count 3 --region CH --only-stage --tts-engine edge-tts --voice-variants "en-US-AriaNeural" --english-only
"""

import argparse
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Optional

import requests

# try import langdetect for language filtering; if missing we'll fallback to ASCII heuristic
try:
    from langdetect import detect_langs

    LANGDETECT_AVAILABLE = True
except Exception:
    LANGDETECT_AVAILABLE = False

# local short maker
try:
    from short_maker import generate_short
except Exception as e:
    print("Failed to import short_maker.generate_short:", e)
    raise

# optional sheets logger
SHEETS_AVAILABLE = False
try:
    from sheets_logger import SheetsLogger

    SHEETS_AVAILABLE = True
except Exception:
    SHEETS_AVAILABLE = False

# config from env
SCRAPER_URL = os.environ.get(
    "SCRAPER_URL",
    "https://us-central1-automate-trends-scraper.cloudfunctions.net/scrapeTrends",
)
OUTPUT_ROOT = Path(os.environ.get("OUTPUT_DIR", "shorts"))
OUTBOX_DIR = Path(os.environ.get("OUTBOX_DIR", "outbox"))
RUN_SUMMARY_DIR = OUTPUT_ROOT / "run_summaries"
DEFAULT_MIN_DURATION = float(os.environ.get("MIN_DURATION", "20.0"))

# logging
log = logging.getLogger("run_daily")
if not log.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(ch)
log.setLevel(logging.INFO)


def is_ascii_heavy(s: str) -> bool:
    """Simple heuristic: return True if the string is mostly ASCII letters/digits/punctuation."""
    if not s:
        return False
    total = len(s)
    ascii_count = sum(1 for ch in s if ord(ch) < 128)
    # require at least 70% ascii or at least 3 latin letters
    latin_letters = len(re.findall(r"[A-Za-z]", s))
    return (ascii_count / total) >= 0.7 or latin_letters >= 3


def detect_english(text: str, prob_threshold: float = 0.60) -> bool:
    """Return True if `text` is likely English.

    Uses langdetect if available; otherwise falls back to ascii-heavy heuristic.
    """
    if not text or text.strip() == "":
        return False

    # Quick pre-clean: remove hashtags/punctuation that confuse detectors
    sample = re.sub(r"[_#@]", " ", text)
    sample = re.sub(
        r"[^\w\s\-\']", " ", sample
    )  # keep letters, numbers, dashes, apostrophes
    sample = re.sub(r"\s+", " ", sample).strip()

    if LANGDETECT_AVAILABLE:
        try:
            langs = detect_langs(sample)
            # langs is like [LangProb(lang='en', prob=0.998), ...]
            if len(langs) > 0:
                top = langs[0]
                if (
                    getattr(top, "lang", None) == "en"
                    and getattr(top, "prob", 0.0) >= prob_threshold
                ):
                    return True
                # if the detector says 'und' or another script but probability low, fallback to ascii
        except Exception:
            # fall through to ascii heuristic
            pass

    # fallback heuristic
    return is_ascii_heavy(sample)


def fetch_trends(scraper_url: str, region: Optional[str] = None) -> List[str]:
    """
    Call scraper endpoint to fetch trends. Endpoint should return JSON: {"trends": [...]}.
    The 'region' parameter is passed as querystring if provided.
    """
    params = {}
    if region:
        params["region"] = region
    try:
        log.debug("Fetching trends from %s params=%s", scraper_url, params)
        res = requests.get(scraper_url, params=params, timeout=15)
        res.raise_for_status()
        data = res.json()
        trends = data.get("trends") or data.get("topics") or []
        if isinstance(trends, list):
            return trends
        else:
            log.warning("Unexpected trends payload, not a list: %s", type(trends))
            return []
    except Exception as e:
        log.error("Failed to fetch trends: %s", e)
        return []


def ensure_dirs():
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    (OUTBOX_DIR / "instagram").mkdir(parents=True, exist_ok=True)
    (OUTBOX_DIR / "tiktok").mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT).mkdir(parents=True, exist_ok=True)
    RUN_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)


def write_run_summary(summary_lines: List[str]):
    ensure_dirs()
    fname = RUN_SUMMARY_DIR / f"{time.strftime('%Y-%m-%d')}.txt"
    with open(fname, "a", encoding="utf-8") as f:
        for line in summary_lines:
            f.write(line + "\n")
    log.info("Wrote summary -> %s", fname)


def stage_for_platforms(mp4_path: str, caption: str, slug: str, voice_variant: str):
    """Copy final mp4 to outbox for Instagram and TikTok, plus caption files."""
    ig_dir = OUTBOX_DIR / "instagram"
    tt_dir = OUTBOX_DIR / "tiktok"
    ig_dir.mkdir(parents=True, exist_ok=True)
    tt_dir.mkdir(parents=True, exist_ok=True)
    src = Path(mp4_path)
    if not src.exists():
        log.warning("stage_for_platforms: mp4 not found: %s", mp4_path)
        return
    voice_tag = (
        voice_variant.replace("/", "_").replace(":", "_")
        if voice_variant
        else "default"
    )
    dest_name = f"{slug}_{voice_tag}.mp4"
    ig_target = ig_dir / dest_name
    tt_target = tt_dir / dest_name
    try:
        from shutil import copy2

        copy2(src, ig_target)
        copy2(src, tt_target)
        (ig_dir / f"{slug}_{voice_tag}.txt").write_text(caption or "", encoding="utf-8")
        (tt_dir / f"{slug}_{voice_tag}.txt").write_text(caption or "", encoding="utf-8")
        log.info("Staged video -> %s", ig_target)
        log.info("Staged video -> %s", tt_target)
    except Exception as e:
        log.error("Staging failed: %s", e)


def safe_slug_for_display(s: str) -> str:
    """Quick slug to name files consistently."""
    s = str(s or "").strip()
    s = s.replace(" ", "-").replace("/", "-").replace("\\", "-")
    s = "".join(ch for ch in s if ch.isalnum() or ch in "-_")
    if not s:
        s = f"topic-{int(time.time())}"
    return s.lower()


def try_sheets_log(sheets_logger, row):
    if SHEETS_AVAILABLE and sheets_logger:
        try:
            sheets_logger.append_row(row)
            log.info("Logged result to Google Sheet.")
        except Exception as e:
            log.warning("Sheets logging failed: %s", e)
    else:
        log.debug("Sheets not available or not configured; skipping sheet log.")


def filter_english(trends: List[str], limit: int) -> List[str]:
    """Return up to `limit` trends that are English-language first choices."""
    picked = []
    for t in trends:
        if len(picked) >= limit:
            break
        # Small guard: skip empty or pure symbols
        if not t or re.fullmatch(r"[\W_]+", t):
            continue
        if detect_english(t):
            picked.append(t)
    return picked


def main():
    parser = argparse.ArgumentParser(description="Daily Shorts generator")
    parser.add_argument(
        "--count", type=int, default=3, help="How many trends to process"
    )
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help="Region/Country code (passed to scraper)",
    )
    parser.add_argument(
        "--tts-engine",
        type=str,
        default=None,
        help="Which TTS engine to prefer (edge-tts, gtts, pyttsx3)",
    )
    parser.add_argument(
        "--voice-variants",
        type=str,
        default=None,
        help='Comma-separated voice variant strings (e.g. "en-US-AriaNeural,en-GB-SomeOther")',
    )
    parser.add_argument(
        "--only-stage",
        action="store_true",
        help="Don't upload; just stage for IG/TikTok",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload to YouTube (requires youtube oauth)",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=DEFAULT_MIN_DURATION,
        help="Minimum audio duration (seconds)",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Start from this index in trends list",
    )
    parser.add_argument(
        "--english-only",
        "--en-only",
        action="store_true",
        help="Filter returned trends to English only",
    )
    args = parser.parse_args()

    ensure_dirs()

    voice_variants_list = []
    if args.voice_variants:
        voice_variants_list = [
            v.strip() for v in args.voice_variants.split(",") if v.strip()
        ]

    # init sheets logger if available
    sheets_logger = None
    if SHEETS_AVAILABLE:
        try:
            sheets_logger = SheetsLogger()
            log.info("SheetsLogger loaded.")
        except Exception as e:
            log.warning("Failed to init SheetsLogger: %s", e)
            sheets_logger = None

    # fetch trends
    log.info("Fetching trends...")
    trends = fetch_trends(SCRAPER_URL, region=args.region)
    if not trends:
        log.warning("No trends returned.")
        write_run_summary(
            [f"{time.strftime('%Y-%m-%d %H:%M:%S')} - No trends returned."]
        )
        return

    # Optionally filter to English
    if args.english_only:
        filtered = filter_english(
            trends, args.count + 10
        )  # try a few extras to ensure enough items
        if len(filtered) < args.count:
            log.warning(
                "Not enough English trends found (%d) - returning the best %d found.",
                len(filtered),
                len(filtered),
            )
        trends = filtered

    start = max(0, args.start_index)
    to_process = trends[start : start + args.count]
    log.info("Will process %d trends: %s", len(to_process), to_process)

    run_summary_lines = []
    for topic in to_process:
        slug = safe_slug_for_display(topic)
        try:
            log.info("Processing topic: %s", topic)
            voice_variant_for_run = (
                voice_variants_list[0] if voice_variants_list else None
            )

            mp4_path, parts = generate_short(
                topic,
                region=args.region or "US",
                voice_variant=voice_variant_for_run,
                min_duration=args.min_duration,
            )
            log.info("Generated short: %s", mp4_path)

            if args.only_stage:
                caption = parts.get("caption", "")
                stage_for_platforms(
                    mp4_path, caption, slug, voice_variant_for_run or "default"
                )
                log.info("Only-stage mode: skipping sheet logging.")
            else:
                if args.upload:
                    try:
                        from youtube_uploader import upload_short

                        title = parts.get("title") or topic
                        desc = parts.get("caption") or ""
                        tags = []
                        if isinstance(desc, str):
                            tags = [
                                t.strip("#") for t in desc.split() if t.startswith("#")
                            ]
                        youtube_url = upload_short(
                            filepath=mp4_path, title=title, description=desc, tags=tags
                        )
                        log.info("Uploaded to YouTube: %s", youtube_url)
                    except Exception as e:
                        log.warning("YouTube upload failed: %s", e)
                stage_for_platforms(
                    mp4_path,
                    parts.get("caption", ""),
                    slug,
                    voice_variant_for_run or "default",
                )
                row = [
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    args.region or "",
                    "generated",
                    topic,
                    parts.get("title", ""),
                    parts.get("hook", ""),
                    parts.get("body", ""),
                    parts.get("cta", ""),
                    ",".join([h for h in (parts.get("suggested_hashtags") or [])]),
                    parts.get("caption", ""),
                    parts.get("voice", ""),
                    mp4_path,
                ]
                try_sheets_log(sheets_logger, row)

            run_summary_lines.append(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {topic}: status=generated mp4={mp4_path}"
            )
        except Exception as e:
            log.exception("Error processing topic '%s': %s", topic, e)
            run_summary_lines.append(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {topic}: status=error: {type(e).__name__} {e}"
            )

    write_run_summary(run_summary_lines)
    log.info("Run finished. Summary:")
    for line in run_summary_lines:
        log.info(" - %s", line)


if __name__ == "__main__":
    main()
