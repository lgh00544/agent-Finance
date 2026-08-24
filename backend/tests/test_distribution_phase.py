"""关系持仓批次 D·后半段：派发期自动判定链路测试（≤5 用例）

覆盖：①6 维时间计算正确 ②缺数据→null+missing_data ③缺3维→confidence低+phase_label带?
      ④路由返回完整6维+phase+confidence ⑤Sell/Score collect 段正确注入（monitor 前半段已改）
约定：不跑真实行情源（计算函数全部 monkeypatch）；各用例用独立 trade_date/symbol 隔离 86400s 缓存。
"""
import pandas as pd
import pytest

import app.services.distribution_phase as dph


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    """建全部测试表（llm_score 的 cache_key 需查 hot_money 指纹；仿 test_hot_money_inject）"""
    from app.db.session import init_db
    init_db()


# 各用例用独立 trade_date/symbol 隔离 86400s 缓存键，无需改动真实 cache 行为


def _kline_rows(n: int = 30, base: float = 10.0) -> list:
    """合成日K：单边缓涨（无反转形态），近5日动能弱于近20日 → 用于纯计算断言"""
    import datetime

    rows = []
    for i in range(n):
        d = datetime.date(2026, 7, 20) + datetime.timedelta(days=i)
        rows.append((d.strftime("%Y-%m-%d"), round(base * (1 + 0.01 * i), 2), 100000))
    return rows


# ---- ① 6 维时间计算正确 ----
def test_time_dimension_compute_correct():
    kl = _kline_rows(30)
    t = dph.time_dimension(kl)
    assert t["value"] is not None and 0 < t["value"] < 1  # 近5日动能比 < 近20日动能
    assert t["triggered"] in (True, False)

    s = dph.space_dimension(kl)
    assert s["value"] == 0.0  # 单边新高 → 距52周高 0%
    assert s["triggered"] is True  # 0 < 20 阈值

    vp = dph.volume_price_dimension(kl)
    assert vp["value"] is not None  # 20 日量价齐全 → 值非空

    p = dph.pattern_dimension(kl)
    assert p["value"] == 0  # 单边缓涨无反转形态

    # 数据不足 → null（不补零；compute 入口已有 if kl else 守卫，此处用不足窗口验证）
    assert dph.time_dimension(_kline_rows(5))["value"] is None
    assert dph.pattern_dimension([])["value"] is None
    assert dph.volume_price_dimension(_kline_rows(5))["value"] is None


# ---- ② 缺数据 → null + missing_data 标注 ----
def test_missing_data_nulls_and_annotated(monkeypatch):
    monkeypatch.setattr(dph, "_kline", lambda *a, **k: None)
    monkeypatch.setattr(dph, "capital_flow_dimension",
                        lambda *a, **k: {"value": None, "triggered": False})
    r = dph.compute_distribution_phase("600000", "2026-08-21")
    key6 = ["time", "space", "volume_price", "capital_flow", "pattern", "policy"]
    assert list(r["six_dim"].keys()) == key6
    for k in key6:
        assert r["six_dim"][k]["value"] is None
    assert sorted(r["missing_data"]) == sorted(key6)
    assert r["confidence"] == "低"


# ---- ③ 缺 3 维 → confidence 低 + phase_label 带 ? ----
def test_three_missing_low_confidence_question(monkeypatch):
    monkeypatch.setattr(dph, "_kline", lambda *a, **k: _kline_rows(30))  # 有效K线
    monkeypatch.setattr(dph, "volume_price_dimension",
                        lambda kl: {"value": None, "triggered": False})
    monkeypatch.setattr(dph, "capital_flow_dimension",
                        lambda *a, **k: {"value": None, "triggered": False})
    # time/space/pattern 由合成K线出值；缺 volume_price + capital_flow + policy 恰 3 维
    r = dph.compute_distribution_phase("601288", "2026-08-22")
    assert len(r["missing_data"]) == 3
    assert r["confidence"] == "低"
    assert r["phase_label"].endswith("?")


# ---- ④ 路由返回完整 6 维 + phase + confidence ----
def test_route_returns_full_six_dim(monkeypatch):
    from app.api import routes

    fake = {"phase": 2, "phase_label": "砸盘期?", "confidence": "低",
            "six_dim": {k: {"value": round(i, 2), "triggered": False}
                        for i, k in enumerate(
                            ["time", "space", "volume_price", "capital_flow",
                             "pattern", "policy"])},
            "missing_data": ["policy"], "trade_date": "2026-08-23"}
    monkeypatch.setattr(dph, "compute_distribution_phase", lambda *a, **k: fake)
    r = routes.distribution_phase("600036")  # 默认 force=False
    assert sorted(r["six_dim"].keys()) == sorted(
        ["time", "space", "volume_price", "capital_flow", "pattern", "policy"])
    assert r["phase"] == 2 and r["confidence"] == "低"
    assert len(r["six_dim"]) == 6


