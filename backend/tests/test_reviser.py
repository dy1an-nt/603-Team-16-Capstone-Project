"""Reviser logic tests (FR-15 to FR-18). No LLM and no database."""

import pytest

from app.schemas import SuggestionDecision, SuggestionDraft
from app.services import reviser

RESUME = """Jane Doe
jane@example.com

Summary
Backend developer who builds APIs.

Experience
Software Intern at Acme
- Built REST APIs in Python and PostgreSQL

Skills
Python, SQL
"""

SECTIONS = {
    "summary": "Backend developer who builds APIs.",
    "experience": "Software Intern at Acme\n- Built REST APIs in Python and PostgreSQL",
    "skills": "Python, SQL",
}


def draft(original, revised, section="experience", keywords=()):
    return SuggestionDraft(
        section=section,
        original=original,
        revised=revised,
        reason="Clearer.",
        keywords_added=list(keywords),
    )


def test_prepare_keeps_grounded_suggestion_unflagged():
    out = reviser.prepare(
        [draft("- Built REST APIs in Python and PostgreSQL",
               "- Built REST APIs in Python backed by PostgreSQL for internal tools")],
        RESUME,
        SECTIONS,
        ["Python", "PostgreSQL", "Docker"],
    )

    assert len(out) == 1
    assert out[0].flagged is False
    assert out[0].accepted is None


def test_prepare_flags_new_skill_and_number():
    out = reviser.prepare(
        [draft("- Built REST APIs in Python and PostgreSQL",
               "- Built 12 REST APIs in Python and PostgreSQL, deployed with Docker")],
        RESUME,
        SECTIONS,
        ["Python", "PostgreSQL", "Docker"],
    )

    assert out[0].flagged is True
    assert "new skill: Docker" in out[0].flag_reasons
    assert "new number: 12" in out[0].flag_reasons


def test_prepare_drops_unusable_suggestions():
    drafts = [
        draft("- Built GraphQL APIs", "- Built fast GraphQL APIs"),  # not in the resume
        draft("Python, SQL", "Python, SQL, Go", section="skills"),  # not revisable
        draft("Backend developer who builds APIs.", "Backend developer who builds APIs.",
              section="summary"),  # no change
        draft("   ", "Something", section="summary"),  # blank original
        draft("Python, SQL", "Python and SQL"),  # text from skills, labeled experience
    ]

    assert reviser.prepare(drafts, RESUME, SECTIONS, []) == []


def test_prepare_strips_whitespace_around_original():
    out = reviser.prepare(
        [draft("  Backend developer who builds APIs.\n", "Backend developer who builds REST APIs.",
               section="summary")],
        RESUME,
        SECTIONS,
        [],
    )

    assert out[0].original == "Backend developer who builds APIs."


def test_apply_decisions_sets_only_listed_suggestions():
    suggestions = [{"accepted": None}, {"accepted": True}, {"accepted": None}]

    out = reviser.apply_decisions(
        suggestions,
        [SuggestionDecision(index=0, accepted=True), SuggestionDecision(index=2, accepted=False)],
    )

    assert [s["accepted"] for s in out] == [True, True, False]
    assert suggestions[0]["accepted"] is None  # input not mutated


def test_apply_decisions_rejects_out_of_range_index():
    with pytest.raises(IndexError):
        reviser.apply_decisions([{"accepted": None}], [SuggestionDecision(index=1, accepted=True)])


def test_apply_accepted_swaps_only_accepted_text():
    suggestions = [
        {"original": "Backend developer who builds APIs.",
         "revised": "Backend developer who builds REST APIs.", "accepted": True},
        {"original": "- Built REST APIs in Python and PostgreSQL",
         "revised": "- Built APIs", "accepted": False},
    ]

    text = reviser.apply_accepted(RESUME, suggestions)

    assert "Backend developer who builds REST APIs." in text
    assert "- Built REST APIs in Python and PostgreSQL" in text


def test_apply_accepted_uses_first_of_two_rewrites_of_same_text():
    original = "- Built REST APIs in Python and PostgreSQL"
    suggestions = [
        {"original": original, "revised": "- First rewrite", "accepted": True},
        {"original": original, "revised": "- Second rewrite", "accepted": True},
    ]

    text = reviser.apply_accepted(RESUME, suggestions)

    assert "- First rewrite" in text
    assert "- Second rewrite" not in text
