"""多人化批次 1/2 的最小隔离契约测试。"""
from datetime import datetime, timedelta

import pytest

from app import cache as cache_module
from app.core import auth
from app.db import repo
from app.db.models import (
    AiReasoningTrace, AiReasoningTraceHistory, Holding, PaperAccount, PositionPlan,
    TradeProfile, User,
)
from app.db.session import SessionLocal, init_db
from app.services import reasoning_trace


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


def test_reasoning_trace_isolation_and_idor(monkeypatch):
    from fastapi import HTTPException
    from app.api import routes

    stamp = str(int(datetime.now().timestamp() * 1_000_000))
    code = f"6{stamp[-5:]}"
    date = "2026-09-10"
    owner = repo.create_user(f"trace-owner-{stamp}", "secret", "researcher")
    other = repo.create_user(f"trace-other-{stamp}", "secret", "researcher")
    admin = repo.create_user(f"trace-admin-{stamp}", "secret", "admin")
    monkeypatch.setattr(repo.settings, "multi_user_enabled", True)

    try:
        owner_tokens = auth.set_user_context(owner["id"], owner["role"])
        try:
            reasoning_trace.trace_score(
                code, "留痕隔离股", date, 80.0, "B",
                {"技术趋势": {"comment": "owner"}}, [],
            )
        finally:
            auth.reset_user_context(owner_tokens)

        other_tokens = auth.set_user_context(other["id"], other["role"])
        try:
            reasoning_trace.trace_score(
                code, "留痕隔离股", date, 90.0, "A",
                {"技术趋势": {"comment": "other"}}, [],
            )
        finally:
            auth.reset_user_context(other_tokens)
        reasoning_trace.flush()
        assert repo.list_traces(code=code, date=date) == []
        assert repo.list_trace_history(code=code, date=date) == []

        owner_tokens = auth.set_user_context(owner["id"], owner["role"])
        try:
            owner_rows = routes.list_traces(code=code, date=date)
            owner_history = routes.list_trace_history(code=code, date=date)
            assert len(owner_rows) == len(owner_history) == 1
            owner_trace_id = owner_rows[0]["trace_id"]
            owner_history_id = owner_history[0]["history_id"]
            assert "owner" in routes.get_trace(owner_trace_id)["technical_reasoning"]
            assert "owner" in routes.get_trace_history(owner_history_id)["technical_reasoning"]
        finally:
            auth.reset_user_context(owner_tokens)

        other_tokens = auth.set_user_context(other["id"], other["role"])
        try:
            other_rows = routes.list_traces(code=code, date=date)
            other_history = routes.list_trace_history(code=code, date=date)
            assert len(other_rows) == len(other_history) == 1
            other_trace_id = other_rows[0]["trace_id"]
            other_history_id = other_history[0]["history_id"]
            assert other_trace_id != owner_trace_id
            assert "other" in routes.get_trace(other_trace_id)["technical_reasoning"]
            assert "other" in routes.get_trace_history(other_history_id)["technical_reasoning"]
            with pytest.raises(HTTPException, match="留痕记录不存在") as exc:
                routes.get_trace(owner_trace_id)
            assert exc.value.status_code == 404
            with pytest.raises(HTTPException, match="历史留痕记录不存在") as exc:
                routes.get_trace_history(owner_history_id)
            assert exc.value.status_code == 404
        finally:
            auth.reset_user_context(other_tokens)

        admin_tokens = auth.set_user_context(admin["id"], admin["role"])
        try:
            assert {row["trace_id"] for row in routes.list_traces(code=code, date=date)} == {
                owner_trace_id, other_trace_id,
            }
            assert {row["history_id"] for row in routes.list_trace_history(code=code, date=date)} == {
                owner_history_id, other_history_id,
            }
        finally:
            auth.reset_user_context(admin_tokens)

        with SessionLocal() as db:
            current_rows = db.query(AiReasoningTrace).filter(
                AiReasoningTrace.stock_code == code,
                AiReasoningTrace.generate_date == date,
                AiReasoningTrace.source_module == "score",
            ).all()
            history_rows = db.query(AiReasoningTraceHistory).filter(
                AiReasoningTraceHistory.stock_code == code,
                AiReasoningTraceHistory.generate_date == date,
                AiReasoningTraceHistory.source_module == "score",
            ).all()
            assert {row.user_id for row in current_rows} == {owner["id"], other["id"]}
            assert {row.user_id for row in history_rows} == {owner["id"], other["id"]}
    finally:
        with SessionLocal() as db:
            db.query(AiReasoningTraceHistory).filter(
                AiReasoningTraceHistory.stock_code == code,
                AiReasoningTraceHistory.generate_date == date,
            ).delete(synchronize_session=False)
            db.query(AiReasoningTrace).filter(
                AiReasoningTrace.stock_code == code,
                AiReasoningTrace.generate_date == date,
            ).delete(synchronize_session=False)
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


