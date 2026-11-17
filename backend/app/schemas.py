"""Pydantic models for API requests, responses, and LLM output validation (NFR-5).

docs/api-contract.md shows an example request and response for each endpoint.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator


# ---------- Auth (FR-1, FR-2, FR-3) ----------
class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime


class TokenOut(BaseModel):
    # Sent back as `Authorization: Bearer <access_token>` (NFR-8).
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds


# ---------- Resumes (FR-4 to FR-8, FR-20) ----------
class ResumeSummary(BaseModel):
    id: int
    filename: str | None
    created_at: datetime


class ResumeOut(ResumeSummary):
    # Keys come from services.parser: contact, summary, education, experience,
    # projects, skills. Only headings found in the resume are present.
    sections: dict[str, str]


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

    @field_validator("required_skills", "preferred_skills", "responsibilities")
    @classmethod
    def drop_blank_and_duplicate(cls, v: list[str]) -> list[str]:
        # A blank skill would match every resume in match_scorer.
        seen: set[str] = set()
        cleaned = []
        for item in v:
            text = item.strip()
            if text and text.lower() not in seen:
                seen.add(text.lower())
                cleaned.append(text)
        return cleaned


# ---------- Analyses (FR-9 to FR-13, FR-20) ----------
NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AnalysisCreate(BaseModel):
    resume_id: int
    # Pasted job description text (FR-11). Omit for an ATS-only analysis.
    job_description: NonBlankText | None = None


class AnalysisOut(BaseModel):
    id: int
    resume_id: int
    job_description_id: int | None
    ats_score: int = Field(ge=0, le=100)
    issues: list[AtsIssue]
    # The three fields below are null only for an ATS-only analysis. If LLM
    # extraction fails, the request fails with 502 and nothing is saved.
    job_requirements: JobRequirements | None
    match_score: int | None = Field(ge=0, le=100)
    keywords: KeywordReport | None
    created_at: datetime


# ---------- LLM output: revision suggestions (FR-14, FR-15) ----------
class SuggestionDraft(BaseModel):
    # Only the fields the LLM may set. Extra keys such as "flagged" or
    # "accepted" in its output are dropped during validation.
    section: str
    original: str
    revised: str
    reason: str
    keywords_added: list[str] = []


class SuggestionList(BaseModel):
    suggestions: list[SuggestionDraft]


class Suggestion(SuggestionDraft):
    # Set by services.grounding (FR-18) and the user (FR-16), never by the LLM.
    flagged: bool = False
    flag_reasons: list[str] = []
    accepted: bool | None = None


# ---------- Revisions (FR-14 to FR-19) ----------
class SuggestionDecision(BaseModel):
    # Position of the suggestion in RevisionOut.suggestions, starting at 0.
    index: int = Field(ge=0)
    accepted: bool


class RevisionUpdate(BaseModel):
    decisions: list[SuggestionDecision] = Field(min_length=1)

    @field_validator("decisions")
    @classmethod
    def unique_indexes(cls, v: list[SuggestionDecision]) -> list[SuggestionDecision]:
        if len({d.index for d in v}) != len(v):
            raise ValueError("each suggestion index may appear only once")
        return v


class RevisionOut(BaseModel):
    id: int
    analysis_id: int
    suggestions: list[Suggestion]
    # Null until the first PATCH applies accepted suggestions (FR-17).
    revised_text: str | None
    # Before and after match scores (FR-17). Null for an ATS-only analysis.
    original_match_score: int | None = Field(ge=0, le=100)
    new_match_score: int | None = Field(ge=0, le=100)
    created_at: datetime


ExportFormat = Literal["txt", "docx"]
