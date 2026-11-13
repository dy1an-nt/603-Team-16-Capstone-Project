"""Rule-based ATS score (FR-9, FR-10). Deterministic, no LLM (NFR-3)."""

import re

from app.schemas import AtsIssue
from app.services.parser import has_unusual_symbols

REQUIRED_SECTIONS = ["experience", "education", "skills"]

# All scoring penalties are centralized here.
PENALTIES = {
    "missing_section": 15,
    "missing_contact_info": 10,
    "multi_column_layout": 10,
    "tables": 10,
    "header_footer_content": 5,
    "too_many_pages": 5,
    "mixed_date_formats": 5,
    "unusual_symbols": 10,
}


def _get_resume_text(sections: dict[str, str]) -> str:
    """Combine section text for rules that inspect the resume's content."""
    return "\n".join(
        value for value in sections.values() if isinstance(value, str)
    )


class MissingSectionRule:
    """Checks whether required resume sections are present."""

    def check(self, sections: dict[str, str], metadata: dict) -> list[AtsIssue]:
        issues = []

        for name in REQUIRED_SECTIONS:
            if not sections.get(name) or not sections[name].strip():
                issues.append(
                    AtsIssue(
                        rule=f"missing_{name}",
                        message=f"No '{name.title()}' section found.",
                        fix=f"Add a section with the standard heading '{name.title()}'.",
                        penalty=PENALTIES["missing_section"],
                    )
                )

        return issues


class MissingContactInfoRule:
    """Checks whether the resume contains an email address or phone number."""

    EMAIL_PATTERN = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )

    # A run of digits and phone separators on one line. Whether it is a phone
    # number is decided by _is_phone, since a date range like "2019 - 2023"
    # has the same shape.
    PHONE_CANDIDATE = re.compile(r"(?<!\w)\+?\(?\d[\d \t().-]{6,}\d(?!\w)")

    @staticmethod
    def _is_phone(candidate: str) -> bool:
        groups = re.findall(r"\d+", candidate)
        digits = "".join(groups)

        # National numbers with area code have at least 10 digits, and E.164
        # allows at most 15.
        if not 10 <= len(digits) <= 15:
            return False

        # Runs of years, e.g. "2015 2016 2019".
        return not all(
            len(group) == 4 and 1900 <= int(group) <= 2099 for group in groups
        )

    @classmethod
    def _contains_phone(cls, candidate: str) -> bool:
        # The candidate can join a phone with a neighboring number, such as a
        # ZIP code or a second phone, so test each run of whole tokens.
        tokens = candidate.split()

        return any(
            cls._is_phone(" ".join(tokens[start:end]))
            for start in range(len(tokens))
            for end in range(start + 1, len(tokens) + 1)
        )

    def check(self, sections: dict[str, str], metadata: dict) -> list[AtsIssue]:
        text = _get_resume_text(sections)

        has_email = bool(self.EMAIL_PATTERN.search(text))
        has_phone = any(
            self._contains_phone(match.group())
            for match in self.PHONE_CANDIDATE.finditer(text)
        )

        if has_email or has_phone:
            return []

        return [
            AtsIssue(
                rule="missing_contact_info",
                message="No email address or phone number found.",
                fix="Add a valid email address or phone number so employers can contact you.",
                penalty=PENALTIES["missing_contact_info"],
            )
        ]


class MultiColumnLayoutRule:
    """Checks whether the parser detected a multi-column layout."""

    def check(self, sections: dict[str, str], metadata: dict) -> list[AtsIssue]:
        if not metadata.get("has_multiple_columns", False):
            return []

        return [
            AtsIssue(
                rule="multi_column_layout",
                message="The resume appears to use a multi-column layout.",
                fix="Use a single-column layout to improve ATS text extraction.",
                penalty=PENALTIES["multi_column_layout"],
            )
        ]


