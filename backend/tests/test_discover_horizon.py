"""Discover 前瞻兑现子 Agent 单元测试

覆盖执行指令 §六 单测 ①②③ + §五 步骤 8：
1. DiscoverCandidate 三 horizon 字段缺省默认（回归/低/前瞻数据不足）
2. build_final_prompt 含/不含前瞻段（空串省略）
3. build_horizon_context 纯函数：10 条同桶 → 文本含胜率数字；3 条 → 样本不足（D1: 按 select_rating 桶）
4. 代码层硬兜底：回吐+清晰度高/中+强烈推荐 → 降档建议关注+观察；清晰度低不降档
5. 防丢键：防御式 merge 保留既有 detail 旧字段
"""
import pytest

from app.db import repo
from app.db.session import init_db
from agent_prompts import discover_prompt


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


# ==================== 1. schema 缺省默认 ====================

def test_schema_horizon_defaults_on_missing_fields():
    from app.agents.schemas import DiscoverCandidate
    cand = DiscoverCandidate(
        stock_code="600519", stock_name="贵州茅台", reason="r", risk_notice="n",
        stock_type="吸筹末期-优选型", confidence_tier="建议关注", confidence_pct=72.0,
        macro_view="m", meso_view="e", micro_view="s", volume_analysis="v",
        risks=["风险A", "风险B"], focus_type="低吸")
    assert cand.horizon_bias == "回归"
    assert cand.horizon_clarity == "低"
    assert cand.horizon_note == "前瞻数据不足"


def test_schema_horizon_pattern_enforced():
    from pydantic import ValidationError
    from app.agents.schemas import DiscoverCandidate
    base = dict(stock_code="600519", stock_name="x", reason="r", risk_notice="n",
                stock_type="吸筹末期-优选型", confidence_tier="建议关注", confidence_pct=72.0,
                macro_view="m", meso_view="e", micro_view="s", volume_analysis="v",
                risks=["a", "b"], focus_type="低吸")
    with pytest.raises(ValidationError):
        DiscoverCandidate(**base, horizon_bias="必涨")  # 非法三态外取值


# ==================== 2. build_final_prompt 前后瞻段 ====================

def test_build_final_prompt_omits_horizon_when_empty():
    p = discover_prompt.build_final_prompt("table", "news")
    # 前瞻数据块（【前瞻对照】段）未被注入：仅静态指引文字在
    assert "【前瞻对照】" not in p


def test_build_final_prompt_includes_horizon_when_provided():
    p = discover_prompt.build_final_prompt("table", "news", horizon_context="【前瞻对照】600519 x\n位置：...")
    assert "【前瞻对照】600519" in p
    assert "候选股新闻/公告检索结果" in p


# ==================== 3. build_horizon_context 纯函数（D1: select_rating 桶） ====================

def _track_row(code, date, rating, t5, t3=None):
    return {"stock_code": code, "stock_name": "x", "select_date": date,
            "select_rating": rating, "base_close_price": 10.0,
            "t3_pct": t3, "t5_pct": t5, "t10_pct": None, "max_drawdown": 1.0,
            "verify_result": {}, "factor_scores": None, "is_finished": 1, "id": 1,
            "update_time": "", "created_at": "2026-08-20"}


def test_horizon_context_ten_peers_has_winrate(monkeypatch):
    from app.services.track_verify import build_horizon_context
    rows = [_track_row(f"60000{i}", f"2026-08-{i:02d}", "C", 1.0 + i * 0.5) for i in range(1, 6)]
    rows += [_track_row(f"60001{i}", f"2026-08-{i:02d}", "C", -1.0) for i in range(1, 6)]
    monkeypatch.setattr(repo, "list_track_verify", lambda **kw: rows)
    shortlist = [{"stock_code": "601138", "stock_name": "工业富联", "confidence_tier": "C",
                  "pct_change_5d": 3.2, "dist_52w_high_pct": 12.0, "pos_52w": 88.0,
                  "ma20_pos_pct": 5.0, "ma60_pos_pct": 8.0, "vol_5_20": 1.4}]
    text = build_horizon_context(shortlist, {})
    assert "同类T+5" in text and "样本=10" in text  # 10 条 C 档
    assert "胜率=" in text and "均收益=" in text
    assert "距52周高点 12.0%" in text  # 位置列如实注入


def test_horizon_context_few_peers_insufficient(monkeypatch):
    from app.services.track_verify import build_horizon_context
    rows = [_track_row(f"60000{i}", f"2026-08-{i:02d}", "B", 1.0) for i in range(1, 4)]
    monkeypatch.setattr(repo, "list_track_verify", lambda **kw: rows)
    shortlist = [{"stock_code": "601138", "stock_name": "工业富联", "confidence_tier": "B",
                  "pct_change_5d": 3.2, "dist_52w_high_pct": 12.0, "pos_52w": 88.0}]
    text = build_horizon_context(shortlist, {})
    assert "样本不足" in text and "禁止当作结论" in text


