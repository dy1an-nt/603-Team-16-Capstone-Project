
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

from app.config import get_settings
from app.main import app, api

settings = get_settings()

client = TestClient(app)


async def _trigger_error():
    raise RuntimeError("Intentional test exception")


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_cors_headers_present_on_unhandled_500(monkeypatch):
    # Register the error endpoint only during this test.
    error_route = APIRoute(
        path="/__test-error",
        endpoint=_trigger_error,
        methods=["GET"],
        include_in_schema=False,
    )

    monkeypatch.setattr(
        api.router,
        "routes",
        [*api.router.routes, error_route],
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
