import base64
from io import BytesIO

from docx import Document

from app.schemas import JobRequirements, Suggestion, SuggestionDraft
from app.services import ats_scorer, grounding, match_scorer, parser

RESUME = """Jane Doe
jane@example.com

Experience
Software Intern at Acme
- Built REST APIs in Python and PostgreSQL

Education
B.S. Computer Science

Skills
Python, JS, SQL
"""


def valid_sections():
    """Return a resume with all required sections and contact information."""
    return {
        "contact": "Jane Doe, jane@example.com",
        "experience": "Software Engineer at Acme",
        "education": "B.S. Computer Science",
        "skills": "Python, JavaScript, SQL",
    }


def test_split_sections():
    sections = parser.split_sections(RESUME)
    assert "jane@example.com" in sections["contact"]
    assert "REST APIs" in sections["experience"]
    assert "Python" in sections["skills"]


def test_ats_score_is_deterministic_and_flags_missing():
    sections = parser.split_sections(RESUME)
    s1, issues1 = ats_scorer.score(sections)
    s2, _ = ats_scorer.score(sections)

    assert s1 == s2 == 100
    assert issues1 == []

    score, issues = ats_scorer.score({"contact": "x"})

    assert score == 45
    assert {i.rule for i in issues} == {
        "missing_experience",
        "missing_education",
        "missing_skills",
        "missing_contact_info",
    }


def test_missing_contact_info_rule():
    sections = valid_sections()
    sections["contact"] = "Jane Doe"

    score, issues = ats_scorer.score(sections)

    assert score == 90
    assert "missing_contact_info" in {issue.rule for issue in issues}


def test_contact_info_rule_accepts_email_or_phone():
    sections = valid_sections()
    sections["contact"] = "Jane Doe, 555-123-4567"

    _, issues = ats_scorer.score(sections)

    assert "missing_contact_info" not in {issue.rule for issue in issues}


def test_contact_info_rule_ignores_date_ranges():
    sections = valid_sections()
    sections["contact"] = "Jane Doe"
    sections["experience"] = "Engineer, Acme 2019-2023\nAnalyst 2015 2016 2018"

    _, issues = ats_scorer.score(sections)

    assert "missing_contact_info" in {issue.rule for issue in issues}


def test_contact_info_rule_accepts_common_phone_formats():
    for phone in [
        "(555) 123-4567",
        "+44 20 7946 0958",
        "555.123.4567",
        "555-123-4567 555-987-6543",
        "Raleigh NC 27601-1234 555-123-4567",
    ]:
        sections = valid_sections()
        sections["contact"] = f"Jane Doe {phone}"

        _, issues = ats_scorer.score(sections)

        assert "missing_contact_info" not in {issue.rule for issue in issues}, phone


def test_multi_column_layout_rule():
    score, issues = ats_scorer.score(
        valid_sections(),
        {"has_multiple_columns": True},
    )

    assert score == 90
    assert "multi_column_layout" in {issue.rule for issue in issues}


def test_tables_rule():
    score, issues = ats_scorer.score(
        valid_sections(),
        {"has_tables": True},
    )

    assert score == 90
    assert "tables" in {issue.rule for issue in issues}


def test_header_footer_content_rule():
    score, issues = ats_scorer.score(
        valid_sections(),
        {"has_header_footer_text": True},
    )

    assert score == 95
    assert "header_footer_content" in {issue.rule for issue in issues}


def test_header_footer_images_rule():
    score, issues = ats_scorer.score(
        valid_sections(),
        {"has_header_footer_images": True},
    )

    assert score == 95
    assert "header_footer_content" in {issue.rule for issue in issues}


def test_too_many_pages_rule():
    score, issues = ats_scorer.score(
        valid_sections(),
        {"page_count": 3},
    )

    assert score == 95
    assert "too_many_pages" in {issue.rule for issue in issues}


def test_two_pages_does_not_trigger_page_rule():
    score, issues = ats_scorer.score(
        valid_sections(),
        {"page_count": 2},
    )

    assert score == 100
    assert "too_many_pages" not in {issue.rule for issue in issues}


