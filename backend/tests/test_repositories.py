"""Repository tests against a real PostgreSQL database.

Set TEST_DATABASE_URL to a throwaway database to run them, e.g.
postgresql://resume:resume@localhost:5432/resume_reviewer_test
Each test runs inside a transaction that is rolled back afterwards.
"""

import os
from pathlib import Path
from typing import Annotated

import psycopg
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from app.repositories import (
    AnalysisRepository,
    EmailTaken,
    JobDescriptionRepository,
    ResumeRepository,
    RevisionRepository,
    UserRepository,
)

TEST_DB = os.environ.get("TEST_DATABASE_URL")
SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema.sql"

pytestmark = pytest.mark.skipif(not TEST_DB, reason="set TEST_DATABASE_URL to run DB tests")


@pytest.fixture(scope="module", autouse=True)
def schema():
    if TEST_DB:
        # The DROP below would wipe a real database, so require a _test name.
        dbname = conninfo_to_dict(TEST_DB).get("dbname", "")
        if not dbname.endswith("_test"):
            pytest.exit(f"TEST_DATABASE_URL must name a *_test database, got {dbname!r}")
        with psycopg.connect(TEST_DB) as conn:
            # Rebuild from schema.sql every run. Its IF NOT EXISTS would keep an
            # outdated table, and this also clears rows a crashed run committed.
            conn.execute(
                "DROP TABLE IF EXISTS revisions, analyses, job_descriptions, resumes, users"
            )
            conn.execute(SCHEMA.read_text())


@pytest.fixture
def conn():
    with psycopg.connect(TEST_DB, row_factory=dict_row) as c:
        yield c
        c.rollback()


@pytest.fixture
def repos(conn):
    class R:
        users = UserRepository(conn)
        resumes = ResumeRepository(conn)
        jds = JobDescriptionRepository(conn)
        analyses = AnalysisRepository(conn)
        revisions = RevisionRepository(conn)

    return R


def count(conn, table: str) -> int:
    return conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]


JD_EXTRACTED = {"job_title": "Dev", "required_skills": []}


def make_user(repos, email: str = "ann@example.com") -> int:
    return repos.users.create(email, "hash")


def make_full_analysis(repos, user_id: int) -> tuple[int, int, int]:
    resume_id = repos.resumes.create(user_id, "cv.pdf", "Python dev", {"skills": "Python"})
    jd_id = repos.jds.create(user_id, resume_id, "Need Python", JD_EXTRACTED)
    analysis_id = repos.analyses.create(
        user_id, resume_id, 90, [], job_description_id=jd_id, match_score=70,
        keywords={"matched": ["Python"], "missing": []},
    )
    return resume_id, jd_id, analysis_id


# ---------- users ----------
def test_user_create_and_lookup_ignore_email_case(repos):
    user_id = make_user(repos, "Ann@Example.com")
    assert repos.users.get(user_id)["email"] == "ann@example.com"
    assert repos.users.get_by_email("ANN@example.com")["password_hash"] == "hash"


def test_user_get_omits_password_hash(repos):
    assert "password_hash" not in repos.users.get(make_user(repos))


def test_rejects_duplicate_email_and_keeps_transaction_usable(repos):
    make_user(repos, "ann@example.com")
    with pytest.raises(EmailTaken):
        repos.users.create("ANN@example.com", "other")
    assert make_user(repos, "bob@example.com")


def test_user_delete_removes_all_their_data(conn, repos):
    user_id = make_user(repos)
    _, _, analysis_id = make_full_analysis(repos, user_id)
    repos.revisions.create(user_id, analysis_id, [])
    assert repos.users.delete(user_id)
    for table in ("users", "resumes", "job_descriptions", "analyses", "revisions"):
        assert count(conn, table) == 0, table


# ---------- resumes ----------
def test_resume_list_is_own_and_newest_first(repos):
    ann, bob = make_user(repos, "ann@x.com"), make_user(repos, "bob@x.com")
    first = repos.resumes.create(ann, "a.pdf", "text", {})
    second = repos.resumes.create(ann, "b.pdf", "text", {})
    repos.resumes.create(bob, "c.pdf", "text", {})
    assert [r["id"] for r in repos.resumes.list_for_user(ann)] == [second, first]


def test_resume_get_returns_sections_as_dict(repos):
    user_id = make_user(repos)
    resume_id = repos.resumes.create(user_id, "a.pdf", "text", {"skills": "Python"})
    assert repos.resumes.get(user_id, resume_id)["sections"] == {"skills": "Python"}


def test_rejects_other_users_resume(repos):
    ann, bob = make_user(repos, "ann@x.com"), make_user(repos, "bob@x.com")
    resume_id = repos.resumes.create(ann, "a.pdf", "text", {})
    assert repos.resumes.get(bob, resume_id) is None
    assert repos.resumes.delete(bob, resume_id) is False
    assert repos.resumes.get(ann, resume_id) is not None


def test_resume_delete_removes_analyses_revisions_and_job_descriptions(conn, repos):
    user_id = make_user(repos)
    resume_id, _, analysis_id = make_full_analysis(repos, user_id)
    repos.revisions.create(user_id, analysis_id, [])
    other_resume, other_jd, _ = make_full_analysis(repos, user_id)
    assert repos.resumes.delete(user_id, resume_id)
    assert count(conn, "resumes") == 1
    assert count(conn, "analyses") == 1
    assert count(conn, "revisions") == 0
    assert [r["id"] for r in conn.execute("SELECT id FROM job_descriptions")] == [other_jd]


# ---------- job descriptions ----------
def test_rejects_job_description_on_other_users_resume(repos):
    ann, bob = make_user(repos, "ann@x.com"), make_user(repos, "bob@x.com")
    resume_id = repos.resumes.create(ann, "a.pdf", "text", {})
    assert repos.jds.create(bob, resume_id, "text", JD_EXTRACTED) is None


