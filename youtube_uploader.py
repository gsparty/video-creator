import os
import json
from pathlib import Path
from typing import Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from config import TOKENS_DIR, YOUTUBE_CLIENT_SECRETS, YOUTUBE_CATEGORY_ID, YOUTUBE_DEFAULT_VISIBILITY

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = Path(TOKENS_DIR) / "youtube_token.json"

def _get_youtube() -> "googleapiclient.discovery.Resource":
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(YOUTUBE_CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def upload_short(
    filepath: str, title: str, description: str,
    tags: Optional[list]=None, visibility: str = None
) -> str:
    """
    Uploads a video and returns the YouTube watch URL.
    """
    youtube = _get_youtube()
    visibility = visibility or YOUTUBE_DEFAULT_VISIBILITY
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "categoryId": YOUTUBE_CATEGORY_ID,
            "tags": tags or []
        },
        "status": {"privacyStatus": visibility},
    }
    media = MediaFileUpload(filepath, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
    vid = response["id"]
    return f"https://www.youtube.com/watch?v={vid}"
