# trend_classifier.py
# Small TF-IDF + LogisticRegression classifier for quick topic -> label mapping.
# On first run the module will create a small built-in training set and persist a model file.
# Functions:
#   predict_label(text) -> label (str)
#   train_from_csv(csv_path) -> trains and overwrites model (csv: text,label)

import os
from pathlib import Path
from typing import List
import joblib

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

MODEL_PATH = Path("trend_classifier.joblib")


def _default_training_data():
    # Very small seed dataset. Expand with your own CSV via train_from_csv().
    texts = [
        "World Cup match highlights",
        "Huge football upset today — Ronaldo shocked fans",
        "New album by Taylor Swift released",
        "Taylor Swift announces tour dates",
        "Google launches new product",
        "New AI startup raises millions",
        "White House policy controversial statement",
        "Senator gives speech about taxes",
        "impressive product review by tech blogger",
        "famous actor wins award",
        "celebrity scandal trending",
        "how to grow hair faster",
        "best recipes for dinner",
    ]
    labels = [
        "sports", "sports",
        "music", "music",
        "tech", "tech",
        "politics", "politics",
        "tech", "celebrity",
        "celebrity",
        "lifestyle", "lifestyle",
    ]
    return texts, labels


def _build_pipeline():
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=4000)),
            ("clf", LogisticRegression(max_iter=200)),
        ]
    )


def train_and_save(model_path: Path = MODEL_PATH):
    print("[trend_classifier] training model...")
    texts, labels = _default_training_data()
    pipe = _build_pipeline()
    pipe.fit(texts, labels)
    joblib.dump(pipe, model_path)
    print(f"[trend_classifier] model saved to {model_path}")
    return pipe


def load_model(model_path: Path = MODEL_PATH):
    if model_path.exists():
        try:
            pipe = joblib.load(model_path)
            return pipe
        except Exception as e:
            print("[trend_classifier] failed to load model:", e)
            # fallthrough -> retrain
    return train_and_save(model_path)


# convenience wrapper
_model = load_model()


def predict_label(text: str) -> str:
    if not text:
        return "other"
    try:
        lbl = _model.predict([text])[0]
        return str(lbl)
    except Exception as e:
        print("[trend_classifier] predict error:", e)
        return "other"


def train_from_csv(csv_path: str):
    # Expect CSV with two columns: text,label (no header required)
    import csv

    rows: List[str] = []
    labs: List[str] = []
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(csv_path)
    with p.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        for r in reader:
            if len(r) >= 2:
                rows.append(r[0].strip())
                labs.append(r[1].strip())
    if not rows:
        raise ValueError("No rows in CSV")
    pipe = _build_pipeline()
    pipe.fit(rows, labs)
    joblib.dump(pipe, MODEL_PATH)
    global _model
    _model = pipe
    print(f"[trend_classifier] trained on {len(rows)} rows and saved to {MODEL_PATH}")
    return pipe


# allow module usage as script
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Train or test trend classifier")
    ap.add_argument("--train-csv", help="CSV file to train from (text,label)")
    ap.add_argument("--predict", help="Single text to predict label for")
    args = ap.parse_args()
    if args.train_csv:
        train_from_csv(args.train_csv)
    elif args.predict:
        print("label:", predict_label(args.predict))
    else:
        print("model file:", MODEL_PATH.resolve())
        print("example prediction:", predict_label("Huge football upset today — Ronaldo shocked fans"))
