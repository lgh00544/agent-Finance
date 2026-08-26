"""关系持仓批次G：持仓红线扫描链路测试（≤5 用例）

覆盖：①C1 单只占比超 60% 触发 ②C3 当前价 ≤ 成本×0.92 触发（含 C2 回撤触发/缺 low→null）
      ③K139 trailing_stop 计算 + stage 推进 ④K189/K226 缓存缺失 → 显式 null 不伪造
      ⑤Schema 全字段可读 + Agent 注入字段可提取（monitor 读整行 / sell 读 k139_sop）
约定：不跑真实行情源；各用例独立 stock_code/trade_date 隔离 86400s 缓存键。
"""
import pytest

from app.services.red_line_check import (
    C2_DRAWDOWN_PCT, C3_FACTOR, K139_TRAILING_FACTOR, compute_red_line,
)


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    """建全部测试表（account_total_asset 依赖 baseline 表）"""
    from app.db.session import init_db
    init_db()


def _holding(code: str, cost: float = 10.0, shares: int = 1000,
             high_price: float | None = None) -> dict:
    return {"stock_code": code, "entry_price": cost, "shares": shares,
            "high_price": high_price or round(cost * 1.1, 2)}


# ① C1 单只占比超 60% 触发（L0 阈值不可改）
def test_c1_concentration_alert():
    code, date, total = "RL0001", "2026-08-24", 100000.0
    rows = compute_red_line([_holding(code, cost=10.0, shares=8000)],
                            {code: 10.0}, total, trade_date=date)
    assert rows[0]["c1_cap_pct"] == 80.0          # 80000/100000
    assert rows[0]["c1_alert"] is True
    rows2 = compute_red_line([_holding(code, cost=10.0, shares=5000)],
                             {code: 10.0}, total, trade_date=date)
    assert rows2[0]["c1_cap_pct"] == 50.0
    assert rows2[0]["c1_alert"] is False


# ② C3 当前价 ≤ 成本×0.92 触发（附 C2 回撤触发 / 缺 low → null）
def test_c3_stop_loss_and_c2_drawdown():
    code, date = "RL0002", "2026-08-24"
    cost = 10.0
    rows = compute_red_line([_holding(code, cost=cost)], {code: 9.1}, 100000.0, trade_date=date)
    assert rows[0]["c3_stop_loss"] == round(cost * C3_FACTOR, 2)   # 9.2
    assert rows[0]["c3_alert"] is True
    rows2 = compute_red_line([_holding(code, cost=cost)], {code: 9.5}, 100000.0, trade_date=date)
    assert rows2[0]["c3_alert"] is False

    # C2：日内最低价跌破成本 -30% → 触发；-28% → 不触发；缺 low → null
    rows3 = compute_red_line([_holding(code, cost=cost)], {code: 7.0}, 100000.0,
                             trade_date=date, lows={code: 6.9})
    assert rows3[0]["c2_alert"] is True          # (6.9-10)/10 = -31% ≤ -30%
    rows4 = compute_red_line([_holding(code, cost=cost)], {code: 7.2}, 100000.0,
                             trade_date=date, lows={code: 7.2})
    assert rows4[0]["c2_alert"] is False         # (7.2-10)/10 = -28% > -30%
    rows5 = compute_red_line([_holding(code, cost=cost)], {code: 7.0}, 100000.0, trade_date=date)
    assert rows5[0]["c2_alert"] is None          # 缺 low → 显式 null
    assert C2_DRAWDOWN_PCT == 30.0               # L0 阈值未被改


# ③ K139 SOP：trailing_stop 计算 + stage 推进（参考权重，判断在 LLM）
def test_k139_trailing_stop_and_stage():
    code, date = "RL0003", "2026-08-24"
    cost = 100.0
    cases = [
        (95.0, "试探仓", 97.5),    # 亏损但高于 C3（92）
        (101.0, "持有观察", 100.5),
        (106.0, "+5%减仓", 103.0),
        (112.0, "+10%减仓", 106.0),
        (90.0, "跌破C3", 95.0),    # ≤ C3
    ]
    for price, stage, ts in cases:
        rows = compute_red_line([_holding(code, cost=cost)], {code: price}, 100000.0, trade_date=date)
        k = rows[0]["k139_sop"]
        assert k["trailing_stop"] == round(cost + (price - cost) * K139_TRAILING_FACTOR, 2)
        assert k["stage"] == stage
        assert isinstance(k["next_action"], str) and k["next_action"]


# ④ K189/K226 缓存缺失 → 显式 null 不伪造（不补 False/不补 0）
def test_missing_cache_null_not_fabricated():
    code, date = "RL0004", "2026-08-24"
    from app.cache import cache
    cache.delete(f"capital_view:{date}:{code}")
    cache.delete(f"distribution_phase:{date}:{code}")
    rows = compute_red_line([_holding(code)], {code: 10.0}, 100000.0, trade_date=date)
    row = rows[0]
    assert row["k189_wash_suspect"] is None      # E 缓存缺失 → None
    assert row["k226_subject_count"] is None     # D 缓存缺失 → None
    assert row["k226_alert_level"] is None


# ⑤ Schema 全字段可读 + Agent 注入字段可提取（monitor 读整行 / sell 读 k139_sop）
def test_schema_keys_and_agent_inject_readable():
    code, date = "RL0005", "2026-08-24"
    rows = compute_red_line([_holding(code, high_price=11.0)], {code: 10.0}, 100000.0, trade_date=date)
    row = rows[0]
    assert {"stock_code", "c1_cap_pct", "c1_alert", "c2_alert", "c3_stop_loss", "c3_alert",
            "c4_high_break", "pnl_pct", "k139_sop", "k226_subject_count", "k226_alert_level",
            "k189_wash_suspect"} <= set(row)
    # 现价 10 < 持仓期最高 11 → C4 不突破（不伪造 True）
    assert row["c4_high_break"] is False
    assert row["pnl_pct"] == 0.0
    # sell 注入：读 k139_sop 子结构
    assert isinstance(row["k139_sop"], dict)
    assert {"trailing_stop", "stage", "next_action"} <= set(row["k139_sop"])
