"""Resume scanner: FR-4 to FR-8, FR-20. Security: NFR-9, NFR-11."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.schemas import ResumeOut, ResumeSummary
from app.security import get_current_user

# Every route here needs a logged-in user (NFR-8).
router = APIRouter(prefix="/resumes", tags=["resumes"], dependencies=[Depends(get_current_user)])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ResumeOut)
async def upload_resume(file: UploadFile):
    # TODO(Week 3): validate type/size, call services.parser, save, return sections
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "upload not implemented")


@router.get("", response_model=list[ResumeSummary])
def list_resumes():
    # TODO(Week 7): list current user's resumes
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "list not implemented")


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(resume_id: int):
    # TODO(Week 3): return resume if owned by current user
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "get not implemented")


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: int):
    # TODO(Week 7): delete if owned by current user
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "delete not implemented")
