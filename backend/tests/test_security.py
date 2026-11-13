"""Password hashing, tokens, and auth on protected routes. No database needed:
a request without a valid token is rejected before a connection opens."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import api, app
from app.security import (
    ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "test-secret-at-least-32-bytes-long-0123456789"

client = TestClient(app)


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setattr(get_settings(), "secret_key", SECRET)


def test_hash_is_bcrypt_and_not_the_password():
    h = hash_password("correct-horse")
    assert h.startswith("$2b$")
    assert "correct-horse" not in h
    assert verify_password("correct-horse", h)
    assert not verify_password("wrong-horse", h)


def test_hash_is_salted():
    assert hash_password("correct-horse") != hash_password("correct-horse")


def test_password_longer_than_72_bytes_does_not_crash():
    long_pw = "é" * 100  # 200 bytes in UTF-8
    assert verify_password(long_pw, hash_password(long_pw))


def test_verify_without_account_is_false():
    assert not verify_password("anything", None)


def test_verify_against_malformed_hash_is_false():
    assert not verify_password("anything", "not-a-bcrypt-hash")


@pytest.mark.parametrize("key", ["", "dev-only-change-me"])
def test_short_or_blank_secret_refuses_tokens(monkeypatch, key):
    monkeypatch.setattr(get_settings(), "secret_key", key)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_access_token(7)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        decode_access_token("not-a-jwt")


def test_token_round_trip():
    token, expires_in = create_access_token(7)
    assert expires_in == get_settings().access_token_expire_minutes * 60
    assert decode_access_token(token) == 7


def _status(token: str) -> int:
    try:
        decode_access_token(token)
    except Exception as e:  # HTTPException
        return e.status_code
    return 200


def test_expired_token_is_rejected():
    past = datetime.now(UTC) - timedelta(minutes=5)
    token = jwt.encode({"sub": "7", "exp": past}, SECRET, algorithm=ALGORITHM)
    assert _status(token) == 401


def test_token_signed_with_other_key_is_rejected():
    future = datetime.now(UTC) + timedelta(minutes=5)
    token = jwt.encode({"sub": "7", "exp": future}, "x" * 40, algorithm=ALGORITHM)
    assert _status(token) == 401


def test_tampered_token_is_rejected():
    token, _ = create_access_token(7)
    header, payload, sig = token.split(".")
    forged = jwt.utils.base64url_encode(b'{"sub":"8","exp":9999999999}').decode()
    assert _status(f"{header}.{forged}.{sig}") == 401


def test_unsigned_token_is_rejected():
    token = jwt.encode({"sub": "7", "exp": 9999999999}, None, algorithm="none")
    assert _status(token) == 401


@pytest.mark.parametrize(
    "claims", [{"exp": 9999999999}, {"sub": "7"}, {"sub": "abc", "exp": 9999999999}]
)
def test_token_missing_or_bad_claims_is_rejected(claims):
    assert _status(jwt.encode(claims, SECRET, algorithm=ALGORITHM)) == 401


def test_garbage_token_is_rejected():
    assert _status("not-a-jwt") == 401


PROTECTED = [
    ("post", "/auth/logout"),
    ("delete", "/account"),
    ("post", "/resumes"),
    ("get", "/resumes"),
    ("get", "/resumes/1"),
    ("delete", "/resumes/1"),
    ("post", "/analyses"),
    ("get", "/analyses/1"),
    ("post", "/analyses/1/revisions"),
    ("patch", "/revisions/1"),
    ("get", "/revisions/1/export"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_protected_routes_need_a_token(method, path):
    resp = client.request(method, path)
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"
    assert resp.json() == {"detail": "Not authenticated"}


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_protected_routes_reject_a_bad_token(method, path):
    resp = client.request(method, path, headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_non_bearer_scheme_is_rejected():
    resp = client.post("/auth/logout", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert resp.status_code == 401


def test_every_route_except_register_login_health_requires_auth():
    # The OpenAPI schema lists HTTPBearer on each route that takes the token.
    open_routes = {"/auth/register", "/auth/login", "/health"}
    for path, methods in api.openapi()["paths"].items():
        for method, op in methods.items():
            secured = {"HTTPBearer": []} in op.get("security", [])
            assert secured == (path not in open_routes), f"{method.upper()} {path}"
