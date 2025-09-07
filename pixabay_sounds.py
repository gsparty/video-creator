import os

import requests

# ---------------- CONFIG ----------------
API_KEY = "YOUR_PIXABAY_API_KEY"  # replace with your key
SEARCH_QUERY = "motorcycle"       # example: "engine", "bike", etc.
DOWNLOAD_LIMIT = 5                # how many sounds to download
SAVE_DIR = "sounds"               # local folder
# ----------------------------------------

PIXABAY_API_URL = "https://pixabay.com/api/sounds/"

def search_and_download_sounds(query, limit=5):
    params = {
        "key": API_KEY,
        "q": query,
        "per_page": limit
    }
    response = requests.get(PIXABAY_API_URL, params=params)
    data = response.json()

    if "hits" not in data or len(data["hits"]) == 0:
        print(f"No sounds found for query '{query}'")
        return

    os.makedirs(SAVE_DIR, exist_ok=True)

    for i, hit in enumerate(data["hits"]):
        sound_url = hit["audio"]
        sound_name = hit["tags"].replace(",", "_").replace(" ", "_")
        file_path = os.path.join(SAVE_DIR, f"{sound_name}_{i}.mp3")

        print(f"Downloading: {sound_name} -> {file_path}")
        sound_data = requests.get(sound_url)
        with open(file_path, "wb") as f:
            f.write(sound_data.content)

    print(f"✅ Download complete. Files saved in '{SAVE_DIR}'")

if __name__ == "__main__":
    search_and_download_sounds(SEARCH_QUERY, DOWNLOAD_LIMIT)
