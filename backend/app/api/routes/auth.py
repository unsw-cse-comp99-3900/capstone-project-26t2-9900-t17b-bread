"""Simple database-backed authentication routes."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine

from app.db import dal
from app.db.base import _normalize_url

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = os.getenv(
        "SQLALCHEMY_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/postgres",
    )

engine = create_engine(_normalize_url(DATABASE_URL))

router = APIRouter(prefix="/api/auth", tags=["auth"])

HASH_NAME = "sha256"
HASH_ITERATIONS = 120_000


class AuthRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    display_name: str | None = Field(default=None, max_length=80)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        email = value.lower().strip()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address.")
        return email


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        email = value.lower().strip()
        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address.")
        return email


class AuthUser(BaseModel):
    id: int
    email: str
    display_name: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        HASH_NAME,
        password.encode("utf-8"),
        bytes.fromhex(salt),
        HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_{HASH_NAME}${HASH_ITERATIONS}${salt}${digest}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iterations, salt, expected = stored_hash.split("$", 3)
        if scheme != f"pbkdf2_{HASH_NAME}":
            return False
        digest = hashlib.pbkdf2_hmac(
            HASH_NAME,
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations),
        ).hex()
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(digest, expected)


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def get_current_user_from_header(authorization: str | None) -> dict:
    token = _extract_bearer_token(authorization)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login is required.",
        )

    with engine.begin() as conn:
        user = dal.get_user_by_token(conn, token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
        )

    return user


def get_optional_user_from_header(authorization: str | None) -> dict | None:
    token = _extract_bearer_token(authorization)
    if token is None:
        return None

    try:
        with engine.begin() as conn:
            return dal.get_user_by_token(conn, token)
    except Exception:
        return None


def _auth_response_for_user(conn, user: dict) -> AuthResponse:
    token = secrets.token_urlsafe(32)
    dal.insert_auth_token(conn, int(user["id"]), token)
    return AuthResponse(
        access_token=token,
        user=AuthUser(
            id=int(user["id"]),
            email=user["email"],
            display_name=user.get("display_name"),
        ),
    )


@router.post("/register", response_model=AuthResponse)
async def register(payload: AuthRequest) -> AuthResponse:
    email = payload.email.lower().strip()

    with engine.begin() as conn:
        existing = dal.get_user_by_email(conn, email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists for this email.",
            )

        user_id = dal.create_user(
            conn,
            email,
            _hash_password(payload.password),
            payload.display_name.strip() if payload.display_name else None,
        )
        user = dal.get_user(conn, user_id)
        return _auth_response_for_user(conn, user)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    email = payload.email.lower().strip()

    with engine.begin() as conn:
        user = dal.get_user_by_email(conn, email)
        if user is None or not _verify_password(payload.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email or password is incorrect.",
            )
        return _auth_response_for_user(conn, user)


@router.get("/me", response_model=AuthUser)
async def me(authorization: str | None = Header(default=None)) -> AuthUser:
    user = get_current_user_from_header(authorization)
    return AuthUser(
        id=int(user["id"]),
        email=user["email"],
        display_name=user.get("display_name"),
    )


@router.post("/logout")
async def logout(authorization: str | None = Header(default=None)) -> dict[str, str]:
    token = _extract_bearer_token(authorization)
    if token is not None:
        with engine.begin() as conn:
            dal.delete_auth_token(conn, token)
    return {"status": "ok"}
