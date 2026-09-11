"""Authentication registration and account isolation contract tests.

These tests use the project conftest's PID-scoped SQLite database and build a
small FastAPI app without the production lifespan or scheduler.
"""

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.core.auth import AuthMiddleware
from app.core.config import settings
from app.db.session import init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "multi_user_enabled", True)
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(router)
    return TestClient(app)


def _name(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _register(client: TestClient, username: str | None = None,
              password: str = "safe-pass-1"):
    return client.post(
        "/api/auth/register",
        json={"username": username or _name("user"), "password": password},
    )


def test_anonymous_register_returns_token_and_status_identity(client):
    username = _name("alice")
    before = client.get("/api/auth/status")
    assert before.status_code == 200
    assert before.json() == {
        "multi_user_enabled": True,
        "user_id": None,
        "username": None,
        "role": None,
    }

    response = _register(client, username)
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == username
    assert body["role"] == "researcher"
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert "password_hash" not in body

    status = client.get(
        "/api/auth/status",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert status.status_code == 200
    assert status.json()["username"] == username
    assert status.json()["user_id"] == body["id"]
    assert status.json()["role"] == "researcher"


def test_registered_users_cannot_read_each_others_private_paper_accounts(client):
    alice = _register(client, _name("alice"), "alice-pass-1").json()
    bob = _register(client, _name("bob"), "bob-pass-1").json()
    alice_headers = {"Authorization": f"Bearer {alice['access_token']}"}
    bob_headers = {"Authorization": f"Bearer {bob['access_token']}"}

    created = client.post(
        "/api/paper/accounts",
        headers=alice_headers,
        json={"name": _name("private"), "initial_cash": 100000},
    )
    assert created.status_code == 200
    account_id = created.json()["id"]

    bob_accounts = client.get("/api/paper/accounts", headers=bob_headers)
    assert bob_accounts.status_code == 200
    assert all(row["id"] != account_id for row in bob_accounts.json())
    hidden = client.get(f"/api/paper/accounts/{account_id}/summary", headers=bob_headers)
    assert hidden.status_code == 404


@pytest.mark.parametrize(
    ("username", "password", "detail"),
    [
        ("a", "safe-pass-1", "用户名至少需要 2 个字符"),
        ("   ", "safe-pass-1", "用户名至少需要 2 个字符"),
        ("valid-user", "short", "密码至少需要 8 个字符"),
    ],
)
def test_registration_rejects_invalid_credentials(client, username, password, detail):
    response = _register(client, username, password)
    assert response.status_code == 400
    assert response.json()["detail"] == detail


def test_registration_trims_username_and_rejects_duplicate(client):
    username = _name("duplicate")
    first = _register(client, f"  {username}  ")
    assert first.status_code == 200
    assert first.json()["username"] == username

    duplicate = _register(client, username)
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "用户名已存在"


def test_password_change_requires_authenticated_user_and_rotates_credentials(client):
    username = _name("password")
    created = _register(client, username, "old-pass-1").json()
    headers = {"Authorization": f"Bearer {created['access_token']}"}

    changed = client.post(
        "/api/auth/password",
        headers=headers,
        json={"current_password": "old-pass-1", "new_password": "new-pass-1"},
    )
    assert changed.status_code == 200
    assert changed.json()["ok"] is True

    old_login = client.post("/api/auth/login",
                            json={"username": username, "password": "old-pass-1"})
    assert old_login.status_code == 401
    new_login = client.post("/api/auth/login",
                            json={"username": username, "password": "new-pass-1"})
    assert new_login.status_code == 200
