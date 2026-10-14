"""Pydantic models for API requests, responses, and LLM output validation (NFR-5)."""

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------
class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


# ---------- Scoring ----------
class AtsIssue(BaseModel):
    rule: str
    message: str
    fix: str
    penalty: int


class KeywordReport(BaseModel):
    matched: list[str] = []
    missing: list[str] = []


# ---------- LLM output: job description extraction (FR-12) ----------
class JobRequirements(BaseModel):
    job_title: str
    required_skills: list[str]
    preferred_skills: list[str] = []
    responsibilities: list[str] = []


# ---------- LLM output: revision suggestions (FR-14, FR-15) ----------
class Suggestion(BaseModel):
    section: str
    original: str
    revised: str
    reason: str
    keywords_added: list[str] = []
    flagged: bool = False
    flag_reasons: list[str] = []
    accepted: bool | None = None


class SuggestionList(BaseModel):
    suggestions: list[Suggestion]
