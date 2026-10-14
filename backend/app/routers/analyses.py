"""ATS scorer and job match: FR-9 to FR-13, FR-20."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_analysis():
    # TODO(Week 4-5): ats_scorer.score(), optional llm.extract_job_requirements(),
    # match_scorer.score(), save analysis
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "analysis not implemented")


@router.get("/{analysis_id}")
def get_analysis(analysis_id: int):
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "get not implemented")


@router.post("/{analysis_id}/revisions", status_code=status.HTTP_201_CREATED)
def create_revision(analysis_id: int):
    # TODO(Week 6): llm.generate_suggestions(), grounding.flag(), save
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "revision not implemented")
