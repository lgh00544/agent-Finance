"""板块轮动·状态判定 服务层测试（dev SQLite，不触网；箱位 mock）

覆盖 3 例（对应执行指令批次B §四）：
1. calc_churn_rate 全换 = 1.0（含部分重叠口径）
2. streak≥3 且 top3 仍在 → 判 mainline
3. churn≥0.6 且无 streak≥3 → 判 rotation
"""
from datetime import date, timedelta
from unittest import mock

import pytest

from app.datasource.akshare_source import AkshareSource
from app.db import repo
from app.db.session import init_db
from app.services.sector_rotation import calc_churn_rate, judge_rotation_state


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _snapshot_rows(trade_date, names):
    return [{"trade_date": trade_date, "sector_name": n, "change_pct": float(5 - i),
             "rank_no": i + 1, "source": "em"}
            for i, n in enumerate(names)]


# ============ 1: churn 全换 = 1.0 ============

def test_calc_churn_rate_full_change():
    assert calc_churn_rate(["A", "B", "C", "D", "E"], ["F", "G", "H", "I", "J"]) == 1.0
    # 部分重叠：2/5 重叠 → 1 − 0.4 = 0.6
    assert calc_churn_rate(["A", "B", "C", "D", "E"], ["A", "B", "X", "Y", "Z"]) == pytest.approx(0.6)
    # 任一侧为空 → 1.0
    assert calc_churn_rate([], ["F", "G"]) == 1.0


# ============ 2: streak≥3 且 top3 仍在 → mainline ============

def test_streak3_judge_mainline():
    today = date.today().isoformat()
    d1 = (date.today() - timedelta(days=1)).isoformat()
    d2 = (date.today() - timedelta(days=2)).isoformat()
    top5 = ["半导体", "银行", "白酒", "券商", "军工"]
    for d in (d2, d1, today):
        repo.upsert_sector_daily_snapshot(_snapshot_rows(d, top5))
    with mock.patch.object(AkshareSource, "fetch_board_box_positions", return_value={}):
        result = judge_rotation_state(trade_date=today)
    assert result["success"] is True
    assert result["rotation_state"] == "mainline"
    assert result["mainline_sector"] == "半导体"   # rank1 连续3日居前
    assert result["streaks"]["半导体"] >= 3
    # 已落库
    log = repo.get_sector_rank_log(today)
    assert log["rotation_state"] == "mainline"
    assert log["mainline_sector"] == "半导体"


# ============ 3: churn≥0.6 且无 streak≥3 → rotation ============

def test_churn06_no_streak_rotation():
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    repo.upsert_sector_daily_snapshot(_snapshot_rows(yesterday, ["旧1", "旧2", "旧3", "旧4", "旧5"]))
    repo.upsert_sector_daily_snapshot(_snapshot_rows(today, ["新1", "新2", "新3", "新4", "新5"]))
    with mock.patch.object(AkshareSource, "fetch_board_box_positions", return_value={}):
        result = judge_rotation_state(trade_date=today)
    assert result["success"] is True
    assert result["churn_rate"] == 1.0
    assert result["rotation_state"] == "rotation"
    assert result["mainline_sector"] is None
