"""Layout metadata and fallbacks in services/parser.py (FR-6, FR-9, NFR-4)."""

import subprocess
from io import BytesIO
from types import SimpleNamespace

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.services import ats_scorer, parser

PAGE_WIDTH = 612
PAGE_HEIGHT = 792

BULLET = (
    "Built and maintained internal services in Python and SQL for reporting"
    " across five teams"
)


def make_pdf(pages: list[list[tuple[float, float, str]]]) -> bytes:
    """Build a minimal Letter-size PDF. Each item is (x, y, text), y from the bottom."""

    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")
    pages_id = add(b"")
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids = []
    for items in pages:
        stream = b"".join(
            b"BT /F1 10 Tf %.1f %.1f Td (%s) Tj ET\n"
            % (x, y, text.replace("(", r"\(").replace(")", r"\)").encode())
            for x, y, text in items
        )
        content = add(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        page_ids.append(
            add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d]"
                b" /Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                % (pages_id, PAGE_WIDTH, PAGE_HEIGHT, font, content)
            )
        )

    kids = b" ".join(b"%d 0 R" % page_id for page_id in page_ids)
    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id
    objects[pages_id - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_ids))

    out = BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n%s\nendobj\n" % (number, body))

    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, catalog, xref)
    )
    return out.getvalue()


def single_column_page() -> list[tuple[float, float, str]]:
    """A standard resume page: name on top, job titles with right-aligned dates."""

    items = [(260, 750, "Jane Doe")]
    y = 720
    for job in range(4):
        items.append((72, y, f"Software Engineer, Company {job}"))
        items.append((460, y, "Jan 2020 - Present"))
        y -= 14
        for _ in range(3):
            items.append((72, y, BULLET))
            y -= 14
        y -= 10
    return items


def two_column_page() -> list[tuple[float, float, str]]:
    items = [(260, 750, "Jane Doe")]
    for row in range(20):
        y = 700 - row * 14
        items.append((72, y, "Python SQL Docker"))
        items.append((320, y, "Led migration of reporting jobs to Airflow"))
    return items


def test_right_aligned_dates_are_not_multi_column():
    metadata = parser._inspect_pdf_layout(make_pdf([single_column_page()]))

    assert metadata["page_count"] == 1
    assert metadata["has_multiple_columns"] is False


def test_two_column_layout_is_detected():
    metadata = parser._inspect_pdf_layout(make_pdf([two_column_page()]))

    assert metadata["has_multiple_columns"] is True


def test_name_at_top_of_one_page_is_not_header_text():
    metadata = parser._inspect_pdf_layout(make_pdf([single_column_page()]))

    assert metadata["has_header_footer_text"] is False


def test_text_repeated_at_top_of_every_page_is_header_text():
    header = (72, 770, "Jane Doe Resume")
    pdf = make_pdf(
        [
            [header, (72, 400, "Experience")],
            [header, (72, 400, "Education")],
        ]
    )

    metadata = parser._inspect_pdf_layout(pdf)

    assert metadata["page_count"] == 2
    assert metadata["has_header_footer_text"] is True


def test_page_numbers_in_footer_match_across_pages():
    pdf = make_pdf(
        [
            [(72, 400, "Experience"), (280, 20, "Page 1 of 2")],
            [(72, 400, "Education"), (280, 20, "Page 2 of 2")],
        ]
    )

    assert parser._inspect_pdf_layout(pdf)["has_header_footer_text"] is True


def test_different_text_at_top_of_each_page_is_not_header_text():
    pdf = make_pdf(
        [
            [(72, 770, "Jane Doe"), (72, 400, "Experience")],
            [(72, 770, "Education"), (72, 400, "Skills")],
        ]
    )

    assert parser._inspect_pdf_layout(pdf)["has_header_footer_text"] is False


def test_pdf_upload_survives_layout_inspection_failure(monkeypatch):
    def broken(_):
        raise RuntimeError("table finder crashed")

    monkeypatch.setattr(parser, "_inspect_pdf_layout", broken)

    text, metadata = parser.extract_document(
        make_pdf([single_column_page()]), "resume.pdf"
    )

    assert "Jane Doe" in text
    assert metadata["page_count"] == 1
    assert metadata["has_multiple_columns"] is False


def simple_docx() -> bytes:
    document = Document()
    document.add_paragraph("Jane Doe")
    document.add_paragraph("jane@example.com")
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_docx_upload_works_without_libreoffice(monkeypatch):
    monkeypatch.setattr(
        parser,
        "get_settings",
        lambda: SimpleNamespace(libreoffice_path="/nonexistent/soffice"),
    )

    text, metadata = parser.extract_document(simple_docx(), "resume.docx")

    assert "Jane Doe" in text
    assert metadata["page_count"] is None


def test_docx_upload_works_when_libreoffice_times_out(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="soffice", timeout=30)

    monkeypatch.setattr(parser.subprocess, "run", timeout)

    text, metadata = parser.extract_document(simple_docx(), "resume.docx")

    assert "Jane Doe" in text
    assert metadata["page_count"] is None


def test_docx_upload_works_when_libreoffice_fails(monkeypatch):
    monkeypatch.setattr(
        parser.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
    )

    _, metadata = parser.extract_document(simple_docx(), "resume.docx")

    assert metadata["page_count"] is None


def test_docx_without_page_count_skips_page_rule():
    sections = {
        "contact": "jane@example.com",
        "experience": "Engineer",
        "education": "BS",
        "skills": "Python",
    }

    score, issues = ats_scorer.score(sections, {"page_count": None})

    assert score == 100
    assert issues == []


def test_docx_column_setting_is_detected_without_libreoffice(monkeypatch):
    monkeypatch.setattr(parser, "_convert_docx_to_pdf", lambda _: None)

    document = Document()
    document.add_paragraph("Jane Doe")
    sect_pr = document.sections[0]._sectPr
    cols = sect_pr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sect_pr.append(cols)
    cols.set(qn("w:num"), "2")

    buffer = BytesIO()
    document.save(buffer)

    _, metadata = parser.extract_document(buffer.getvalue(), "resume.docx")

    assert metadata["has_multiple_columns"] is True


def test_docx_header_footer_comes_from_docx_parts_not_rendered_pdf(monkeypatch):
    monkeypatch.setattr(parser, "_convert_docx_to_pdf", lambda _: b"pdf")
    monkeypatch.setattr(
        parser,
        "_inspect_pdf_layout",
        lambda _: {
            "page_count": 1,
            "has_header_footer_text": True,
            "has_header_footer_images": True,
        },
    )

    _, metadata = parser.extract_document(simple_docx(), "resume.docx")

    assert metadata["page_count"] == 1
    assert metadata["has_header_footer_text"] is False
    assert metadata["has_header_footer_images"] is False


def test_docx_upload_survives_bad_column_setting(monkeypatch):
    monkeypatch.setattr(parser, "_convert_docx_to_pdf", lambda _: None)

    document = Document()
    document.add_paragraph("Jane Doe")
    cols = document.sections[0]._sectPr.find(qn("w:cols"))
    cols.set(qn("w:num"), "two")

    buffer = BytesIO()
    document.save(buffer)

    text, _ = parser.extract_document(buffer.getvalue(), "resume.docx")

    assert "Jane Doe" in text
