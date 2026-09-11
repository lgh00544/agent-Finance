"""Self-service registration contract tests.

These tests build a small FastAPI app without the production lifespan, so no
scheduler, external service, or production database is started.  The global
test conftest forces SQLite into a PID-scoped temporary database.
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
    monkeypatch.setattr(settings, "auth_self_registration_enabled", True)
    app = FastAPI()
    app.add_middleware(AuthMiddleware)
    app.include_router(router)
    return TestClient(app)


def _name(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


def _register(client: TestClient, username: str | None = None, password: str = "safe-pass-1"):
    return client.post(
        "/api/auth/register",
        json={"username": username or _name("user"), "password": password},
    )


def test_anonymous_register_returns_token_and_status_identity(client):
    username = _name("alice")
    before = client.get("/api/auth/status")
    assert before.status_code == 200
    assert before.json()["registration_enabled"] is True
    assert before.json()["user_id"] is None

    response = _register(client, username)
    assert response.status_code == 201
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
    assert status.json()["registration_enabled"] is True


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
    ("multi_user", "self_registration"),
    [(False, True), (True, False)],
)
def test_registration_requires_both_feature_switches(client, monkeypatch, multi_user, self_registration):
    monkeypatch.setattr(settings, "multi_user_enabled", multi_user)
    monkeypatch.setattr(settings, "auth_self_registration_enabled", self_registration)
    status = client.get("/api/auth/status")
    assert status.status_code == 200
    assert status.json()["registration_enabled"] is False
    response = _register(client)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "a", "password": "safe-pass-1"},
        {"username": "   ", "password": "safe-pass-1"},
        {"username": "u" * 65, "password": "safe-pass-1"},
        {"username": "valid-user", "password": "short"},
        {"username": "valid-user", "password": "p" * 257},
        {"username": "valid-user", "password": "safe-pass-1", "role": "admin"},
        {"username": "valid-user", "password": "safe-pass-1", "user_id": 1},
    ],
)
def test_registration_rejects_invalid_or_privileged_payload(client, payload):
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 422


def test_registration_trims_username_and_rejects_normalized_duplicate(client):
    username = _name("duplicate")
    first = _register(client, f"  {username}  ")
    assert first.status_code == 201
    assert first.json()["username"] == username

    duplicate = _register(client, username)
    assert duplicate.status_code == 409

