"""Resume scanner: FR-4 to FR-8, FR-20. Security: NFR-9, NFR-11."""

from fastapi import APIRouter, HTTPException, UploadFile, status

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_resume(file: UploadFile):
    # TODO(Week 3): validate type/size, call services.parser, save, return sections
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "upload not implemented")


@router.get("")
def list_resumes():
    # TODO(Week 7): list current user's resumes
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "list not implemented")


@router.get("/{resume_id}")
def get_resume(resume_id: int):
    # TODO(Week 3): return resume if owned by current user
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "get not implemented")


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: int):
    # TODO(Week 7): delete if owned by current user
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "delete not implemented")
