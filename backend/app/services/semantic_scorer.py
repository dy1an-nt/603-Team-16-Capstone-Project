"""Semantic similarity scoring using Sentence Transformers (FR-13)."""

import logging
from typing import Any

import numpy as np
from fastapi import Request

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"

# MiniLM reads at most 256 tokens and silently drops the rest. 128 words stays
# under that limit for typical resume text, so every chunk is read in full.
CHUNK_WORDS = 128


def load_model() -> Any | None:
    """Load the embedding model once at startup. Returns None if it fails, so
    the app still starts and ATS-only analyses keep working (NFR-4)."""
    try:
        # Imported here because torch is slow to import and only this needs it.
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(MODEL_NAME)
    except Exception:
        logger.exception("Semantic model failed to load")
        return None


def get_model(request: Request) -> Any | None:
    """FastAPI dependency. Tests override it with a fake model."""
    return getattr(request.app.state, "semantic_model", None)


def chunks(text: str) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + CHUNK_WORDS]) for i in range(0, len(words), CHUNK_WORDS)]


def embed(model: Any, text: str) -> np.ndarray:
    """Mean of the chunk embeddings, normalized to unit length."""
    vectors = np.asarray(model.encode(chunks(text), normalize_embeddings=True))
    mean = vectors.mean(axis=0)
    norm = np.linalg.norm(mean)
    return mean / norm if norm else mean


def score(model: Any, resume_text: str, job_description: str) -> float:
    """Cosine similarity between resume and job description, clamped to 0 to 1."""
    if not resume_text.strip() or not job_description.strip():
        return 0.0

    similarity = float(embed(model, resume_text) @ embed(model, job_description))
    return max(0.0, min(1.0, similarity))
