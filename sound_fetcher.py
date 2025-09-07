# sound_fetcher.py
# Search, download, normalize and index ambient/beds and short SFX from Freesound.
# Usage examples:
#  python sound_fetcher.py --mode beds --keywords "stadium crowd cheer" --label sports
#  python sound_fetcher.py --mode sfx --keywords "impact whoosh ding" --label sfx

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets" / "sounds"
INDEX_JSON = ASSETS / "index.json"
ENV_FILE = ROOT / ".env"

ASSETS.mkdir(parents=True, exist_ok=True)

def load_env() -> Dict[str, str]:
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env

def slugify(s: str, maxlen: int = 80) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s\-]+", "", s)
    s = re.sub(r"[\s\-]+", "-", s).strip("-")
    return s[:maxlen] or "item"

def run_ffmpeg(cmd: List[str]) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, text=True, capture_output=True)
    return p

def ensure_index() -> Dict:
    if INDEX_JSON.exists():
        try:
            return json.loads(INDEX_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sounds": []}

def save_index(idx: Dict):
    INDEX_JSON.write_text(json.dumps(idx, indent=2), encoding="utf-8")

def probe_mean_volume_db(path: Path) -> Optional[float]:
    # Use ffmpeg volumedetect to estimate mean_volume in dB
    # Run ffmpeg and capture stderr (volumedetect prints to stderr)
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(path),
        "-af", "volumedetect", "-f", "null", "-"
    ]
    p = subprocess.run(cmd, text=True, capture_output=True)
    out = p.stderr or p.stdout or ""
    # look for mean_volume
    m = re.search(r"mean_volume:\s*(-?\d+(\.\d+)?)\s*dB", out)
    if m:
        return float(m.group(1))
    # debug: print ffmpeg output to help diagnose why volumedetect failed
    print(f"[sound_fetcher] volumedetect output for {path} (no mean_volume found):")
    print(out.strip()[:2000])  # print first 2000 chars
    return None


def normalize_to_44100_stereo(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vn",
        "-af", "loudnorm=I=-20:TP=-1.5:LRA=11",
        "-ar", "44100", "-ac", "2",
        str(dst)
    ]
    p = run_ffmpeg(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg normalize failed: {p.stderr}")

@dataclass
class SoundMeta:
    path: str
    provider: str
    id: str
    tags: List[str]
    duration: float
    mean_db: Optional[float]
    keywords: List[str]
    label: str

# ---------------- Freesound client ----------------
class FreeSound:
    SEARCH_URL = "https://freesound.org/apiv2/search/text/"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, q: str, min_dur: float, max_dur: float, page_size: int = 15):
        filt = f"duration:[{min_dur} TO {max_dur}]"
        params = {
            "query": q,
            "filter": filt,
            "fields": "id,name,tags,duration,previews",
            "page_size": page_size,
            "sort": "score"
        }
        headers = {"Authorization": f"Token {self.api_key}"}
        r = requests.get(self.SEARCH_URL, params=params, headers=headers, timeout=20)
        r.raise_for_status()
        return r.json().get("results", [])

