"""Auth endpoints against a real PostgreSQL database (FR-1 to FR-3, NFR-7 to NFR-9, NFR-14).

Set TEST_DATABASE_URL to a throwaway *_test database to run them. Requests
commit, so the tables are rebuilt once and every users row (and by cascade,
everything else) is cleared before each test.
"""

import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from app.config import get_settings
from app.db import get_db
from app.main import app
from app.repositories import (
    AnalysisRepository,
    JobDescriptionRepository,
    ResumeRepository,
    RevisionRepository,
)
from app.security import decode_access_token

TEST_DB = os.environ.get("TEST_DATABASE_URL")
SCHEMA = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
TABLES = ["users", "resumes", "job_descriptions", "analyses", "revisions"]

pytestmark = pytest.mark.skipif(not TEST_DB, reason="set TEST_DATABASE_URL to run DB tests")

ANN = {"email": "ann@example.com", "password": "correct-horse"}
BOB = {"email": "bob@example.com", "password": "battery-staple"}


def _test_db():
    with psycopg.connect(TEST_DB, row_factory=dict_row) as conn:
        yield conn


@pytest.fixture(scope="module", autouse=True)
def schema():
    if TEST_DB:
        # The DROP below would wipe a real database, so require a _test name.
        dbname = conninfo_to_dict(TEST_DB).get("dbname", "")
        if not dbname.endswith("_test"):
            pytest.exit(f"TEST_DATABASE_URL must name a *_test database, got {dbname!r}")
        with psycopg.connect(TEST_DB) as conn:
            # Rebuild, since schema.sql's IF NOT EXISTS would keep an outdated table.
            conn.execute(
                "DROP TABLE IF EXISTS revisions, analyses, job_descriptions, resumes, users"
            )
            conn.execute(SCHEMA.read_text())


@pytest.fixture(autouse=True)
def client(monkeypatch):
    monkeypatch.setattr(get_settings(), "secret_key", "test-secret-at-least-32-bytes-long-0123")
    with psycopg.connect(TEST_DB) as conn:
        conn.execute("TRUNCATE users RESTART IDENTITY CASCADE")
    app.dependency_overrides[get_db] = _test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def count(table: str) -> int:
    with psycopg.connect(TEST_DB) as conn:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def register(client, creds=ANN):
    return client.post("/auth/register", json=creds)


def login(client, creds=ANN) -> dict:
    resp = client.post("/auth/login", json=creds)
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------- Register (FR-1) ----------
def test_register_returns_user_without_password(client):
    resp = register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == {"id", "email", "created_at"}
    assert body["email"] == "ann@example.com"


def test_register_stores_a_bcrypt_hash_not_the_password(client):
    register(client)
    with psycopg.connect(TEST_DB) as conn:
        stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    assert stored.startswith("$2b$")
    assert ANN["password"] not in stored


def test_register_does_not_log_in(client):
    resp = register(client)
    assert "access_token" not in resp.json()


def test_register_duplicate_email_is_409_in_any_case(client):
    register(client)
    resp = register(client, {"email": "ANN@Example.com", "password": "other-password"})
    assert resp.status_code == 409
    assert resp.json() == {"detail": "Email already registered"}
    assert count("users") == 1


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"email": "not-an-email", "password": "correct-horse"}, "email"),
        ({"email": "ann@example.com", "password": "short"}, "password"),
        ({"email": "ann@example.com"}, "password"),
        ({"password": "correct-horse"}, "email"),
    ],
)
def test_register_invalid_input_is_422_list(client, body, field):
    resp = client.post("/auth/register", json=body)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert detail[0]["loc"] == ["body", field]
    assert count("users") == 0


# ---------- Login (FR-2) ----------
def test_login_returns_contract_shape_and_valid_token(client):
    user_id = register(client).json()["id"]
    resp = client.post("/auth/login", json=ANN)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"access_token", "token_type", "expires_in"}
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().access_token_expire_minutes * 60
    assert decode_access_token(body["access_token"]) == user_id


def test_login_email_is_case_insensitive(client):
    register(client)
    assert client.post("/auth/login", json={**ANN, "email": "Ann@EXAMPLE.com"}).status_code == 200


@pytest.mark.parametrize(
    "creds",
    [
        {"email": "ann@example.com", "password": "wrong-horse"},
        {"email": "nobody@example.com", "password": "correct-horse"},
    ],
)
def test_login_wrong_credentials_same_401(client, creds):
    register(client)
    resp = client.post("/auth/login", json=creds)
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid email or password"}


# ---------- Logout (FR-2) ----------
def test_logout_is_204_with_token(client):
    register(client)
    resp = client.post("/auth/logout", headers=login(client))
    assert resp.status_code == 204
    assert resp.content == b""
    # api.js parses any JSON content-type, so an empty 204 must not claim JSON.
    assert "content-type" not in resp.headers


# ---------- Delete account (FR-3, NFR-14) ----------
def seed_everything(user_id: int) -> None:
    """One resume, job description, analysis, and revision for this user."""
    with psycopg.connect(TEST_DB, row_factory=dict_row) as conn:
        resume_id = ResumeRepository(conn).create(user_id, "r.pdf", "text", {"skills": "Python"})
        jd_id = JobDescriptionRepository(conn).create(
            user_id, resume_id, "jd", {"job_title": "Dev", "required_skills": []}
        )
        analysis_id = AnalysisRepository(conn).create(
            user_id, resume_id, 80, [], job_description_id=jd_id, match_score=50, keywords={}
        )
        RevisionRepository(conn).create(user_id, analysis_id, [])


def test_delete_account_removes_all_their_data_and_no_one_elses(client):
    ann_id = register(client).json()["id"]
    bob_id = register(client, BOB).json()["id"]
    seed_everything(ann_id)
    seed_everything(bob_id)

    resp = client.delete("/account", headers=login(client))
    assert resp.status_code == 204
    assert "content-type" not in resp.headers

    for table in TABLES:
        assert count(table) == 1, table  # only Bob's rows remain
    assert client.post("/auth/login", json=BOB).status_code == 200
    assert client.post("/auth/login", json=ANN).status_code == 401


def test_token_of_deleted_account_is_401(client):
    register(client)
    headers = login(client)
    client.delete("/account", headers=headers)
    resp = client.post("/auth/logout", headers=headers)
    assert resp.status_code == 401
    assert client.delete("/account", headers=headers).status_code == 401


def test_email_can_register_again_after_delete(client):
    register(client)
    client.delete("/account", headers=login(client))
    assert register(client).status_code == 201


# ---------- Isolation (NFR-9) ----------
def test_each_token_acts_only_on_its_own_account(client):
    register(client)
    register(client, BOB)
    bob_headers = login(client, BOB)
    client.delete("/account", headers=bob_headers)
    assert client.post("/auth/login", json=ANN).status_code == 200
    assert count("users") == 1


def test_authenticated_stub_still_reports_not_implemented(client):
    register(client)
    resp = client.get("/resumes", headers=login(client))
    assert resp.status_code == 501
