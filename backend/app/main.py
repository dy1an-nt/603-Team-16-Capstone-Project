from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import analyses, auth, resumes, revisions
from app.services import semantic_scorer

settings = get_settings()


@asynccontextmanager
async def lifespan(api: FastAPI):
    # Load the embedding model once when this application starts.
    api.state.semantic_model = semantic_scorer.load_model()

    yield

    # Release the application reference during shutdown.
    api.state.semantic_model = None


api = FastAPI(
    title="Resume Reviewer API",
    description="CSC 603 Team 16 capstone: resume scanner, ATS scorer, and reviser.",
    version="0.1.0",
    lifespan=lifespan,
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
