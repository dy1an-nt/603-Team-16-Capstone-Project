from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import analyses, auth, resumes, revisions

settings = get_settings()

api = FastAPI(
    title="Resume Reviewer API",
    description="CSC 603 Team 16 capstone: resume scanner, ATS scorer, and reviser.",
    version="0.1.0",
)

api.include_router(auth.router)
api.include_router(resumes.router)
api.include_router(analyses.router)
api.include_router(revisions.router)


@api.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# Outer middleware ensures CORS headers on unhandled 500 responses.
app = CORSMiddleware(
    app=api,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)
