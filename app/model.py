"""Loads the trained model and turns a text into a verdict + explanation."""
from pathlib import Path

import joblib

from .text_utils import clean_text, word_count

FAKE = 1  # label convention used in training: 1 = fake, 0 = real
FAKE_THRESHOLD = 0.60
REAL_THRESHOLD = 0.40
MIN_RELIABLE_WORDS = 50


class ModelNotReady(RuntimeError):
    """Raised when no trained model file exists yet."""


class Detector:
    def __init__(self, path: Path):
        path = Path(path)
        if not path.exists():
            raise ModelNotReady(f"Model file not found: {path}")
        bundle = joblib.load(path)
        self.pipeline = bundle["pipeline"]
        self.meta = bundle.get("meta", {})
        self._vec = self.pipeline.named_steps["tfidf"]
        self._clf = self.pipeline.named_steps["clf"]
        self._fake_idx = list(self._clf.classes_).index(FAKE)
        self._terms = self._vec.get_feature_names_out()

    def predict(self, text: str, top_k: int = 8) -> dict:
        cleaned = clean_text(text)
        if not cleaned:
            raise ValueError("The text has no readable words.")

        x = self._vec.transform([cleaned])
        p_fake = float(self._clf.predict_proba(x)[0, self._fake_idx])

        # Logistic regression is linear, so each word's push on the decision is
        # (its tf-idf value) x (its coefficient). Positive pushes toward "fake".
        coefs = self._clf.coef_[0]
        row = x.tocoo()
        contributions = [
            (str(self._terms[j]), float(v * coefs[j])) for j, v in zip(row.col, row.data)
        ]
        fake_terms = sorted((c for c in contributions if c[1] > 0), key=lambda c: -c[1])[:top_k]
        real_terms = sorted((c for c in contributions if c[1] < 0), key=lambda c: c[1])[:top_k]

        if p_fake >= FAKE_THRESHOLD:
            verdict = "fake"
        elif p_fake <= REAL_THRESHOLD:
            verdict = "real"
        else:
            verdict = "uncertain"

        words = word_count(text)
        return {
            "verdict": verdict,
            "fake_probability": round(p_fake, 4),
            "word_count": words,
            "short_text": words < MIN_RELIABLE_WORDS,
            "top_fake_terms": [{"term": t, "weight": round(w, 4)} for t, w in fake_terms],
            "top_real_terms": [{"term": t, "weight": round(abs(w), 4)} for t, w in real_terms],
        }