def test_mixed_date_formats_rule():
    sections = valid_sections()
    sections["experience"] = (
        "Software Engineer, Jan 2022 - Dec 2023\n"
        "Developer, 01/2020 - 12/2021"
    )

    score, issues = ats_scorer.score(sections)

    assert score == 95
    assert "mixed_date_formats" in {issue.rule for issue in issues}


def test_consistent_date_formats_do_not_trigger_rule():
    sections = valid_sections()
    sections["experience"] = (
        "Software Engineer, Jan 2022 - Dec 2023\n"
        "Developer, Feb 2020 - Dec 2021"
    )

    score, issues = ats_scorer.score(sections)

    assert score == 100
    assert "mixed_date_formats" not in {issue.rule for issue in issues}


def test_unusual_symbols_rule():
    score, issues = ats_scorer.score(
        valid_sections(),
        {"has_unusual_symbols": True},
    )

    assert score == 90
    assert "unusual_symbols" in {issue.rule for issue in issues}


def test_unusual_symbols_detected_from_text():
    sections = valid_sections()
    sections["experience"] = "Software Engineer \ue000 Python"

    score, issues = ats_scorer.score(sections)

    assert score == 90
    assert "unusual_symbols" in {issue.rule for issue in issues}


def test_empty_sections_are_handled():
    score, issues = ats_scorer.score({})

    assert score == 45
    assert {issue.rule for issue in issues} == {
        "missing_experience",
        "missing_education",
        "missing_skills",
        "missing_contact_info",
    }


def test_match_score_uses_synonyms():
    job = JobRequirements(
        job_title="Software Engineer",
        required_skills=["Python", "JavaScript", "Docker"],
        preferred_skills=["PostgreSQL"],
    )
    score, report = match_scorer.score(RESUME, job)
    assert "JavaScript" in report.matched
    assert "Docker" in report.missing
    # R=2/3, P=1, T=0, S=0 -> 100*(0.5*0.667 + 0.2) = 53
    assert score == 53


def test_grounding_flags_invented_content():
    suggestion = Suggestion(
        section="experience",
        original="Built REST APIs in Python and PostgreSQL",
        revised="Built REST APIs in Python and Kubernetes, cutting latency 40%",
        reason="test",
    )
    out = grounding.flag(suggestion, RESUME, ["Kubernetes", "Python"])

    assert out.flagged
    assert "new number: 40%" in out.flag_reasons
    assert "new skill: Kubernetes" in out.flag_reasons


def test_grounding_passes_faithful_rewrite():
    suggestion = Suggestion(
        section="experience",
        original="Built REST APIs in Python and PostgreSQL",
        revised="Designed and built REST APIs using Python and PostgreSQL",
        reason="test",
    )
    out = grounding.flag(suggestion, RESUME, ["Python", "PostgreSQL"])

    assert not out.flagged


def test_grounding_ignores_bullet_marker_before_first_word():
    suggestion = SuggestionDraft(
        section="experience",
        original="- Built REST APIs in Python and PostgreSQL",
        revised="- Designed, built, and tested REST APIs using Python and PostgreSQL",
        reason="test",
    )
    out = grounding.flag(suggestion, RESUME, ["Python", "PostgreSQL"])

    assert not out.flagged
    assert out.accepted is None


def test_grounding_flags_new_name_at_bullet_start():
    suggestion = SuggestionDraft(
        section="experience",
        original="- Built REST APIs in Python and PostgreSQL",
        revised="- Kubernetes clusters managed for 3 teams",
        reason="test",
    )
    out = grounding.flag(suggestion, RESUME, ["Python"])

    assert "new name: Kubernetes" in out.flag_reasons


def test_grounding_skips_action_verb_at_bullet_start():
    suggestion = SuggestionDraft(
        section="experience",
        original="- Built REST APIs in Python and PostgreSQL",
        revised="- Led REST API work in Python and PostgreSQL",
        reason="test",
    )
    out = grounding.flag(suggestion, RESUME, ["Python", "PostgreSQL"])

    assert not out.flagged


