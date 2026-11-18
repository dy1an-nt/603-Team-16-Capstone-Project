
"""Analysis endpoint tests against a real PostgreSQL test database."""

import json
import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from app.config import get_settings
from app.db import get_db
from app.main import api, app
from app.repositories import ResumeRepository
from app.services import llm, semantic_scorer

TEST_DB = os.environ.get("TEST_DATABASE_URL")
SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema.sql"

pytestmark = pytest.mark.skipif(
    not TEST_DB,
    reason="set TEST_DATABASE_URL to run DB tests",
)

ANN = {"email": "ann@example.com", "password": "correct-horse"}
BOB = {"email": "bob@example.com", "password": "battery-staple"}


def _test_db():
    with psycopg.connect(TEST_DB, row_factory=dict_row) as conn:
        yield conn


@pytest.fixture(scope="module", autouse=True)
def schema():
    if TEST_DB:
        dbname = conninfo_to_dict(TEST_DB).get("dbname", "")
        if not dbname.endswith("_test"):
            pytest.exit(
                f"TEST_DATABASE_URL must name a *_test database, got {dbname!r}"
            )

        with psycopg.connect(TEST_DB) as conn:
            conn.execute(
                "DROP TABLE IF EXISTS revisions, analyses, "
                "job_descriptions, resumes, users"
            )
            conn.execute(SCHEMA.read_text())


@pytest.fixture(autouse=True)
def client(monkeypatch):
    monkeypatch.setattr(
        get_settings(),
        "secret_key",
        "test-secret-at-least-32-bytes-long-0123",
    )

    with psycopg.connect(TEST_DB) as conn:
        conn.execute("TRUNCATE users RESTART IDENTITY CASCADE")

    api.dependency_overrides[get_db] = _test_db
    # Stands in for the embedding model. Tests set the score they need.
    api.dependency_overrides[semantic_scorer.get_model] = lambda: object()
    yield TestClient(app)
    api.dependency_overrides.clear()


def register(client, credentials=ANN):
    response = client.post("/auth/register", json=credentials)
    assert response.status_code == 201, response.text
    return response.json()


def login(client, credentials=ANN):
    response = client.post("/auth/login", json=credentials)
    assert response.status_code == 200, response.text
    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


def create_resume(user_id: int) -> int:
    with psycopg.connect(TEST_DB, row_factory=dict_row) as conn:
        return ResumeRepository(conn).create(
            user_id=user_id,
            filename="resume.pdf",
            raw_text=(
                "Jane Doe\njane@example.com\n"
                "Experience\nSoftware Engineer\n"
                "Education\nComputer Science\n"
                "Skills\nPython, SQL"
            ),
            sections={
                "contact": "Jane Doe\njane@example.com",
                "experience": "Software Engineer",
                "education": "Computer Science",
                "skills": "Python, SQL",
            },
            parsing_metadata={
                "page_count": 1,
                "has_multiple_columns": False,
                "has_tables": False,
                "has_header_footer_text": False,
                "has_header_footer_images": False,
                "has_unusual_symbols": False,
            },
        )


def analysis_count() -> int:
    with psycopg.connect(TEST_DB) as conn:
        return conn.execute("SELECT count(*) FROM analyses").fetchone()[0]


def test_create_ats_analysis_successfully(client):
    user = register(client)
    resume_id = create_resume(user["id"])

    response = client.post(
        "/analyses",
        headers=login(client),
        json={"resume_id": resume_id},
    )

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["resume_id"] == resume_id
    assert 0 <= body["ats_score"] <= 100
    assert isinstance(body["issues"], list)
    assert body["job_description_id"] is None
    assert body["job_requirements"] is None
    assert body["match_score"] is None
    assert body["keywords"] is None
    assert analysis_count() == 1


def test_create_analysis_rejects_missing_resume(client):
    register(client)

    response = client.post(
        "/analyses",
        headers=login(client),
        json={"resume_id": 999999},
    )

    assert response.status_code == 404
    assert analysis_count() == 0


def test_create_analysis_hides_another_users_resume(client):
    ann = register(client)
    register(client, BOB)
    resume_id = create_resume(ann["id"])

    response = client.post(
        "/analyses",
        headers=login(client, BOB),
        json={"resume_id": resume_id},
    )

    assert response.status_code == 404
    assert analysis_count() == 0


class FakeLLM:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = 0

    def complete_json(self, system, user, temperature):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


JOB_JSON = json.dumps(
    {
        "job_title": "Software Engineer",
        "required_skills": ["Python", "SQL", "Docker"],
        "preferred_skills": ["AWS"],
        "responsibilities": [],
    }
)


def use_llm(fake):
    api.dependency_overrides[llm.get_llm_client] = lambda: fake
    return fake


def job_description_count() -> int:
    with psycopg.connect(TEST_DB) as conn:
        return conn.execute("SELECT count(*) FROM job_descriptions").fetchone()[0]


def use_semantic(monkeypatch, value: float):
    monkeypatch.setattr(semantic_scorer, "score", lambda model, resume, job: value)