def test_lock_owner_renew_and_release():
    backend = cache_module.MemoryCache()
    assert backend.acquire_lock_owner("leader", "a", ttl_seconds=10) is True
    assert backend.get_lock_owner("leader") == "a"
    assert backend.acquire_lock_owner("leader", "b", ttl_seconds=10) is False
    assert backend.renew_lock_owner("leader", "b", ttl_seconds=10) is False
    assert backend.renew_lock_owner("leader", "a", ttl_seconds=10) is True
    backend.release_lock_owner("leader", "b")
    assert backend.get_lock_owner("leader") == "a"
    backend.release_lock_owner("leader", "a")
    assert backend.get_lock_owner("leader") is None


def test_scheduler_uses_owner_lease(monkeypatch):
    from app.scheduler import jobs

    class FakeCache:
        def __init__(self):
            self.owner = None
            self.calls = []

        def acquire_lock_owner(self, name, owner, ttl_seconds):
            self.calls.append(("acquire", name, owner, ttl_seconds))
            if self.owner is not None:
                return False
            self.owner = owner
            return True

        def renew_lock_owner(self, name, owner, ttl_seconds):
            self.calls.append(("renew", name, owner, ttl_seconds))
            return self.owner == owner

        def release_lock_owner(self, name, owner):
            self.calls.append(("release", name, owner))
            if self.owner == owner:
                self.owner = None

        def get_lock_owner(self, name):
            return self.owner

        def acquire_lock(self, *args, **kwargs):
            return True

        def release_lock(self, *args, **kwargs):
            return None

        def set(self, *args, **kwargs):
            return None

        def get(self, *args, **kwargs):
            return None

    class FakeScheduler:
        def __init__(self, **kwargs):
            self.started = False

        def add_job(self, *args, **kwargs):
            return None

        def start(self):
            self.started = True

        def shutdown(self, **kwargs):
            self.started = False

        def get_jobs(self):
            return []

    fake = FakeCache()
    monkeypatch.setattr(jobs, "cache", fake)
    monkeypatch.setattr(jobs, "BackgroundScheduler", FakeScheduler)
    monkeypatch.setattr(jobs.settings, "multi_user_enabled", True)
    monkeypatch.setattr(jobs.settings, "cache_backend", "redis")
    jobs.stop_scheduler()
    jobs.start_scheduler()
    try:
        assert jobs._leader_acquired is True
        assert fake.calls[0][0] == "acquire"
        assert fake.owner == jobs._leader_owner
    finally:
        jobs.stop_scheduler()
    assert fake.owner is None


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


