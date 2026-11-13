
"""Resume scanner: FR-4 to FR-8, FR-20. Security: NFR-9, NFR-11."""

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.config import get_settings
from app.db import get_db
from app.repositories import ResumeRepository
from app.schemas import ResumeOut, ResumeSummary
from app.security import CurrentUser, get_current_user
from app.services import parser

# Every route here needs a logged-in user (NFR-8).
router = APIRouter(
    prefix="/resumes",
    tags=["resumes"],
    dependencies=[Depends(get_current_user)],
)

Db = Annotated[psycopg.Connection, Depends(get_db)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ResumeOut)
async def upload_resume(
    user: CurrentUser,
    conn: Db,
    file: UploadFile,
):
    filename = file.filename or ""

    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if extension not in {"pdf", "docx"}:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only PDF and DOCX files are supported.",
        )

    max_size = get_settings().max_upload_mb * 1024 * 1024

    data = await file.read(max_size + 1)
    await file.close()

    if len(data) > max_size:
        raise HTTPException(
            413,
            f"File exceeds the {get_settings().max_upload_mb} MB upload limit.",
        )

    try:
        # Parsing is blocking (pdfplumber, and LibreOffice for DOCX), so it runs
        # in a worker thread instead of stalling every other request.
        raw_text, parsing_metadata = await run_in_threadpool(
            parser.extract_document, data, filename
        )
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            str(exc),
        ) from exc

    sections = parser.split_sections(raw_text)

    repository = ResumeRepository(conn)

    resume_id = repository.create(
        user["id"],
        filename,
        raw_text,
        sections,
        parsing_metadata,
    )

    return repository.get(user["id"], resume_id)


@router.get("", response_model=list[ResumeSummary])
def list_resumes():
    # TODO(Week 7): list current user's resumes
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "list not implemented")


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(
    resume_id: int,
    user: CurrentUser,
    conn: Db,
):
    resume = ResumeRepository(conn).get(user["id"], resume_id)

    if resume is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "Resume not found.",
        )

    return resume


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(resume_id: int):
    # TODO(Week 7): delete if owned by current user
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "delete not implemented")
