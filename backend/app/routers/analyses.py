"""ATS scorer and job match: FR-9 to FR-13, FR-20."""

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_db
from app.repositories import AnalysisRepository, ResumeRepository
from app.schemas import AnalysisCreate, AnalysisOut, RevisionOut
from app.security import CurrentUser, get_current_user
from app.services import ats_scorer

router = APIRouter(
    prefix="/analyses",
    tags=["analyses"],
    dependencies=[Depends(get_current_user)],
)

Db = Annotated[psycopg.Connection, Depends(get_db)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AnalysisOut)
def create_analysis(
    body: AnalysisCreate,
    user: CurrentUser,
    conn: Db,
):
    # Retrieve the resume while enforcing ownership.
    resume = ResumeRepository(conn).get(user["id"], body.resume_id)

    if resume is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Resume not found.",
        )

    # Job-description analysis will be implemented after the LLM service.
    if body.job_description is not None:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "Job-description analysis is not implemented yet.",
        )

    # Calculate the deterministic ATS score.
    ats_score, issues = ats_scorer.score(
        resume["sections"],
        resume.get("parsing_metadata"),
    )

    repository = AnalysisRepository(conn)

    analysis_id = repository.create(
        user_id=user["id"],
        resume_id=body.resume_id,
        ats_score=ats_score,
        issues=[issue.model_dump() for issue in issues],
    )

    if analysis_id is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Resume not found.",
        )

    # Return the saved analysis in the API response format.
    analysis = repository.get(user["id"], analysis_id)

    return analysis


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: int):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "get not implemented")


@router.post(
    "/{analysis_id}/revisions",
    status_code=status.HTTP_201_CREATED,
    response_model=RevisionOut,
)
def create_revision(analysis_id: int):
    # TODO(Week 6): llm.generate_suggestions(), grounding.flag(), save
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "revision not implemented")
