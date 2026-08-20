"""游资数据链·步骤四：四 Agent 注入点（mock agent_call，断言 user_prompt 含游资段）"""
import pytest

from app.db import repo
from app.db.session import SessionLocal, init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()
    repo.seed_default_hot_money_profiles()
    # 造一份游资数据（独立日期 2026-08-09，避免与其他测试文件数据串扰）：
    # 601138 双源采信 + 席位命中赵老哥
    repo.insert_lhb_flows([
        {"trade_date": "2026-08-09", "stock_code": "601138", "stock_name": "工业富联",
         "lhb_type": "1d", "seat_name": "中信证券上海分公司",
         "buy_amt": 5e7, "sell_amt": 1e7, "net_buy": 4e7, "confidence": 0.8, "source": "eastmoney"},
        {"trade_date": "2026-08-09", "stock_code": "601138", "stock_name": "工业富联",
         "lhb_type": "1d", "seat_name": "", "buy_amt": 4.2e7, "sell_amt": 0,
         "net_buy": 4.2e7, "confidence": 0.8, "source": "sina"},
    ])


def _capture(monkeypatch, module, fake_output):
    """mock module.agent_call，捕获 user_prompt"""
    captured = {}

    def _fake(agent, cache_key, system_prompt, user_prompt, schema,
              ttl_seconds=86400, with_profile=True, with_knowledge=True, model_level=None):
        captured["prompt"] = user_prompt
        captured["cache_key"] = cache_key
        return fake_output

    monkeypatch.setattr(module, "agent_call", _fake)
    return captured


def test_score_injects_hot_money(monkeypatch):
    """Score：data_pack 含「游资聚合」段（口径后缀字段），cache_key 含指纹"""
    from app.agents import score as score_mod
    from app.agents.schemas import ScoreFactor, ScoreOutput

    out = ScoreOutput(stock_code="601138", stock_name="工业富联", score=70, grade="B",
                      factors=[ScoreFactor(factor=n, score=i, reason=f"测试{n}", signal="中性")
                               for i, n in enumerate(["动量", "催化", "估值", "主线契合",
                                                      "资金面", "基本面质量"], 1)],
                      potential_flag=False, cross_validation_note="",
                      risk_list=[], final_advice="综合评估：1/6 因子看多")
    cap = _capture(monkeypatch, score_mod, out)

    from app.services import hot_money as hm_svc
    hm_agg = hm_svc.aggregate_for_stock("601138", "工业富联", "2026-08-09")
    state = {"stock_code": "601138", "stock_name": "工业富联", "trade_date": "2026-08-09",
             "tech_index": {"recent_klines": [{"date": "2026-08-09", "close": 20.0}]},
             "finance_data": [], "fund_flow_rows": [], "news_report": [],
             "basic_info": {"industry_spot": []}, "hot_money": hm_agg, "trace": []}
    score_mod.llm_score(state)
    prompt = cap["prompt"]
    assert "游资聚合" in prompt
    assert "lhb_1d_net_buy" in prompt and "赵老哥" in prompt
    assert "h" in cap["cache_key"]  # 指纹并入


def test_score_no_data_placeholder(monkeypatch):
    """Score：无游资数据 → data_pack 游资聚合为 null，但键存在（LLM 标中性）"""
    from app.agents import score as score_mod
    from app.agents.schemas import ScoreFactor, ScoreOutput

    out = ScoreOutput(stock_code="600000", stock_name="无数据股", score=60, grade="C",
                      factors=[ScoreFactor(factor=n, score=i, reason=f"测试{n}", signal="中性")
                               for i, n in enumerate(["动量", "催化", "估值", "主线契合",
                                                      "资金面", "基本面质量"], 1)],
                      potential_flag=False, cross_validation_note="",
                      risk_list=[], final_advice="综合评估：0/6 因子看多")
    cap = _capture(monkeypatch, score_mod, out)
    state = {"stock_code": "600000", "stock_name": "无数据股", "trade_date": "2026-08-09",
             "tech_index": {"recent_klines": []}, "finance_data": [], "fund_flow_rows": [],
             "news_report": [], "basic_info": {"industry_spot": []}, "hot_money": None,
             "trace": []}
    score_mod.llm_score(state)
    assert '"游资聚合": null' in cap["prompt"] or "游资聚合" in cap["prompt"]


