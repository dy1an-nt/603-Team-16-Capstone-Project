"""Job match score (FR-13). Deterministic (NFR-3).

Match = 100 * (0.5*R + 0.2*P + 0.1*T + 0.2*S)
  R = share of required skills found
  P = share of preferred skills found
  T = job title present (0 or 1)
  S = embedding cosine similarity (added Week 5)
"""

import re

from app.schemas import JobRequirements, KeywordReport

WEIGHTS = {"required": 0.5, "preferred": 0.2, "title": 0.1, "semantic": 0.2}

SYNONYMS: dict[str, str] = {
    "js": "javascript",
    "ts": "typescript",
    "ml": "machine learning",
    "postgres": "postgresql",
}


def normalize(term: str) -> str:
    t = re.sub(r"\s+", " ", term.strip().lower())
    return SYNONYMS.get(t, t)


def contains(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(normalize(term))}(?![a-z0-9])", text) is not None


def keyword_report(resume_text: str, skills: list[str]) -> KeywordReport:
    text = normalize(resume_text)
    for short, full in SYNONYMS.items():
        text = re.sub(rf"(?<![a-z0-9]){short}(?![a-z0-9])", full, text)
    report = KeywordReport()
    for skill in skills:
        (report.matched if contains(text, skill) else report.missing).append(skill)
    return report


def score(
    resume_text: str, job: JobRequirements, semantic: float = 0.0
) -> tuple[int, KeywordReport]:
    req = keyword_report(resume_text, job.required_skills)
    pref = keyword_report(resume_text, job.preferred_skills)

    r = len(req.matched) / len(job.required_skills) if job.required_skills else 1.0
    p = len(pref.matched) / len(job.preferred_skills) if job.preferred_skills else 1.0
    t = 1.0 if job.job_title and contains(normalize(resume_text), job.job_title) else 0.0

    total = 100 * (
        WEIGHTS["required"] * r
        + WEIGHTS["preferred"] * p
        + WEIGHTS["title"] * t
        + WEIGHTS["semantic"] * semantic
    )
    combined = KeywordReport(
        matched=req.matched + pref.matched,
        missing=req.missing + pref.missing,
    )
    return round(total), combined
