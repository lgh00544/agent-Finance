"""多人化批次 1/2 的最小隔离契约测试。"""
from datetime import datetime, timedelta

import pytest

from app import cache as cache_module
from app.core import auth
from app.db import repo
from app.db.models import Holding, PaperAccount, TradeProfile, User
from app.db.session import SessionLocal, init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def test_default_user_and_session_roundtrip():
    legacy_id = repo.ensure_default_user()
    assert legacy_id == 1
    user = repo.create_user("multi-test", "secret", "researcher")
    assert user["role"] == "researcher"
    token = auth.issue_token(user["id"])
    resolved = repo.get_user_by_token(token)
    assert resolved and resolved["id"] == user["id"]
    assert repo.get_user_by_token("invalid-token") is None


def test_paper_account_isolation_by_authenticated_user():
    owner = repo.create_user("paper-owner", "secret", "researcher")
    other = repo.create_user("paper-other", "secret", "viewer")
    account = repo.create_paper_account("owner-account", 10000, user_id=owner["id"])
    assert repo.get_paper_account_for_user(account["id"], owner["id"]) is not None
    assert repo.get_paper_account_for_user(account["id"], other["id"]) is None
    assert repo.get_paper_account_for_user(account["id"], other["id"], is_admin=True) is not None
    with SessionLocal() as db:
        row = db.get(PaperAccount, account["id"])
        assert row.user_id == owner["id"]


def test_public_fact_is_deduplicated_without_user_scope():
    payload = {"symbol": "600000", "price": 12.3, "source": "test"}
    first = repo.upsert_public_fact("quote", "test-source", "600000", "2026-09-09T10:00:00", payload)
    second = repo.upsert_public_fact("quote", "test-source", "600000", "2026-09-09T10:00:00", payload)
    assert first["id"] == second["id"]
    assert len(repo.list_public_facts("600000", "quote")) == 1


def test_news_is_projected_to_public_fact_layer():
    assert repo.add_news("600010", "测试新闻股", "公告标题", "公告正文",
                         "test-news", "https://example.invalid/news", "2026-09-09")
    facts = repo.list_public_facts("600010", "news")
    assert len(facts) == 1
    assert facts[0]["payload"]["title"] == "公告标题"


def test_trade_profile_isolated_by_user_context():
    owner = repo.create_user("profile-owner", "secret", "researcher")
    other = repo.create_user("profile-other", "secret", "researcher")
    owner_tokens = auth.set_user_context(owner["id"], owner["role"])
    try:
        repo.update_trade_profile({"style": "owner"})
        assert repo.get_trade_profile_content() == {"style": "owner"}
    finally:
        auth.reset_user_context(owner_tokens)
    other_tokens = auth.set_user_context(other["id"], other["role"])
    try:
        assert repo.get_trade_profile_content() != {"style": "owner"}
        repo.update_trade_profile({"style": "other"})
        assert repo.get_trade_profile_content() == {"style": "other"}
    finally:
        auth.reset_user_context(other_tokens)
    with SessionLocal() as db:
        rows = db.query(TradeProfile).filter(TradeProfile.user_id.in_(
            [owner["id"], other["id"]])).all()
        assert len(rows) == 2
        for row in rows:
            db.delete(row)
        db.commit()


def test_redis_namespace_is_applied_to_backend_keys(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.calls = []

        def set(self, *args, **kwargs):
            self.calls.append(("set", args, kwargs))
            return True

        def get(self, *args, **kwargs):
            self.calls.append(("get", args, kwargs))
            return None

        def delete(self, *args, **kwargs):
            self.calls.append(("delete", args, kwargs))

        def scan(self, cursor, **kwargs):
            self.calls.append(("scan", cursor, kwargs))
            return 0, []

    fake = FakeClient()
    monkeypatch.setattr(cache_module.redis_lib, "from_url", lambda *a, **k: fake)
    monkeypatch.setattr(cache_module.settings, "redis_namespace", "test-namespace")
    backend = cache_module.RedisCache()
    backend.set("sample", "1", 10)
    backend.acquire_lock("job", 10)
    assert fake.calls[0][1][0] == "test-namespace:sample"
    assert fake.calls[1][1][0] == "test-namespace:lock:job"


def test_private_query_cache_is_scoped_to_user():
    owner = repo.create_user("cache-owner", "secret", "researcher")
    other = repo.create_user("cache-other", "secret", "researcher")
    owner_code, other_code = "600901", "600902"
    repo.insert_holding(owner_code, "缓存甲", "2026-09-09", 10, 100,
                        1000, user_id=owner["id"])
    repo.insert_holding(other_code, "缓存乙", "2026-09-09", 10, 100,
                        1000, user_id=other["id"])
    try:
        owner_tokens = auth.set_user_context(owner["id"], owner["role"])
        try:
            owner_rows = repo.list_holdings(user_id=owner["id"])
        finally:
            auth.reset_user_context(owner_tokens)
        other_tokens = auth.set_user_context(other["id"], other["role"])
        try:
            other_rows = repo.list_holdings(user_id=other["id"])
        finally:
            auth.reset_user_context(other_tokens)
        assert {r["stock_code"] for r in owner_rows} == {owner_code}
        assert {r["stock_code"] for r in other_rows} == {other_code}
    finally:
        with SessionLocal() as db:
            db.query(Holding).filter(Holding.stock_code.in_([owner_code, other_code])).delete(
                synchronize_session=False)
            db.commit()


def test_task_owner_context_cannot_be_overridden(monkeypatch):
    from app.api import routes

    captured = {}

    def fake_submit(kind, label, fn, params):
        captured.update(params)
        return "task-test"

    monkeypatch.setattr(routes.task_queue, "submit", fake_submit)
    tokens = auth.set_user_context(42, "researcher")
    try:
        routes._submit_task("score", {"stock_code": "600000", "user_id": 999,
                                      "user_role": "admin"})
    finally:
        auth.reset_user_context(tokens)
    assert captured["user_id"] == 42
    assert captured["user_role"] == "researcher"