def test_grounding_empty_revision_is_not_flagged():
    suggestion = SuggestionDraft(
        section="experience",
        original="Built REST APIs",
        revised="",
        reason="test",
    )
    out = grounding.flag(suggestion, RESUME, ["Python"])

    assert not out.flagged
    assert out.flag_reasons == []


def test_extract_document_detects_docx_structure(monkeypatch):
    document = Document()
    document.add_paragraph("Jane Doe")
    document.add_paragraph("jane@example.com")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Python"

    document.sections[0].header.paragraphs[0].text = "Jane Doe"
    document.sections[0].footer.paragraphs[0].text = "Page 1"

    buffer = BytesIO()
    document.save(buffer)
    data = buffer.getvalue()

    # Keep this test independent of a local LibreOffice installation.
    monkeypatch.setattr(
        parser,
        "_convert_docx_to_pdf",
        lambda _: b"mock-pdf",
    )
    monkeypatch.setattr(
        parser,
        "_inspect_pdf_layout",
        lambda _: {
            "page_count": 1,
            "has_multiple_columns": False,
            "has_tables": False,
            "has_header_footer_text": False,
            "has_images": False,
        },
    )

    text, metadata = parser.extract_document(data, "resume.docx")

    assert "Jane Doe" in text
    assert "Python" in text
    assert metadata["has_tables"] is True
    assert metadata["has_header_footer_text"] is True
    assert metadata["page_count"] == 1


def test_extract_document_detects_unusual_symbols():
    assert parser.has_unusual_symbols("Jane Doe � Python")
    assert parser.has_unusual_symbols("Name \ue000")
    assert not parser.has_unusual_symbols("José — Python • SQL")
def test_extract_document_detects_header_image(monkeypatch):
    document = Document()

    document.add_paragraph("Jane Doe")
    document.add_paragraph("jane@example.com")

    # Create a tiny valid PNG image.
    image_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    )

    document.sections[0].header.paragraphs[0].add_run().add_picture(
        BytesIO(image_data)
    )

    buffer = BytesIO()
    document.save(buffer)

    monkeypatch.setattr(
        parser,
        "_convert_docx_to_pdf",
        lambda _: b"mock-pdf",
    )
    monkeypatch.setattr(
        parser,
        "_inspect_pdf_layout",
        lambda _: {
            "page_count": 1,
            "has_multiple_columns": False,
            "has_tables": False,
            "has_header_footer_text": False,
            "has_header_footer_images": False,
            "has_images": False,
        },
    )

    _, metadata = parser.extract_document(
        buffer.getvalue(),
        "resume.docx",
    )

    assert metadata["has_header_footer_images"] is True


def test_pdf_header_footer_image_detection(monkeypatch):
    class FakePage:
        width = 612
        height = 792
        chars = []

        def __init__(self, image):
            self.images = [image]

        def find_tables(self):
            return []

        def extract_words(self):
            return []

    class FakePDF:
        def __init__(self, page):
            self.pages = [page]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    # Image near the top of the page.
    header_image = {"top": 20, "bottom": 60}

    monkeypatch.setattr(
        parser.pdfplumber,
        "open",
        lambda *args, **kwargs: FakePDF(FakePage(header_image)),
    )

    header_metadata = parser._inspect_pdf_layout(b"fake-pdf")

    assert header_metadata["has_images"] is True
    assert header_metadata["has_header_footer_images"] is True

    # Image in the body should not trigger the header/footer rule.
    body_image = {"top": 300, "bottom": 400}

    monkeypatch.setattr(
        parser.pdfplumber,
        "open",
        lambda *args, **kwargs: FakePDF(FakePage(body_image)),
    )

    body_metadata = parser._inspect_pdf_layout(b"fake-pdf")

    assert body_metadata["has_images"] is True
    assert body_metadata["has_header_footer_images"] is False
