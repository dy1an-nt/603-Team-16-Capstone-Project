"""Resume text extraction and section splitting (FR-6, FR-8)."""

import re

SECTION_ALIASES: dict[str, list[str]] = {
    "summary": ["summary", "profile", "objective", "about me"],
    "education": ["education", "academic background"],
    "experience": ["experience", "work experience", "professional experience", "employment"],
    "projects": ["projects", "personal projects", "academic projects"],
    "skills": ["skills", "technical skills", "core competencies"],
}


def extract_text(data: bytes, filename: str) -> str:
    """Return plain text from a PDF or DOCX. Raises ValueError on unsupported or empty files."""
    # TODO(Week 3): pdfplumber for .pdf, python-docx for .docx
    raise NotImplementedError


def split_sections(text: str) -> dict[str, str]:
    """Split resume text into standard sections by matching heading lines.

    Lines before the first recognized heading go to "contact".
    """
    lookup = {alias: name for name, aliases in SECTION_ALIASES.items() for alias in aliases}
    sections: dict[str, list[str]] = {"contact": []}
    current = "contact"
    for line in text.splitlines():
        key = re.sub(r"[^a-z ]", "", line.strip().lower()).strip()
        if key in lookup:
            current = lookup[key]
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}
