"""Grounding check (FR-18, NFR-6): flag rewrites that add facts not in the original resume."""

import re

from app.schemas import Suggestion

NUMBER = re.compile(r"\d+(?:[.,]\d+)?%?")
PROPER_NOUN = re.compile(r"\b[A-Z][a-zA-Z0-9+#.]+\b")


def _new_items(pattern: re.Pattern[str], revised: str, original_resume: str) -> list[str]:
    return sorted({m for m in pattern.findall(revised) if m not in original_resume})


def flag(suggestion: Suggestion, original_resume: str, skills: list[str]) -> Suggestion:
    reasons: list[str] = []

    for n in _new_items(NUMBER, suggestion.revised, original_resume):
        reasons.append(f"new number: {n}")

    lower_resume = original_resume.lower()
    for skill in skills:
        s = skill.lower()
        if s in suggestion.revised.lower() and s not in lower_resume:
            reasons.append(f"new skill: {skill}")

    first_word = suggestion.revised.split(" ", 1)[0] if suggestion.revised else ""
    for noun in _new_items(PROPER_NOUN, suggestion.revised, original_resume):
        if noun != first_word and f"new skill: {noun}" not in reasons:
            reasons.append(f"new name: {noun}")

    suggestion.flagged = bool(reasons)
    suggestion.flag_reasons = reasons
    return suggestion
