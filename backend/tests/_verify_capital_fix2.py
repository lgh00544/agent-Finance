"""批次E 资本视图测试 · 最终版（验证用；验证后内容覆盖 backend/tests/test_capital_view.py）
修正点：①Score 注入在 collect_data，llm_score 只读 state → state 带 capital_view_context
②routes.py 的 cache 为函数内 import → patch app.cache.cache.delete
③monitor.agent_call 全关键字调用 → mock 用 **kw
④用例5 不 patch compute_capital_view（会绕过缓存层），改为 patch _compute 计数 + 真实 SimpleCache
"""
from types import SimpleNamespace

import pandas as pd
import pytest

from app.db import repo
from app.db.session import init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _fake_capital_view() -> dict:
    return {
        "stock_code": "600519", "trade_date": "2026-08-20",
        "recent_actors": [{"name": "测试游资", "seat": "银河证券绍兴营业部", "tier": "一线",
                           "net_buy": 1e7, "days_active": 2}],
        "coordination": "多游资同买", "wash_suspect": False,
        "stats_30d": {"胜率": 0.6, "盈亏比": 1.5, "平均持仓天数": None},
        "theme_resonance": True, "source": "sse_only",
        "missing_data": ["stats_30d.平均持仓天数"],
        "dragon_tiger_rows": [], "capital_flow_rows": [],
    }


# ---- 用例1：K189 对倒（纯代码，不交 LLM） ----

def test_wash_suspect_k189_true_and_amount_gate():
    from app.services import capital_view
    flows_big = [
        {"trade_date": "2026-08-19", "seat_name": "测试营业部", "buy_amt": 1500e4, "sell_amt": 0, "net_buy": 1500e4},
        {"trade_date": "2026-08-20", "seat_name": "测试营业部", "buy_amt": 0, "sell_amt": 1200e4, "net_buy": -1200e4},
    ]
    assert capital_view._wash_suspect_k189(flows_big) is True
    flows_small = [
        {"trade_date": "2026-08-19", "seat_name": "测试营业部", "buy_amt": 500e4, "sell_amt": 0, "net_buy": 500e4},
        {"trade_date": "2026-08-20", "seat_name": "测试营业部", "buy_amt": 0, "sell_amt": 400e4, "net_buy": -400e4},
    ]
    assert capital_view._wash_suspect_k189(flows_small) is False


# ---- 用例2：30 日无数据 → "数据不足"，绝不写"无动作"（K227 诚实） ----

def test_no_data_writes_insufficient(monkeypatch):
    from app.services import capital_view
    monkeypatch.setattr(capital_view, "_flows_for_stock", lambda code: [])
    monkeypatch.setattr(capital_view, "_kline", lambda code: [])
    monkeypatch.setattr(capital_view, "_fund_flow_rows", lambda code: [])
    monkeypatch.setattr(capital_view, "_stock_industry", lambda code: "")
    monkeypatch.setattr(repo, "list_hot_money_profiles", lambda: [])
    cv = capital_view.compute_capital_view("600000", "2026-08-20")
    assert cv["coordination"] == "数据不足"
    assert cv["recent_actors"] == []
    assert cv["wash_suspect"] is False
    line = capital_view.build_capital_view_line(cv)
    assert "数据不足" in line and "无动作" not in line
    stats = repo.get_capital_stats("600000", "2026-08-20")
    assert stats is not None and stats["coordination"] == "数据不足"
    assert "stats_30d" in stats["missing_data"]


# ---- 用例3：recent_actors 字段齐全 + 未知营业部不硬绑 ----

def test_recent_actors_fields_complete(monkeypatch):
    from app.services import capital_view
    monkeypatch.setattr(repo, "list_hot_money_profiles", lambda: [
        {"seat_code": "银河证券绍兴营业部", "actor_name": "测试游资", "tier": "一线", "good_themes": ["半导体"]},
    ])
    flows = [
        {"trade_date": "2026-08-19", "seat_name": "银河证券绍兴营业部", "buy_amt": 5e7, "sell_amt": 0, "net_buy": 5e7},
        {"trade_date": "2026-08-20", "seat_name": "银河证券绍兴营业部", "buy_amt": 3e7, "sell_amt": 0, "net_buy": 3e7},
        {"trade_date": "2026-08-21", "seat_name": "未知营业部X", "buy_amt": 1e8, "sell_amt": 0, "net_buy": 1e8},
    ]
    actors = capital_view._recent_actors(flows, "2026-08-21")
    assert len(actors) == 1
    for k in ("name", "tier", "net_buy", "days_active"):
        assert k in actors[0]
    assert actors[0]["name"] == "测试游资" and actors[0]["tier"] == "一线"
    assert actors[0]["days_active"] == 2 and actors[0]["net_buy"] == 8e7


# ---- 用例4：4 Agent collect 段注入 capital_view_context ----

