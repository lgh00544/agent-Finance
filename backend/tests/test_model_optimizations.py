"""模型体系优化（A-D 四项）验证：V1-V12
- A: 经验沉淀 Worker 提供方抽象（minimax 可配置 + 失败降级 deepseek）
- B: Monitor/PortfolioSentinel 纯规则兜底告警（LLM 异常分支）
- C: Score 两段式粗筛（默认关闭零回归 + 安全阀回退）
- D: llm_stats 成本换算（向后兼容）
"""
import json

import pandas as pd
import pytest
from sqlalchemy import func, select

from app.db import repo
from app.db.models import AlertLog, Holding
from app.db.session import SessionLocal, init_db
from app.core.config import settings

DATE = "2026-08-13"


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _clean_alert_and_holdings():
    with SessionLocal() as db:
        db.execute(AlertLog.__table__.delete())
        db.execute(Holding.__table__.delete())
        db.commit()


def _alert_rows(alert_type: str | None = None) -> list[AlertLog]:
    with SessionLocal() as db:
        q = select(AlertLog)
        if alert_type:
            q = q.where(AlertLog.alert_type == alert_type)
        return list(db.execute(q).scalars().all())


# =====================================================================
# A. 经验沉淀 Worker → MiniMax 提供方（V1-V4）
# =====================================================================

def _route_conflict_json(**over) -> str:
    return json.dumps({"conflict": over.get("conflict", False),
                       "conflicting_ids": over.get("conflicting_ids", []),
                       "reason": over.get("reason", "test")}, ensure_ascii=False)


def test_v1_provider_deepseek_gentle_light(monkeypatch):
    """V1 provider=deepseek：_llm_extract 走 LIGHT（llm_call_json），不触 MiniMax，零差异"""
    from app.services import experience_worker as ew
    from app.llm.structured import ModelLevel

    monkeypatch.setattr(settings, "experience_worker_provider", "deepseek")
    calls = {}

    def _fake_call(system, user, schema, **kw):
        calls["level"] = kw.get("model_level")
        return schema.model_validate_json(_route_conflict_json())

    monkeypatch.setattr(ew, "llm_call_json", _fake_call)
    # MiniMax 不应被触碰
    import app.services.multimodal as mm
    monkeypatch.setattr(mm, "MiniMaxClient", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("deepseek 路径不应实例化 MiniMaxClient")))

    res = ew._llm_extract("sys", "user", __import__("app.agents.schemas",
                                                    fromlist=["RouteConflict"]).RouteConflict)
    assert res.conflict is False
    assert calls["level"] == ModelLevel.LIGHT  # 走 LIGHT


def test_v2_provider_minimax_success(monkeypatch):
    """V2 provider=minimax：chat_text 返回合法 JSON → 解析成功 + llm_stats 记录 MiniMax-M3"""
    from app.services import experience_worker as ew
    from app.services import llm_stats as lsmod

    monkeypatch.setattr(settings, "experience_worker_provider", "minimax")
    monkeypatch.setattr(settings, "minimax_api_key", "fake-key")
    calls = {"record": None}

    class _FakeMM:
        def chat_text(self, system, user, max_tokens=2048):
            return _route_conflict_json(conflict=True, reason="minimax判定冲突"), {
                "prompt_tokens": 100, "completion_tokens": 50,
                "prompt_cache_hit_tokens": 20}

    import app.services.multimodal as mm
    monkeypatch.setattr(mm, "MiniMaxClient", lambda *a, **k: _FakeMM())
    monkeypatch.setattr(ew, "llm_call_json",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("minimax 成功路径不应降级 llm_call_json")))
    monkeypatch.setattr(lsmod, "record", lambda *a, **k: calls.update(record=(a, k)))

    from app.agents.schemas import RouteConflict
    res = ew._llm_extract("sys", "user", RouteConflict)
    assert res.conflict is True and res.reason == "minimax判定冲突"
    assert calls["record"] is not None
    model, hit, miss, comp = calls["record"][0][:4]
    assert model == "MiniMax-M3"
    assert hit == 20 and miss == 100 and comp == 50


