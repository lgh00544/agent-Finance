"""评级重做-A：六因子透明评分体系测试
覆盖：ScoreFactor/ScoreOutput schema 解析、potential_flag 代码层推导覆写、
factors 六项强校验、交叉验证字段、cache_key v4 失效、collect_data 候选上下文注入、
旧数据向后兼容、reasoning_trace v4 格式留痕。
"""
import json

import pytest

from app.agents.schemas import ScoreFactor, ScoreOutput


def _six_factors(**overrides):
    """构造 6 因子列表；overrides 覆盖指定因子 score/signal"""
    names = ["动量", "催化", "估值", "主线契合", "资金面", "基本面质量"]
    return [overrides.get(n, ScoreFactor(factor=n, score=i, reason=f"测试{n}", signal="中性"))
            if isinstance(overrides.get(n), ScoreFactor) else
            ScoreFactor(factor=n, score=overrides.get(n, {}).get("score", i),
                        reason=f"测试{n}",
                        signal=overrides.get(n, {}).get("signal", "中性"))
            for i, n in enumerate(names, 1)]


# ---- Schema 解析 ----

def test_score_factor_valid():
    """ScoreFactor 正常解析"""
    f = ScoreFactor(factor="动量", score=7, reason="MA20多头排列", signal="看多")
    assert f.score == 7 and f.signal == "看多"


def test_score_factor_score_range():
    """score 超出 0-10 被 pydantic 拦截"""
    with pytest.raises(Exception):
        ScoreFactor(factor="动量", score=11, reason="x", signal="看多")
    with pytest.raises(Exception):
        ScoreFactor(factor="动量", score=-1, reason="x", signal="看多")


def test_score_factor_invalid_signal():
    """signal 不是 看多/中性/看空 被拦截"""
    with pytest.raises(Exception):
        ScoreFactor(factor="动量", score=5, reason="x", signal="强买")


def test_score_output_six_factors():
    """ScoreOutput 正常解析 6 因子"""
    out = ScoreOutput(stock_code="600519", stock_name="贵州茅台",
                      score=78, grade="B", factors=_six_factors(),
                      potential_flag=False, cross_validation_note="测试",
                      risk_list=[], final_advice="综合评估：6/6 因子看多")
    assert len(out.factors) == 6
    assert out.potential_flag is False
    assert out.cross_validation_note == "测试"


def test_score_output_defaults():
    """potential_flag 默认 False，cross_validation_note 默认空串"""
    out = ScoreOutput(stock_code="001", stock_name="t", score=50, grade="C",
                      factors=_six_factors(), risk_list=[])
    assert out.potential_flag is False
    assert out.cross_validation_note == ""


# ---- factors 六项强校验（P1-2 审核增强）----

def test_score_output_rejects_partial_factors():
    """少于 6 因子或因子名不合法 → pydantic 拦截（走 LLM 重试修正）"""
    # 少于 6 因子
    with pytest.raises(Exception):
        ScoreOutput(stock_code="600519", stock_name="贵州茅台", score=78, grade="B",
                    factors=[ScoreFactor(factor="动量", score=5, reason="x", signal="中性")],
                    risk_list=[])
    # 因子名不合法（自创因子）
    with pytest.raises(Exception):
        ScoreOutput(stock_code="600519", stock_name="贵州茅台", score=78, grade="B",
                    factors=[
                        ScoreFactor(factor=n, score=5, reason="x", signal="中性")
                        for n in ["动量", "催化", "估值", "主线契合", "资金面", "自创因子"]],
                    risk_list=[])


def test_score_output_rejects_duplicate_factors():
    """重复因子名（6 项但同名）→ 拦截"""
    with pytest.raises(Exception):
        ScoreOutput(stock_code="1", stock_name="t", score=50, grade="C",
                    factors=[ScoreFactor(factor="动量", score=5, reason="x", signal="中性")] * 6,
                    risk_list=[])


# ---- cache_key v4 失效 ----

