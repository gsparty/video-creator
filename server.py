# server.py - wrapper to run your video_builder from Cloud Run (or locally)
import glob
import json
import logging
import os
import shutil
import sys
import tempfile

import requests
from flask import Flask, jsonify, request

# Add repo root to path so we can import video_builder from same folder
ROOT = os.path.dirname(__file__)
sys.path.insert(0, ROOT)

# Try to import google storage (optional)
try:
    from google.cloud import storage
except Exception:
    storage = None

# Import your existing video_builder module (should be in same folder)
try:
    import video_builder
except Exception as e:
    video_builder = None
    logging.exception("Could not import video_builder: %s", e)

app = Flask(__name__)


def choose_topic_from_scraper():
    scraper = os.environ.get("SCRAPER_URL")
    if not scraper:
        raise RuntimeError("SCRAPER_URL env var is not set and no topic provided")
    r = requests.get(scraper, timeout=25)
    r.raise_for_status()
    data = r.json()
    # Try common shapes: list of strings, list of dicts, dict with items
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            # try common keys
            for k in ("title", "term", "query", "keyword", "trend", "name"):
                if first.get(k):
                    return first.get(k)
            # fallback to JSON serialize
            return json.dumps(first)
    if isinstance(data, dict):
        # pick first value that looks like a string
        for k, v in data.items():
            if isinstance(v, str) and v.strip():
                return v
        # fallback: stringify a key
        return json.dumps(data)
    raise RuntimeError("Unexpected scraper response format")


def upload_to_gcs(local_path, bucket_name, dest_name=None):
    if storage is None:
        raise RuntimeError("google.cloud.storage not available in environment")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    if not dest_name:
        dest_name = os.path.basename(local_path)
    blob = bucket.blob(dest_name)
    blob.cache_control = "public, max-age=3600"
    blob.upload_from_filename(local_path)
    return f"gs://{bucket_name}/{dest_name}"


@app.route("/health")
def health():
    return jsonify(ok=True, env=os.environ.get("ENV", "dev"))


@app.route("/run", methods=["GET"])
def run_once():
    # accepts optional ?topic=...
    topic = request.args.get("topic")
    try:
        if not topic:
            topic = choose_topic_from_scraper()
        # create tempdir and run builder inside it
        tmp = tempfile.mkdtemp(prefix="auto_video_")
        cwd = os.getcwd()
        try:
            os.chdir(tmp)
            # prefer calling the function directly if available
            if video_builder and hasattr(video_builder, "build_video_from_trend"):
                video_builder.build_video_from_trend(topic)
            else:
                # fallback: try to run video_builder as a script via subprocess
                # pass topic as environment variable or arg if your script supports it
                import subprocess

                subprocess.run(
                    [sys.executable, os.path.join(ROOT, "video_builder.py"), topic],
                    check=True,
                    capture_output=True,
                )
            # find produced mp4 in tmp folder
            mp4s = glob.glob(os.path.join(tmp, "*.mp4")) + glob.glob(
                os.path.join(tmp, "**", "*.mp4"), recursive=True
            )
            if not mp4s:
                return jsonify(ok=False, error="No MP4 produced"), 500
            # pick largest mp4
            mp4s = sorted(mp4s, key=lambda p: os.path.getsize(p), reverse=True)
            local_file = mp4s[0]
            result = {"ok": True, "local": local_file}
            # upload if BUCKET set
            bucket = os.environ.get("BUCKET")
            if bucket:
                try:
                    dest_name = os.path.basename(local_file)
                    gcs_path = upload_to_gcs(local_file, bucket, dest_name)
                    result["gcs"] = gcs_path
                except Exception as e:
                    logging.exception("GCS upload failed")
                    result["gcs_error"] = str(e)
            return jsonify(result)
        finally:
            # cleanup: keep file if upload failed (do not remove)
            os.chdir(cwd)
            # If you want to preserve files add logic here; by default remove tempdir to avoid filling container.
            try:
                shutil.rmtree(tmp)
            except Exception:
                logging.exception("Failed to remove tempdir %s", tmp)
    except Exception as e:
        logging.exception("Run failed")
        return jsonify(ok=False, error=str(e)), 500


if __name__ == "__main__":
    # For local testing
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