def test_job_description_analysis_returns_match_score(client, monkeypatch):
    use_semantic(monkeypatch, 0.0)
    fake = use_llm(FakeLLM(JOB_JSON))
    user = register(client)
    resume_id = create_resume(user["id"])

    response = client.post(
        "/analyses",
        headers=login(client),
        json={
            "resume_id": resume_id,
            "job_description": "Software Engineer. Python, SQL, Docker.",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert fake.calls == 1
    assert body["job_description_id"] is not None
    assert body["job_requirements"]["required_skills"] == ["Python", "SQL", "Docker"]
    assert body["keywords"] == {"matched": ["Python", "SQL"], "missing": ["Docker", "AWS"]}
    # R=2/3, P=0, T=1, S=0 -> 100*(0.5*0.667 + 0.1) = 43
    assert body["match_score"] == 43
    assert job_description_count() == 1
    assert analysis_count() == 1


def test_job_description_analysis_saves_nothing_when_llm_fails(client):
    use_llm(FakeLLM("not json", "still not json"))
    user = register(client)
    resume_id = create_resume(user["id"])

    response = client.post(
        "/analyses",
        headers=login(client),
        json={"resume_id": resume_id, "job_description": "Software Engineer. Python."},
    )

    assert response.status_code == 502
    assert "ATS-only" in response.json()["detail"]
    assert analysis_count() == 0
    assert job_description_count() == 0


def test_job_description_analysis_returns_502_when_call_fails(client):
    use_llm(FakeLLM(llm.LLMError("APITimeoutError")))
    user = register(client)
    resume_id = create_resume(user["id"])

    response = client.post(
        "/analyses",
        headers=login(client),
        json={"resume_id": resume_id, "job_description": "Software Engineer. Python."},
    )

    assert response.status_code == 502
    assert analysis_count() == 0


def test_ats_only_analysis_never_calls_llm(client):
    fake = use_llm(FakeLLM())
    user = register(client)
    resume_id = create_resume(user["id"])

    response = client.post("/analyses", headers=login(client), json={"resume_id": resume_id})

    assert response.status_code == 201
    assert fake.calls == 0


def test_blank_job_description_is_rejected(client):
    fake = use_llm(FakeLLM())
    user = register(client)
    resume_id = create_resume(user["id"])

    response = client.post(
        "/analyses",
        headers=login(client),
        json={"resume_id": resume_id, "job_description": "   "},
    )

    assert response.status_code == 422
    assert fake.calls == 0
    assert analysis_count() == 0


def test_job_description_analysis_hides_another_users_resume(client):
    fake = use_llm(FakeLLM(JOB_JSON))
    ann = register(client)
    register(client, BOB)
    resume_id = create_resume(ann["id"])

    response = client.post(
        "/analyses",
        headers=login(client, BOB),
        json={"resume_id": resume_id, "job_description": "Software Engineer. Python."},
    )

    assert response.status_code == 404
    assert fake.calls == 0
    assert job_description_count() == 0


def test_create_analysis_requires_authentication(client):
    response = client.post(
        "/analyses",
        json={"resume_id": 1},
    )

    assert response.status_code == 401
    assert analysis_count() == 0


def test_job_description_analysis_adds_semantic_score(client, monkeypatch):
    use_semantic(monkeypatch, 0.5)
    use_llm(FakeLLM(JOB_JSON))
    user = register(client)
    resume_id = create_resume(user["id"])

    response = client.post(
        "/analyses",
        headers=login(client),
        json={"resume_id": resume_id, "job_description": "Software Engineer. Python."},
    )

    assert response.status_code == 201, response.text
    # Same as the S=0 case above, plus 100 * 0.2 * 0.5 = 10.
    assert response.json()["match_score"] == 53


def test_job_description_analysis_returns_503_without_model(client):
    api.dependency_overrides[semantic_scorer.get_model] = lambda: None
    fake = use_llm(FakeLLM(JOB_JSON))
    user = register(client)
    resume_id = create_resume(user["id"])

    response = client.post(
        "/analyses",
        headers=login(client),
        json={"resume_id": resume_id, "job_description": "Software Engineer. Python."},
    )

    assert response.status_code == 503
    assert "ATS-only" in response.json()["detail"]
    assert fake.calls == 0
    assert job_description_count() == 0
    assert analysis_count() == 0


def test_ats_only_analysis_works_without_model(client):
    api.dependency_overrides[semantic_scorer.get_model] = lambda: None
    user = register(client)
    resume_id = create_resume(user["id"])

    response = client.post("/analyses", headers=login(client), json={"resume_id": resume_id})

    assert response.status_code == 201


def create_ats_analysis(client, user_id: int, headers) -> dict:
    response = client.post(
        "/analyses", headers=headers, json={"resume_id": create_resume(user_id)}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_get_analysis_returns_saved_analysis(client):
    user = register(client)
    headers = login(client)
    created = create_ats_analysis(client, user["id"], headers)

    response = client.get(f"/analyses/{created['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json() == created


def test_get_analysis_missing_returns_404(client):
    register(client)

    response = client.get("/analyses/999999", headers=login(client))

    assert response.status_code == 404


def test_get_analysis_hides_another_users_analysis(client):
    ann = register(client)
    register(client, BOB)
    created = create_ats_analysis(client, ann["id"], login(client))

    response = client.get(f"/analyses/{created['id']}", headers=login(client, BOB))

    assert response.status_code == 404


def test_get_analysis_requires_authentication(client):
    response = client.get("/analyses/1")

    assert response.status_code == 401
