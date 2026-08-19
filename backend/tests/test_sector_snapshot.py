"""板块数据稳定性优化：sector_snapshot 服务与 DB 层测试（dev SQLite，不触网）

覆盖（8 条，与执行指令 4.2 对应）：
1. upsert_sector_snapshot 幂等（删后插，不重复）
2. list_sector_snapshot_by_date 按 rank_no 升序
3. get_sector_snapshot_updated_at 空表 → None
4. get_hot_sectors_with_fallback：DB 有数据 + stale（updated_at 1h 前）→ stale=true
5. 同上：DB 空 + 交易时段 → 触发 refresh 兜底
6. 同上：DB 空 + 非交易时段 → 返回空 + error
7. market_view.hot_sectors 响应 4 字段齐全（sectors/updated_at/stale/error）
8. akshare fetch_industry_spot 带 kind="snapshot" 时走 snapshot 断路器（连续失败进降级→备用）
"""
from datetime import datetime, timedelta
from unittest import mock

import pandas as pd
import pytest

from app.datasource import market_hours
from app.db import repo
from app.db.session import init_db
from app.services import sector_snapshot
from app.services.sector_snapshot import (STALE_THRESHOLD_SECONDS,
                                          get_hot_sectors_with_fallback,
                                          refresh_sector_snapshot)


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


# ============ 1-3: repo 层（真实 SQLite） ============

def _row(rank_no, name="半导体", pct=3.5):
    return {
        "trade_date": "2026-08-19",
        "sector_name": name,
        "change_pct": pct,
        "leading_stock_name": "中芯",
        "leading_stock_code": "688981",
        "source": "em",
        "rank_no": rank_no,
    }


def test_upsert_sector_snapshot_idempotent():
    rows = [_row(i, name=f"板块{i}", pct=float(i)) for i in range(1, 6)]
    assert repo.upsert_sector_snapshot(rows) == 5
    # 再 upsert 同样 5 条 → 仍 5 条（删后插，不重复）
    assert repo.upsert_sector_snapshot(rows) == 5
    assert len(repo.list_sector_snapshot_by_date("2026-08-19")) == 5


def test_list_sector_snapshot_by_date_ordered():
    repo.upsert_sector_snapshot([
        _row(2, name="板块B", pct=2.0),
        _row(1, name="板块A", pct=3.0),
    ])
    sectors = repo.list_sector_snapshot_by_date("2026-08-19")
    assert [s["rank_no"] for s in sectors] == [1, 2]


def test_get_sector_snapshot_updated_at_none_when_empty():
    assert repo.get_sector_snapshot_updated_at("2099-01-01") is None


# ============ 4-7: 读路径（mock repo / 交易时段） ============

def test_get_hot_sectors_with_fallback_stale_true(monkeypatch):
    """DB 有数据但 updated_at 是 1 小时前 → stale=true（返回旧值 + 标注）"""
    one_hour_ago = (datetime.now() - timedelta(minutes=60)).strftime("%Y-%m-%d %H:%M:%S")
    monkeypatch.setattr(repo, "list_sector_snapshot_by_date",
                        lambda d, limit=5: [{"board_name": "A", "change_pct": 1.0,
                                             "leading_stock": "x", "leading_code": "1",
                                             "rank_no": 1, "source": "em"}])
    monkeypatch.setattr(repo, "get_sector_snapshot_updated_at",
                        lambda d: one_hour_ago)
    result = get_hot_sectors_with_fallback()
    assert result["sectors"]  # 有旧值
    assert result["stale"] is True  # 标注陈旧
    assert result["error"] is None


def test_get_hot_sectors_with_fallback_db_empty_trading(monkeypatch):
    """DB 空 + 交易时段 → 触发一次 refresh 兜底"""
    # 初始 list 返回空（模拟 DB 空）；refresh 成功后二次 list 返回数据
    list_calls = {"n": 0}

    def _flaky_list(d, limit=5):
        list_calls["n"] += 1
        if list_calls["n"] == 1:
            return []
        return [{"board_name": "A", "change_pct": 1.0, "leading_stock": "x",
                 "leading_code": "1", "rank_no": 1, "source": "em"}]

    monkeypatch.setattr(repo, "list_sector_snapshot_by_date", _flaky_list)
    monkeypatch.setattr(repo, "get_sector_snapshot_updated_at", lambda d: None)
    monkeypatch.setattr(market_hours, "snapshot_allowed", lambda: True)
    with mock.patch.object(sector_snapshot, "refresh_sector_snapshot") as m_refresh:
        m_refresh.return_value = {"success": True, "rows": 1, "error": None}
        result = get_hot_sectors_with_fallback()
    m_refresh.assert_called_once()  # 触发了 refresh
    assert result["error"] is None
    assert result["stale"] is False
    assert result["sectors"]  # refresh 后有兜底数据


def test_get_hot_sectors_with_fallback_db_empty_non_trading(monkeypatch):
    """DB 空 + 非交易时段 → 返回空 + error（不触发 refresh）"""
    monkeypatch.setattr(repo, "list_sector_snapshot_by_date", lambda d, limit=5: [])
    monkeypatch.setattr(repo, "get_sector_snapshot_updated_at", lambda d: None)
    monkeypatch.setattr(market_hours, "snapshot_allowed", lambda: False)
    with mock.patch.object(sector_snapshot, "refresh_sector_snapshot") as m_refresh:
        result = get_hot_sectors_with_fallback()
    m_refresh.assert_not_called()
    assert result["sectors"] == []
    assert result["error"] == "非交易时段，板块行情暂不可用"


def test_hot_sectors_response_shape(monkeypatch):
    """market_view.hot_sectors 响应含 sectors/updated_at/stale/error 4 字段（向前兼容新增 stale）"""
    from app.services import market_view
    with mock.patch("app.services.sector_snapshot.get_hot_sectors_with_fallback") as m_fb:
        m_fb.return_value = {"sectors": [], "updated_at": "", "stale": False, "error": "x"}
        resp = market_view.hot_sectors()
    assert set(resp.keys()) == {"sectors", "updated_at", "stale", "error"}


# ============ 8: akshare 断路器（kind=snapshot） ============

def test_akshare_industry_spot_with_breaker(monkeypatch):
    """fetch_industry_spot 带 kind='snapshot'：主源连续失败 → 进 snapshot 断路器 → 降级走备用"""
    from app.core.config import settings
    from app.datasource.akshare_source import AkshareSource
    from app.datasource.breaker import get_breaker, reset as breaker_reset

    breaker_reset()
    monkeypatch.setattr(settings, "datasource_breaker_threshold", 2)

    boom_calls = {"primary": 0}

    def primary_boom():
        boom_calls["primary"] += 1
        raise ConnectionError("东财拒绝连接")

    def fallback_ok():
        return pd.DataFrame([{"board_name": "回落", "change_pct": 1.0,
                              "leading_stock": "某股"}])

    src = AkshareSource()
    # 主源连续失败达阈值 → 进断路器（服务层已把 kind 传 snapshot）
    with pytest.raises(Exception):
        src._call_with_retry("industry_spot", primary_boom, None, kind="snapshot")
    assert get_breaker("snapshot").is_degraded
    # 降级期间：不复用 try 主源，直接走备用
    df = src._call_with_retry("industry_spot", primary_boom, fallback_ok, kind="snapshot")
    assert not df.empty
    breaker_reset()
