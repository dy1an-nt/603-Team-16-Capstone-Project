"""Grounding check (FR-18, NFR-6): flag rewrites that add facts not in the original resume."""

import re

from app.schemas import Suggestion, SuggestionDraft

NUMBER = re.compile(r"\d+(?:[.,]\d+)?%?")
PROPER_NOUN = re.compile(r"\b[A-Z][a-zA-Z0-9+#.]+\b")
BULLET = "-*\u2022 \t"


def _new_items(pattern: re.Pattern[str], revised: str, original_resume: str) -> list[str]:
    return sorted({m for m in pattern.findall(revised) if m not in original_resume})


def flag(suggestion: SuggestionDraft, original_resume: str, skills: list[str]) -> Suggestion:
    reasons: list[str] = []

    for n in _new_items(NUMBER, suggestion.revised, original_resume):
        reasons.append(f"new number: {n}")

    lower_resume = original_resume.lower()
    for skill in skills:
        s = skill.lower()
        if s in suggestion.revised.lower() and s not in lower_resume:
            reasons.append(f"new skill: {skill}")

    # The first word is capitalized by grammar, not because it is a name.
    first = PROPER_NOUN.match(suggestion.revised.lstrip(BULLET))
    first_word = first.group(0) if first else ""
    for noun in _new_items(PROPER_NOUN, suggestion.revised, original_resume):
        if noun != first_word and f"new skill: {noun}" not in reasons:
            reasons.append(f"new name: {noun}")

    return Suggestion(
        **suggestion.model_dump(include=set(SuggestionDraft.model_fields)),
        flagged=bool(reasons),
        flag_reasons=reasons,
    )
