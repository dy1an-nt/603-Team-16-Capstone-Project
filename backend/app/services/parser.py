"""Resume text extraction and section splitting (FR-6, FR-8)."""

import io
import logging
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pdfplumber
from docx import Document
from docx.oxml.ns import qn

from app.config import get_settings

logger = logging.getLogger(__name__)

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

# Top and bottom share of a page treated as the header or footer area.
HEADER_FOOTER_BAND = 0.08

# Words closer than this (in points) belong to the same run of text, so a
# column gutter has to be at least this wide.
MIN_GUTTER_WIDTH = 12

# Share of lines allowed to cross a gutter, e.g. a centered name or a
# full-width summary above two columns.
MAX_GUTTER_CROSSING = 0.15

# Lines each side needs before a page counts as multi-column.
MIN_COLUMN_LINES = 5

LIBREOFFICE_TIMEOUT_SECONDS = 30


def _empty_metadata() -> dict:
    return {
        "page_count": None,
        "has_multiple_columns": False,
        "has_tables": False,
        "has_header_footer_text": False,
        "has_header_footer_images": False,
        "has_images": False,
        "has_unusual_symbols": False,
    }


def _group_lines(words: list[dict]) -> list[list[dict]]:
    """Group pdfplumber words into text lines by their vertical position."""

    lines: list[list[dict]] = []

    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(word["top"] - lines[-1][0]["top"]) <= 2:
            lines[-1].append(word)
        else:
            lines.append([word])

    return lines


def _line_runs(line: list[dict]) -> list[tuple[float, float]]:
    """Merge a line's words into runs separated by gaps of MIN_GUTTER_WIDTH or more."""

    runs: list[tuple[float, float]] = []

    for word in sorted(line, key=lambda w: w["x0"]):
        if runs and word["x0"] - runs[-1][1] < MIN_GUTTER_WIDTH:
            runs[-1] = (runs[-1][0], max(runs[-1][1], word["x1"]))
        else:
            runs.append((word["x0"], word["x1"]))

    return runs


def _has_column_gutter(words: list[dict], page_width: float, page_height: float) -> bool:
    """Find a vertical gap that most lines never cross, with text on both sides.

    Single-column resumes with right-aligned dates do not match, because their
    full-width bullet lines cross every candidate gutter.
    """

    lines = _group_lines(words)

    if len(lines) < 2 * MIN_COLUMN_LINES:
        return False

    line_runs = [(line[0]["top"], _line_runs(line)) for line in lines]
    max_crossing = len(lines) * MAX_GUTTER_CROSSING

    for x in range(int(page_width * 0.2), int(page_width * 0.8) + 1):
        crossing = 0
        left_tops: list[float] = []
        right_tops: list[float] = []

        for top, runs in line_runs:
            if any(start < x < end for start, end in runs):
                crossing += 1
                continue

            if any(end <= x for _, end in runs):
                left_tops.append(top)
            if any(start >= x for start, _ in runs):
                right_tops.append(top)

        if crossing > max_crossing:
            continue

        if len(left_tops) < MIN_COLUMN_LINES or len(right_tops) < MIN_COLUMN_LINES:
            continue

        overlap = min(max(left_tops), max(right_tops)) - max(
            min(left_tops), min(right_tops)
        )

        if overlap > page_height * 0.15:
            return True

    return False


def _band_lines(words: list[dict], page_height: float, top: bool) -> set[str]:
    """Normalized text lines inside the header (top) or footer (bottom) band."""

    limit = page_height * HEADER_FOOTER_BAND

    if top:
        band = [w for w in words if w["top"] <= limit]
    else:
        band = [w for w in words if w["bottom"] >= page_height - limit]

    normalized = set()

    for line in _group_lines(band):
        text = " ".join(w["text"] for w in sorted(line, key=lambda w: w["x0"]))
        # Drop digits so "Page 1 of 2" and "Page 2 of 2" compare equal.
        text = re.sub(r"[\d\s]+", " ", text).strip().lower()

        if text:
            normalized.add(text)

    return normalized


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

    headers: list[set[str]] = []
    footers: list[set[str]] = []

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
                        top <= page_height * HEADER_FOOTER_BAND
                        or bottom >= page_height * (1 - HEADER_FOOTER_BAND)
                    ):
                        metadata["has_header_footer_images"] = True
                        break

            # Detect tables using pdfplumber's table finder.
            if page.find_tables():
                metadata["has_tables"] = True

            words = page.extract_words()

            # A PDF has no real header part, and most resumes put the name at
            # the top of page one. Only text repeated on every page counts.
            headers.append(_band_lines(words, page_height, top=True))
            footers.append(_band_lines(words, page_height, top=False))

            if _has_column_gutter(words, page_width, page_height):
                metadata["has_multiple_columns"] = True

    if len(headers) >= 2 and (
        set.intersection(*headers) or set.intersection(*footers)
    ):
        metadata["has_header_footer_text"] = True

    return metadata


