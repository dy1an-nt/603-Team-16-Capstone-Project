from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import analyses, auth, resumes, revisions

settings = get_settings()

app = FastAPI(
    title="Resume Reviewer API",
    description="CSC 603 Team 16 capstone: resume scanner, ATS scorer, and reviser.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(resumes.router)
app.include_router(analyses.router)
app.include_router(revisions.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
