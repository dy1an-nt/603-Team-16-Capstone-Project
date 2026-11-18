"""Reviser: FR-16, FR-17, FR-19."""

from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_db
from app.repositories import AnalysisRepository, ResumeRepository, RevisionRepository
from app.schemas import ExportFormat, JobRequirements, RevisionOut, RevisionUpdate
from app.security import CurrentUser, get_current_user
from app.services import match_scorer, reviser, semantic_scorer

# Every route here needs a logged-in user (NFR-8).
router = APIRouter(
    prefix="/revisions", tags=["revisions"], dependencies=[Depends(get_current_user)]
)

Db = Annotated[psycopg.Connection, Depends(get_db)]
SemanticModel = Annotated[Any | None, Depends(semantic_scorer.get_model)]


@router.patch("/{revision_id}", response_model=RevisionOut)
def update_revision(
    revision_id: int,
    body: RevisionUpdate,
    user: CurrentUser,
    conn: Db,
    semantic_model: SemanticModel,
):
    repository = RevisionRepository(conn)
    revision = repository.get(user["id"], revision_id)
    if revision is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revision not found.")

    try:
        suggestions = reviser.apply_decisions(revision["suggestions"], body.decisions)
    except IndexError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"No suggestion at index {exc.args[0]}."
        ) from exc

    analysis = AnalysisRepository(conn).get(user["id"], revision["analysis_id"])
    resume = ResumeRepository(conn).get(user["id"], analysis["resume_id"]) if analysis else None
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Revision not found.")

    revised_text = reviser.apply_accepted(resume["raw_text"], suggestions)
    # Only the match score is re-scored (docs/api-contract.md assumptions).
    new_match_score = None
    if analysis["job_requirements"] is not None:
        if semantic_model is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Match scoring is unavailable. Try again later.",
            )
        job = JobRequirements.model_validate(analysis["job_requirements"])
        new_match_score, _ = match_scorer.score_with_model(
            semantic_model, revised_text, job, analysis["job_text"]
        )

    repository.update(user["id"], revision_id, suggestions, revised_text, new_match_score)
    return repository.get(user["id"], revision_id)


@router.get("/{revision_id}/export")
def export_revision(revision_id: int, fmt: ExportFormat = "txt"):
    # TODO(Week 7): return TXT or DOCX
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "export not implemented")
