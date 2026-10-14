from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_stub_endpoints_return_501():
    resp = client.post("/auth/register", json={"email": "a@b.com", "password": "password123"})
    assert resp.status_code == 501
