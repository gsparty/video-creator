# config.py (replace existing)
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv()

ROOT = Path(__file__).resolve().parent

# Directories (use OUTPUT_DIR if set in .env)
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", str(ROOT / "output_videos")))
SHORTS_ROOT = Path(os.environ.get("SHORTS_ROOT", str(ROOT / "shorts")))
OUTBOX_IG = Path(os.environ.get("OUTBOX_IG", str(ROOT / "outbox" / "instagram")))
OUTBOX_TT = Path(os.environ.get("OUTBOX_TT", str(ROOT / "outbox" / "tiktok")))
TOKENS_DIR = Path(os.environ.get("TOKENS_DIR", str(ROOT / "tokens")))

for p in (OUTPUT_DIR, SHORTS_ROOT, OUTBOX_IG, OUTBOX_TT, TOKENS_DIR):
    p.mkdir(parents=True, exist_ok=True)

# === External services & Keys ===
# Accept both TRENDS_URL and SCRAPER_URL (your .env uses SCRAPER_URL)
TRENDS_URL = os.environ.get("SCRAPER_URL") or os.environ.get("TRENDS_URL") or \
    "https://us-central1-automate-trends-scraper.cloudfunctions.net/scrapeTrends"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY", "").strip()

# Google Sheets: accept SERVICE_ACCOUNT_FILE and GOOGLE_SERVICE_ACCOUNT_JSON
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("SERVICE_ACCOUNT_FILE") or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
# Accept SHEET_ID or SHEET_NAME
SHEET_ID = os.environ.get("SHEET_ID", "").strip()
SHEET_NAME = os.environ.get("SHEET_NAME", "Auto Video Agent Data").strip()

# YouTube
YOUTUBE_CLIENT_SECRETS = os.environ.get("YOUTUBE_CLIENT_SECRETS", str((ROOT / "client_secret.json").resolve()))
YOUTUBE_CATEGORY_ID = os.environ.get("YOUTUBE_CATEGORY_ID", "24")
YOUTUBE_DEFAULT_VISIBILITY = os.environ.get("YOUTUBE_DEFAULT_VISIBILITY", "unlisted")
YOUTUBE_REGION = os.environ.get("YOUTUBE_REGION", "CH")

# Misc
MODEL_PROVIDER = os.environ.get("MODEL_PROVIDER", "openai")
TTS_ENGINE = os.environ.get("TTS_ENGINE", "gtts")  # fallback to gTTS in code
FONT_PATH = os.environ.get("FONT_PATH", r"C:\Windows\Fonts\arial.ttf")
BG_IMAGE = os.environ.get("BG_IMAGE", str(ROOT / "bg.jpg"))
