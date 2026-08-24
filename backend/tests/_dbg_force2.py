import time
from types import SimpleNamespace

import pandas as pd

from app.db.session import init_db

init_db()
from app.api import routes
from app.services import capital_view as cv
from app import cache as cm


def _fake():
    return {"stock_code": "600519", "trade_date": "2026-08-20",
            "recent_actors": [{"name": "测试游资", "seat": "银河证券绍兴营业部", "tier": "一线",
                               "net_buy": 1e7, "days_active": 2}],
            "coordination": "多游资同买", "wash_suspect": False,
            "stats_30d": {"胜率": 0.6, "盈亏比": 1.5, "平均持仓天数": None},
            "theme_resonance": True, "source": "sse_only",
            "missing_data": ["stats_30d.平均持仓天数"],
            "dragon_tiger_rows": [], "capital_flow_rows": []}


def test_dbg_force_spy(capsys):
    """spy-delete（记录 + 真删）→ force 后应重算"""
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return _fake()

    cv._compute = lambda code, date: loader()
    deleted = []
    orig = cm.cache.delete
    cm.cache.delete = lambda k: (deleted.append(k), orig(k))
    routes.capital_view("600010")
    routes.capital_view("600010")
    routes.capital_view("600010", force=True)
    print("spy n=", calls["n"], "deleted:", deleted)
    assert calls["n"] == 2


def test_dbg_agents(capsys):
    """用例4 五段逐个断言定位"""
    from app.agents import discover, monitor, score, sell
    from app.agents.schemas import ScoreFactor, ScoreOutput
    from app.services import capital_view as cv_svc
    from app.services import distribution_phase as dp_svc
    from app.services import hot_money as hm_svc
    cv_svc.compute_capital_view = lambda code, date=None: _fake()
    dp_svc.compute_distribution_phase = lambda code, date=None: None
    hm_svc.aggregate_for_stock = lambda *a, **k: None
    monitor.read_portfolio_overview = lambda today: {}

    out = ScoreOutput(stock_code="600519", stock_name="贵州茅台", score=70, grade="B",
                      factors=[ScoreFactor(factor=f, score=i, reason="测试", signal="中性")
                               for i, f in enumerate(["动量", "催化", "估值", "主线契合", "资金面", "基本面质量"], 1)],
                      potential_flag=False, cross_validation_note="", risk_list=[], final_advice="测试")
    captured = {}
    score.agent_call = lambda agent, cache_key, system_prompt, user_prompt, schema, **kw: (
        captured.update(prompt=user_prompt), out)[1]
    state = {"stock_code": "600519", "stock_name": "贵州茅台", "trade_date": "2026-08-20",
             "tech_index": {"recent_klines": []}, "finance_data": [], "fund_flow_rows": [],
             "news_report": [], "basic_info": {"industry_spot": []}, "hot_money": None,
             "capital_view_context": _fake(), "trace": []}
    score.llm_score(state)
    print("score ok:", "capital_view_context" in captured["prompt"],
          "多游资同买" in captured["prompt"])

    from app.db import repo
    repo.get_holding = lambda hid: SimpleNamespace(
        entry_date="2026-08-01", entry_price=1400.0, shares=100, stop_loss=1300.0,
        take_profit=1700.0, target_pct=10.0, note="", stock_code="600519", stock_name="贵州茅台")
    cap2 = {}
    monitor.agent_call = lambda **kw: (cap2.update(prompt=kw["user_prompt"]), out)[1]
    mstate = {"holding_id": 1, "stock_code": "600519", "stock_name": "贵州茅台",
              "trade_date": "2026-08-20",
              "tech_index": {"recent_klines": [{"date": "2026-08-20", "close": 1500.0}]},
              "real_time": {"price": 1510.0}, "news_report": [], "trace": []}
    monitor.llm_signal(mstate)
    print("monitor ok:", "capital_view_context" in cap2["prompt"],
          "多游资同买" in cap2["prompt"])

    class _FakeSource:
        def fetch_daily_kline(self, code, start, end):
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        def fetch_news(self, code):
            return pd.DataFrame(columns=["title", "date"])
    repo.get_alerts_by_code = lambda code, limit=20: []
    repo.get_latest_plan = lambda code: None
    sell.get_datasource = lambda: _FakeSource()
    sell.compute_indicators = lambda kline: {"recent_klines": []}
    sstate = sell.collect_sell_input({"holding_id": 1, "trade_date": "2026-08-20"})
    scv = sstate["sell_input"]["capital_view_context"]
    print("sell ok:", scv is not None and scv.get("coordination") == "多游资同买", scv is not None)

    print("disc cols ok:", "capital_view_context" in discover._TABLE_COLS)
    line = cv_svc.build_capital_view_line(_fake())
    print("disc line:", line)
    print("disc line ok:", "对倒=否" in line and "30日胜率=60%" in line and "题材共振=是" in line)
