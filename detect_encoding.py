import os

bad = []
for root, dirs, files in os.walk(".", topdown=True):
    dirs[:] = [d for d in dirs if d not in (".venv", "venv", ".git", "__pycache__")]
    for f in files:
        path = os.path.join(root, f)
        try:
            b = open(path, "rb").read(4096)
        except Exception:
            continue
        if b"\x00" in b:
            bad.append((path, "binary (null byte detected)"))
            continue
        try:
            open(path, "r", encoding="utf-8").read()
        except Exception as e:
            bad.append((path, str(e)))
if not bad:
    print("All files look UTF-8 decodable")
else:
    print("Files with encoding/decoding issues (path -> reason):")
    for p, r in bad:
        print(p, "->", r)