def test_agents_collect_inject_capital_view(monkeypatch):
    from app.agents import discover, monitor, score, sell
    from app.agents.schemas import ScoreFactor, ScoreOutput
    from app.services import capital_view as cv_svc
    from app.services import distribution_phase as dp_svc
    from app.services import hot_money as hm_svc
    monkeypatch.setattr(cv_svc, "compute_capital_view", lambda code, date=None: _fake_capital_view())
    monkeypatch.setattr(dp_svc, "compute_distribution_phase", lambda code, date=None: None)
    monkeypatch.setattr(hm_svc, "aggregate_for_stock", lambda *a, **k: None)
    monkeypatch.setattr(monitor, "read_portfolio_overview", lambda today: {})

    # Score：llm_score 的 data_pack 注入（注入点在 collect_data，llm_score 只读 state）
    out = ScoreOutput(stock_code="600519", stock_name="贵州茅台", score=70, grade="B",
                      factors=[ScoreFactor(factor=f, score=i, reason="测试", signal="中性")
                               for i, f in enumerate(["动量", "催化", "估值", "主线契合", "资金面", "基本面质量"], 1)],
                      potential_flag=False, cross_validation_note="", risk_list=[], final_advice="测试")
    captured = {}

    def _fake_call(agent, cache_key, system_prompt, user_prompt, schema, **kw):
        captured["prompt"] = user_prompt
        return out
    monkeypatch.setattr(score, "agent_call", _fake_call)
    state = {"stock_code": "600519", "stock_name": "贵州茅台", "trade_date": "2026-08-20",
             "tech_index": {"recent_klines": []}, "finance_data": [], "fund_flow_rows": [],
             "news_report": [], "basic_info": {"industry_spot": []}, "hot_money": None,
             "capital_view_context": _fake_capital_view(),
             "trace": []}
    score.llm_score(state)
    assert "capital_view_context" in captured["prompt"] and "多游资同买" in captured["prompt"]

    # Monitor：llm_signal 的 quote_data 注入（agent_call 全关键字调用）
    monkeypatch.setattr(repo, "get_holding", lambda hid: SimpleNamespace(
        entry_date="2026-08-01", entry_price=1400.0, shares=100, stop_loss=1300.0,
        take_profit=1700.0, target_pct=10.0, note="", stock_code="600519", stock_name="贵州茅台"))
    cap2 = {}
    monkeypatch.setattr(monitor, "agent_call",
                        lambda **kw: (cap2.update(prompt=kw["user_prompt"]), out)[1])
    mstate = {"holding_id": 1, "stock_code": "600519", "stock_name": "贵州茅台",
              "trade_date": "2026-08-20",
              "tech_index": {"recent_klines": [{"date": "2026-08-20", "close": 1500.0}]},
              "real_time": {"price": 1510.0}, "news_report": [], "trace": []}
    monitor.llm_signal(mstate)
    assert "capital_view_context" in cap2["prompt"] and "多游资同买" in cap2["prompt"]

    # Sell：collect_sell_input 的 sell_input.capital_view_context 注入
    class _FakeSource:
        def fetch_daily_kline(self, code, start, end):
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        def fetch_news(self, code):
            return pd.DataFrame(columns=["title", "date"])
    monkeypatch.setattr(repo, "get_alerts_by_code", lambda code, limit=20: [])
    monkeypatch.setattr(repo, "get_latest_plan", lambda code: None)
    monkeypatch.setattr(sell, "get_datasource", lambda: _FakeSource())
    monkeypatch.setattr(sell, "compute_indicators", lambda kline: {"recent_klines": []})
    sstate = sell.collect_sell_input({"holding_id": 1, "trade_date": "2026-08-20"})
    assert sstate["sell_input"]["capital_view_context"]["coordination"] == "多游资同买"

    # Discover：候选富化列声明 + 注入行文渲染
    assert "capital_view_context" in discover._TABLE_COLS
    line = cv_svc.build_capital_view_line(_fake_capital_view())
    assert "对倒=否" in line and "30日胜率=60%" in line and "题材共振=是" in line


# ---- 用例5：force=true 击穿 86400s 缓存（真实 SimpleCache + routes 删键） ----

def test_force_cache_bypass(monkeypatch):
    from app.api import routes
    from app.services import capital_view as cv_svc
    loader_calls = {"n": 0}

    def _loader():
        loader_calls["n"] += 1
        return _fake_capital_view()
    # 真实缓存层：patch _compute（loader 计数），不 patch compute_capital_view
    monkeypatch.setattr(cv_svc, "_compute", lambda code, date: _loader())
    monkeypatch.setattr(repo, "list_hot_money_profiles", lambda: [])
    from app import cache as cache_mod
    deleted = []
    monkeypatch.setattr(cache_mod.cache, "delete", lambda key: deleted.append(key))
    code = "600010"  # 唯一 code 防用例间缓存串扰
    routes.capital_view(code)                 # 缓存 miss → _compute 1 次
    routes.capital_view(code)                 # 缓存命中 → 不重算
    routes.capital_view(code, force=True)     # routes 删键 → 重算
    assert loader_calls["n"] == 2
    assert any(str(k).startswith("capital_view:") for k in deleted)
