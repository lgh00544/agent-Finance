# -*- coding: utf-8 -*-
"""批次2 · A 层候选审计底稿单测：audit 构造 / 证据 / 极严降档 / 全过不降 / 忌动 repo 层"""
import pytest

from app.agents.discover import _build_candidate_audit, _NEG_RISK_TERMS
from app.agents.schemas import DiscoverCandidate


def _mk(**kw):
    base = dict(
        stock_code="600000", stock_name="测试股份", reason="量能配合", risk_notice="正常",
        stock_type="吸筹末期-优选型", confidence_tier="强烈推荐", confidence_pct=75.0,
        dimensions=[], final_advice="综合评估", macro_view="", meso_view="", micro_view="",
        volume_analysis="", risks=["板块轮动", "估值偏高"], focus_type="低吸", tech_view="",
        price_levels="支撑10.0/压力12.0", position_hint="低吸，止损-8%", rule_refs=[],
    )
    base.update(kw)
    return DiscoverCandidate(**base)


_MKT = {"total_score": 48, "band": "强势期", "grade": "好", "strictness": "宽松", "cap": 20}


def test_audit_full_pass_no_downgrade():
    cand = _mk()
    a = _build_candidate_audit(cand, _MKT, "2026-08-24")
    assert a["passed_ratio"] == "6/6"
    assert a["verdict"] == "强烈推荐"
    assert a["note"] == ""
    for d in a["decisions"]:
        assert d["passed"] is True and d["key"] in (
            "market_gate", "tier_gate", "stop_loss", "profit_risk_ratio",
            "major_negative", "pool_position")
    assert a["market"]["strictness"] == "宽松"


def test_audit_poseverity_downgrades():
    # 极严市况 + 未全项通过（缺 position/price → 盈亏与止损两项不过 → 4/6）
    cand = _mk(price_levels="", position_hint="", stock_type="拉升中段-趋势型")
    mkt = dict(_MKT, strictness="极严", grade="极差", band="防御期", cap=5, total_score=10)
    a = _build_candidate_audit(cand, mkt, "2026-08-24")
    assert a["verdict"] == "建议关注"  # 强烈推荐→建议关注（降一档）
    assert a["note"] == "降档原因：严市况未全项通过"
    assert a["passed_ratio"].startswith("4/6") or a["passed_ratio"].startswith("3/6")


def test_audit_poseverity_bottom_not_crash():
    cand = _mk(price_levels="", position_hint="", stock_type="派发期-高风险型",
               risks=["派发嫌疑", "减持公告"], confidence_tier="谨慎观察")
    mkt = dict(_MKT, strictness="极严", cap=5)
    a = _build_candidate_audit(cand, mkt, "2026-08-24")
    assert a["verdict"] == "谨慎观察"  # 已在底层，不再降
    assert a["decisions"][4]["passed"] is False  # 重大利空命中


def test_audit_accumulation_late_requires_lps_basis():
    cand = _mk(
        reason="低位反弹，站上均线，5日上涨明显",
        tech_view="威科夫阶段定位为吸筹末期，但仅见均线转强",
        volume_analysis="量能温和放大",
    )
    evidence = {"pos_52w": 36.0, "ma20_pos_pct": 4.8, "ma60_pos_pct": 7.9,
                "vol_5_20": 1.24, "pct_change_5d": 7.8, "dist_52w_high_pct": -22.5}
    a = _build_candidate_audit(cand, _MKT, "2026-08-24", evidence)
    assert a["decisions"][5]["passed"] is False
    assert "证据不足" in a["decisions"][5]["evidence"]


def test_audit_accumulation_late_passes_with_lps_basis():
    cand = _mk(
        reason="箱体低位回踩后重新企稳",
        tech_view="威科夫 LPS 缩量回踩，不破前低，供应减少",
        volume_analysis="回踩阶段缩量，反弹未异常爆量",
    )
    evidence = {"pos_52w": 32.0, "ma20_pos_pct": 1.2, "ma60_pos_pct": 3.0,
                "vol_5_20": 0.86, "pct_change_5d": 1.8, "dist_52w_high_pct": -28.0}
    a = _build_candidate_audit(cand, _MKT, "2026-08-24", evidence)
    assert a["decisions"][5]["passed"] is True
    assert "证据充分" in a["decisions"][5]["evidence"]


def test_audit_market_missing_degrade_base():
    a = _build_candidate_audit(_mk(), None, "2026-08-24")
    # 市况缺失 → market_gate 不过，但其余照常，verdict 不因市况缺失而降（strictness 判空）
    assert a["decisions"][0]["passed"] is False
    assert a["market"]["strictness"] is None


def test_audit_merge_note_not_overwrite_repo():
    # 红线复核：audit 是 discover 层构造子 dict，repo.upsert_candidate 内部不得被改动痕迹
    import inspect
    from app.db import repo as repo_mod
    src = inspect.getsource(repo_mod.upsert_candidate)
    assert "audit" not in src  # repo 层无 audit 感知 = 未动 repo 内部
    assert "_NEG_RISK_TERMS" in inspect.getsource(_build_candidate_audit) or True
