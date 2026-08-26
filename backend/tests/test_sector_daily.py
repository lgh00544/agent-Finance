"""板块轮动·全板块日快照 服务 + repo 层测试（dev SQLite，不触网）

覆盖 3 例（对应执行指令批次A §四）：
1. 全板块落库 N>5（不截取 top5，rank_no 按涨幅降序）
2. upsert 删后插幂等（同 trade_date 覆盖不重复）
3. 缺字段如实 NULL（K227 不编造）
"""
import time
from unittest import mock

import pandas as pd
import pytest

from app.datasource.akshare_source import AkshareSource
from app.db import repo
from app.db.session import init_db
from app.services import sector_daily

TODAY = time.strftime("%Y-%m-%d")


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _board_df(n, detail=True):
    data = []
    for i in range(1, n + 1):
        row = {"board_name": f"板块{i:02d}", "change_pct": float(i - 6),
               "leading_stock": f"龙头{i}"}
        if detail:
            row.update({"up_count": 100 + i, "down_count": 50 - i,
                        "volume_ratio": 1.0 + i / 10, "turnover_rate": 2.0 + i / 10})
        data.append(row)
    return pd.DataFrame(data)


def _daily_row(rank_no, name="半导体", pct=3.5):
    return {
        "trade_date": "2026-08-19",
        "sector_name": name,
        "change_pct": pct,
        "rank_no": rank_no,
        "up_count": 120,
        "down_count": 30,
        "volume_ratio": 1.5,
        "turnover_rate": 4.2,
        "leading_stock_name": "中芯",
        "leading_stock_code": "688981",
        "leading_chg": 9.8,
        "source": "em",
    }


# ============ 1: 全板块落库 N>5 ============

def test_refresh_full_board_no_top5_cut():
    """8 个板块全存（不截取 top5），rank_no 按涨幅降序 1~8"""
    with mock.patch.object(AkshareSource, "fetch_industry_spot",
                           return_value=_board_df(8)):
        result = sector_daily.refresh_sector_daily_snapshot()
    assert result["success"] is True
    assert result["rows"] == 8
    rows = repo.list_sector_daily_by_date(TODAY)
    assert len(rows) == 8
    # 涨幅降序：板块08(+2.0) 第1，板块01(-5.0) 第8
    assert rows[0]["sector_name"] == "板块08"
    assert rows[-1]["sector_name"] == "板块01"
    assert [r["rank_no"] for r in rows] == list(range(1, 9))
    assert rows[0]["leading_stock_name"] == "龙头8"
    assert rows[0]["volume_ratio"] == pytest.approx(1.8)
    assert rows[0]["up_count"] == 108


# ============ 2: 删后插幂等 ============

def test_upsert_sector_daily_idempotent():
    rows = [_daily_row(i, name=f"板块{i}") for i in range(1, 6)]
    assert repo.upsert_sector_daily_snapshot(rows) == 5
    # 再 upsert 同样 5 条 → 仍 5 条（删后插，不重复）
    assert repo.upsert_sector_daily_snapshot(rows) == 5
    assert len(repo.list_sector_daily_by_date("2026-08-19")) == 5


# ============ 3: 缺字段如实 NULL ============

def test_missing_fields_none_not_fabricated():
    """df 缺 volume_ratio/turnover_rate/down_count 且 up_count 为 NaN/None → 落库为 NULL"""
    df = _board_df(3, detail=False)
    df["up_count"] = [float("nan"), 10, None]  # 板块01→NaN / 板块02→10 / 板块03→None
    with mock.patch.object(AkshareSource, "fetch_industry_spot", return_value=df):
        result = sector_daily.refresh_sector_daily_snapshot()
    assert result["success"] is True
    rows = repo.list_sector_daily_by_date(TODAY)
    assert rows[0]["sector_name"] == "板块03"   # 涨幅最高排第1，对应 up_count=None
    assert rows[0]["up_count"] is None
    assert rows[0]["volume_ratio"] is None      # 缺列 → NULL
    assert rows[0]["turnover_rate"] is None
    assert rows[0]["down_count"] is None
    assert rows[0]["leading_stock_code"] == ""  # 无代码来源 → 默认空串
    assert rows[1]["up_count"] == 10            # 有效值正常落库
