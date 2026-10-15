"""Accounts: FR-1, FR-2, FR-3. Security: NFR-7, NFR-8."""

from fastapi import APIRouter, HTTPException, status

from app.schemas import Credentials, UserOut

router = APIRouter(tags=["auth"])


@router.post("/auth/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def register(creds: Credentials):
    # TODO(Week 2): hash with bcrypt, insert user, return id
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "register not implemented")


@router.post("/auth/login", response_model=UserOut)
def login(creds: Credentials):
    # TODO(Week 2): verify password, set HTTP-only session cookie
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "login not implemented")


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout():
    # TODO(Week 2): clear session cookie
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "logout not implemented")


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account():
    # TODO(Week 2): delete user; tables cascade (NFR-14)
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "delete account not implemented")
