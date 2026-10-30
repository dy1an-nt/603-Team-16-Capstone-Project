"""Password hashing, access tokens, and the current-user dependency (NFR-7, NFR-8).

Routes that need a logged-in user take `CurrentUser`. Declare it before any
`Depends(get_db)` parameter so a request without a valid token gets 401
before a database connection is opened.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
import psycopg
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.db import get_db
from app.repositories import UserRepository

ALGORITHM = "HS256"

# bcrypt reads at most 72 bytes and bcrypt 5 raises on longer input, so cut the
# password the same way at hash and at check time.
_BCRYPT_MAX_BYTES = 72

# Checked against when the email is unknown, so a failed login takes about the
# same time whether or not the account exists.
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode()

_bearer = HTTPBearer(auto_error=False)


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    """Pass None when no account matched. Always runs bcrypt, then returns False."""
    try:
        ok = bcrypt.checkpw(_password_bytes(password), (password_hash or _DUMMY_HASH).encode())
    except ValueError:  # stored hash is not a bcrypt hash
        return False
    return ok and password_hash is not None


def _signing_key() -> str:
    # The config default is public in the repo, and a blank key from an unfilled
    # .env makes PyJWT raise. Either way, refuse to sign or check tokens.
    key = get_settings().secret_key
    if len(key.encode()) < 32:
        raise RuntimeError("SECRET_KEY must be set to at least 32 bytes. See .env.example.")
    return key


def create_access_token(user_id: int) -> tuple[str, int]:
    """Returns the signed token and its lifetime in seconds."""
    expires_in = get_settings().access_token_expire_minutes * 60
    now = datetime.now(UTC)
    claims = {"sub": str(user_id), "iat": now, "exp": now + timedelta(seconds=expires_in)}
    return jwt.encode(claims, _signing_key(), algorithm=ALGORITHM), expires_in


def _unauthorized() -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_access_token(token: str) -> int:
    """Returns the user id. Raises 401 for a bad signature, expiry, or shape."""
    try:
        claims = jwt.decode(
            token,
            _signing_key(),
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return int(claims["sub"])
    except (jwt.InvalidTokenError, ValueError) as e:
        raise _unauthorized() from e


def get_current_user_id(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> int:
    if creds is None:
        raise _unauthorized()
    return decode_access_token(creds.credentials)


def get_current_user(
    user_id: Annotated[int, Depends(get_current_user_id)],
    conn: Annotated[psycopg.Connection, Depends(get_db)],
) -> dict:
    """The token's user, shaped like schemas.UserOut.

    A token outlives a deleted account, so the user must still exist.
    """
    user = UserRepository(conn).get(user_id)
    if user is None:
        raise _unauthorized()
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]
