# sheets_logger.py (replace or patch)
import time
from typing import Dict, Optional

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from config import GOOGLE_SERVICE_ACCOUNT_JSON, SHEET_ID, SHEET_NAME

_scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_worksheet = None


def _open_ws():
    global _worksheet
    if _worksheet is not None:
        return _worksheet
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError(
            "Service account path not set in config.GOOGLE_SERVICE_ACCOUNT_JSON / SERVICE_ACCOUNT_FILE env"
        )
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        GOOGLE_SERVICE_ACCOUNT_JSON, _scopes
    )
    gc = gspread.authorize(creds)
    if SHEET_ID:
        sh = gc.open_by_key(SHEET_ID)
    else:
        sh = gc.open(SHEET_NAME)
    ws = sh.sheet1
    # Optionally ensure headers are present (be careful not to overwrite existing header row)
    # expected headers are assumed to be already in your sheet; skip aggressive updating to avoid overwriting.
    _worksheet = ws
    return ws


def append_log(row: Dict[str, str]):
    ws = _open_ws()
    # Build row respecting the sheet's header order; fallback will just append values in some order.
    # Here we assume the sheet columns match what we send (Timestamp..YouTubeURL)
    values = [
        row.get("Timestamp", ""),
        row.get("Region", ""),
        row.get("Status", ""),
        row.get("Topic", ""),
        row.get("Title", ""),
        row.get("Hook", ""),
        row.get("Body", ""),
        row.get("CTA", ""),
        row.get("Hashtags", ""),
        row.get("Caption", ""),
        row.get("Voice", ""),
        row.get("Filepath", ""),
        row.get("YouTubeURL", ""),
    ]
    ws.append_row(values, value_input_option="USER_ENTERED")


def log_post_result(
    region: str,
    status: str,
    topic: str,
    parts: Dict[str, str],
    filepath: str,
    youtube_url: Optional[str],
):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    row = {
        "Timestamp": ts,
        "Region": region,
        "Status": status,
        "Topic": topic,
        "Title": parts.get("title", ""),
        "Hook": parts.get("hook", ""),
        "Body": parts.get("body", ""),
        "CTA": parts.get("cta", ""),
        "Hashtags": " ".join(
            [t for t in parts.get("caption", "").split() if t.startswith("#")]
        ),
        "Caption": parts.get("caption", ""),
        "Voice": parts.get("voice", ""),
        "Filepath": filepath,
        "YouTubeURL": youtube_url or "",
    }
    append_log(row)
