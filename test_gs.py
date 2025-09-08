import os

import requests

url = (
    os.environ.get("SCRAPER_URL")
    or "https://us-central1-automate-trends-scraper.cloudfunctions.net/scrapeTrends"
)
print("Using URL:", url)
r = requests.get(url, timeout=15)
print("HTTP", r.status_code)
try:
    print("JSON:", r.json())
except Exception:
    print("Text:", r.text[:1000])
