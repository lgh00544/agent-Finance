"""Paper archive preserves history and closes execution/monitor entry points."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.api import routes
from app.db import repo
from app.db.models import AuditLog, Holding, PaperAccount, TradeRecord
from app.db.session import SessionLocal, init_db
from app.services import paper_execution, paper_monitor


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes, "_request_user_id", lambda: 77001)
    monkeypatch.setattr(routes, "_is_admin", lambda: False)
    monkeypatch.setattr(routes, "current_user_role", lambda: "user")
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as api:
        yield api


def _account():
    return repo.create_paper_account("archive-test", 100_000, user_id=77001)


def _execution(account_id, suffix="buy"):
    return {"execution_key": f"archive:{account_id}:{suffix}", "stock_code": "600009",
            "stock_name": "paper-test", "side": "buy", "shares": 100,
            "requested_price": 10, "executed_price": 10, "gross_amount": 1000,
            "total_amount": 1000, "status": "filled", "trade_date": "2026-09-08",
            "fact_as_of": "2026-09-08", "source_label": "paper-test"}


def _real_rows():
    with SessionLocal() as db:
        return {model.__tablename__: [tuple(getattr(row, col.name) for col in model.__table__.columns)
                                      for row in db.execute(select(model).order_by(model.id)).scalars()]
                for model in (Holding, TradeRecord)}


def _audits(account_id):
    with SessionLocal() as db:
        return db.execute(select(AuditLog).where(
            AuditLog.target_type == "paper_account", AuditLog.target_id == account_id
        ).order_by(AuditLog.id)).scalars().all()


def test_archive_hides_account_and_preserves_history_and_real_tables(client):
    real_before = _real_rows()
    account = _account()
    aid = account["id"]
    execution = repo.paper_apply_execution(aid, _execution(aid))
    review_id = repo.create_paper_review(aid, "600009", "paper-test", "2026-09-08",
                                         {"result": "retained"}, execution_id=execution["id"])
    positions_before = repo.list_paper_positions(aid)
    executions_before = client.get(f"/api/paper/accounts/{aid}/executions").json()
    reviews_before = client.get(f"/api/paper/reviews?account_id={aid}").json()
    response = client.post(f"/api/paper/accounts/{aid}/archive", json={"reason": "test cleanup"})
    assert response.status_code == 200
    assert response.json()["status"] == "archived"
    assert response.json()["cash"] == 99_000
    assert aid not in {row["id"] for row in client.get("/api/paper/accounts").json()}
    assert aid in {row["id"] for row in client.get("/api/paper/accounts?include_archived=true").json()}
    assert aid in {row["id"] for row in repo.list_paper_accounts(status="archived")}
    assert repo.list_paper_positions(aid) == positions_before
    assert client.get(f"/api/paper/accounts/{aid}/executions").json() == executions_before
    assert client.get(f"/api/paper/reviews?account_id={aid}").json() == reviews_before
    assert any(row["id"] == review_id for row in reviews_before)
    assert repo.get_paper_account(aid) is not None
    assert _real_rows() == real_before


def test_account_status_query_returns_only_owned_archived_accounts(client):
    archived, active, paused = _account()["id"], _account()["id"], _account()["id"]
    other = repo.create_paper_account("other-archived", 100_000, user_id=77002)["id"]
    repo.archive_paper_account(archived)
    repo.archive_paper_account(other)
    repo.update_paper_account_status(paused, "paused")
    response = client.get("/api/paper/accounts?status=archived")
    assert response.status_code == 200
    rows = response.json()
    assert archived in {row["id"] for row in rows}
    assert not {active, paused, other} & {row["id"] for row in rows}
    assert all(row["status"] == "archived" and row["user_id"] == 77001 for row in rows)


def test_archive_pauses_first_and_audits_atomically(client):
    aid = _account()["id"]
    transitions = []

    def before_update(mapper, connection, row):
        if row.id == aid:
            transitions.append(row.status)

    event.listen(PaperAccount, "before_update", before_update)
    try:
        assert client.post(f"/api/paper/accounts/{aid}/archive").status_code == 200
    finally:
        event.remove(PaperAccount, "before_update", before_update)
    assert transitions == ["paused", "archived"]
    audits = _audits(aid)
    assert [json.loads(row.reasoning)["action"] for row in audits] == ["pause_before_archive", "archive"]
    assert all(row.user_id == 77001 and row.audit_model == "human" for row in audits)
    assert json.loads(audits[1].reasoning)["actor_user_id"] == 77001
    assert client.post(f"/api/paper/accounts/{aid}/archive").status_code == 200
    assert len(_audits(aid)) == 2


def test_archive_rolls_back_when_audit_cannot_be_saved():
    aid = _account()["id"]

    def fail_audit(mapper, connection, row):
        if row.target_type == "paper_account" and row.target_id == aid:
            raise RuntimeError("audit unavailable")

    event.listen(AuditLog, "before_insert", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="audit unavailable"):
            repo.archive_paper_account(aid)
    finally:
        event.remove(AuditLog, "before_insert", fail_audit)
    assert repo.get_paper_account(aid).status == "active"
    assert not _audits(aid)


@pytest.mark.parametrize("path,body", [
    ("run", {}), ("run", {"trade_date": "2026-09-08", "facts": {}}),
    ("monitor", {}), ("status", {"status": "active"}), ("status", {"status": "paused"}),
])
def test_archive_blocks_run_replay_monitor_and_reactivation(client, path, body):
    aid = _account()["id"]
    repo.archive_paper_account(aid)
    response = client.post(f"/api/paper/accounts/{aid}/{path}", json=body)
    assert response.status_code == 400
    assert "已归档" in response.json()["detail"]
    assert repo.get_paper_account(aid).status == "archived"
    assert not repo.list_paper_executions(aid)


def test_archive_blocks_service_replay_and_execution_commit(monkeypatch):
    aid = _account()["id"]
    repo.paper_apply_execution(aid, _execution(aid))
    positions = repo.list_paper_positions(aid)
    repo.archive_paper_account(aid)
    with pytest.raises(ValueError, match="已归档"):
        paper_execution.run(aid, "2026-09-09", facts={})
    with pytest.raises(ValueError, match="已归档"):
        paper_monitor.run(aid, "2026-09-09", mode="historical_replay", historical_facts={})
    with pytest.raises(ValueError, match="已归档"):
        repo.paper_apply_execution(aid, _execution(aid, "late-commit"))
    assert repo.release_paper_t1(aid, "2026-09-09") == 0
    assert not repo.update_paper_position_state(aid, "600009", high_price=99)
    assert repo.list_paper_positions(aid) == positions
    assert len(repo.list_paper_executions(aid)) == 1


def test_archived_summary_reads_history_without_refresh(monkeypatch, client):
    aid = _account()["id"]
    repo.archive_paper_account(aid)
    from app.services import paper_valuation
    monkeypatch.setattr(paper_valuation, "refresh_account",
                        lambda _: pytest.fail("archived summary must not refresh quotes"))
    response = client.get(f"/api/paper/accounts/{aid}/summary")
    assert response.status_code == 200
    assert response.json()["account_id"] == aid


def test_archive_endpoint_and_explicit_list_preserve_ownership(client):
    other = repo.create_paper_account("other-owner", 100_000, user_id=77002)
    aid = other["id"]
    assert client.post(f"/api/paper/accounts/{aid}/archive").status_code == 404
    assert repo.get_paper_account(aid).status == "active"
    repo.archive_paper_account(aid)
    assert aid not in {row["id"] for row in client.get("/api/paper/accounts?include_archived=true").json()}
    assert client.get(f"/api/paper/accounts/{aid}/executions").status_code == 404


def test_scheduler_ignores_archived_accounts(monkeypatch):
    from app.scheduler import jobs

    archived, active = _account()["id"], _account()["id"]
    repo.archive_paper_account(archived)
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    calls = []
    list_accounts = repo.list_paper_accounts

    def selected_accounts(**kwargs):
        assert kwargs["status"] == "active"
        return [row for row in list_accounts(**kwargs) if row["id"] in {archived, active}]

    monkeypatch.setattr(jobs.repo, "list_paper_accounts", selected_accounts)
    monkeypatch.setattr(jobs, "_in_trading_window", lambda _: True)
    monkeypatch.setattr(jobs.AkshareSource, "fetch_trade_calendar", lambda _: [today])
    monkeypatch.setattr(jobs.cache, "acquire_lock", lambda *args, **kwargs: True)
    monkeypatch.setattr(jobs.cache, "release_lock", lambda *args: None)
    monkeypatch.setattr(jobs.cache, "set", lambda *args: None)
    monkeypatch.setattr(paper_execution, "run", lambda aid, _: calls.append(("run", aid)))
    monkeypatch.setattr(paper_monitor, "run", lambda aid, _: calls.append(("monitor", aid)))
    jobs.paper_monitor_job()
    assert calls == [("run", active), ("monitor", active)]
