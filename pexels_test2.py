# pexels_test2.py
import os

import requests

key = os.environ.get("PEXELS_API_KEY")
print("PEXELS_API_KEY present:", bool(key))
if not key:
    raise SystemExit("No PEXELS_API_KEY in environment.")

url = "https://api.pexels.com/videos/popular"
# Two header styles to try:
headers_plain = {"Authorization": key}
headers_bearer = {"Authorization": f"Bearer {key}"}
tests = [("plain", headers_plain), ("bearer", headers_bearer)]

for name, headers in tests:
    print("\n--- Testing header style:", name, "---")
    # print what we'd send (safe: show lengths not full key)
    safe_key = key[:6] + "..." + key[-4:]
    print("Sending header Authorization value (snippet):", safe_key)
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print("status:", r.status_code)
        # show a small portion of JSON body or text
        text = r.text[:800]
        print("body snippet:", text)
        # print server response content-type
        print("content-type:", r.headers.get("content-type"))
        # If JSON, pretty-print the error
        try:
            j = r.json()
            print("json keys:", list(j.keys())[:10])
        except Exception:
            pass
    except Exception as e:
        print("request exception:", repr(e))
