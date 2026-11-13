
"""Analysis endpoint tests against a real PostgreSQL test database."""

import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from app.config import get_settings
from app.db import get_db
from app.main import api as app
from app.repositories import ResumeRepository
from app.security import get_current_user

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

    app.dependency_overrides[get_db] = _test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


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


def test_job_description_analysis_returns_not_implemented(client):
    user = register(client)
    resume_id = create_resume(user["id"])

    response = client.post(
        "/analyses",
        headers=login(client),
        json={
            "resume_id": resume_id,
            "job_description": "Looking for a Python developer.",
        },
    )

    assert response.status_code == 501
    assert analysis_count() == 0


def test_create_analysis_requires_authentication(client):
    response = client.post(
        "/analyses",
        json={"resume_id": 1},
    )

    assert response.status_code == 401
    assert analysis_count() == 0
