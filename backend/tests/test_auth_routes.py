from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.api.routes import auth
from app.main import app


client = TestClient(app)


class FakeConn:
    pass


class FakeEngine:
    def begin(self):
        return self

    def __enter__(self):
        return FakeConn()

    def __exit__(self, *_args):
        return False


def _patch_auth_storage(monkeypatch):
    state = {
        "users": {},
        "users_by_email": {},
        "codes": [],
        "tokens": {},
        "next_user_id": 1,
        "next_code_id": 1,
    }

    monkeypatch.setattr(auth, "engine", FakeEngine())
    monkeypatch.setattr(auth, "_send_verification_code", lambda *_args: None)

    def get_user_by_username(_conn, username):
        return state["users"].get(username)

    def get_user_by_email(_conn, email):
        return state["users_by_email"].get(email.lower())

    def create_user(_conn, username, password_hash, display_name=None, email=None):
        user_id = state["next_user_id"]
        state["next_user_id"] += 1
        user = {
            "id": user_id,
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "display_name": display_name,
        }
        state["users"][username] = user
        if email:
            state["users_by_email"][email.lower()] = user
        return user_id

    def get_user(_conn, user_id):
        return next(
            (user for user in state["users"].values() if user["id"] == user_id),
            None,
        )

    def insert_code(_conn, email, code_hash, purpose, expires_at):
        code_id = state["next_code_id"]
        state["next_code_id"] += 1
        state["codes"].append(
            {
                "id": code_id,
                "email": email.lower(),
                "code_hash": code_hash,
                "purpose": purpose,
                "expires_at": expires_at,
                "used_at": None,
                "created_at": datetime.utcnow(),
            },
        )
        return code_id

    def latest_code(_conn, email, purpose):
        matches = [
            code
            for code in state["codes"]
            if code["email"] == email.lower()
            and code["purpose"] == purpose
            and code["used_at"] is None
        ]
        return matches[-1] if matches else None

    def latest_request(_conn, email, purpose):
        matches = [
            code
            for code in state["codes"]
            if code["email"] == email.lower() and code["purpose"] == purpose
        ]
        return matches[-1] if matches else None

    def mark_code_used(_conn, code_id):
        for code in state["codes"]:
            if code["id"] == code_id:
                code["used_at"] = datetime.utcnow()

    def insert_token(_conn, user_id, token, expires_at=None):
        state["tokens"][token] = {"user_id": user_id, "expires_at": expires_at}
        return len(state["tokens"])

    def get_user_by_token(_conn, token):
        token_row = state["tokens"].get(token)
        if not token_row:
            return None
        expires_at = token_row["expires_at"]
        if expires_at and expires_at <= datetime.utcnow():
            return None
        return get_user(_conn, token_row["user_id"])

    def delete_tokens_for_user(_conn, user_id):
        for token, token_row in list(state["tokens"].items()):
            if token_row["user_id"] == user_id:
                del state["tokens"][token]

    def update_user_password(_conn, user_id, password_hash):
        user = get_user(_conn, user_id)
        if user:
            user["password_hash"] = password_hash

    monkeypatch.setattr(auth.dal, "get_user_by_username", get_user_by_username)
    monkeypatch.setattr(auth.dal, "get_user_by_email", get_user_by_email)
    monkeypatch.setattr(auth.dal, "create_user", create_user)
    monkeypatch.setattr(auth.dal, "get_user", get_user)
    monkeypatch.setattr(auth.dal, "insert_email_verification_code", insert_code)
    monkeypatch.setattr(auth.dal, "get_latest_email_verification_code", latest_code)
    monkeypatch.setattr(auth.dal, "get_latest_email_verification_request", latest_request)
    monkeypatch.setattr(auth.dal, "mark_email_verification_code_used", mark_code_used)
    monkeypatch.setattr(auth.dal, "insert_auth_token", insert_token)
    monkeypatch.setattr(auth.dal, "get_user_by_token", get_user_by_token)
    monkeypatch.setattr(auth.dal, "update_user_password", update_user_password)
    monkeypatch.setattr(auth.dal, "delete_expired_auth_tokens", lambda _conn: None)
    monkeypatch.setattr(auth.dal, "delete_auth_tokens_for_user", delete_tokens_for_user)
    monkeypatch.setattr(auth.dal, "delete_stale_email_verification_codes", lambda _conn: None)

    return state


def test_email_verification_registers_and_logs_in(monkeypatch):
    state = _patch_auth_storage(monkeypatch)
    monkeypatch.setattr(auth, "_generate_verification_code", lambda: "123456")

    request_response = client.post(
        "/api/auth/register/request-code",
        json={"username": "tester", "email": "tester@example.com"},
    )
    assert request_response.status_code == 200
    assert request_response.json()["dev_code"] == "123456"

    verify_response = client.post(
        "/api/auth/register/verify",
        json={
            "username": "tester",
            "email": "tester@example.com",
            "password": "abc12345",
            "code": "123456",
        },
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["user"]["username"] == "tester"
    assert verify_response.json()["access_token"]
    assert state["users"]["tester"]["email"] == "tester@example.com"


def test_register_rejects_wrong_code(monkeypatch):
    _patch_auth_storage(monkeypatch)
    monkeypatch.setattr(auth, "_generate_verification_code", lambda: "123456")

    client.post(
        "/api/auth/register/request-code",
        json={"username": "tester", "email": "tester@example.com"},
    )
    response = client.post(
        "/api/auth/register/verify",
        json={
            "username": "tester",
            "email": "tester@example.com",
            "password": "abc12345",
            "code": "000000",
        },
    )
    assert response.status_code == 400


def test_register_request_is_rate_limited(monkeypatch):
    _patch_auth_storage(monkeypatch)
    monkeypatch.setattr(auth, "_generate_verification_code", lambda: "123456")

    first = client.post(
        "/api/auth/register/request-code",
        json={"username": "tester", "email": "tester@example.com"},
    )
    second = client.post(
        "/api/auth/register/request-code",
        json={"username": "tester", "email": "tester@example.com"},
    )

    assert first.status_code == 200
    assert second.status_code == 429


def test_legacy_register_requires_email_verification():
    response = client.post(
        "/api/auth/register",
        json={"username": "tester", "password": "abc12345"},
    )
    assert response.status_code == 410


def test_password_reset_invalidates_old_tokens(monkeypatch):
    state = _patch_auth_storage(monkeypatch)
    monkeypatch.setattr(auth, "_generate_verification_code", lambda: "123456")

    state["users"]["tester"] = {
        "id": 1,
        "username": "tester",
        "email": "tester@example.com",
        "password_hash": auth._hash_password("oldpass1"),
        "display_name": None,
    }
    state["users_by_email"]["tester@example.com"] = state["users"]["tester"]
    state["tokens"]["old-token"] = {
        "user_id": 1,
        "expires_at": datetime.utcnow() + timedelta(hours=1),
    }

    request_response = client.post(
        "/api/auth/password/request-reset",
        json={"email": "tester@example.com"},
    )
    assert request_response.status_code == 200

    reset_response = client.post(
        "/api/auth/password/confirm-reset",
        json={
            "email": "tester@example.com",
            "code": "123456",
            "new_password": "newpass1",
        },
    )
    assert reset_response.status_code == 200
    assert "old-token" not in state["tokens"]