def test_v3_provider_minimax_fail_degrade(monkeypatch):
    """V3 provider=minimax 且 chat_text 抛异常 → 降级调用 flash（llm_call_json），抽取照常完成"""
    from app.services import experience_worker as ew

    monkeypatch.setattr(settings, "experience_worker_provider", "minimax")
    monkeypatch.setattr(settings, "minimax_api_key", "fake-key")
    called = {"n": 0}

    class _FakeMM:
        def chat_text(self, system, user, max_tokens=2048):
            raise RuntimeError("MiniMax 网络失败")

    import app.services.multimodal as mm
    monkeypatch.setattr(mm, "MiniMaxClient", lambda *a, **k: _FakeMM())
    from app.agents.schemas import RouteConflict

    def _fake_call(system, user, schema, **kw):
        called["n"] += 1
        return schema.model_validate_json(_route_conflict_json())

    monkeypatch.setattr(ew, "llm_call_json", _fake_call)
    res = ew._llm_extract("sys", "user", RouteConflict)
    assert called["n"] == 1  # 降级调用一次 flash
    assert res.conflict is False


def test_v4_provider_minimax_no_key_degrade(monkeypatch):
    """V4 provider=minimax 但未配置密钥 → 直接降级 flash，无报错（MiniMaxClient 构造抛错被捕获）"""
    from app.services import experience_worker as ew

    monkeypatch.setattr(settings, "experience_worker_provider", "minimax")
    monkeypatch.setattr(settings, "minimax_api_key", "")  # 未配置
    called = {"n": 0}
    import app.services.multimodal as mm
    # 真构造会因无 key 抛 RuntimeError；也验证该路径
    monkeypatch.setattr(mm, "MiniMaxClient", lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("MiniMax 密钥未配置")))
    from app.agents.schemas import RouteConflict

    def _fake_call(system, user, schema, **kw):
        called["n"] += 1
        return schema.model_validate_json(_route_conflict_json())

    monkeypatch.setattr(ew, "llm_call_json", _fake_call)
    res = ew._llm_extract("sys", "user", RouteConflict)
    assert called["n"] == 1
    assert res is not None


# =====================================================================
# B. PortfolioSentinel 规则兜底（V5-V6）
# =====================================================================

class _FakeSource:
    def __init__(self, quotes, boards=None, sectors=None):
        self.quotes = quotes or {}
        self.boards = boards if boards is not None else pd.DataFrame()
        self.sectors = sectors or {}

    def fetch_spot_quotes_batch(self, codes):
        return self.quotes

    def fetch_industry_spot(self):
        return self.boards

    def fetch_stock_info(self, code):
        s = self.sectors.get(code)
        return {"行业": s} if s else {}


def _insert_holding(code, name, entry_price, shares, entry_date="2026-08-01") -> int:
    return repo.insert_holding(code, name, entry_date, entry_price, shares,
                               cost=round(entry_price * shares, 2),
                               stop_loss=round(entry_price * 0.92, 2),
                               take_profit=round(entry_price * 1.15, 2))


def test_v5_sentinel_rule_fallback_push_and_dedup(monkeypatch):
    """V5 LLM 异常 + 回撤触发 → 推送 rule_fallback 且落库；同日去重不重复推"""
    from app.agents import portfolio_sentinel as ps

    v5_date = "2099-01-02"  # 独立日期：避免与同模块其它 rule_fallback 测试共用 dedup key
    _insert_holding("600519", "贵州茅台", 10.0, 100)
    source = _FakeSource(
        quotes={"600519": {"code": "600519", "price": 9.0, "change_pct": -10.0}},
        sectors={"600519": "白酒"})
    monkeypatch.setattr(ps, "get_datasource", lambda: source)
    # LLM 不可用
    def _boom(**kw):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(ps, "agent_call", _boom)
    pushed = []
    monkeypatch.setattr(ps, "push_alert",
                        lambda *a, **k: pushed.append({"name": a[0], "type": a[2]}) or True)

    ps.portfolio_sentinel_node({"trade_date": v5_date})
    rows = _alert_rows("rule_fallback")
    assert len(rows) >= 1
    assert rows[0].source == "portfolio_sentinel"
    assert "规则兜底" in rows[0].message
    # 同日去重：再跑一次，push_alert 不重复推
    ps.portfolio_sentinel_node({"trade_date": v5_date})
    fallback_push = [p for p in pushed if p["type"] == "rule_fallback"]
    assert len(fallback_push) == 1  # 只推一次


