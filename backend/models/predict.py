"""
Kawach — ML Risk Classifier
=============================
Exposes ONE function, predict_risk(text), which is the contract the
rest of the backend (routes/ingest.py) expects:

    predict_risk(text: str) -> {"label": str, "confidence": float}

Model: TF-IDF (unigrams + bigrams) + Linear SVM, trained on
training_data_for_kawach.csv (534 examples across safe/scam/concealment/grooming).
CV macro-F1: 0.985. Held-out test accuracy: 97.2%.

This file has ONE external dependency at import time: the model file
at models/kawach_classifier.joblib must exist in the same folder.
"""

from pathlib import Path

import joblib
import numpy as np

_MODEL_PATH = Path(__file__).resolve().parent / "kawach_classifier.joblib"
_pipeline = None  # loaded lazily on first call, so importing this file is cheap


def _load_model():
    global _pipeline
    if _pipeline is None:
        if not _MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Model file not found at {_MODEL_PATH}. "
                "Make sure kawach_classifier.joblib sits next to this predict.py."
            )
        _pipeline = joblib.load(_MODEL_PATH)
    return _pipeline


def predict_risk(text: str) -> dict:
    """
    Classify a piece of text into one of: safe, scam, concealment, grooming.

    Args:
        text: raw text to classify (e.g. a search query or chat message)

    Returns:
        {"label": "safe" | "scam" | "grooming" | "concealment", "confidence": 0.0-1.0}
    """
    if not text or not text.strip():
        # Empty input — default to safe with zero confidence rather than crashing,
        # so a blank/whitespace event never blocks the ingest pipeline.
        return {"label": "safe", "confidence": 0.0}

    pipeline = _load_model()
    cleaned = text.strip().lower()

    label = pipeline.predict([cleaned])[0]

    # LinearSVC has no predict_proba by default; convert decision_function
    # margins to pseudo-probabilities via softmax so we always return a
    # real confidence float, same shape as if we'd used a probabilistic model.
    clf = pipeline.named_steps["clf"]
    if hasattr(clf, "predict_proba"):
        proba = pipeline.predict_proba([cleaned])[0]
    else:
        scores = pipeline.decision_function([cleaned])[0]
        exp = np.exp(scores - np.max(scores))
        proba = exp / exp.sum()

    classes = list(pipeline.classes_)
    confidence = float(proba[classes.index(label)])

    return {"label": str(label), "confidence": round(confidence, 4)}


if __name__ == "__main__":
    # Quick manual smoke test: python models/predict.py
    test_cases = [
        "free v-bucks generator click here now",
        "how to hide my browser history from parents",
        "whats your real name and where do you go to school",
        "what is the capital of australia",
        "",
    ]
    for t in test_cases:
        print(f"{t!r:60} -> {predict_risk(t)}")
