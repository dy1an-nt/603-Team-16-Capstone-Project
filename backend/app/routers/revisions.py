"""Reviser: FR-16, FR-17, FR-19."""

from fastapi import APIRouter, HTTPException, status

from app.schemas import ExportFormat, RevisionOut, RevisionUpdate

router = APIRouter(prefix="/revisions", tags=["revisions"])


@router.patch("/{revision_id}", response_model=RevisionOut)
def update_revision(revision_id: int, body: RevisionUpdate):
    # TODO(Week 6): apply accept/reject flags, rebuild text, re-score
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "update not implemented")


@router.get("/{revision_id}/export")
def export_revision(revision_id: int, fmt: ExportFormat = "txt"):
    # TODO(Week 7): return TXT or DOCX
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "export not implemented")
