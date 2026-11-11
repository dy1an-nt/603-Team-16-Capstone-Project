from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_frontend_served_at_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "<title>Resume Reviewer</title>" in resp.text


def test_api_routes_win_over_static_mount():
    # A protected API route must still answer as the API, not as a missing file.
    resp = client.get("/resumes")
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/json")
