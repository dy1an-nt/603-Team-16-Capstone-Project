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
    assert score == 55
    assert {i.rule for i in issues} == {"missing_experience", "missing_education", "missing_skills"}


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
    s = Suggestion(
        section="experience",
        original="Built REST APIs in Python and PostgreSQL",
        revised="Built REST APIs in Python and Kubernetes, cutting latency 40%",
        reason="test",
    )
    out = grounding.flag(s, RESUME, ["Kubernetes", "Python"])
    assert out.flagged
    assert "new number: 40%" in out.flag_reasons
    assert "new skill: Kubernetes" in out.flag_reasons


def test_grounding_passes_faithful_rewrite():
    s = Suggestion(
        section="experience",
        original="Built REST APIs in Python and PostgreSQL",
        revised="Designed and built REST APIs using Python and PostgreSQL",
        reason="test",
    )
    out = grounding.flag(s, RESUME, ["Python", "PostgreSQL"])
    assert not out.flagged


def test_grounding_ignores_bullet_marker_before_first_word():
    s = SuggestionDraft(
        section="experience",
        original="- Built REST APIs in Python and PostgreSQL",
        revised="- Designed, built, and tested REST APIs using Python and PostgreSQL",
        reason="test",
    )
    out = grounding.flag(s, RESUME, ["Python", "PostgreSQL"])
    assert not out.flagged
    assert out.accepted is None


def test_grounding_flags_new_name_at_bullet_start():
    s = SuggestionDraft(
        section="experience",
        original="- Built REST APIs in Python and PostgreSQL",
        revised="- Kubernetes clusters managed for 3 teams",
        reason="test",
    )
    out = grounding.flag(s, RESUME, ["Python"])
    assert "new name: Kubernetes" in out.flag_reasons


def test_grounding_skips_action_verb_at_bullet_start():
    s = SuggestionDraft(
        section="experience",
        original="- Built REST APIs in Python and PostgreSQL",
        revised="- Led REST API work in Python and PostgreSQL",
        reason="test",
    )
    out = grounding.flag(s, RESUME, ["Python", "PostgreSQL"])
    assert not out.flagged


def test_grounding_empty_revision_is_not_flagged():
    s = SuggestionDraft(section="experience", original="Built REST APIs", revised="", reason="test")
    out = grounding.flag(s, RESUME, ["Python"])
    assert not out.flagged
    assert out.flag_reasons == []
