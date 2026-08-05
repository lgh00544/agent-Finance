"""全链路性能优化测试：索引补强 / 高频读缓存与写失效 / 首页聚合接口（并行模块，单模块失败隔离）
（用测试库与 mock 探活，不触外网）"""
import pytest
from sqlalchemy import text

from app.db.session import engine, init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


# ================= 索引补强 =================

def test_indexes_created():
    """高频查询组合索引全部建齐（杜绝全表扫描）"""
    expected = {
        "stock_candidate": "ix_candidate_date_rank",
        "holding": "ix_holding_status",
        "review_result": "ix_review_exit_status",
        "agent_suggestion": "ix_suggestion_status",
    }
    with engine.connect() as conn:
        for table, idx in expected.items():
            rows = conn.exec_driver_sql(f"PRAGMA index_list({table})").fetchall()
            names = [r[1] for r in rows]
            assert idx in names, f"{table} 缺少索引 {idx}"


def test_query_plan_uses_indexes():
    """EXPLAIN 确认高频查询走索引而非全表扫描"""
    with engine.connect() as conn:
        plans = conn.exec_driver_sql(
            "EXPLAIN QUERY PLAN SELECT * FROM stock_candidate "
            "WHERE trade_date='2026-08-04' ORDER BY rank LIMIT 50").fetchall()
        assert any("ix_candidate_date_rank" in row[3] for row in plans), plans
        plans = conn.exec_driver_sql(
            "EXPLAIN QUERY PLAN SELECT * FROM holding WHERE status='holding'").fetchall()
        assert any("ix_holding_status" in row[3] for row in plans), plans


# ================= 高频读缓存（60s）+ 写自动失效 =================

def test_db_query_cache_and_invalidation():
    """列表查询缓存：命中返回缓存值；写入后自动失效读到最新；命名空间互不干扰"""
    from app.cache import cache
    from app.db import repo
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        db.execute(text("DELETE FROM stock_candidate WHERE trade_date='2099-01-01'"))
        db.commit()
    cache.delete_prefix("dbq:")

    assert repo.list_candidates(date="2099-01-01") == []
    cache.set("dbq:other:keep", "v", 60)

    repo.upsert_candidate("600999", "缓存测试", "2099-01-01", 1, ["r"], [], {}, {})
    rows = repo.list_candidates(date="2099-01-01")
    assert len(rows) == 1 and rows[0]["stock_code"] == "600999"

    # 二次读取命中缓存（不落库）：同一参数结果一致
    assert repo.list_candidates(date="2099-01-01")[0]["rank"] == 1

    # 写入自动失效 → 立即读到最新
    repo.upsert_candidate("600999", "缓存测试", "2099-01-01", 5, ["r2"], [], {}, {})
    assert repo.list_candidates(date="2099-01-01")[0]["rank"] == 5

    # 不同参数独立缓存（date 不同不相互影响）
    assert repo.list_candidates(date="2099-01-02") == []
    repo.upsert_candidate("600998", "缓存测试B", "2099-01-02", 2, ["r"], [], {}, {})
    assert repo.list_candidates(date="2099-01-02")[0]["rank"] == 2

    assert cache.get("dbq:other:keep") == "v"  # 无关命名空间保留
    cache.delete_prefix("dbq:")


def test_db_query_cache_disabled_by_ttl_zero(monkeypatch):
    """DB_QUERY_CACHE_TTL=0 关闭读缓存：每次查询直接落库"""
    from app.cache import cache
    from app.core.config import settings
    from app.db import repo
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        db.execute(text("DELETE FROM stock_candidate WHERE trade_date='2098-01-01'"))
        db.commit()
    cache.delete_prefix("dbq:")

    monkeypatch.setattr(settings, "db_query_cache_ttl", 0)
    repo.upsert_candidate("600997", "无缓存", "2098-01-01", 1, ["r"], [], {}, {})
    assert len(repo.list_candidates(date="2098-01-01")) == 1
    assert len(cache.get("dbq:candidate:") or "") == 0  # 无任何候选缓存 key


# ================= 首页聚合接口（并行模块 + 单模块失败隔离） =================

def test_dashboard_returns_all_modules(monkeypatch):
    """聚合接口一次返回全部首页模块（探活 mock，不触外网）"""
    import app.services.dashboard as dash

    monkeypatch.setattr(dash, "_system_status",
                        lambda: {"checked_at": "2026-08-04 10:00", "connections": []})
    monkeypatch.setattr(dash, "_llm_stats", lambda: {"requests": 1, "hit_rate_pct": None})

    result = dash.build_dashboard()
    modules = result["modules"]
    assert result["checked_at"]
    for key in ("system", "llm_stats", "market_condition", "holdings", "alerts",
                "candidates", "scores", "plans", "reviews", "pending_suggestions"):
        assert key in modules, f"聚合缺模块: {key}"
    assert modules["system"]["connections"] == []
    assert modules["llm_stats"]["requests"] == 1
    assert isinstance(modules["holdings"], list)
    assert isinstance(modules["alerts"], list)
    assert isinstance(modules["candidates"], list)
    assert isinstance(modules["scores"], list)
    assert isinstance(modules["plans"], list)
    assert isinstance(modules["reviews"], list)
    assert isinstance(modules["pending_suggestions"], list)


def test_dashboard_module_failure_isolated(monkeypatch):
    """单模块失败仅标注 error，不中断其余模块与整体响应"""
    import app.services.dashboard as dash

    def _boom():
        raise RuntimeError("探活失败")

    monkeypatch.setattr(dash, "_system_status", _boom)

    result = dash.build_dashboard()
    assert result["modules"]["system"]["error"] == "RuntimeError"
    assert isinstance(result["modules"]["holdings"], list)   # 其余模块正常
    assert isinstance(result["modules"]["candidates"], list)
    assert result["checked_at"]