def test_score_cache_key_v4(monkeypatch):
    """cache_key 包含 v4 前缀，确保旧缓存不命中"""
    from app.agents import score as score_mod

    captured = {}

    def _fake_agent_call(**kwargs):
        captured["cache_key"] = kwargs.get("cache_key", "")
        return ScoreOutput(stock_code="600000", stock_name="测试", score=60, grade="C",
                           factors=_six_factors(), risk_list=[])

    monkeypatch.setattr(score_mod, "agent_call", _fake_agent_call)
    monkeypatch.setattr(score_mod.repo, "hot_money_fingerprint", lambda: "fp123")
    monkeypatch.setattr(score_mod.repo, "get_latest_preference", lambda: None)
    monkeypatch.setattr(score_mod.repo, "get_candidate_context", lambda *a: None)
    monkeypatch.setattr(score_mod.repo, "get_latest_market_intel", lambda: None)
    monkeypatch.setattr(score_mod.repo, "upsert_score", lambda *a, **k: None)

    state = {"stock_code": "600000", "stock_name": "测试",
             "trade_date": "2026-08-18", "trace": [],
             "tech_index": {}, "finance_data": [], "fund_flow_rows": [],
             "news_report": [], "basic_info": {}, "hot_money": None}
    score_mod.llm_score(state)
    assert "v4" in captured["cache_key"], f"cache_key 缺 v4: {captured['cache_key']}"


# ---- collect_data 候选上下文注入 ----

def test_collect_data_injects_discover_context(monkeypatch):
    """collect_data 注入 discover_context 和 market_intel_summary"""
    import pandas as pd
    from app.agents import score as score_mod

    monkeypatch.setattr(score_mod.repo, "get_candidate_context",
                        lambda code, date: {"reasons": ["技术突破+量能放大"],
                                            "confidence_tier": "建议关注",
                                            "focus_type": "突破",
                                            "final_advice": "综合评估：3/5维支持"})
    monkeypatch.setattr(score_mod.repo, "get_latest_market_intel",
                        lambda: {"summary": "结构性分化，主线AI+消费"})

    class _FakeSource:
        def fetch_daily_kline(self, *a): return []
        def fetch_financial(self, *a): return type("DF", (), {"empty": True, "head": lambda s: s})()
        def fetch_fund_flow(self, *a): return None
        def fetch_news(self, *a): return pd.DataFrame()
        def fetch_industry_spot(self, *a): return type("DF", (), {"empty": True})()

    monkeypatch.setattr(score_mod, "get_datasource", lambda: _FakeSource())
    monkeypatch.setattr(score_mod, "compute_indicators", lambda k: {})
    monkeypatch.setattr(score_mod, "get_vector_store",
                        lambda: type("VS", (), {"index_news": lambda *a: None})())

    state = {"stock_code": "600000", "stock_name": "测试",
             "trade_date": "2026-08-18", "trace": []}
    result = score_mod.collect_data(state)
    assert "技术突破+量能放大" in result.get("discover_context", "")
    assert "结构性分化" in result.get("market_intel_summary", "")


# ---- 向后兼容 ----

def test_trace_score_old_format_compat():
    """v3 旧格式 detail（维度名字典）留痕不报错"""
    from app.services import reasoning_trace
    detail = {
        "技术趋势": {"score": 85, "verdict": "支持", "advice": "均线多头排列"},
        "基本面": {"score": 70, "verdict": "支持", "advice": "业绩稳定"},
        "final_advice": "综合评估：3/5 维支持",
    }
    # 不抛异常即通过
    reasoning_trace.trace_score("600110", "兼容测试", "2026-08-05",
                                78.0, "B", detail, ["无"])
    reasoning_trace.flush()


# ---- potential_flag 代码层推导（P1-1 审核增强）----

