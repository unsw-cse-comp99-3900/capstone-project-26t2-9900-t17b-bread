"""Simple database-backed authentication routes."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine

from app.db import dal
from app.config import get_settings

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = os.getenv(
        "SQLALCHEMY_DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/postgres",
    )

# Force sync driver for SQLAlchemy
sync_url = DATABASE_URL

# Strip async driver prefixes
sync_url = sync_url.replace("postgresql+psycopg://", "postgresql://")
sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://")

engine = create_engine(sync_url)

router = APIRouter(prefix="/api/auth", tags=["auth"])

HASH_NAME = "sha256"
HASH_ITERATIONS = 120_000
VERIFICATION_CODE_PURPOSE_REGISTER = "register"
VERIFICATION_CODE_PURPOSE_RESET = "reset_password"
VERIFICATION_CODE_TTL_MINUTES = 10


USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")
CODE_RE = re.compile(r"^\d{6}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address.")
    return email


def _validate_password_strength(value: str) -> str:
    if not PASSWORD_RE.match(value):
        raise ValueError("Use at least 8 characters with at least one letter and one number.")
    return value

class AuthRequest(BaseModel):
    username: str
    password: str
    display_name: str | None = Field(default=None, max_length=80)
    email: str | None = None

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        username = value.strip()
        if not USERNAME_RE.match(username):
            raise ValueError("Username must be 3-20 chars, letters/numbers/underscore only.")
        return username

    @field_validator("email")
    @classmethod
    def _validate_optional_email(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        return _normalize_email(value)

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        return _validate_password_strength(value)



class LoginRequest(BaseModel):
    username: str
    password: str = Field(min_length=1)

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        username = value.strip()
        if not USERNAME_RE.match(username):
            raise ValueError("Enter a valid username.")
        return username



class AuthUser(BaseModel):
    id: int
    username: str
    email: str | None = None
    display_name: str | None = None



class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class RequestRegisterCodeRequest(BaseModel):
    username: str
    email: str

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        username = value.strip()
        if not USERNAME_RE.match(username):
            raise ValueError("Username must be 3-20 chars, letters/numbers/underscore only.")
        return username

    @field_validator("email")
    @classmethod
    def _validate_register_code_email(cls, value: str) -> str:
        return _normalize_email(value)


class VerifyRegisterRequest(AuthRequest):
    email: str
    code: str

    @field_validator("email")
    @classmethod
    def _validate_required_register_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        code = value.strip()
        if not CODE_RE.match(code):
            raise ValueError("Enter the 6-digit verification code.")
        return code


class PasswordResetCodeRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _validate_password_reset_email(cls, value: str) -> str:
        return _normalize_email(value)


class PasswordResetConfirmRequest(BaseModel):
    email: str
    code: str
    new_password: str

    @field_validator("email")
    @classmethod
    def _validate_password_reset_confirm_email(cls, value: str) -> str:
        return _normalize_email(value)

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        code = value.strip()
        if not CODE_RE.match(code):
            raise ValueError("Enter the 6-digit verification code.")
        return code

    @field_validator("new_password")
    @classmethod
    def _validate_new_password(cls, value: str) -> str:
        return _validate_password_strength(value)


class VerificationCodeResponse(BaseModel):
    status: str = "ok"
    message: str
    dev_code: str | None = None


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        HASH_NAME,
        password.encode("utf-8"),
        bytes.fromhex(salt),
        HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_{HASH_NAME}${HASH_ITERATIONS}${salt}${digest}"


def _hash_code(email: str, purpose: str, code: str) -> str:
    return hashlib.sha256(f"{email.lower()}:{purpose}:{code}".encode("utf-8")).hexdigest()


def _generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _verification_expiry() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        minutes=VERIFICATION_CODE_TTL_MINUTES
    )


def _token_expiry() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        hours=get_settings().auth_token_ttl_hours,
    )


def _send_verification_code(email: str, purpose: str, code: str) -> None:
    settings = get_settings()

    if not settings.smtp_host:
        print(f"[Auth email code] purpose={purpose} email={email} code={code}")
        return

    purpose_label = "account registration" if purpose == VERIFICATION_CODE_PURPOSE_REGISTER else "password reset"
    message = EmailMessage()
    message["Subject"] = "Your Narrative Diff verification code"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                f"Your verification code for {purpose_label} is: {code}",
                "",
                f"This code expires in {VERIFICATION_CODE_TTL_MINUTES} minutes.",
                "If you did not request this, you can ignore this email.",
            ],
        ),
    )

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email could not be sent. Please check the SMTP configuration or use development mode.",
        ) from exc


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


def _verify_email_code(conn, email: str, purpose: str, code: str) -> dict:
    record = dal.get_latest_email_verification_code(conn, email, purpose)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code is incorrect or has expired.",
        )

    expires_at = record["expires_at"]
    if expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code is incorrect or has expired.",
        )

    expected_hash = record["code_hash"]
    actual_hash = _hash_code(email, purpose, code)
    if not hmac.compare_digest(actual_hash, expected_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code is incorrect or has expired.",
        )

    return record


def _enforce_code_request_cooldown(conn, email: str, purpose: str) -> None:
    latest = dal.get_latest_email_verification_request(conn, email, purpose)
    if latest is None:
        return

    settings = get_settings()
    created_at = latest["created_at"]
    elapsed = datetime.now(timezone.utc).replace(tzinfo=None) - created_at
    remaining = settings.auth_code_cooldown_seconds - int(elapsed.total_seconds())
    if remaining > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {remaining} seconds before requesting another code.",
        )


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
    dal.delete_expired_auth_tokens(conn)
    dal.insert_auth_token(conn, int(user["id"]), token, _token_expiry())
    return AuthResponse(
        access_token=token,
        user=AuthUser(
            id=int(user["id"]),
            username=user["username"],
            email=user.get("email"),
            display_name=user.get("display_name"),
        ),
    )


def _create_verification_code_response(
    conn,
    email: str,
    purpose: str,
    message: str,
) -> VerificationCodeResponse:
    code = _generate_verification_code()
    dal.insert_email_verification_code(
        conn,
        email,
        _hash_code(email, purpose, code),
        purpose,
        _verification_expiry(),
    )
    _send_verification_code(email, purpose, code)
    dev_code = code if not get_settings().smtp_host else None
    return VerificationCodeResponse(message=message, dev_code=dev_code)


@router.post("/register/request-code", response_model=VerificationCodeResponse)
async def request_register_code(payload: RequestRegisterCodeRequest) -> VerificationCodeResponse:
    username = payload.username.strip()
    email = str(payload.email).strip().lower()

    with engine.begin() as conn:
        dal.delete_stale_email_verification_codes(conn)
        if dal.get_user_by_username(conn, username) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists for this username.",
            )
        if dal.get_user_by_email(conn, email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists for this email address.",
            )
        _enforce_code_request_cooldown(
            conn,
            email,
            VERIFICATION_CODE_PURPOSE_REGISTER,
        )
        return _create_verification_code_response(
            conn,
            email,
            VERIFICATION_CODE_PURPOSE_REGISTER,
            "Verification code sent.",
        )


@router.post("/register/verify", response_model=AuthResponse)
async def verify_register(payload: VerifyRegisterRequest) -> AuthResponse:
    username = payload.username.strip()
    email = str(payload.email).strip().lower()

    with engine.begin() as conn:
        if dal.get_user_by_username(conn, username) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists for this username.",
            )
        if dal.get_user_by_email(conn, email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists for this email address.",
            )

        code_record = _verify_email_code(
            conn,
            email,
            VERIFICATION_CODE_PURPOSE_REGISTER,
            payload.code,
        )
        user_id = dal.create_user(
            conn,
            username,
            _hash_password(payload.password),
            payload.display_name.strip() if payload.display_name else None,
            email,
        )
        dal.mark_email_verification_code_used(conn, int(code_record["id"]))
        user = dal.get_user(conn, user_id)
        return _auth_response_for_user(conn, user)


@router.post("/password/request-reset", response_model=VerificationCodeResponse)
async def request_password_reset(payload: PasswordResetCodeRequest) -> VerificationCodeResponse:
    email = str(payload.email).strip().lower()

    with engine.begin() as conn:
        dal.delete_stale_email_verification_codes(conn)
        if dal.get_user_by_email(conn, email) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account exists for this email address.",
            )
        _enforce_code_request_cooldown(
            conn,
            email,
            VERIFICATION_CODE_PURPOSE_RESET,
        )
        return _create_verification_code_response(
            conn,
            email,
            VERIFICATION_CODE_PURPOSE_RESET,
            "Password reset code sent.",
        )


@router.post("/password/confirm-reset")
async def confirm_password_reset(payload: PasswordResetConfirmRequest) -> dict[str, str]:
    email = str(payload.email).strip().lower()

    with engine.begin() as conn:
        user = dal.get_user_by_email(conn, email)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account exists for this email address.",
            )

        code_record = _verify_email_code(
            conn,
            email,
            VERIFICATION_CODE_PURPOSE_RESET,
            payload.code,
        )
        dal.update_user_password(conn, int(user["id"]), _hash_password(payload.new_password))
        dal.delete_auth_tokens_for_user(conn, int(user["id"]))
        dal.mark_email_verification_code_used(conn, int(code_record["id"]))
        return {"status": "ok", "message": "Password has been reset."}



@router.post("/register", response_model=AuthResponse)
async def register(payload: AuthRequest) -> AuthResponse:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Email verification is required. Please request a verification code before creating an account.",
    )



@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    username = payload.username.strip()

    with engine.begin() as conn:
        user = dal.get_user_by_username(conn, username)
        if user is None or not _verify_password(payload.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Username or password is incorrect.",
            )
        return _auth_response_for_user(conn, user)



@router.get("/me", response_model=AuthUser)
async def me(authorization: str | None = Header(default=None)) -> AuthUser:
    user = get_current_user_from_header(authorization)
    return AuthUser(
        id=int(user["id"]),
        username=user["username"],
        email=user.get("email"),
        display_name=user.get("display_name"),
    )


@router.post("/logout")
async def logout(authorization: str | None = Header(default=None)) -> dict[str, str]:
    token = _extract_bearer_token(authorization)
    if token is not None:
        with engine.begin() as conn:
            dal.delete_auth_token(conn, token)
    return {"status": "ok"}