def test_v6_sentinel_normal_path_zero_change(monkeypatch):
    """V6 LLM 正常：不触发 rule_fallback，告警为正常类型（零变化锚点）"""
    from app.agents import portfolio_sentinel as ps
    from app.agents.schemas import PortfolioSentinelOutput

    _insert_holding("600519", "贵州茅台", 10.0, 100)
    source = _FakeSource(
        quotes={"600519": {"code": "600519", "price": 11.0, "change_pct": 1.0}},
        boards=pd.DataFrame({"board_name": ["白酒"], "change_pct": [1.0],
                             "volume_ratio": [0.8]}),
        sectors={"600519": "白酒"})
    monkeypatch.setattr(ps, "get_datasource", lambda: source)
    out = PortfolioSentinelOutput(
        sector_alerts=[], time_stop_alerts=[], portfolio_risk={
            "total_pnl_pct": 0.0, "max_sector_pct": 10.0,
            "drawdown_alert": False, "concentration_alert": False},
        overall_assessment="正常", action_suggestions=[])
    monkeypatch.setattr(ps, "agent_call", lambda **kw: out)
    pushed = []
    monkeypatch.setattr(ps, "push_alert", lambda *a, **k: pushed.append(a[2]) or True)

    ps.portfolio_sentinel_node({"trade_date": DATE})
    assert _alert_rows("rule_fallback") == []  # 无 rule_fallback
    assert "rule_fallback" not in pushed


# =====================================================================
# B. Monitor 规则兜底（V7）
# =====================================================================

def test_v7_monitor_rule_fallback_push_when_big_loss(monkeypatch):
    """V7 LLM 异常 + 浮亏 ≤-5% → 推送 rule_fallback；无浮亏时不推送"""
    from app.agents import monitor as mn

    hid = _insert_holding("600519", "贵州茅台", 10.0, 100)
    # 现价 9.0 → 浮亏 -10% ≤ -5%
    state = {"holding_id": hid, "stock_code": "600519", "stock_name": "贵州茅台",
             "trade_date": DATE, "tech_index": {}, "real_time": {"price": 9.0},
             "news_report": [], "hot_money": None}

    def _boom(**kw):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(mn, "agent_call", _boom)
    pushed = []
    monkeypatch.setattr(mn, "push_alert",
                        lambda *a, **k: pushed.append({"name": a[0], "type": a[2]}) or True)

    with pytest.raises(RuntimeError):
        mn.llm_signal(state)
    rows = _alert_rows("rule_fallback")
    assert len(rows) >= 1
    fb = [p for p in pushed if p["type"] == "rule_fallback"]
    assert len(fb) == 1


def test_v7b_monitor_no_fallback_when_no_big_loss(monkeypatch):
    """V7 反例：浮亏 >-5%（现价 10.5=+5%）→ 不推送 rule_fallback"""
    from app.agents import monitor as mn

    hid2 = _insert_holding("000001", "平安银行", 10.0, 100)
    state = {"holding_id": hid2, "stock_code": "000001", "stock_name": "平安银行",
             "trade_date": DATE, "tech_index": {}, "real_time": {"price": 10.5},
             "news_report": [], "hot_money": None}

    def _boom(**kw):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(mn, "agent_call", _boom)
    pushed = []
    monkeypatch.setattr(mn, "push_alert", lambda *a, **k: pushed.append(a[2]) or True)

    with pytest.raises(RuntimeError):
        mn.llm_signal(state)
    assert _alert_rows("rule_fallback") == []
    assert "rule_fallback" not in pushed


# =====================================================================
# C. Score 两段式粗筛（V8-V10）
# =====================================================================

def _make_cands(n: int) -> list[dict]:
    return [{"stock_code": f"60{i:04d}", "stock_name": f"股{i}",
             "reason": "r", "confidence_tier": "建议关注", "focus_type": "突破"}
            for i in range(1, n + 1)]