def has_unusual_symbols(text: str) -> bool:
    """Detect characters that commonly indicate extraction problems."""

    for char in text:
        codepoint = ord(char)

        if char == "�":
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


def _convert_docx_to_pdf(data: bytes) -> bytes | None:
    """Convert DOCX bytes to PDF using LibreOffice.

    Returns None when LibreOffice is missing, times out, or fails, so the
    upload still succeeds with the checks python-docx can do on its own.
    """

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        docx_path = temp_path / "resume.docx"

        docx_path.write_bytes(data)

        try:
            result = subprocess.run(
                [
                    get_settings().libreoffice_path,
                    # A private profile per call. Concurrent runs that share
                    # the default profile fail without an error.
                    f"-env:UserInstallation={(temp_path / 'profile').as_uri()}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(temp_path),
                    str(docx_path),
                ],
                capture_output=True,
                text=True,
                timeout=LIBREOFFICE_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("DOCX layout check skipped: %s", type(exc).__name__)
            return None

        pdf_path = temp_path / "resume.pdf"

        if result.returncode != 0 or not pdf_path.exists():
            logger.warning(
                "DOCX layout check skipped: LibreOffice exited with %s",
                result.returncode,
            )
            return None

        return pdf_path.read_bytes()


def _docx_metadata(document) -> dict:
    """Structural checks python-docx can do without LibreOffice."""

    metadata = _empty_metadata()
    metadata["has_tables"] = bool(document.tables)
    metadata["has_images"] = bool(document.inline_shapes)

    for section in document.sections:
        header = section.header
        footer = section.footer

        header_text = "\n".join(paragraph.text for paragraph in header.paragraphs)
        footer_text = "\n".join(paragraph.text for paragraph in footer.paragraphs)

        if header_text.strip() or footer_text.strip():
            metadata["has_header_footer_text"] = True

        header_has_images = any(
            rel.reltype.endswith("/image") for rel in header.part.rels.values()
        )
        footer_has_images = any(
            rel.reltype.endswith("/image") for rel in footer.part.rels.values()
        )

        if header_has_images or footer_has_images:
            metadata["has_header_footer_images"] = True

        # Word's own column setting, e.g. <w:cols w:num="2"/>.
        cols = section._sectPr.find(qn("w:cols"))
        if cols is not None and int(cols.get(qn("w:num"), "1")) > 1:
            metadata["has_multiple_columns"] = True

    return metadata


def _safe_pdf_layout(pdf_bytes: bytes) -> dict:
    """Layout metadata, or an empty dict if the layout inspection fails."""

    try:
        return _inspect_pdf_layout(pdf_bytes)
    except Exception as exc:
        logger.warning("PDF layout check skipped: %s", type(exc).__name__)
        return {}


def extract_document(data: bytes, filename: str) -> tuple[str, dict]:
    """Return extracted text and structural metadata for a PDF or DOCX.

    Text extraction errors reject the file. Layout checks are best effort, so
    a failure there leaves the related metadata at its default and the
    matching ATS rules are skipped.
    """

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
                    page.extract_text() or ""
                    for page in pdf.pages
                )
                page_count = len(pdf.pages)

            metadata = _empty_metadata()
            metadata["page_count"] = page_count
            metadata.update(_safe_pdf_layout(data))

        else:
            if not zipfile.is_zipfile(io.BytesIO(data)):
                raise ValueError("Invalid DOCX file.")

            document = Document(io.BytesIO(data))

            parts = [paragraph.text for paragraph in document.paragraphs]

            for table in document.tables:
                for row in table.rows:
                    parts.append(" ".join(cell.text for cell in row.cells))

            text = "\n".join(parts)

            try:
                metadata = _docx_metadata(document)
            except Exception as exc:
                logger.warning("DOCX structure check skipped: %s", type(exc).__name__)
                metadata = _empty_metadata()

    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Unable to read the uploaded resume.") from exc

    text = text.strip()

    if not text:
        raise ValueError(
            "No readable text was found. Image-only resumes are not supported."
        )

    if extension == "docx":
        # Page count and rendered layout need LibreOffice. Run it only after
        # the text is known to be usable.
        layout_pdf = _convert_docx_to_pdf(data)
        layout = _safe_pdf_layout(layout_pdf) if layout_pdf else {}

        metadata["page_count"] = layout.get("page_count")
        for key in ("has_multiple_columns", "has_tables", "has_images"):
            metadata[key] = metadata[key] or layout.get(key, False)
        # Header and footer findings come from the DOCX parts, which are
        # exact. The rendered PDF cannot tell a header from body text.

    metadata["has_unusual_symbols"] = has_unusual_symbols(text)
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
