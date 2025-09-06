# pexels_test.py
import os, requests, sys
key = os.environ.get("PEXELS_API_KEY")
print("PEXELS_API_KEY present:", bool(key))
if not key:
    print("No key in env. Set it and re-run.")
    sys.exit(1)

headers = {"Authorization": key}
try:
    r = requests.get("https://api.pexels.com/videos/popular", headers=headers, timeout=15)
    print("status:", r.status_code)
    print("headers (server):", r.headers.get("content-type"))
    print("body snippet:", r.text[:400])
except Exception as e:
    print("Request error:", e)
