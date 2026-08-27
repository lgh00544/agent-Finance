"""板块轮动·批次D 多窗口规律测试（dev SQLite，不触网）

2 例：①窗口统计正确（累计强度/生命周期/放量延续率/轮动周期）②空数据返回空结构不报错
"""
import pytest
from sqlalchemy import text

from app.db import repo
from app.db.session import SessionLocal, init_db
from app.services.sector_rotation_pattern import analyze_patterns

D1, D2, D3 = "2026-08-11", "2026-08-12", "2026-08-13"


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _snap(d, names, pcts, vol=None):
    repo.upsert_sector_daily_snapshot([
        {"trade_date": d, "sector_name": n, "change_pct": p, "rank_no": i + 1,
         "up_count": 30, "down_count": 10,
         "volume_ratio": (vol or {}).get(n, 1.0), "turnover_rate": 3.0,
         "leading_stock_name": "", "leading_stock_code": "", "leading_chg": None,
         "source": "em"}
        for i, (n, p) in enumerate(zip(names, pcts))])


# ============ 2: 空数据返回空结构不报错 ============

def test_empty_window_no_error():
    with SessionLocal() as db:
        db.execute(text("DELETE FROM sector_daily_snapshot"))
        db.commit()
    res = analyze_patterns(days=3)
    assert res["success"] is False
    assert res["cumulative_strength_top10"] == []
    assert res["mainline_candidates"] == []
    assert res["rotation_cycle_days"] is None
    assert res["volume_breakout_continuation"] is None


# ============ 1: 窗口统计正确 ============

def test_window_stats():
    names = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"]
    _snap(D1, names, [5, 4, 3, 2, 1, 0.5, 0, -0.5, -1, -1.5], vol={"S1": 2.0})
    _snap(D2, names, [3, 2, 1, 0.5, 0, -0.5, -1, -1.5, -2, -2.5], vol={"S1": 2.0})
    _snap(D3, ["S1", "S2", "S3", "S4", "S5", "T6", "T7", "T8", "T9", "T10"],
          [2, 1, 0.5, 0, -0.5, 2, 1, 0.5, 0, -0.5], vol={"S1": 2.0})
    res = analyze_patterns(days=5)
    assert res["success"] is True
    assert res["days"] == 3
    # 累计强度：S1 最高（5+3+2=10），S2 次之（4+2+1=7）
    assert res["cumulative_strength_top10"][0]["sector_name"] == "S1"
    assert res["cumulative_strength_top10"][0]["cum_strength"] == pytest.approx(10.0)
    assert res["cumulative_strength_top10"][1]["sector_name"] == "S2"
    # 生命周期：S1-5 连续 3 天、T6-10 连续 1 天 → 均值 2.0
    assert res["lifecycle_avg_streak"] == pytest.approx(2.0)
    # S1 放量（量比2.0）且居前：D1→D2(+3)、D2→D3(+2) 均延续 → 延续率 1.0
    assert res["volume_breakout_continuation"] == pytest.approx(1.0)
    # 高切频次：D1→D2 换手 0、D2→D3 换手 0.5（<0.6）→ 0 次
    assert res["switch_frequency"] == 0
    # 轮动周期：日均换手 0.25 → 10/0.25 = 40
    assert res["rotation_cycle_days"] == 40
