"""经验沉淀闭环·批1：pending_experience 合并重复（同 hour 桶同 (stock_code, signal_type) → count++）

5 用例：首次 insert / 同 hour 合并 1 次 / 同 hour 合并 3+ 次仍 1 行 / 跨 hour 新行 /
不同 signal_type 各 1 行；另用独立 code 防同进程共享临时库串扰。
"""
import datetime as dt
import json

import pytest
from sqlalchemy import select

from app.db import repo
from app.db.models import PendingExperience
from app.db.session import SessionLocal, init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _rows(code: str) -> list:
    return [r for r in repo.list_pending_experience() if str(r["summary"]).startswith(code)]


def test_first_insert_count_1():
    rid = repo.add_pending_experience("t1", "持仓", "000701 监控信号 hold", "100")
    rows = _rows("000701")
    assert len(rows) == 1 and rows[0]["id"] == rid
    assert json.loads(rows[0]["artifacts_ref"])["count"] == 1


def test_same_hour_merge_count_and_old_int_compat():
    rid = repo.add_pending_experience("t2", "持仓", "000702 监控信号 hold", "100")
    # 模拟旧数据（artifacts_ref=int）：直接改库后再次插入 → 合并且不报错
    with SessionLocal() as db:
        row = db.execute(select(PendingExperience).where(PendingExperience.id == rid)).scalar_one()
        row.artifacts_ref = "42"
        db.commit()
    repo.add_pending_experience("t2", "持仓", "000702 监控信号 hold", "100")
    rows = _rows("000702")
    assert len(rows) == 1
    assert json.loads(rows[0]["artifacts_ref"])["count"] == 2


def test_same_hour_three_plus_merge_still_one_row():
    for _ in range(4):
        repo.add_pending_experience("t3", "持仓", "000703 监控信号 hold", "100")
    rows = _rows("000703")
    assert len(rows) == 1
    assert json.loads(rows[0]["artifacts_ref"])["count"] == 4


def test_diff_hour_not_merged(monkeypatch):
    repo.add_pending_experience("t4", "持仓", "000704 监控信号 hold", "100")
    real = dt.datetime.now()

    class _FakeDT:
        @staticmethod
        def now():
            return real + dt.timedelta(hours=2)

    monkeypatch.setattr(repo, "datetime", _FakeDT)
    repo.add_pending_experience("t4", "持仓", "000704 监控信号 hold", "100")
    rows = _rows("000704")
    assert len(rows) == 2


def test_diff_signal_type_not_merged():
    repo.add_pending_experience("t5", "持仓", "000705 监控信号 hold", "100")
    repo.add_pending_experience("t5", "持仓", "000705 监控信号 reduce", "100")
    rows = _rows("000705")
    assert len(rows) == 2
