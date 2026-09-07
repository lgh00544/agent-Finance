import pandas as pd
from sqlalchemy import text

from app.agents import review, sell
from app.db import repo
from app.db.session import SessionLocal, init_db


def test_position_plan_history_migration_is_idempotent():
    init_db()
    with SessionLocal() as db:
        columns = {row[1] for row in db.execute(text("PRAGMA table_info(position_plan)"))}
    assert "supersedes_id" in columns


def test_plan_history_links_new_version_to_previous():
    first = repo.insert_plan(
        "601234", "历史测试", "2026-09-07", 20.0,
        [{"tranche": 1, "price_zone": "10~10.5", "ratio_pct": 20}],
        9.0, 12.0, "第一版",
    )
    second = repo.insert_plan(
        "601234", "历史测试", "2026-09-07", 30.0,
        [{"tranche": 1, "price_zone": "10.5~11", "ratio_pct": 30}],
        9.5, 13.0, "第二版",
    )

    rows = [row for row in repo.list_plans(code="601234", limit=10)
            if row["plan_date"] == "2026-09-07"]
    assert {row["id"] for row in rows} == {first, second}
    old = next(row for row in rows if row["id"] == first)
    new = next(row for row in rows if row["id"] == second)
    assert old["status"] == "superseded"
    assert new["supersedes_id"] == first


def test_review_uses_holding_plan_id_after_later_plan_is_created(monkeypatch):
    first = repo.insert_plan(
        "601235", "绑定测试", "2026-09-01", 20.0, [], 9.0, 12.0, "入场版本",
    )
    second = repo.insert_plan(
        "601235", "绑定测试", "2026-09-07", 40.0, [], 8.0, 14.0, "后来版本",
    )
    hid = repo.insert_holding(
        "601235", "绑定测试", "2026-09-01", 10.0, 100, 1000.0,
        plan_id=first,
    )

    class _FakeSource:
        def fetch_daily_kline(self, code, start, end):
            return pd.DataFrame(columns=["date", "open", "high", "low",
                                         "close", "change_pct", "volume"])

    monkeypatch.setattr(review, "get_datasource", lambda: _FakeSource())
    state = review.collect_review({"holding_id": hid, "trade_date": "2026-09-07"})
    bound = state["exit_suggest"]["plan"]

    assert second > first
    assert bound["plan_id"] == first
    assert bound["binding"] == "holding.plan_id"
    assert bound["rationale"] == "入场版本"
