
"""Resume text extraction and section splitting (FR-6, FR-8)."""

import io
import re
import zipfile

import pdfplumber
from docx import Document


SECTION_ALIASES: dict[str, list[str]] = {
    "summary": [
        "summary",
        "professional summary",
        "profile",
        "objective",
        "about me",
    ],
    "education": ["education", "academic background"],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment",
    ],
    "projects": ["projects", "personal projects", "academic projects"],
    "skills": [
        "skills",
        "technical skills",
        "core competencies",
        "additional skills",
    ],
    "additional": ["additional"],
}


def extract_text(data: bytes, filename: str) -> str:
    """Return plain text from a PDF or DOCX. Raises ValueError on invalid or empty files."""

    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if extension not in {"pdf", "docx"}:
        raise ValueError("Only PDF and DOCX files are supported.")

    if not data:
        raise ValueError("The uploaded file is empty.")

    try:
        if extension == "pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError("Invalid PDF file.")

            with pdfplumber.open(io.BytesIO(data)) as pdf:
                text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                )

        else:
            if not zipfile.is_zipfile(io.BytesIO(data)):
                raise ValueError("Invalid DOCX file.")

            document = Document(io.BytesIO(data))

            parts = [paragraph.text for paragraph in document.paragraphs]

            for table in document.tables:
                for row in table.rows:
                    parts.append(" ".join(cell.text for cell in row.cells))

            text = "\n".join(parts)

    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Unable to read the uploaded resume.") from exc

    text = text.strip()

    if not text:
        raise ValueError(
            "No readable text was found. Image-only resumes are not supported."
        )

    return text


def split_sections(text: str) -> dict[str, str]:
    """Split resume text into standard sections by recognizing headings."""

    lookup = {
        alias: name
        for name, aliases in SECTION_ALIASES.items()
        for alias in aliases
    }

    aliases = sorted(lookup.keys(), key=len, reverse=True)

    sections: dict[str, list[str]] = {"contact": []}
    current = "contact"

    for line in text.splitlines():
        remaining = line.strip()

        # Recognize headings at the beginning of a line.
        while remaining:
            heading_found = False

            for alias in aliases:
                pattern = (
                    r"^" + re.escape(alias)
                    + r"(?=$|[\s:])"
                )

                match = re.match(pattern, remaining, re.IGNORECASE)

                if match:
                    current = lookup[alias]
                    sections.setdefault(current, [])

                    remaining = remaining[match.end():].strip()

                    # Remove a repeated heading if present.
                    heading_found = True
                    break

            if not heading_found:
                break

        if remaining:
            sections.setdefault(current, []).append(remaining)

    return {
        name: "\n".join(lines).strip()
        for name, lines in sections.items()
    }
