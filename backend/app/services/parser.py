"""Resume text extraction and section splitting (FR-6, FR-8)."""

import io
import re
import zipfile
import subprocess
import pdfplumber
import tempfile
from pathlib import Path

from app.config import get_settings
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


def _inspect_pdf_layout(pdf_bytes: bytes) -> dict:
    """Inspect PDF pages for structural ATS metadata."""

    metadata = {
        "page_count": 0,
        "has_multiple_columns": False,
        "has_tables": False,
        "has_header_footer_text": False,
        "has_header_footer_images": False,
        "has_images": False,
    }

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        metadata["page_count"] = len(pdf.pages)

        for page in pdf.pages:
            page_width = page.width
            page_height = page.height

            # Detect embedded images.
            if page.images:
                metadata["has_images"] = True
                for image in page.images:
                    top = image.get("top")
                    bottom = image.get("bottom")

                    if top is None or bottom is None:
                        continue

                    if (
                        top <= page_height * 0.08
                        or bottom >= page_height * 0.92
                    ):
                        metadata["has_header_footer_images"] = True
                        break


            # Detect tables using pdfplumber's table finder.
            if page.find_tables():
                metadata["has_tables"] = True

            # Detect text near the top or bottom of a page.
            for char in page.chars:
                top = char.get("top", 0)
                bottom = char.get("bottom", 0)

                if top <= page_height * 0.08 or bottom >= page_height * 0.92:
                    if char.get("text", "").strip():
                        metadata["has_header_footer_text"] = True
                        break

            # Heuristic: detect substantial text in both halves
            # of the page with a clear central gutter.
            words = page.extract_words()
            left_words = [
                word for word in words
                if word["x1"] < page_width * 0.45
            ]
            right_words = [
                word for word in words
                if word["x0"] > page_width * 0.55
            ]

            if len(left_words) >= 3 and len(right_words) >= 3:
                left_top = min(word["top"] for word in left_words)
                left_bottom = max(word["bottom"] for word in left_words)
                right_top = min(word["top"] for word in right_words)
                right_bottom = max(word["bottom"] for word in right_words)

                overlap = min(left_bottom, right_bottom) - max(
                    left_top, right_top
                )

                if overlap > page_height * 0.15:
                    metadata["has_multiple_columns"] = True

    return metadata


def _has_unusual_symbols(text: str) -> bool:
    """Detect characters that commonly indicate extraction problems."""

    for char in text:
        codepoint = ord(char)

        if char == "\ufffd":
            return True

        # Unicode private-use areas.
        if (
            0xE000 <= codepoint <= 0xF8FF
            or 0xF0000 <= codepoint <= 0xFFFFD
            or 0x100000 <= codepoint <= 0x10FFFD
        ):
            return True

        # Unexpected control characters, excluding normal whitespace.
        if codepoint < 32 and char not in "\n\r\t":
            return True

    return False


def _convert_docx_to_pdf(data: bytes) -> bytes:
    """Convert DOCX bytes to PDF using LibreOffice."""

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        docx_path = temp_path / "resume.docx"

        docx_path.write_bytes(data)

        result = subprocess.run(
            [
                get_settings().libreoffice_path,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(temp_path),
                str(docx_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        pdf_path = temp_path / "resume.pdf"

        if result.returncode != 0 or not pdf_path.exists():
            raise ValueError("Unable to inspect DOCX layout.")

        return pdf_path.read_bytes()


def extract_document(data: bytes, filename: str) -> tuple[str, dict]:
    """Return extracted text and structural metadata for a PDF or DOCX."""

    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if extension not in {"pdf", "docx"}:
        raise ValueError("Only PDF and DOCX files are supported.")

    if not data:
        raise ValueError("The uploaded file is empty.")

    metadata = {
        "page_count": None,
        "has_multiple_columns": False,
        "has_tables": False,
        "has_header_footer_text": False,
        "has_header_footer_images": False,
        "has_images": False,
        "has_unusual_symbols": False,
    }

    try:
        if extension == "pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError("Invalid PDF file.")

            with pdfplumber.open(io.BytesIO(data)) as pdf:
                text = "\n".join(
                    page.extract_text() or ""
                    for page in pdf.pages
                )

            metadata.update(_inspect_pdf_layout(data))

        else:
            if not zipfile.is_zipfile(io.BytesIO(data)):
                raise ValueError("Invalid DOCX file.")

            document = Document(io.BytesIO(data))

            parts = [paragraph.text for paragraph in document.paragraphs]

            if document.tables:
                metadata["has_tables"] = True

            for table in document.tables:
                for row in table.rows:
                    parts.append(" ".join(cell.text for cell in row.cells))

            metadata["has_images"] = bool(document.inline_shapes)

            for section in document.sections:
                header = section.header
                footer = section.footer

                header_text = "\n".join(
                    paragraph.text for paragraph in header.paragraphs
                )
                footer_text = "\n".join(
                    paragraph.text for paragraph in footer.paragraphs
                )

                if header_text.strip() or footer_text.strip():
                    metadata["has_header_footer_text"] = True

                header_has_images = any(
                    rel.reltype.endswith("/image")
                    for rel in header.part.rels.values()
                )
                footer_has_images = any(
                    rel.reltype.endswith("/image")
                    for rel in footer.part.rels.values()
                )

                if header_has_images or footer_has_images:
                    metadata["has_header_footer_images"] = True

            text = "\n".join(parts)

            layout_pdf = _convert_docx_to_pdf(data)
            layout_metadata = _inspect_pdf_layout(layout_pdf)

            # Preserve DOCX-specific structural findings.
            for key, value in layout_metadata.items():
                if key == "page_count":
                    metadata[key] = value
                else:
                    metadata[key] = metadata[key] or value

    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Unable to read the uploaded resume.") from exc

    text = text.strip()

    if not text:
        raise ValueError(
            "No readable text was found. Image-only resumes are not supported."
        )

    metadata["has_unusual_symbols"] = _has_unusual_symbols(text)
    return text, metadata



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
