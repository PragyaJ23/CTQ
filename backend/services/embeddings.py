"""Embedding service for semantic similarity between patients and trials.

Primary implementation: sentence-transformers (all-MiniLM-L6-v2 by default -
lightweight, CPU-friendly, 384-dim vectors).

Fallback: a deterministic hashed bag-of-words embedding, so the application
still runs (with lower-quality similarity) when the model cannot be
downloaded, e.g. offline demos.
"""
import hashlib
import math
import re
from typing import List

import numpy as np

from config import settings

_DIM = 384
_model = None
_model_failed = False
_FALLBACK_MARKER = "__fallback__"


def _load_model():
    global _model, _model_failed
    if _model is not None or _model_failed:
        return _model
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(f"sentence-transformers/{settings.embedding_model}")
        print(f"[embeddings] loaded sentence-transformers model '{settings.embedding_model}'")
    except Exception as exc:  # offline / no network / not installed
        print(f"[embeddings] WARNING: could not load model ({exc}); using fallback hashed embeddings")
        _model = _FALLBACK_MARKER
        _model_failed = True
    return _model


_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "to", "in", "on", "for", "with",
    "is", "are", "be", "been", "at", "by", "as", "this", "that", "it",
    "from", "will", "than", "then", "their", "have", "has", "had",
}


def _tokenize(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1 and t not in _STOPWORDS]


def _hashed_embedding(text: str) -> np.ndarray:
    """Deterministic hashed bag-of-words vector (cosine-comparable)."""
    vec = np.zeros(_DIM, dtype=np.float32)
    tokens = _tokenize(text)
    if not tokens:
        return vec
    for tok in tokens:
        digest = hashlib.md5(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % _DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


def embed_texts(texts: List[str]) -> np.ndarray:
    """Embed a list of strings -> (n, dim) float32 matrix (L2-normalised)."""
    model = _load_model()
    if model == _FALLBACK_MARKER:
        return np.vstack([_hashed_embedding(t) for t in texts])
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(vectors, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors, clipped to [0, 1]."""
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(max(0.0, min(1.0, np.dot(a, b) / denom)))


def score_to_match_percent(similarity: float) -> int:
    """Cosine similarity (~0.3-0.9 typical) rescaled to a friendly 0-100%."""
    scaled = (similarity - 0.2) / 0.6  # 0.2 -> 0%, 0.8 -> 100%
    return int(round(max(0.0, min(1.0, scaled)) * 100))
