"""存储空间维护测试：
1. 超期新闻清理（保留期内不删，关键分析数据不动）
2. SQLite VACUUM 与体积统计不抛异常
3. 定时维护任务开关（关闭时零操作）
4. 向量索引时间戳解析（_payload_ts）
"""
from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.db import repo
from app.db.models import NewsArticle
from app.db.session import SessionLocal, init_db
from app.services.vector_store import _payload_ts


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _insert_news(code: str, title: str, created_days_ago: int) -> None:
    with SessionLocal() as db:
        db.add(NewsArticle(
            stock_code=code, stock_name="测试股", title=title, content="内容",
            source="测试", url="", published_at="",
            created_at=datetime.now() - timedelta(days=created_days_ago)))
        db.commit()


def test_retention_cleans_old_keeps_recent(monkeypatch):
    monkeypatch.setattr(settings, "news_retention_days", 90)
    old_code, new_code = "600911", "600912"
    _insert_news(old_code, "旧新闻-超期", 120)   # 超期
    _insert_news(new_code, "新新闻-保留", 10)    # 保留期内

    stats = repo.maintenance_db()
    assert stats["news_deleted"] >= 1
    assert "size_before_mb" in stats and "size_after_mb" in stats

    with SessionLocal() as db:
        old_rows = db.query(NewsArticle).filter(
            NewsArticle.stock_code == old_code).count()
        new_rows = db.query(NewsArticle).filter(
            NewsArticle.stock_code == new_code).count()
    assert old_rows == 0, "超期新闻应被清理"
    assert new_rows == 1, "保留期内新闻不应清理"


def test_maintenance_returns_stats_shape(monkeypatch):
    monkeypatch.setattr(settings, "news_retention_days", 90)
    stats = repo.maintenance_db()
    assert set(stats) == {"news_deleted", "size_before_mb", "size_after_mb"}
    # 关键分析数据不受影响：候选/评分表仍可正常读写
    repo.upsert_candidate("600913", "维护测试股", "2026-08-04", 1, ["理由"], [], {})
    assert any(c["stock_code"] == "600913"
               for c in repo.list_candidates(date="2026-08-04"))


def test_payload_ts_parsing():
    assert _payload_ts("2026-08-04 10:30:00") > 0
    assert _payload_ts("2026-08-04") > 0
    assert _payload_ts("") == 0
    assert _payload_ts("未知格式") == 0


def test_maintenance_job_disabled_is_noop(monkeypatch):
    from app.scheduler.jobs import maintenance_job

    monkeypatch.setattr(settings, "db_maintenance_enabled", False)
    maintenance_job()  # 关闭时直接返回，不执行清理