def test_v8_two_stage_off_regression(monkeypatch):
    """V8 score_two_stage=False：DEEP 精打次数 = 候选数（原路径零回归）"""
    from app.graph import router

    n = 5
    monkeypatch.setattr(settings, "score_two_stage", False)
    monkeypatch.setattr(router, "run_discover",
                        lambda *a, **k: {"candidates": _make_cands(n)})
    scores_called = {"n": 0}
    def _fake_score(code, name="", trade_date=None):
        scores_called["n"] += 1
        return {"score_result": {"score": 70, "grade": "B"}, "candidates": [],
                "stock_code": code, "stock_name": name}
    monkeypatch.setattr(router, "run_score", _fake_score)
    monkeypatch.setattr(router, "run_position",
                        lambda *a, **k: {"position_plan": {"plan_id": 1}})
    # 避免联动建仓触发额外 LLM/依赖：B+ 全部走缓存层，但保险起见模拟 plan
    monkeypatch.setattr("app.services.candidate_tradeable.ensure_tradeable",
                        lambda *a, **k: 0)

    router.run_daily_pipeline(DATE)
    assert scores_called["n"] == n  # 关闭时精打全部


def test_v9_two_stage_on_empty_keep_fallback(monkeypatch):
    """V9 粗筛空名单（keep_codes 空）→ 回退全量精打（DEEP 次数=候选数）"""
    from app.agents import score as sc
    from app.agents.schemas import PrefilterOutput

    cands = _make_cands(3)
    monkeypatch.setattr(sc, "agent_call",
                        lambda **kw: PrefilterOutput(keep_codes=[], reason="全弃"))
    out = sc.prefilter_candidates(cands, DATE)
    assert len(out) == len(cands)  # 空名单回退全量


def test_v9b_two_stage_exception_fallback(monkeypatch):
    """V9 粗筛 LLM 异常 → 回退全量精打（安全阀 2）"""
    from app.agents import score as sc

    cands = _make_cands(3)
    def _boom(**kw):
        raise RuntimeError("prefilter down")
    monkeypatch.setattr(sc, "agent_call", _boom)
    out = sc.prefilter_candidates(cands, DATE)
    assert len(out) == len(cands)


def test_v10_two_stage_on_normal_list_and_cache_key(monkeypatch):
    """V10 粗筛正常名单：只精打子集；cache_key=prefilter:v2:*"""
    from app.agents import score as sc
    from app.agents.schemas import PrefilterOutput
    from app.graph import router

    cands = _make_cands(6)
    keep = {"600001", "600002"}
    captured = {}

    def _prefilter_call(**kw):
        captured["cache_key"] = kw.get("cache_key")
        captured["level"] = kw.get("model_level")
        captured["agent"] = kw.get("agent")
        return PrefilterOutput(keep_codes=sorted(keep), reason="挑 2 只")

    monkeypatch.setattr(sc, "agent_call", _prefilter_call)
    sub = sc.prefilter_candidates(cands, DATE)
    assert len(sub) == 2
    assert {c["stock_code"] for c in sub} == keep
    assert captured["cache_key"].startswith("prefilter:v2:")
    # 端到端：score_two_stage=True 且 prefilter 返回 2 只 → run_score 只调 2 次
    monkeypatch.setattr(settings, "score_two_stage", True)
    monkeypatch.setattr(settings, "score_two_stage_keep", 12)
    monkeypatch.setattr("app.agents.score.prefilter_candidates",
                        lambda c, d: sub)
    monkeypatch.setattr(router, "run_discover",
                        lambda *a, **k: {"candidates": cands})
    scores_called = {"n": 0}
    def _fake_score(code, name="", trade_date=None):
        scores_called["n"] += 1
        return {"score_result": {"score": 70, "grade": "B"}}
    monkeypatch.setattr(router, "run_score", _fake_score)
    monkeypatch.setattr(router, "run_position",
                        lambda *a, **k: {"position_plan": {"plan_id": 1}})
    monkeypatch.setattr("app.services.candidate_tradeable.ensure_tradeable",
                        lambda *a, **k: 0)
    router.run_daily_pipeline(DATE)
    assert scores_called["n"] == 2  # 只精打粗筛保留的 2 只


