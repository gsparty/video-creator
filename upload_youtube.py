# upload_youtube.py
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CRED_PICKLE = "youtube_creds.pkl"

def get_authenticated_service(client_secrets_file="client_secrets.json"):
    creds = None
    if os.path.exists(CRED_PICKLE):
        import pickle
        with open(CRED_PICKLE, "rb") as f:
            creds = pickle.load(f)
    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
        creds = flow.run_console()
        with open(CRED_PICKLE, "wb") as f:
            pickle.dump(creds, f)
    return build("youtube", "v3", credentials=creds)

def upload_video(youtube, video_file, title, description, privacyStatus="private"):
    body = {
        "snippet": {"title": title, "description": description, "tags": ["auto","shorts"], "categoryId":"22"},
        "status": {"privacyStatus": privacyStatus},
    }
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")
    print("Upload complete. Response:", response)
    return response

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python upload_youtube.py <video.mp4> <title> <description> [privacy]")
        sys.exit(1)
    video_file, title, description = sys.argv[1], sys.argv[2], sys.argv[3]
    privacy = sys.argv[4] if len(sys.argv) > 4 else "private"
    youtube = get_authenticated_service()
    upload_video(youtube, video_file, title, description, privacyStatus=privacy)