def test_horizon_context_missing_columns_marks_insufficient(monkeypatch):
    from app.services.track_verify import build_horizon_context
    monkeypatch.setattr(repo, "list_track_verify", lambda **kw: [])
    shortlist = [{"stock_code": "601138", "stock_name": "工业富联", "confidence_tier": "C"}]  # 无横截列
    text = build_horizon_context(shortlist, {})
    assert "数据不足" in text  # 位置缺列写数据不足


# ==================== 4. 代码层硬兜底 ====================

def _capture(monkeypatch, module, fake_output):
    captured = {}
    def _fake(agent, cache_key, system_prompt, user_prompt, schema,
              ttl_seconds=86400, with_profile=True, with_knowledge=True, model_level=None):
        captured["prompt"] = user_prompt
        return fake_output
    monkeypatch.setattr(module, "agent_call", _fake)
    return captured


def _mk_candidate(tier, bias, clarity, focus="低吸"):
    from app.agents.schemas import DiscoverCandidate, DiscoverOutput
    cand = DiscoverCandidate(
        stock_code="601138", stock_name="工业富联", reason="r", risk_notice="n",
        stock_type="吸筹末期-优选型", confidence_tier=tier, confidence_pct=80.0,
        macro_view="m", meso_view="e", micro_view="s", volume_analysis="v",
        risks=["风险A", "风险B"], focus_type=focus,
        horizon_bias=bias, horizon_clarity=clarity,
        horizon_note="高位放量滞涨，同类C档样本20胜率35%，倾向回吐")
    return DiscoverOutput(market_summary="测试", candidates=[cand])


def _run_llm_final(monkeypatch, fake_output, existing_detail=None):
    """以给定 LLM 输出跑 discover.llm_final，返回 state + 落库捕获的 detail"""
    from app.agents import discover as disc_mod
    captured = {}
    # upsert_candidate(stock_code, stock_name, trade_date, rank, reasons, risk_notice, snapshot, detail)
    monkeypatch.setattr(disc_mod.repo, "upsert_candidate",
                        lambda *a, **k: captured.update(detail=a[7] if len(a) > 7 else k.get("detail")))
    monkeypatch.setattr(disc_mod.repo, "get_candidate_detail",
                        lambda code, date: dict(existing_detail or {}))
    monkeypatch.setattr("app.services.track_verify.repo.list_track_verify", lambda **kw: [])
    _capture(monkeypatch, disc_mod, fake_output)
    state = {"shortlist": [{"stock_code": "601138", "stock_name": "工业富联"}],
             "enrichment": {}, "data_enrichment": {}, "market_cap": 10,
             "trade_date": "2026-08-09",
             "universe": [{"code": "601138", "name": "工业富联"}], "trace": []}
    disc_mod.llm_final(state)
    return state, captured.get("detail")


def test_hard_fallback_retreat_reshares(monkeypatch):
    """回吐+清晰度高+强烈推荐 → 代码硬兜底降档建议关注+观察"""
    out = _mk_candidate("强烈推荐", "回吐", "高")
    state, detail = _run_llm_final(monkeypatch, out)
    item = state["candidates"][0]
    assert item["confidence_tier"] == "建议关注"
    assert item["focus_type"] == "观察"
    assert detail["confidence_tier"] == "建议关注"
    assert detail["horizon_bias"] == "回吐"


def test_hard_fallback_not_when_clarity_low(monkeypatch):
    """回吐但清晰度低 → 不降档（样本不足不按回吐一票否决）"""
    out = _mk_candidate("强烈推荐", "回吐", "低")
    state, _ = _run_llm_final(monkeypatch, out)
    assert state["candidates"][0]["confidence_tier"] == "强烈推荐"


def test_hard_fallback_not_when_continue(monkeypatch):
    """延续 + 强烈推荐 → 不降档"""
    out = _mk_candidate("强烈推荐", "延续", "高")
    state, _ = _run_llm_final(monkeypatch, out)
    assert state["candidates"][0]["confidence_tier"] == "强烈推荐"


# ==================== 5. 防丢键（防御式 merge） ====================

def test_defensive_merge_keeps_existing_fields(monkeypatch):
    """detail 防御式 merge：既有 detail 中「非本轮覆盖」的旧字段不被整 dict 覆盖丢失；
    enriched 等本轮显式重写的键按新值（保持旧行为，merge 只加保护不改变本体字段语义）"""
    existing = {"legacy_field": "keep-me", "confidence_tier": "谨慎观察"}
    out = _mk_candidate("建议关注", "延续", "高")
    state, detail = _run_llm_final(monkeypatch, out, existing_detail=existing)
    assert detail["legacy_field"] == "keep-me"      # 旧字段保留
    assert detail["confidence_tier"] == "建议关注"    # 本体字段本轮覆盖
    assert detail["horizon_bias"] == "延续"          # 新字段写入