def test_position_plan_is_scoped_and_owned():
    owner = repo.create_user("plan-owner", "secret", "researcher")
    other = repo.create_user("plan-other", "secret", "researcher")
    owner_tokens = auth.set_user_context(owner["id"], owner["role"])
    try:
        owner_id = repo.insert_plan("600911", "计划甲", "2026-09-09", 10,
                                    [], 9, 12, "owner", user_id=owner["id"])
        assert repo.get_plan(owner_id, owner["id"]) is not None
        assert repo.get_plan(owner_id, other["id"]) is None
    finally:
        auth.reset_user_context(owner_tokens)
    try:
        other_id = repo.insert_plan("600912", "计划乙", "2026-09-09", 10,
                                    [], 9, 12, "other", user_id=other["id"])
        owner_rows = repo.list_plans(user_id=owner["id"])
        other_rows = repo.list_plans(user_id=other["id"])
        assert {row["stock_code"] for row in owner_rows} == {"600911"}
        assert {row["stock_code"] for row in other_rows} == {"600912"}
        assert repo.update_plan_status(owner_id, "accepted", other["id"]) is None
        assert repo.update_plan_status(other_id, "accepted", other["id"]) is not None
    finally:
        with SessionLocal() as db:
            db.query(PositionPlan).filter(PositionPlan.id.in_([owner_id, other_id])).delete(
                synchronize_session=False)
            db.commit()


def test_viewer_is_read_only(monkeypatch):
    from app.api import routes
    from fastapi import HTTPException

    viewer = repo.create_user(f"viewer-{datetime.now().timestamp()}", "secret", "viewer")
    monkeypatch.setattr(routes.settings, "multi_user_enabled", True)
    tokens = auth.set_user_context(viewer["id"], "viewer")
    try:
        with pytest.raises(HTTPException) as exc:
            routes.auth_user_create(routes.UserCreateBody(username="x", password="x"))
        assert exc.value.status_code == 403
        with pytest.raises(HTTPException) as exc:
            routes.add_holding(routes.HoldingBody(
                stock_code="600000", stock_name="x", entry_date="2026-09-09",
                entry_price=1, shares=100))
        assert exc.value.status_code == 403
    finally:
        auth.reset_user_context(tokens)