def test_v10b_two_stage_keep_cap(monkeypatch):
    """V10 粗筛后按 score_two_stage_keep 截断（keep=1 → 只精打 1 只）"""
    from app.graph import router

    cands = _make_cands(5)
    monkeypatch.setattr(settings, "score_two_stage", True)
    monkeypatch.setattr(settings, "score_two_stage_keep", 1)
    monkeypatch.setattr("app.agents.score.prefilter_candidates",
                        lambda c, d: c[:3])  # 粗筛返回 3 只，但 keep=1 截断
    monkeypatch.setattr(router, "run_discover",
                        lambda *a, **k: {"candidates": cands})
    scores_called = {"n": 0}
    def _fake_score(code, name="", trade_date=None):
        scores_called["n"] += 1
        return {"score_result": {"score": 70, "grade": "B"}}
    monkeypatch.setattr(router, "run_score", _fake_score)
    monkeypatch.setattr(router, "run_position",
                        lambda *a, **k: {"position_plan": {"plan_id": 1}})
    monkeypatch.setattr("app.services.candidate_tradeable.ensure_tradeable",
                        lambda *a, **k: 0)
    router.run_daily_pipeline(DATE)
    assert scores_called["n"] == 1  # keep=1 截断


# =====================================================================
# D. llm_stats 成本换算（V11-V12）
# =====================================================================

def _snapshot_llm_stats():
    from app.services import llm_stats
    return llm_stats.snapshot()


def test_v11_cost_calculation(monkeypatch):
    """V11 已知 token + 单价 → cost_yuan 与手算一致（±0.01）"""
    from app.services import llm_stats

    monkeypatch.setattr(settings, "deepseek_cached_input_price", 1.0)   # 元/百万
    monkeypatch.setattr(settings, "deepseek_input_price", 4.0)
    monkeypatch.setattr(settings, "deepseek_output_price", 16.0)
    before = _snapshot_llm_stats().get("cost_yuan", 0.0)
    # 命中 100k / 未命中 50k / 输出 20k（百万单位）
    llm_stats.record("deepseek-chat", 100_000, 50_000, 20_000)
    expected = (100_000 * 1.0 + 50_000 * 4.0 + 20_000 * 16.0) / 1_000_000.0
    after = _snapshot_llm_stats().get("cost_yuan", 0.0)
    assert abs((after - before) - expected) <= 0.01


def test_v11b_cost_zero_when_no_price(monkeypatch):
    """单价未填（默认 0）→ cost 恒 0，不计成本（向后兼容）"""
    from app.services import llm_stats

    monkeypatch.setattr(settings, "deepseek_cached_input_price", 0.0)
    monkeypatch.setattr(settings, "deepseek_input_price", 0.0)
    monkeypatch.setattr(settings, "deepseek_output_price", 0.0)
    before = _snapshot_llm_stats().get("cost_yuan", 0.0)
    llm_stats.record("deepseek-v4-flash", 100_000, 50_000, 20_000)
    assert abs(_snapshot_llm_stats().get("cost_yuan", 0.0) - before) <= 0.01


def test_v11c_minimax_price_route(monkeypatch):
    """模型名含 minimax → 用 MiniMax 单价"""
    from app.services import llm_stats

    monkeypatch.setattr(settings, "minimax_input_price", 5.0)
    monkeypatch.setattr(settings, "minimax_output_price", 8.0)
    before = _snapshot_llm_stats().get("cost_yuan", 0.0)
    llm_stats.record("MiniMax-M3", 0, 100_000, 50_000)
    expected = (100_000 * 5.0 + 50_000 * 8.0) / 1_000_000.0
    after = _snapshot_llm_stats().get("cost_yuan", 0.0)
    assert abs((after - before) - expected) <= 0.01


def test_v12_snapshot_compat(monkeypatch):
    """V12 snapshot() 含 cost_yuan 且旧字段全部保留（前端不炸）"""
    snap = _snapshot_llm_stats()
    assert "cost_yuan" in snap
    for old in ["date", "requests", "hit_tokens", "miss_tokens",
                "completion_tokens", "hit_rate_pct", "models", "checked_at"]:
        assert old in snap, f"旧字段缺失: {old}"
