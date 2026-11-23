"""ATS scorer and job match: FR-9 to FR-13, FR-20."""

import logging
from typing import Annotated, Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_db
from app.repositories import (
    AnalysisRepository,
    JobDescriptionRepository,
    ResumeRepository,
    RevisionRepository,
)
from app.schemas import AnalysisCreate, AnalysisOut, JobRequirements, RevisionOut
from app.security import CurrentUser, get_current_user
from app.services import ats_scorer, llm, match_scorer, reviser, semantic_scorer

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analyses",
    tags=["analyses"],
    dependencies=[Depends(get_current_user)],
)

Db = Annotated[psycopg.Connection, Depends(get_db)]
Llm = Annotated[llm.LLMClient, Depends(llm.get_llm_client)]
SemanticModel = Annotated[Any | None, Depends(semantic_scorer.get_model)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AnalysisOut)
def create_analysis(
    body: AnalysisCreate,
    user: CurrentUser,
    conn: Db,
    llm_client: Llm,
    semantic_model: SemanticModel,
):
    # Retrieve the resume while enforcing ownership.
    resume = ResumeRepository(conn).get(user["id"], body.resume_id)

    if resume is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Resume not found.",
        )

    # Extract job requirements before any write, so an LLM failure saves nothing.
    job = None
    if body.job_description is not None:
        if semantic_model is None:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Match scoring is unavailable. Try again later or run an ATS-only analysis.",
            )
        try:
            job = llm.extract_job_requirements(llm_client, body.job_description)
        except llm.LLMError as exc:
            logger.warning("Job description extraction failed: %s", exc)
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Job description analysis failed. Try again or run an ATS-only analysis.",
            ) from exc

    # Calculate the deterministic ATS score.
    ats_score, issues = ats_scorer.score(
        resume["sections"],
        resume.get("parsing_metadata"),
    )

    job_description_id = None
    match_score = None
    keywords = None
    if job is not None:
        job_description_id = JobDescriptionRepository(conn).create(
            user["id"], body.resume_id, body.job_description, job.model_dump()
        )
        if job_description_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found.")
        match_score, report = match_scorer.score_with_model(
            semantic_model, resume["raw_text"], job, body.job_description
        )
        keywords = report.model_dump()

    repository = AnalysisRepository(conn)

    analysis_id = repository.create(
        user_id=user["id"],
        resume_id=body.resume_id,
        ats_score=ats_score,
        issues=[issue.model_dump() for issue in issues],
        job_description_id=job_description_id,
        match_score=match_score,
        keywords=keywords,
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
def get_analysis(
    analysis_id: int,
    user: CurrentUser,
    conn: Db,
):
    analysis = AnalysisRepository(conn).get(
        user["id"],
        analysis_id,
    )

    if analysis is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Analysis not found.",
        )

    return analysis


@router.post(
    "/{analysis_id}/revisions",
    status_code=status.HTTP_201_CREATED,
    response_model=RevisionOut,
)
def create_revision(
    analysis_id: int,
    user: CurrentUser,
    conn: Db,
    llm_client: Llm,
):
    analysis = AnalysisRepository(conn).get(user["id"], analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found.")
    resume = ResumeRepository(conn).get(user["id"], analysis["resume_id"])
    if resume is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found.")

    job = None
    skills: list[str] = []
    missing: list[str] = []
    if analysis["job_requirements"] is not None:
        job = JobRequirements.model_validate(analysis["job_requirements"])
        skills = job.required_skills + job.preferred_skills
        missing = (analysis["keywords"] or {}).get("missing", [])

    # A resume with no summary, experience, or projects text has nothing to rewrite.
    suggestions = []
    if any(resume["sections"].get(name) for name in llm.REVISABLE_SECTIONS):
        try:
            drafts = llm.generate_suggestions(llm_client, resume["sections"], job, missing)
        except llm.LLMError as exc:
            logger.warning("Revision suggestions failed: %s", exc)
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "Could not generate suggestions. Try again.",
            ) from exc
        suggestions = reviser.prepare(
            drafts.suggestions, resume["raw_text"], resume["sections"], skills
        )

    repository = RevisionRepository(conn)
    revision_id = repository.create(
        user["id"], analysis_id, [s.model_dump() for s in suggestions]
    )
    if revision_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found.")
    return repository.get(user["id"], revision_id)
