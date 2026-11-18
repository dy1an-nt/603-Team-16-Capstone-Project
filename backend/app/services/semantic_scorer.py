
"""Semantic similarity scoring using Sentence Transformers (FR-13)."""

from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"


def load_model() -> SentenceTransformer:
    """Load the embedding model. Called once during application startup."""
    return SentenceTransformer(MODEL_NAME)


def score(
    model: SentenceTransformer,
    resume_text: str,
    job_description: str,
) -> float:
    """Calculate cosine similarity between resume and job description."""

    if not resume_text.strip() or not job_description.strip():
        return 0.0

    embeddings = model.encode(
        [resume_text, job_description],
        convert_to_tensor=True,
        normalize_embeddings=True,
    )

    # Normalized embeddings: dot product equals cosine similarity.
    similarity = float((embeddings[0] @ embeddings[1]).item())

    # Keep S within the required 0–1 scoring range.
    return max(0.0, min(1.0, similarity))