class TablesRule:
    """Checks whether the resume contains tables."""

    def check(self, sections: dict[str, str], metadata: dict) -> list[AtsIssue]:
        if not metadata.get("has_tables", False):
            return []

        return [
            AtsIssue(
                rule="tables",
                message="The resume contains tables that may interfere with ATS parsing.",
                fix="Replace tables with simple headings, paragraphs, and bullet points.",
                penalty=PENALTIES["tables"],
            )
        ]


class HeaderFooterContentRule:
    """Checks for text or images in document headers and footers."""

    def check(self, sections: dict[str, str], metadata: dict) -> list[AtsIssue]:
        has_content = (
            metadata.get("has_header_footer_text", False)
            or metadata.get("has_header_footer_images", False)
        )

        if not has_content:
            return []

        return [
            AtsIssue(
                rule="header_footer_content",
                message="The resume contains text or images in its headers or footers.",
                fix=(
                    "Move important contact details and resume content"
                    " into the main document body."
                ),
                penalty=PENALTIES["header_footer_content"],
            )
        ]


class TooManyPagesRule:
    """Checks whether the resume exceeds two pages."""

    def check(self, sections: dict[str, str], metadata: dict) -> list[AtsIssue]:
        page_count = metadata.get("page_count")

        if not isinstance(page_count, int) or isinstance(page_count, bool):
            return []

        if page_count <= 2:
            return []

        return [
            AtsIssue(
                rule="too_many_pages",
                message=f"The resume has {page_count} pages. The recommended maximum is two.",
                fix="Condense the resume to two pages or fewer while keeping relevant information.",
                penalty=PENALTIES["too_many_pages"],
            )
        ]


class MixedDateFormatsRule:
    """Checks whether multiple date formats are used in the resume."""

    DATE_PATTERNS = {
        "month_name": re.compile(
            r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
            r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|"
            r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
            r"\s+\d{4}\b",
            re.IGNORECASE,
        ),
        "month_year_numeric": re.compile(
            r"\b(?:0?[1-9]|1[0-2])[/\.]\d{4}\b"
        ),
        "year_month_numeric": re.compile(
            r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])\b"
        ),
    }

    def check(self, sections: dict[str, str], metadata: dict) -> list[AtsIssue]:
        text = _get_resume_text(sections)

        detected_formats = {
            name
            for name, pattern in self.DATE_PATTERNS.items()
            if pattern.search(text)
        }

        if len(detected_formats) <= 1:
            return []

        return [
            AtsIssue(
                rule="mixed_date_formats",
                message="Multiple date formats were detected in the resume.",
                fix="Use one consistent date format throughout your work and education history.",
                penalty=PENALTIES["mixed_date_formats"],
            )
        ]


class UnusualSymbolsRule:
    """Checks for characters that commonly indicate extraction problems."""

    def check(self, sections: dict[str, str], metadata: dict) -> list[AtsIssue]:
        text = _get_resume_text(sections)

        if not (
            metadata.get("has_unusual_symbols", False) or has_unusual_symbols(text)
        ):
            return []

        return [
            AtsIssue(
                rule="unusual_symbols",
                message="The resume contains unusual or potentially unparseable characters.",
                fix=(
                    "Replace unusual symbols with standard text characters"
                    " and verify the extracted resume text."
                ),
                penalty=PENALTIES["unusual_symbols"],
            )
        ]


# Each rule is evaluated independently.
RULES = [
    MissingSectionRule(),
    MissingContactInfoRule(),
    MultiColumnLayoutRule(),
    TablesRule(),
    HeaderFooterContentRule(),
    TooManyPagesRule(),
    MixedDateFormatsRule(),
    UnusualSymbolsRule(),
]


def score(
    sections: dict[str, str],
    parsing_metadata: dict | None = None,
) -> tuple[int, list[AtsIssue]]:
    """Start at 100 and subtract a fixed penalty per violated rule."""

    if not isinstance(sections, dict):
        sections = {}

    if not isinstance(parsing_metadata, dict):
        parsing_metadata = {}

    issues: list[AtsIssue] = []

    for rule in RULES:
        issues.extend(rule.check(sections, parsing_metadata))

    total = max(0, 100 - sum(issue.penalty for issue in issues))

    return total, issues