def test_potential_flag_derived_from_factors(monkeypatch):
    """代码层按催化>=7 且 动量<=4 覆写 potential_flag（不信任 LLM 自报）"""
    from app.agents import score as score_mod
    from app.agents.schemas import ScoreFactor, ScoreOutput

    def _state():
        return {"stock_code": "600000", "stock_name": "测试", "trade_date": "2026-08-18",
                "trace": [], "tech_index": {}, "finance_data": [], "fund_flow_rows": [],
                "news_report": [], "basic_info": {}, "hot_money": None}

    def _setup(monkeypatch, out):
        monkeypatch.setattr(score_mod, "agent_call", lambda **kw: out)
        monkeypatch.setattr(score_mod.repo, "get_latest_preference", lambda: None)
        monkeypatch.setattr(score_mod.repo, "get_candidate_context", lambda *a: None)
        monkeypatch.setattr(score_mod.repo, "get_latest_market_intel", lambda: None)
        monkeypatch.setattr(score_mod.repo, "hot_money_fingerprint", lambda: "fp")
        monkeypatch.setattr(score_mod.repo, "upsert_score", lambda *a, **k: None)

    # LLM 自报 True 但因子不满足（催化5<7）→ 强制 False
    out = ScoreOutput(stock_code="600000", stock_name="测试", score=60, grade="C",
                      factors=[
                          ScoreFactor(factor="催化", score=5, reason="x", signal="中性"),
                          ScoreFactor(factor="动量", score=3, reason="x", signal="看空"),
                          ScoreFactor(factor="估值", score=5, reason="x", signal="中性"),
                          ScoreFactor(factor="主线契合", score=5, reason="x", signal="中性"),
                          ScoreFactor(factor="资金面", score=5, reason="x", signal="中性"),
                          ScoreFactor(factor="基本面质量", score=5, reason="x", signal="中性"),
                      ],
                      potential_flag=True, risk_list=[])
    _setup(monkeypatch, out)
    score_mod.llm_score(_state())
    assert out.potential_flag is False          # 自报 True 被覆写为 False

    # 因子满足（催化8≥7 且 动量4≤4）→ 强制 True
    out2 = ScoreOutput(stock_code="600000", stock_name="测试", score=60, grade="C",
                       factors=[
                           ScoreFactor(factor="动量", score=4, reason="x", signal="中性"),
                           ScoreFactor(factor="催化", score=8, reason="x", signal="看多"),
                           ScoreFactor(factor="估值", score=5, reason="x", signal="中性"),
                           ScoreFactor(factor="主线契合", score=5, reason="x", signal="中性"),
                           ScoreFactor(factor="资金面", score=5, reason="x", signal="中性"),
                           ScoreFactor(factor="基本面质量", score=5, reason="x", signal="中性"),
                       ],
                       potential_flag=False, risk_list=[])
    monkeypatch.setattr(score_mod, "agent_call", lambda **kw: out2)
    score_mod.llm_score(_state())
    assert out2.potential_flag is True          # 因子满足 → 强制 True


def test_llm_score_detail_stores_factors(monkeypatch):
    """llm_score 落库 detail 为 factors 列表格式（含 potential_flag/cross_validation/final_advice）"""
    from app.agents import score as score_mod
    from app.agents.schemas import ScoreFactor, ScoreOutput

    captured = {}
    factors = [
        ScoreFactor(factor="催化", score=4, reason="x", signal="中性"),
        ScoreFactor(factor="动量", score=2, reason="x", signal="看空"),
        ScoreFactor(factor="估值", score=5, reason="x", signal="中性"),
        ScoreFactor(factor="主线契合", score=5, reason="x", signal="中性"),
        ScoreFactor(factor="资金面", score=5, reason="x", signal="中性"),
        ScoreFactor(factor="基本面质量", score=5, reason="x", signal="中性"),
    ]
    out = ScoreOutput(stock_code="600000", stock_name="测试", score=55, grade="C",
                      factors=factors, risk_list=["风险1"],
                      cross_validation_note="交叉验证结论", final_advice="综合评估：0/6 因子看多")

    def _upsert(code, name, today, score, grade, detail, risk_list, **k):
        captured["detail"] = detail

    monkeypatch.setattr(score_mod, "agent_call", lambda **kw: out)
    monkeypatch.setattr(score_mod.repo, "get_latest_preference", lambda: None)
    monkeypatch.setattr(score_mod.repo, "get_candidate_context", lambda *a: None)
    monkeypatch.setattr(score_mod.repo, "get_latest_market_intel", lambda: None)
    monkeypatch.setattr(score_mod.repo, "hot_money_fingerprint", lambda: "fp")
    monkeypatch.setattr(score_mod.repo, "upsert_score", _upsert)

    state = {"stock_code": "600000", "stock_name": "测试", "trade_date": "2026-08-18",
             "trace": [], "tech_index": {}, "finance_data": [], "fund_flow_rows": [],
             "news_report": [], "basic_info": {}, "hot_money": None}
    score_mod.llm_score(state)

    d = captured["detail"]
    assert "factors" in d and len(d["factors"]) == 6
    assert d["factors"][0]["factor"] == "催化"
    assert d["potential_flag"] is False          # 催化4<7 → 代码层覆写为 False
    assert d["cross_validation_note"] == "交叉验证结论"
    assert d["final_advice"] == "综合评估：0/6 因子看多"
