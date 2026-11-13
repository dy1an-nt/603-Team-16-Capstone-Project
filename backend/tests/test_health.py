from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import api, app

settings = get_settings()

client = TestClient(app)


async def _trigger_error():
    raise RuntimeError("Intentional test exception")


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


def test_cors_headers_present_on_unhandled_500(monkeypatch):
    # Register the error endpoint only during this test, ahead of the
    # frontend mount at "/", which would otherwise answer the path.
    error_route = APIRoute(
        path="/__test-error",
        endpoint=_trigger_error,
        methods=["GET"],
        include_in_schema=False,
    )

    monkeypatch.setattr(
        api.router,
        "routes",
        [error_route, *api.router.routes],
    )

    test_client = TestClient(
        app,
        raise_server_exceptions=False,
    )

    response = test_client.get(
        "/__test-error",
        headers={"Origin": settings.frontend_origin},
    )

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == (
        settings.frontend_origin
    )