# ---- ⑤ Sell/Score collect 段正确注入（monitor 前半段已改，此处验证 sell/score）----
class _FakeHolding:
    stock_code = "601138"
    stock_name = "工业富联"
    entry_date = "2026-08-01"
    entry_price = 18.0
    shares = 1000
    stop_loss = 16.5
    take_profit = 24.0
    target_pct = 10.0
    note = ""


class _FakeSource:
    def fetch_daily_kline(self, *a, **k):
        return pd.DataFrame()

    def fetch_news(self, *a, **k):
        return pd.DataFrame()  # sell 内有 try 保护；score 直接迭代 → 统一返空表

    def fetch_fund_flow(self, *a, **k):
        return None

    def fetch_financial(self, *a, **k):
        return pd.DataFrame()

    def fetch_industry_spot(self, *a, **k):
        return pd.DataFrame()


def _capture_agent_call(monkeypatch, module, fake_output):
    cap = {}

    def _fake(agent, cache_key, system_prompt, user_prompt, schema,
              ttl_seconds=86400, with_profile=True, with_knowledge=True, model_level=None):
        cap["prompt"] = user_prompt
        return fake_output

    monkeypatch.setattr(module, "agent_call", _fake)
    return cap


def test_collect_injects_distribution_phase(monkeypatch):
    from app.agents import score as score_mod
    from app.agents import sell as sell_mod
    from app.agents.schemas import ScoreFactor, ScoreOutput

    fake = {"phase": 3, "phase_label": "砸盘期", "confidence": "中",
            "six_dim": {k: {"value": 1.0, "triggered": False} for k in
                        ("time", "space", "volume_price", "capital_flow", "pattern", "policy")},
            "missing_data": ["policy"], "trade_date": "2026-08-24"}
    monkeypatch.setattr(dph, "compute_distribution_phase", lambda *a, **k: fake)

    src = _FakeSource()
    monkeypatch.setattr(sell_mod, "get_datasource", lambda: src)
    monkeypatch.setattr(sell_mod, "compute_indicators", lambda k: {})
    monkeypatch.setattr(sell_mod.repo, "get_holding", lambda hid: _FakeHolding())
    monkeypatch.setattr(sell_mod.repo, "get_alerts_by_code", lambda *a, **k: [])
    monkeypatch.setattr(sell_mod.repo, "get_latest_plan", lambda *a, **k: None)

    st = sell_mod.collect_sell_input({"holding_id": 1, "trade_date": "2026-08-24", "trace": []})
    dp = st["sell_input"]["distribution_phase_context"]
    assert dp["phase"] == 3 and dp["phase_label"] == "砸盘期" and dp["confidence"] == "中"
    assert dp["missing_data"] == ["policy"] and len(dp["six_dim"]) == 6

    # ---- Score：collect_data 注入 distribution_phase_context ----
    monkeypatch.setattr(score_mod, "get_datasource", lambda: src)
    monkeypatch.setattr(score_mod, "compute_indicators", lambda k: {})
    monkeypatch.setattr(score_mod.repo, "get_candidate_context", lambda *a, **k: None)
    monkeypatch.setattr(score_mod.repo, "get_latest_market_intel", lambda: None)
    monkeypatch.setattr(score_mod.repo, "add_news", lambda *a, **k: 0)
    import app.services.track_verify as track_verify
    monkeypatch.setattr(track_verify, "get_factor_calibration", lambda: "")

    st2 = score_mod.collect_data({"stock_code": "600036", "stock_name": "招商银行",
                                  "trade_date": "2026-08-24", "trace": []})
    assert (st2["distribution_phase_context"] or {}).get("phase") == 3

    # ---- Score：llm_score data_pack 带上 + phase≥2 评分上限压至 90 + 风险提示 ----
    factors = [ScoreFactor(factor=n, score=i, reason=f"测试{n}", signal="中性")
               for i, n in enumerate(["动量", "催化", "估值", "主线契合", "资金面", "基本面质量"], 1)]
    out = ScoreOutput(stock_code="600036", stock_name="招商银行", score=95, grade="A",
                      factors=factors, potential_flag=False,
                      cross_validation_note="", risk_list=[], final_advice="综合评估：6/6 因子看多")
    cap = _capture_agent_call(monkeypatch, score_mod, out)
    monkeypatch.setattr(score_mod.repo, "upsert_score", lambda *a, **k: None)
    monkeypatch.setattr(score_mod.repo, "get_latest_preference", lambda: None)

    score_mod.llm_score(st2)
    assert "distribution_phase_context" in cap["prompt"] and "砸盘期" in cap["prompt"]
    assert st2["score_result"]["score"] == 90  # 95 → 上限 90（不单独占一维）
    assert any("派发期判定" in n for n in st2["risk_notice"])