# ---------------- fetcher ----------------
def fetch_items(
    keywords: List[str],
    label: str = "general",
    min_dur: float = 2.0,
    max_dur: float = 60.0,
    min_mean_db: float = -50.0,
    limit: int = 6,
    api_key: Optional[str] = None
) -> List[SoundMeta]:
    env = load_env()
    api_key = api_key or env.get("FREESOUND_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("No FREESOUND_API_KEY provided. Set .env or pass --api-key")

    fs = FreeSound(api_key)
    q = " ".join(keywords)
    print(f"[sound_fetcher] Searching Freesound for: '{q}' dur[{min_dur},{max_dur}] (label={label})")
    results = fs.search(q, min_dur, max_dur, page_size=max(limit * 3, 12))
    if not results:
        print("[sound_fetcher] No results returned from Freesound. Try different keywords or expand duration range.")
        return []

    saved: List[SoundMeta] = []
    bucket = ASSETS / slugify(label)
    bucket.mkdir(parents=True, exist_ok=True)
    idx = ensure_index()
    kept = 0

    for hit in results:
        if kept >= limit:
            break
        previews = hit.get("previews", {}) or {}
        url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
        if not url:
            continue

        sid = str(hit.get("id", ""))
        dur = float(hit.get("duration", 0) or 0.0)
        tags = hit.get("tags", []) or []
        base = slugify(f"{label}-{sid}")
        raw_mp3 = bucket / f"{base}.raw.mp3"
        norm_mp3 = bucket / f"{base}.mp3"

        try:
            # download preview
            print(f"[sound_fetcher] downloading {sid} ...")
            with requests.get(url, stream=True, timeout=30) as rr:
                rr.raise_for_status()
                with open(raw_mp3, "wb") as f:
                    for chunk in rr.iter_content(8192):
                        f.write(chunk)
        except Exception as e:
            print("[sound_fetcher] download failed:", e)
            continue

        # normalize/resample
        try:
            normalize_to_44100_stereo(raw_mp3, norm_mp3)
        except Exception as e:
            print("[sound_fetcher] normalize failed:", e)
            raw_mp3.unlink(missing_ok=True)
            continue
        finally:
            raw_mp3.unlink(missing_ok=True)

        # measure mean volume
        mean_db = probe_mean_volume_db(norm_mp3)
        if mean_db is None:
            print(f"[sound_fetcher] vol detect failed for {norm_mp3}, skipping.")
            norm_mp3.unlink(missing_ok=True)
            continue
        if mean_db < min_mean_db:
            print(f"[sound_fetcher] too quiet (mean {mean_db:.1f} dB) -> skipping {norm_mp3.name}")
            norm_mp3.unlink(missing_ok=True)
            continue

        meta = SoundMeta(
            path=str(norm_mp3.relative_to(ROOT)),
            provider="freesound",
            id=sid,
            tags=tags,
            duration=dur,
            mean_db=mean_db,
            keywords=keywords,
            label=label
        )
        idx["sounds"].append(asdict(meta))
        saved.append(meta)
        kept += 1
        print(f"[sound_fetcher] saved {norm_mp3} ({dur:.1f}s, {mean_db:.1f} dB)")

    save_index(idx)
    return saved

# ---------------- selectors ----------------
def select_bed(label: str, target_sec: float = 25.0) -> Optional[Path]:
    idx = ensure_index()
    label_slug = slugify(label)
    pool = []
    for s in idx.get("sounds", []):
        try:
            if s.get("label") == label_slug or s.get("label") == "general" or label_slug in (s.get("keywords") or []):
                pool.append(s)
        except Exception:
            continue
    if not pool:
        return None
    pool.sort(key=lambda s: abs(float(s.get("duration", 0.0)) - float(target_sec)))
    return ROOT / pool[0]["path"]

def select_sfx(label: str, max_count: int = 2) -> List[Path]:
    idx = ensure_index()
    label_slug = slugify(label)
    pool = []
    for s in idx.get("sounds", []):
        if s.get("label") == label_slug:
            pool.append(s)
    # allow general sfx too
    for s in idx.get("sounds", []):
        if s.get("label") == "sfx" or "sfx" in (s.get("keywords") or []):
            pool.append(s)
    pool = list({p["path"]: p for p in pool}.values())  # dedupe
    pool.sort(key=lambda s: float(s.get("duration", 0.0)))
    chosen = pool[:max_count]
    return [ROOT / p["path"] for p in chosen]

# ---------------- CLI ----------------
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("beds", "sfx"), default="beds")
    ap.add_argument("--keywords", required=True)
    ap.add_argument("--label", default="general")
    ap.add_argument("--min-dur", type=float, default=4.0)
    ap.add_argument("--max-dur", type=float, default=60.0)
    ap.add_argument("--min-mean-db", type=float, default=-45.0)
    ap.add_argument("--limit", type=int, default=6)
    ap.add_argument("--api-key", default=None)
    args = ap.parse_args()

    kws = [k for k in re.split(r"\s+", args.keywords.strip()) if k]
    try:
        metas = fetch_items(
            keywords=kws,
            label=args.label,
            min_dur=args.min_dur,
            max_dur=args.max_dur,
            min_mean_db=args.min_mean_db,
            limit=args.limit,
            api_key=args.api_key
        )
    except Exception as e:
        print("ERROR:", e)
        metas = []

    if not metas:
        print("No usable sounds fetched (try different keywords or relax thresholds).")
    else:
        print("Fetched:")
        for m in metas:
            print("-", m.path, f"({m.duration:.1f}s, {m.mean_db:.1f} dB)")
