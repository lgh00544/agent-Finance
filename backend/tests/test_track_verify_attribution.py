"""关系持仓批次H：复盘反哺选股链路测试（≤5 用例）

覆盖：①组合曲线按日累计计算正确（_curve_points 纯函数）②组合贡献度排序 + 最大拖累者识别
      ③周期复利多次操作汇总正确 ④无历史 → has_history=False 不伪造 ⑤Score 注入字段可读 + 缺历史不触发加分
约定：不跑真实行情源（build_holding_view / _daily_closes / repo 全部 monkeypatch）；
      build_stock_cycle_attribution 用不存在的股票代码触发"无历史"路径（真实读库，init_db 建表）。
"""
import inspect

import pytest

from app.services import track_verify as tv


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    """建全部测试表（repo.list_holdings/get_trades 依赖 holdings/trades 表）"""
    from app.db.session import init_db
    init_db()


# ① 组合曲线按日累计计算正确（口径：Σ(单票当日浮盈亏) / 当前总成本 × 100；建仓前不计入）
def test_curve_daily_cumulative():
    items = [
        {"code": "A", "cost_ps": 10.0, "shares": 100, "entry_date": "2026-01-01"},
        {"code": "B", "cost_ps": 20.0, "shares": 50, "entry_date": "2026-01-01"},
    ]
    closes = {"A": {"2026-08-24": 12.0}, "B": {"2026-08-24": 18.0}}
    pts = tv._curve_points(items, closes, ["2026-08-24"], 2000.0)
    # (200 + (-100)) / 2000 × 100 = 5.0
    assert pts[0]["date"] == "2026-08-24"
    assert pts[0]["total_pnl_pct"] == 5.0
    # 建仓日晚于该日 → 不计入，不伪造 0
    items2 = [{"code": "A", "cost_ps": 10.0, "shares": 100, "entry_date": "2026-09-01"}]
    pts2 = tv._curve_points(items2, closes, ["2026-08-24"], 1000.0)
    assert pts2[0]["total_pnl_pct"] == 0.0


# ② 组合贡献度排序正确（最负在前）+ 最大拖累者识别（build_portfolio_attribution 全链路）
def test_portfolio_contributors_and_drag(monkeypatch):
    from app.services import holding_view
    fake_rows = [
        {"stock_code": "A", "stock_name": "AA", "entry_price": 10.0, "cost": 1000.0,
         "shares": 100, "entry_date": "2026-08-01", "pnl_amount": 500.0},
        {"stock_code": "B", "stock_name": "BB", "entry_price": 20.0, "cost": 1000.0,
         "shares": 50, "entry_date": "2026-08-01", "pnl_amount": -300.0},
    ]
    monkeypatch.setattr(holding_view, "build_holding_view",
                        lambda: {"rows": fake_rows, "quote_time": ""})
    monkeypatch.setattr(tv, "_daily_closes", lambda codes, days: {
        "A": {"2026-08-21": 11.0, "2026-08-24": 12.0},
        "B": {"2026-08-21": 19.0, "2026-08-24": 18.0},
    })
    attr = tv.build_portfolio_attribution(30)
    assert attr["total_cost"] == 2000.0
    contrib = {c["stock_code"]: c for c in attr["contributors"]}
    assert contrib["A"]["contribution_pct"] == 25.0    # 500/2000×100
    assert contrib["B"]["contribution_pct"] == -15.0   # -300/2000×100
    assert attr["contributors"][0]["stock_code"] == "B"  # 最负在前
    assert attr["drag_analysis"] == "最大拖累者 B (-15.0%)"
    # 组合曲线全链路：2026-08-21 A(100)+B(-50)=50 → 2.5%；2026-08-24 A(200)+B(-100)=100 → 5.0%
    curve = {p["date"]: p["total_pnl_pct"] for p in attr["portfolio_curve"]}
    assert curve["2026-08-21"] == 2.5
    assert curve["2026-08-24"] == 5.0


def _mk_trade(side, amount, tdate):
    return type("T", (), {"side": side, "amount": amount, "trade_date": tdate})()


# ③ 周期复利多次操作汇总正确（总盈亏 / 平均持仓天数 / 胜率拖累率 / 最佳最差周期）
def test_cycle_attribution_multi_trade(monkeypatch):
    holdings = [
        {"id": 1, "stock_code": "RLH0001", "entry_date": "2026-07-01"},
        {"id": 2, "stock_code": "RLH0001", "entry_date": "2026-08-01"},
    ]
    trades1 = [_mk_trade("buy", 1000, "2026-07-01"), _mk_trade("sell", 1500, "2026-07-15")]
    trades2 = [_mk_trade("buy", 2000, "2026-08-01"), _mk_trade("sell", 1600, "2026-08-10")]
    monkeypatch.setattr(tv.repo, "list_holdings", lambda: holdings)
    monkeypatch.setattr(tv.repo, "get_trades", lambda hid: trades1 if hid == 1 else trades2)
    cyc = tv.build_stock_cycle_attribution("RLH0001")
    assert cyc["has_history"] is True
    assert cyc["cycle_count"] == 2 and cyc["closed_cycle_count"] == 2
    assert cyc["total_pnl"] == (1500 - 1000) + (1600 - 2000)   # 500 - 400 = 100
    assert cyc["win_rate"] == 50.0    # 1/2 盈利
    assert cyc["drag_rate"] == 50.0   # 1/2 亏损
    assert cyc["best_cycle"]["pnl"] == 500.0
    assert cyc["worst_cycle"]["pnl"] == -400.0
    assert cyc["avg_hold_days"] == 11.5   # (14 + 9) / 2


# ④ 无历史 → has_history=False，胜率/拖累率 None 不伪造
def test_cycle_attribution_no_history():
    cyc = tv.build_stock_cycle_attribution("RLH9001")
    assert cyc["has_history"] is False
    assert cyc["cycle_count"] == 0
    assert cyc["win_rate"] is None and cyc["drag_rate"] is None
    assert cyc["total_pnl"] is None


# ⑤ Score collect 注入字段可读 + 缺历史不触发加分（源码级 + 行为级）
def test_score_inject_cycle_attribution():
    import app.agents.score as score_mod
    src_collect = inspect.getsource(score_mod.collect_data)
    assert "build_stock_cycle_attribution" in src_collect and "cycle_attribution" in src_collect
    src_score = inspect.getsource(score_mod.llm_score)
    assert "历史胜率" in src_score and "+ 5" in src_score and "- 10" in src_score
    # 缺历史（win_rate/drag_rate None）→ 加分/扣分条件不触发（不伪造 0）
    cyc = tv.build_stock_cycle_attribution("RLH9002")
    assert cyc.get("win_rate") is None or cyc["win_rate"] < 60.0
    assert cyc.get("drag_rate") is None or cyc["drag_rate"] < 30.0
