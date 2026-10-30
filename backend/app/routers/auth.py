"""Accounts: FR-1, FR-2, FR-3. Security: NFR-7, NFR-8."""

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.db import get_db
from app.repositories import EmailTaken, UserRepository
from app.schemas import Credentials, TokenOut, UserOut
from app.security import CurrentUser, create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])

Db = Annotated[psycopg.Connection, Depends(get_db)]


@router.post("/auth/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def register(creds: Credentials, conn: Db):
    users = UserRepository(conn)
    try:
        user_id = users.create(creds.email, hash_password(creds.password))
    except EmailTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
    return users.get(user_id)


@router.post("/auth/login", response_model=TokenOut)
def login(creds: Credentials, conn: Db):
    user = UserRepository(conn).get_by_email(creds.email)
    if not verify_password(creds.password, user["password_hash"] if user else None):
        # Same message for an unknown email and a wrong password.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(user["id"])
    return TokenOut(access_token=token, expires_in=expires_in)


# 204 routes return a bare Response. Returning None sends `content-type:
# application/json` with an empty body, and api.js then fails to parse it.
@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: CurrentUser):
    # JWTs are stateless, so there is no session to end. The client drops its token.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user: CurrentUser, conn: Db):
    # Cascades to resumes, job descriptions, analyses, and revisions (FR-3, NFR-14).
    UserRepository(conn).delete(user["id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
