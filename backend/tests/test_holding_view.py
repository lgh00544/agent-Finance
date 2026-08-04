"""持仓列表只读视图测试（不触网：repo 与行情源全部 mock）：
1. 实时行情计算：市值 / 盈亏金额 / 盈亏比例（数学正确性）
2. 参考止损/止盈补全链：人工设置 → 关联建仓计划 → 默认风控比例（仅展示，不落库）
3. 目标仓位% 按当前市值 / 基准本金计算
4. 行情失败：quote_error 非空、字段为 None（前端警示，不伪造 0 值）
5. 无持仓 / 无报价标的边界
"""
import pandas as pd
import pytest

from app.services import holding_view


def _holding(rid, code, name, entry_date, price, shares, stop=0.0, tp=0.0,
             plan_id=None, created="2026-08-01 10:00:00"):
    return {"id": rid, "stock_code": code, "stock_name": name, "entry_date": entry_date,
            "entry_price": price, "shares": shares, "cost": price * shares,
            "stop_loss": stop, "take_profit": tp, "target_pct": 0.0,
            "status": "holding", "plan_id": plan_id, "note": "",
            "created_at": created}


def _spot(*items):
    return pd.DataFrame([{"code": c, "name": n, "price": p} for c, n, p in items])


def _mock_sources(monkeypatch, holdings, plans=None, spot=None, exc=None):
    monkeypatch.setattr(holding_view.repo, "list_holdings", lambda status=None: holdings)

    def _plans(code=None, limit=50):
        rows = [dict(p) for p in (plans or [])]
        if code:
            rows = [p for p in rows if p["stock_code"] == code]
        return rows

    monkeypatch.setattr(holding_view.repo, "list_plans", _plans)

    class _Source:
        def fetch_spot_universe(self):
            if exc is not None:
                raise exc
            return spot if spot is not None else pd.DataFrame()

    monkeypatch.setattr(holding_view, "get_datasource", lambda: _Source())


def test_quotes_compute_market_value_and_pnl(monkeypatch):
    """实时价 → 市值/盈亏金额/盈亏比例 数学正确"""
    _mock_sources(monkeypatch,
                  holdings=[_holding(1, "600519", "贵州茅台", "2026-07-20", 1520.0, 100),
                            _holding(2, "300750", "宁德时代", "2026-07-25", 198.45, 2000)],
                  spot=_spot(("600519", "贵州茅台", 1550.3), ("300750", "宁德时代", 210.62)))
    view = holding_view.build_holding_view()
    assert view["quote_error"] is None
    assert view["total_capital"] == 100000.0
    by_code = {r["stock_code"]: r for r in view["rows"]}

    m = by_code["600519"]
    assert m["current_price"] == 1550.3
    assert m["market_value"] == 155030.0
    assert m["pnl_amount"] == 3030.0
    assert abs(m["pnl_pct"] - 1.99) < 1e-9

    n = by_code["300750"]
    assert n["market_value"] == 421240.0
    assert n["pnl_amount"] == 24340.0
    assert abs(n["pnl_pct"] - 6.13) < 1e-9


def test_reference_price_manual_first(monkeypatch):
    """人工设置的止损/止盈优先保留，标注来源"""
    _mock_sources(monkeypatch,
                  holdings=[_holding(1, "600519", "贵州茅台", "2026-07-20", 100.0, 100,
                                     stop=92.5, tp=118.0)],
                  spot=_spot(("600519", "贵州茅台", 105.0)))
    r = holding_view.build_holding_view()["rows"][0]
    assert r["stop_loss"] == 92.5 and r["stop_loss_source"] == "手动设置"
    assert r["take_profit"] == 118.0 and r["take_profit_source"] == "手动设置"


def test_reference_price_from_plan(monkeypatch):
    """未手填 → 精确关联 plan_id 的建仓计划止损/止盈"""
    _mock_sources(monkeypatch,
                  holdings=[_holding(1, "600519", "贵州茅台", "2026-07-20", 100.0, 100,
                                     plan_id=9)],
                  plans=[{"id": 9, "stock_code": "600519", "stock_name": "贵州茅台",
                          "plan_date": "2026-07-18", "status": "accepted", "total_pct": 20.0,
                          "batches": [], "stop_loss": 95.0, "take_profit": 120.0,
                          "rationale": "", "created_at": "2026-07-18 16:00:00"}],
                  spot=_spot(("600519", "贵州茅台", 105.0)))
    r = holding_view.build_holding_view()["rows"][0]
    assert r["stop_loss"] == 95.0 and r["stop_loss_source"] == "建仓计划"
    assert r["take_profit"] == 120.0 and r["take_profit_source"] == "建仓计划"


def test_reference_price_default_ratio(monkeypatch, ):
    """无计划 → 成本 × 默认风控比例（配置可调，仅展示参考）"""
    _mock_sources(monkeypatch,
                  holdings=[_holding(1, "600519", "贵州茅台", "2026-07-20", 100.0, 100)],
                  spot=_spot(("600519", "贵州茅台", 105.0)))
    r = holding_view.build_holding_view()["rows"][0]
    assert r["stop_loss"] == 92.0 and r["stop_loss_source"] == "默认风控 8%"
    assert r["take_profit"] == 115.0 and r["take_profit_source"] == "默认风控 15%"


def test_target_pct_from_market_value(monkeypatch):
    """目标仓位% = 当前市值 / 基准本金 × 100"""
    _mock_sources(monkeypatch,
                  holdings=[_holding(1, "600519", "贵州茅台", "2026-07-20", 100.0, 100)],
                  spot=_spot(("600519", "贵州茅台", 110.0)))
    r = holding_view.build_holding_view()["rows"][0]
    assert abs(r["target_pct"] - 11.0) < 1e-9


def test_quote_failure_keeps_none_fields(monkeypatch):
    """行情获取失败：quote_error 非空，行情字段为 None 而非 0"""
    _mock_sources(monkeypatch,
                  holdings=[_holding(1, "600519", "贵州茅台", "2026-07-20", 100.0, 100)],
                  exc=RuntimeError("数据源不可达"))
    view = holding_view.build_holding_view()
    assert view["quote_error"] and "行情获取失败" in view["quote_error"]
    r = view["rows"][0]
    assert r["current_price"] is None
    assert r["market_value"] is None
    assert r["pnl_amount"] is None
    assert r["pnl_pct"] is None


def test_empty_holdings_returns_empty(monkeypatch):
    """无持仓：直接返回空列表，不拉行情"""
    called = {"n": 0}

    def _no_rows(status=None):
        called["n"] += 1
        return []

    monkeypatch.setattr(holding_view.repo, "list_holdings", _no_rows)
    monkeypatch.setattr(holding_view.repo, "list_plans", lambda code=None, limit=50: [])
    view = holding_view.build_holding_view()
    assert view["rows"] == []
    assert called["n"] == 1


def test_no_quote_symbol_keeps_none(monkeypatch):
    """持仓代码在快照中无报价（停牌/新股）→ 行情字段 None，不伪造"""
    _mock_sources(monkeypatch,
                  holdings=[_holding(1, "600519", "贵州茅台", "2026-07-20", 100.0, 100)],
                  spot=_spot(("000001", "平安银行", 10.0)))
    r = holding_view.build_holding_view()["rows"][0]
    assert r["current_price"] is None
    assert r["target_pct"] is None
