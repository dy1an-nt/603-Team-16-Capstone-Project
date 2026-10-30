"""ATS scorer and job match: FR-9 to FR-13, FR-20."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas import AnalysisCreate, AnalysisOut, RevisionOut
from app.security import get_current_user

# Every route here needs a logged-in user (NFR-8).
router = APIRouter(prefix="/analyses", tags=["analyses"], dependencies=[Depends(get_current_user)])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AnalysisOut)
def create_analysis(body: AnalysisCreate):
    # TODO(Week 4-5): ats_scorer.score(), optional llm.extract_job_requirements(),
    # match_scorer.score(), save analysis
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "analysis not implemented")


@router.get("/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: int):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "get not implemented")


@router.post(
    "/{analysis_id}/revisions", status_code=status.HTTP_201_CREATED, response_model=RevisionOut
)
def create_revision(analysis_id: int):
    # TODO(Week 6): llm.generate_suggestions(), grounding.flag(), save
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "revision not implemented")
