"""Batch 9: Memory Curator and experience expiry governance."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect, select

from app.agents.common import experience_section
from app.db import repo
from app.db.models import Experience, ReviewLog
from app.db.session import SessionLocal, init_db
from app.main import app
from app.services import memory_curator


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()
    init_db()


def _cleanup(ids: list[int]) -> None:
    ids = [int(i) for i in ids if i]
    if not ids:
        return
    with SessionLocal() as db:
        db.execute(delete(ReviewLog).where(ReviewLog.experience_id.in_(ids)))
        db.execute(delete(Experience).where(Experience.id.in_(ids)))
        db.commit()


def _exp(title: str, *, body: str = "批9经验正文", stage: str = "选股",
         tags=None, confidence: float = 0.9, status: str = "active") -> int:
    return repo.insert_experience(
        title, body, stage, tags or ["批9"], "low", confidence,
        auto_merged=1 if status == "active" else 0, status=status)


def _set_fields(eid: int, **fields) -> None:
    with SessionLocal() as db:
        row = db.get(Experience, eid)
        for key, value in fields.items():
            setattr(row, key, value)
        db.commit()


def _get(eid: int) -> dict:
    return repo.get_experience(eid)


def test_experience_curator_columns_are_migrated_idempotently():
    with SessionLocal() as db:
        columns = {column["name"] for column in inspect(db.bind).get_columns("experience")}
    assert {"hit_count", "last_used_at", "expires_at", "curator_note"} <= columns


def test_experience_section_injects_active_only_and_bumps_hits():
    active_id = _exp("批9 active 注入", body="批9 active 可注入")
    pending_id = _exp("批9 pending 不注入", body="批9 pending 不可注入", status="pending_review")
    try:
        text = experience_section("score")
        assert "批9 active 可注入" in text
        assert "批9 pending 不可注入" not in text
        row = _get(active_id)
        assert row["hit_count"] >= 1
        assert row["last_used_at"] is not None
    finally:
        _cleanup([active_id, pending_id])


def test_experience_section_tolerates_bump_failure(monkeypatch):
    monkeypatch.setattr(repo, "search_experience", lambda **kwargs: [{
        "id": 999001, "title": "批9 bump 失败", "body": "仍可注入",
        "confidence": 0.8, "auto_merged": 0,
    }])
    monkeypatch.setattr(repo, "bump_experience_hits",
                        lambda ids: (_ for _ in ()).throw(RuntimeError("boom")))
    text = experience_section("score")
    assert "仍可注入" in text


def test_run_curator_dry_run_does_not_change_status():
    eid = _exp("批9 dryrun 过期", confidence=0.9)
    _set_fields(eid, expires_at=datetime.now() - timedelta(days=1))
    try:
        result = memory_curator.run_curator(dry_run=True, limit=50)
        assert any(a.get("id") == eid and a["action"] == "expire" for a in result["actions"])
        assert _get(eid)["status"] == "active"
    finally:
        _cleanup([eid])


def test_expired_active_memory_executes_to_expired_and_logs():
    eid = _exp("批9 执行过期", confidence=0.9)
    _set_fields(eid, expires_at=datetime.now() - timedelta(days=1))
    try:
        result = memory_curator.run_curator(dry_run=False, limit=50)
        assert result["executed"] >= 1
        assert _get(eid)["status"] == "expired"
        with SessionLocal() as db:
            log = db.execute(select(ReviewLog).where(
                ReviewLog.experience_id == eid,
                ReviewLog.action == "curator_expire")).scalar_one_or_none()
        assert log is not None
    finally:
        _cleanup([eid])


def test_low_confidence_old_low_hit_memory_archives():
    eid = _exp("批9 老旧低置信", confidence=0.2)
    _set_fields(eid, created_at=datetime.now() - timedelta(days=120), hit_count=0)
    try:
        memory_curator.run_curator(dry_run=False, limit=50)
        assert _get(eid)["status"] == "archived"
    finally:
        _cleanup([eid])


def test_duplicate_memories_only_create_pending_review_summary():
    ids = [
        _exp("批9 重复A", body="同一主线突破后不要追高，等待缩量回踩。", tags=["批9重复"]),
        _exp("批9 重复A", body="同一主线突破后不要追高，等待缩量回踩。", tags=["批9重复"]),
    ]
    created_id = None
    try:
        result = memory_curator.run_curator(dry_run=False, limit=100)
        summaries = [a for a in result["actions"] if a["action"] == "propose_summary"
                     and set(ids) == set(a["source_ids"])]
        assert summaries
        created_id = summaries[0]["id"]
        summary = _get(created_id)
        assert summary["status"] == "pending_review"
        assert summary["auto_merged"] == 0
    finally:
        _cleanup([*ids, created_id] if created_id else ids)


def test_curator_run_api_requires_confirm_for_write():
    client = TestClient(app)
    resp = client.post("/api/experience/curator/run",
                       json={"dry_run": False, "limit": 10, "confirm": False})
    assert resp.status_code == 400


def test_experience_expire_api_archives_and_logs():
    eid = _exp("批9 API 归档", confidence=0.9)
    try:
        client = TestClient(app)
        resp = client.post(f"/api/experience/{eid}/expire",
                           json={"status": "archived", "note": "人工归档"})
        assert resp.status_code == 200
        row = _get(eid)
        assert row["status"] == "archived"
        assert "人工归档" in row["curator_note"]
        with SessionLocal() as db:
            log = db.execute(select(ReviewLog).where(
                ReviewLog.experience_id == eid,
                ReviewLog.action == "curator_archive")).scalar_one_or_none()
        assert log is not None
    finally:
        _cleanup([eid])


def test_high_value_active_memory_is_not_curated():
    eid = _exp("批9 高价值保留", confidence=0.95)
    _set_fields(eid, created_at=datetime.now() - timedelta(days=120), hit_count=5)
    try:
        result = memory_curator.run_curator(dry_run=False, limit=50)
        ids = {a.get("id") for a in result["actions"] if a["action"] in ("archive", "expire")}
        assert eid not in ids
        assert _get(eid)["status"] == "active"
    finally:
        _cleanup([eid])
