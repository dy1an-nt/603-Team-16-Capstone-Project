"""Rule-based ATS score (FR-9, FR-10). Deterministic, no LLM (NFR-3)."""

from app.schemas import AtsIssue

REQUIRED_SECTIONS = ["experience", "education", "skills"]


def score(sections: dict[str, str]) -> tuple[int, list[AtsIssue]]:
    """Start at 100 and subtract a fixed penalty per violated rule."""
    issues: list[AtsIssue] = []

    for name in REQUIRED_SECTIONS:
        if not sections.get(name):
            issues.append(
                AtsIssue(
                    rule=f"missing_{name}",
                    message=f"No '{name.title()}' section found.",
                    fix=f"Add a section with the standard heading '{name.title()}'.",
                    penalty=15,
                )
            )

    # TODO(Week 4): contact info, multi-column layout, tables, headers/footers,
    # page count, date format consistency, unparseable symbols

    total = max(0, 100 - sum(i.penalty for i in issues))
    return total, issues