def test_http_auth_login_and_viewer_guard(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    viewer = repo.create_user(f"http-viewer-{datetime.now().timestamp()}", "secret", "viewer")
    monkeypatch.setattr("app.core.config.settings.multi_user_enabled", True)
    monkeypatch.setattr("app.api.routes.settings.multi_user_enabled", True)
    with TestClient(app) as client:
        status = client.get("/api/auth/status")
        assert status.status_code == 200
        assert status.json()["multi_user_enabled"] is True
        login = client.post("/api/auth/login", json={"username": viewer["username"], "password": "secret"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        denied = client.post("/api/public-facts", headers={"Authorization": f"Bearer {token}"},
                             json={"fact_type": "quote", "source": "test", "symbol": "600000",
                                   "fact_as_of": "2026-09-09", "payload": {"price": 1}})
        assert denied.status_code == 403


def test_private_knowledge_and_suggestion_are_object_scoped():
    owner = repo.create_user(f"knowledge-owner-{datetime.now().timestamp()}", "secret", "researcher")
    other = repo.create_user(f"knowledge-other-{datetime.now().timestamp()}", "secret", "researcher")
    owner_tokens = auth.set_user_context(owner["id"], owner["role"])
    try:
        kid = repo.add_knowledge("甲方私有", "只属于甲方", user_id=owner["id"])
        review_id = repo.insert_review("600922", "复盘甲", 0, "2026-09-09", 1, 1, {}, "", {},
                                       user_id=owner["id"])
        sid = repo.insert_agent_suggestion(review_id, "score", "k", "1", "2", "r", "e")
    finally:
        auth.reset_user_context(owner_tokens)
    other_tokens = auth.set_user_context(other["id"], other["role"])
    try:
        assert repo.list_knowledge(user_id=other["id"]) == []
        assert repo.delete_knowledge(kid, user_id=other["id"]) is False
        assert repo.get_agent_suggestion_for_user(sid, other["id"]) is None
    finally:
        auth.reset_user_context(other_tokens)
def test_shared_task_state_is_mirrored_when_redis_enabled(monkeypatch):
    from app.services import task_queue

    class FakeCache:
        def __init__(self):
            self.data = {}

        def set(self, key, value, ttl):
            self.data[key] = value

        def get(self, key):
            return self.data.get(key)

    fake = FakeCache()
    monkeypatch.setattr(task_queue, "cache", fake)
    monkeypatch.setattr(task_queue.settings, "multi_user_enabled", True)
    monkeypatch.setattr(task_queue.settings, "cache_backend", "redis")
    owner = repo.create_user(f"task-owner-{datetime.now().timestamp()}", "secret", "researcher")
    tid = task_queue.submit("shared_probe", "共享状态", lambda p: "ok",
                            {"user_id": owner["id"], "user_role": owner["role"]})
    deadline = datetime.now() + timedelta(seconds=3)
    while datetime.now() < deadline:
        row = task_queue.get(tid, owner["id"])
        if row and row["status"] == "done":
            break
    shared = task_queue._load_shared_task(tid)
    assert shared and shared["status"] == "done"


def test_account_baseline_and_pnl_are_scoped_by_user():
    owner = repo.create_user(f"acct-owner-{datetime.now().timestamp()}", "secret", "researcher")
    other = repo.create_user(f"acct-other-{datetime.now().timestamp()}", "secret", "researcher")
    try:
        repo.insert_account_baseline("2026-09-10", 101000, 50000, 50, user_id=owner["id"])
        repo.insert_account_baseline("2026-09-10", 202000, 100000, 25, user_id=other["id"])
        repo.upsert_account_pnl_snapshot("2026-09-10", "10:00:00", pnl_yk=11,
                                         user_id=owner["id"])
        repo.upsert_account_pnl_snapshot("2026-09-10", "10:00:00", pnl_yk=22,
                                         user_id=other["id"])
        assert repo.get_latest_account_baseline(owner["id"])["total_asset"] == 101000
        assert repo.get_latest_account_baseline(other["id"])["total_asset"] == 202000
        assert repo.get_latest_account_pnl(owner["id"])["pnl_yk"] == 11
        assert repo.get_latest_account_pnl(other["id"])["pnl_yk"] == 22
    finally:
        from app.db.models import AccountBaseline, AccountPnlSnapshot
        with SessionLocal() as db:
            db.query(AccountBaseline).filter(AccountBaseline.user_id.in_([owner["id"], other["id"]])).delete(synchronize_session=False)
            db.query(AccountPnlSnapshot).filter(AccountPnlSnapshot.user_id.in_([owner["id"], other["id"]])).delete(synchronize_session=False)
            db.commit()


def test_feishu_binding_and_unbound_sender_are_fail_closed(monkeypatch):
    from app.services import chat_handlers

    owner = repo.create_user(f"feishu-owner-{datetime.now().timestamp()}", "secret", "researcher")
    repo.bind_user_feishu_open_id(owner["id"], "ou_bound_user")
    monkeypatch.setattr(chat_handlers.settings, "multi_user_enabled", True)
    assert chat_handlers._feishu_user("ou_bound_user")["id"] == owner["id"]
    assert chat_handlers.dispatch("查持仓", "holdings", {}, "", "ou_unbound_user").startswith(
        "飞书账号尚未绑定")


def test_remote_task_control_respects_owner_scope(monkeypatch):
    from app.services import task_queue
    owner = repo.create_user(f"remote-owner-{datetime.now().timestamp()}", "secret", "researcher")
    other = repo.create_user(f"remote-other-{datetime.now().timestamp()}", "secret", "researcher")

    class Shared:
        def __init__(self):
            self.data = {}
        def get(self, key):
            return self.data.get(key)
        def set(self, key, value, ttl):
            self.data[key] = value
        def delete(self, key):
            self.data.pop(key, None)

    shared = Shared()
    monkeypatch.setattr(task_queue, "cache", shared)
    monkeypatch.setattr(task_queue.settings, "multi_user_enabled", True)
    monkeypatch.setattr(task_queue.settings, "cache_backend", "redis")
    shared.set("tasks:item:remote", '{"task_id":"remote","params":{"user_id":%d},"status":"running"}' % owner["id"], 10)
    assert task_queue.cancel("remote", other["id"]) is False
    assert task_queue.cancel("remote", owner["id"]) is True
    assert '"action": "cancel"' in shared.get("tasks:control:remote")
