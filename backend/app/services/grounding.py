"""Grounding check (FR-18, NFR-6): flag rewrites that add facts not in the original resume."""

import re

from app.schemas import Suggestion, SuggestionDraft

NUMBER = re.compile(r"\d+(?:[.,]\d+)?%?")
PROPER_NOUN = re.compile(r"\b[A-Z][a-zA-Z0-9+#.]+\b")
BULLET = "-*\u2022 \t"
WORD = re.compile(r"[a-z0-9+#.]+")

# Words a bullet often starts with. A capitalized first word is skipped only if
# it is one of these or already appears in the resume, so a new name that opens
# a bullet is still flagged.
COMMON_FIRST_WORDS = frozenset("""
    a an the this these our my i we
    achieved added analyzed architected assisted automated boosted built
    collaborated conducted contributed coordinated created cut debugged
    delivered deployed designed developed directed drove enabled engineered
    established evaluated expanded facilitated fixed generated guided handled
    helped implemented improved increased integrated introduced launched led
    maintained managed mentored migrated monitored optimized organized
    oversaw owned partnered performed planned presented produced prototyped
    reduced refactored researched resolved reviewed scaled shipped simplified
    spearheaded streamlined supported tested trained transformed tuned wrote
""".split())


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

    # The first word is capitalized by grammar, so skip it only when it is a
    # known leading word or already in the resume.
    first = PROPER_NOUN.match(suggestion.revised.lstrip(BULLET))
    first_word = first.group(0) if first else ""
    known = COMMON_FIRST_WORDS | set(WORD.findall(lower_resume))
    if first_word.lower() not in known:
        first_word = ""
    for noun in _new_items(PROPER_NOUN, suggestion.revised, original_resume):
        if noun != first_word and f"new skill: {noun}" not in reasons:
            reasons.append(f"new name: {noun}")

    return Suggestion(
        **suggestion.model_dump(include=set(SuggestionDraft.model_fields)),
        flagged=bool(reasons),
        flag_reasons=reasons,
    )
