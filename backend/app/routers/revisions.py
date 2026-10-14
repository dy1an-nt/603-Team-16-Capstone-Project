"""Reviser: FR-16, FR-17, FR-19."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/revisions", tags=["revisions"])


@router.patch("/{revision_id}")
def update_revision(revision_id: int):
    # TODO(Week 6): apply accept/reject flags, rebuild text, re-score
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "update not implemented")


@router.get("/{revision_id}/export")
def export_revision(revision_id: int, fmt: str = "txt"):
    # TODO(Week 7): return TXT or DOCX
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "export not implemented")
