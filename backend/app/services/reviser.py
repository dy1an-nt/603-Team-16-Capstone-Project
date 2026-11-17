"""Reviser logic that runs in code, not in the LLM (FR-15 to FR-18)."""

from app.schemas import Suggestion, SuggestionDecision, SuggestionDraft
from app.services import grounding
from app.services.llm import REVISABLE_SECTIONS


def prepare(
    drafts: list[SuggestionDraft],
    resume_text: str,
    sections: dict[str, str],
    skills: list[str],
) -> list[Suggestion]:
    """Drops unusable LLM suggestions, then runs the grounding check on the rest (FR-18).

    A suggestion is dropped when its section is not revisable, when its `original`
    is not text from that section (so it could never be applied, or would be
    applied to the wrong place), or when it changes nothing.
    """
    kept = []
    for draft in drafts:
        original = draft.original.strip()
        revised = draft.revised.strip()
        if (
            draft.section not in REVISABLE_SECTIONS
            or not original
            or not revised
            or original not in sections.get(draft.section, "")
            or original not in resume_text
            or original == revised
        ):
            continue
        clean = draft.model_copy(update={"original": original, "revised": revised})
        kept.append(grounding.flag(clean, resume_text, skills))
    return kept


def apply_decisions(suggestions: list[dict], decisions: list[SuggestionDecision]) -> list[dict]:
    """Returns a copy with `accepted` set from each decision (FR-16).

    Raises IndexError for an index outside the list. Suggestions without a
    decision keep their current value.
    """
    updated = [dict(s) for s in suggestions]
    for decision in decisions:
        if decision.index >= len(updated):
            raise IndexError(decision.index)
        updated[decision.index]["accepted"] = decision.accepted
    return updated


def apply_accepted(resume_text: str, suggestions: list[dict]) -> str:
    """Rebuilds the resume text with every accepted suggestion swapped in (FR-17).

    Suggestions apply in list order, each to the first remaining match of its
    original text. If two accepted suggestions rewrite the same text, only the
    first applies, since its original is gone after the swap.
    """
    text = resume_text
    for s in suggestions:
        if s.get("accepted") and s["original"] in text:
            text = text.replace(s["original"], s["revised"], 1)
    return text
