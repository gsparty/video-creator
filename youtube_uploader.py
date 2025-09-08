"""youtube_uploader.py

Lightweight, flake8-friendly YouTube uploader helper using a service
account. Replace CONFIG values and call upload_video(...) as needed.
"""

from __future__ import annotations

import argparse
import os
from typing import Iterable, Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Minimal OAuth scopes for YouTube Data API v3.
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_authenticated_service(
    sa_json_path: str, scopes: Optional[Iterable[str]] = None
):
    """Return an authenticated YouTube API client using a service account."""
    if scopes is None:
        scopes = YOUTUBE_SCOPES
    credentials = Credentials.from_service_account_file(
        sa_json_path, scopes=list(scopes)
    )
    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    return youtube


def upload_video(
    youtube,
    video_file: str,
    title: str,
    description: str = "",
    tags: Optional[Iterable[str]] = None,
    privacy: str = "public",
):
    """Upload a single video file and return the upload response."""
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": list(tags)[:50] if tags else [],
            "categoryId": "22",  # People & Blogs, change if desired
        },
        "status": {"privacyStatus": privacy},
    }

    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    response = None
    # Simple resumable upload loop (no backoff logic here; add as needed).
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    return response


def main():
    parser = argparse.ArgumentParser(description="Upload video to YouTube.")
    parser.add_argument(
        "--sa-json", required=True, help="Path to service account JSON."
    )
    parser.add_argument("--file", required=True, help="Local video file path.")
    parser.add_argument("--title", required=True, help="Video title.")
    parser.add_argument("--desc", default="", help="Video description.")
    parser.add_argument(
        "--privacy", default="public", help="privacy: public|unlisted|private"
    )
    args = parser.parse_args()

    if not os.path.exists(args.sa_json):
        raise SystemExit(f"Service account JSON not found: {args.sa_json}")

    youtube = get_authenticated_service(args.sa_json)
    resp = upload_video(
        youtube, args.file, args.title, description=args.desc, privacy=args.privacy
    )
    print("Upload finished. Video id:", resp.get("id"))


if __name__ == "__main__":
    main()
