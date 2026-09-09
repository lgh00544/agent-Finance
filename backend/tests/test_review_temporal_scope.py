"""复盘历史事实包的时间边界测试。"""

from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from app.agents import review
from app.db import repo
from app.db.models import AlertLog, SellDecision, StockScore
from app.db.session import SessionLocal, init_db


def test_collect_review_uses_holding_lifecycle_window(monkeypatch):
    holding = SimpleNamespace(
        id=42, stock_code="990901", stock_name="时点测试", entry_date="2026-08-01",
        entry_price=10.0, shares=100, stop_loss=9.0, take_profit=12.0,
        note="", cost=1000.0, status="exited", plan_id=None,
    )
    trades = [
        SimpleNamespace(side="buy", price=10.0, shares=100, amount=1000.0,
                        trade_date="2026-08-01"),
        SimpleNamespace(side="sell", price=11.0, shares=100, amount=1100.0,
                        trade_date="2026-08-05"),
        # 异常晚于退出日的补录，不应进入复盘事实包。
        SimpleNamespace(side="buy", price=8.0, shares=10, amount=80.0,
                        trade_date="2026-08-08"),
    ]
    score = SimpleNamespace(score=81.0, grade="A", risk_list=["历史风险"])
    captured = {}

    monkeypatch.setattr(review.repo, "get_holding", lambda hid: holding)
    monkeypatch.setattr(review.repo, "get_trades", lambda hid: trades)
    monkeypatch.setattr(review.repo, "get_plan", lambda plan_id: None)
    monkeypatch.setattr(review.repo, "get_plan_for_entry", lambda code, day: (None, "missing"))

    def fake_score(code, as_of=None):
        captured["score_as_of"] = as_of
        return score

    monkeypatch.setattr(review.repo, "get_latest_score", fake_score)

    def fake_alerts(code, limit=50, start_date=None, end_date=None):
        captured["alert_window"] = (start_date, end_date)
        return [
            SimpleNamespace(created_at=datetime(2026, 8, 4, 15), alert_type="in",
                            severity="info", action="hold", message="窗口内"),
            SimpleNamespace(created_at=datetime(2026, 8, 6, 15), alert_type="out",
                            severity="critical", action="exit", message="退出后"),
        ]

    monkeypatch.setattr(review.repo, "get_alerts_by_code", fake_alerts)

    def fake_sells(code, limit=20, holding_id=None, start_date=None, end_date=None):
        captured["sell_window"] = (holding_id, start_date, end_date)
        return [
            SimpleNamespace(holding_id=42, created_at=datetime(2026, 8, 5, 15),
                            decision={"action": "exit", "confidence": 0.8, "reasons": ["窗口内"]}),
            SimpleNamespace(holding_id=42, created_at=datetime(2026, 8, 7, 15),
                            decision={"action": "exit", "confidence": 0.9, "reasons": ["退出后"]}),
        ]

    monkeypatch.setattr(review.repo, "get_sell_decisions_by_code", fake_sells)
    monkeypatch.setattr(review.repo, "list_traces", lambda **kwargs: [])
    monkeypatch.setattr(review, "_portfolio_attribution", lambda *args: {})
    monkeypatch.setattr(review, "_cycle_attribution", lambda code: None)
    monkeypatch.setattr(review, "_portfolio_curve_summary", lambda: {})

    class _Source:
        def fetch_daily_kline(self, code, start, end):
            captured["kline_window"] = (start, end)
            return pd.DataFrame([
                {"date": "2026-08-01", "high": 10.5, "low": 9.5,
                 "close": 10.0, "change_pct": 0.0},
                {"date": "2026-08-05", "high": 11.5, "low": 10.5,
                 "close": 11.0, "change_pct": 2.0},
                {"date": "2026-08-06", "high": 99.0, "low": 1.0,
                 "close": 50.0, "change_pct": 300.0},
            ])

    monkeypatch.setattr(review, "get_datasource", lambda: _Source())
    state = review.collect_review({"holding_id": 42, "trade_date": "2026-08-07", "trace": []})
    data = state["exit_suggest"]

    assert captured["score_as_of"] == "2026-08-01"
    assert captured["alert_window"] == ("2026-08-01", "2026-08-05")
    assert captured["sell_window"] == (42, "2026-08-01", "2026-08-05")
    assert captured["kline_window"] == ("2026-08-01", "2026-08-05")
    assert data["holding"]["exit_date"] == "2026-08-05"
    assert len(data["trades"]) == 2
    assert len(data["monitor_signals"]) == 1
    assert len(data["sell_decisions"]) == 1
    assert data["price_stats"]["period_high"] == 11.5
    assert data["price_stats"]["exit_day_close"] == 11.0


def test_repo_temporal_queries_filter_history_and_score_version():
    init_db()
    code = "990902"
    with SessionLocal() as db:
        db.add_all([
            StockScore(stock_code=code, stock_name="时点测试", trade_date="2026-08-01",
                       score=70, grade="B", detail={}, risk_list=[]),
            StockScore(stock_code=code, stock_name="时点测试", trade_date="2026-08-05",
                       score=90, grade="A", detail={}, risk_list=[]),
            AlertLog(stock_code=code, stock_name="时点测试", alert_type="in",
                     severity="info", message="in", action="hold", signal={},
                     created_at=datetime(2026, 8, 3, 12)),
            AlertLog(stock_code=code, stock_name="时点测试", alert_type="out",
                     severity="critical", message="out", action="exit", signal={},
                     created_at=datetime(2026, 8, 6, 12)),
            SellDecision(holding_id=903, stock_code=code, stock_name="时点测试",
                         decision={"action": "exit"}, created_at=datetime(2026, 8, 4, 12)),
            SellDecision(holding_id=904, stock_code=code, stock_name="时点测试",
                         decision={"action": "exit"}, created_at=datetime(2026, 8, 6, 12)),
        ])
        db.commit()

    score = repo.get_latest_score(code, as_of="2026-08-04")
    alerts = repo.get_alerts_by_code(code, start_date="2026-08-01", end_date="2026-08-05")
    sells = repo.get_sell_decisions_by_code(
        code, holding_id=903, start_date="2026-08-01", end_date="2026-08-05")

    assert score is not None and score.trade_date == "2026-08-01"
    assert len(alerts) == 1 and alerts[0].alert_type == "in"
    assert len(sells) == 1 and sells[0].holding_id == 903