def test_discover_final_injects_hot_money(monkeypatch):
    """Discover：build_final_prompt 注入游资段 + cache_key 指纹"""
    from app.agents import discover as disc_mod
    from app.agents.schemas import DiscoverCandidate, DiscoverOutput

    cand = DiscoverCandidate(
        stock_code="601138", stock_name="工业富联", reason="量价健康", risk_notice="估值偏高",
        stock_type="吸筹末期-优选型", confidence_tier="建议关注", confidence_pct=72.0,
        macro_view="m", meso_view="e", micro_view="s", volume_analysis="v",
        risks=["风险A", "风险B"], focus_type="低吸")
    out = DiscoverOutput(market_summary="测试市况", candidates=[cand])
    cap = _capture(monkeypatch, disc_mod, out)

    state = {"shortlist": [{"stock_code": "601138", "stock_name": "工业富联"}],
             "enrichment": {}, "data_enrichment": {}, "market_cap": 10,
             "trade_date": "2026-08-09",
             "universe": [{"code": "601138", "name": "工业富联"}], "trace": []}
    disc_mod.llm_final(state)
    prompt = cap["prompt"]
    assert "候选游资聚合数据" in prompt
    assert "lhb_1d_net_buy" in prompt and "赵老哥" in prompt
    assert "h" in cap["cache_key"]


def test_monitor_injects_hot_money(monkeypatch):
    """Monitor：llm_signal 的 quote_data 含游资聚合键"""
    from app.agents import monitor as mon_mod
    from app.agents.schemas import MonitorOutput

    class _FakeHolding:
        entry_date = "2026-08-01"
        entry_price = 18.0
        shares = 1000
        stop_loss = 16.5
        take_profit = 24.0
        target_pct = 10.0

    monkeypatch.setattr(mon_mod.repo, "get_holding", lambda hid: _FakeHolding())

    out = MonitorOutput(action="hold", severity="info", alert_type="常规跟踪",
                        message="测试", reasons=["无异常"], key_levels={"支撑": 19.0})
    cap = _capture(monkeypatch, mon_mod, out)

    state = {"stock_code": "601138", "stock_name": "工业富联", "trade_date": "2026-08-09",
             "holding_id": 1, "real_time": {"price": 20.0}, "quote_stale": False,
             "tech_index": {"recent_klines": [{"date": "2026-08-09", "close": 20.0}]},
             "news_report": [], "hot_money": None, "trace": []}
    mon_mod.llm_signal(state)
    assert "游资聚合" in cap["prompt"]


def test_sell_injects_hot_money(monkeypatch):
    """Sell：quote_pack 含游资聚合键（口径后缀字段）"""
    from app.agents import sell as sell_mod
    from app.agents.schemas import SellOutput

    out = SellOutput(stock_code="601138", action="hold", confidence="medium",
                     reasons=["信息不足"], exit_price_zone="", risk_warning="", check_list=[])
    cap = _capture(monkeypatch, sell_mod, out)
    # llm_sell 内部还会真实落库 sell_decision——测试环境打桩，避免与其他测试数据串扰
    monkeypatch.setattr(sell_mod.repo, "insert_sell_decision", lambda *a, **k: 1)

    state = {"stock_code": "601138", "stock_name": "工业富联", "trade_date": "2026-08-09",
             "holding_id": 1, "tech_index": {"recent_klines": []},
             "sell_input": {"holding": {"entry_date": "2026-08-01", "entry_price": 18.0,
                                        "shares": 1000, "stop_loss": 16.5, "take_profit": 24.0,
                                        "target_pct": 10.0, "note": "", "latest_close": 20.0,
                                        "pnl_pct": 11.1},
                            "plan": {"rationale": "", "batches": [], "stop_loss": 0,
                                     "take_profit": 0},
                            "monitor_signals": [], "news_titles": [], "hot_money": None},
             "trace": []}
    sell_mod.llm_sell(state)
    assert "游资聚合" in cap["prompt"]


def test_trace_hot_money_lands(monkeypatch):
    """留痕：aggregate_for_stock 触发 trace_hot_money（source_module='hot_money'）"""
    from app.db.models import AiReasoningTrace
    from app.services import hot_money as hm_svc
    from app.services import reasoning_trace
    from sqlalchemy import select

    agg = hm_svc.aggregate_for_stock("601138", "工业富联", "2026-08-09")
    assert agg is not None
    reasoning_trace.flush()
    with SessionLocal() as db:
        rows = db.execute(select(AiReasoningTrace).where(
            AiReasoningTrace.source_module == "hot_money",
            AiReasoningTrace.stock_code == "601138")).scalars().all()
    assert rows, "hot_money 留痕未落库"
    t = rows[-1]
    assert "赵老哥" in t.capital_reasoning
    assert t.final_conclusion and "multi_source_verified" in t.final_conclusion