# ---------- analyses ----------
def test_ats_only_analysis_has_null_match_fields(repos):
    user_id = make_user(repos)
    resume_id = repos.resumes.create(user_id, "a.pdf", "text", {})
    issue = {"rule": "r", "message": "m", "fix": "f", "penalty": 5}
    analysis_id = repos.analyses.create(user_id, resume_id, 95, [issue])
    row = repos.analyses.get(user_id, analysis_id)
    assert row["issues"] == [issue]
    assert row["job_description_id"] is None
    assert row["job_requirements"] is None
    assert row["match_score"] is None
    assert row["keywords"] is None


def test_analysis_with_job_description_includes_requirements(repos):
    user_id = make_user(repos)
    _, jd_id, analysis_id = make_full_analysis(repos, user_id)
    row = repos.analyses.get(user_id, analysis_id)
    assert row["job_description_id"] == jd_id
    assert row["job_requirements"]["job_title"] == "Dev"
    assert row["keywords"] == {"matched": ["Python"], "missing": []}


def test_rejects_analysis_on_other_users_resume(repos):
    ann, bob = make_user(repos, "ann@x.com"), make_user(repos, "bob@x.com")
    resume_id = repos.resumes.create(ann, "a.pdf", "text", {})
    assert repos.analyses.create(bob, resume_id, 90, []) is None


def test_rejects_analysis_with_other_users_job_description(repos):
    ann, bob = make_user(repos, "ann@x.com"), make_user(repos, "bob@x.com")
    resume_id = repos.resumes.create(ann, "a.pdf", "text", {})
    _, bob_jd, _ = make_full_analysis(repos, bob)
    assert repos.analyses.create(ann, resume_id, 90, [], job_description_id=bob_jd) is None


def test_rejects_analysis_with_job_description_from_another_resume(repos):
    user_id = make_user(repos)
    _, jd_from_a, _ = make_full_analysis(repos, user_id)
    resume_b = repos.resumes.create(user_id, "b.pdf", "text", {})
    assert repos.analyses.create(user_id, resume_b, 80, [], job_description_id=jd_from_a) is None


def test_rejects_other_users_analysis(repos):
    ann, bob = make_user(repos, "ann@x.com"), make_user(repos, "bob@x.com")
    _, _, analysis_id = make_full_analysis(repos, ann)
    assert repos.analyses.get(bob, analysis_id) is None


# ---------- revisions ----------
def test_revision_get_includes_original_match_score(repos):
    user_id = make_user(repos)
    _, _, analysis_id = make_full_analysis(repos, user_id)
    revision_id = repos.revisions.create(user_id, analysis_id, [{"section": "experience"}])
    row = repos.revisions.get(user_id, revision_id)
    assert row["original_match_score"] == 70
    assert row["suggestions"] == [{"section": "experience"}]
    assert row["revised_text"] is None
    assert row["new_match_score"] is None


def test_revision_update_saves_decisions_and_rescore(repos):
    user_id = make_user(repos)
    _, _, analysis_id = make_full_analysis(repos, user_id)
    revision_id = repos.revisions.create(user_id, analysis_id, [{"accepted": None}])
    assert repos.revisions.update(user_id, revision_id, [{"accepted": True}], "new text", 85)
    row = repos.revisions.get(user_id, revision_id)
    assert row["suggestions"] == [{"accepted": True}]
    assert row["revised_text"] == "new text"
    assert row["new_match_score"] == 85


def test_rejects_revision_on_other_users_analysis(repos):
    ann, bob = make_user(repos, "ann@x.com"), make_user(repos, "bob@x.com")
    _, _, analysis_id = make_full_analysis(repos, ann)
    assert repos.revisions.create(bob, analysis_id, []) is None


def test_rejects_other_users_revision_read_and_update(repos):
    ann, bob = make_user(repos, "ann@x.com"), make_user(repos, "bob@x.com")
    _, _, analysis_id = make_full_analysis(repos, ann)
    revision_id = repos.revisions.create(ann, analysis_id, [])
    assert repos.revisions.get(bob, revision_id) is None
    assert repos.revisions.update(bob, revision_id, [], "stolen", 1) is False
    assert repos.revisions.get(ann, revision_id)["revised_text"] is None


# ---------- get_db ----------
@pytest.fixture
def client(monkeypatch):
    """App with one route that creates a user, then fails if ?fail=1."""
    from app import config, db

    monkeypatch.setenv("DATABASE_URL", TEST_DB)
    config.get_settings.cache_clear()
    app = FastAPI()

    @app.post("/users")
    def create(email: str, fail: bool, conn: Annotated[psycopg.Connection, Depends(db.get_db)]):
        UserRepository(conn).create(email, "hash")
        if fail:
            raise HTTPException(404)

    yield TestClient(app)
    config.get_settings.cache_clear()
    with psycopg.connect(TEST_DB) as cleanup:
        cleanup.execute("DELETE FROM users WHERE email LIKE 'getdb-%%'")


def user_exists(email: str) -> bool:
    with psycopg.connect(TEST_DB) as check:
        row = check.execute("SELECT 1 FROM users WHERE email = %s", (email,)).fetchone()
    return row is not None


def test_get_db_commits_when_endpoint_returns(client):
    assert client.post("/users", params={"email": "getdb-ok@x.com", "fail": False}).is_success
    assert user_exists("getdb-ok@x.com")


def test_get_db_rolls_back_when_endpoint_raises(client):
    resp = client.post("/users", params={"email": "getdb-fail@x.com", "fail": True})
    assert resp.status_code == 404
    assert not user_exists("getdb-fail@x.com")
