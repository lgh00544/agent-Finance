"""阶段2 白盒维度归因推广到 Position/Sell（dev SQLite，真实落库；不触网）：
1. PositionOutput/SellOutput 带 dimensions/final_advice 解析合法；不传时默认空（向后兼容）
2. insert_plan(detail=...) 落库闭环：list_plans 读回 detail（dimensions/final_advice/market_regime）
3. trace_plan/trace_sell final_conclusion 含 final_advice + dimensions 摘要
4. global_base_prompt.md 游资红线 3 条铁律可见
"""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.schemas import (DiscoverDimension, PositionOutput, SellOutput)
from app.db import repo
from app.db.session import SessionLocal, init_db
from app.services import reasoning_trace


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _dims() -> list:
    return [
        DiscoverDimension(dim="技术趋势", score=72, verdict="支持", advice="回踩MA20企稳"),
        DiscoverDimension(dim="资金/游资", score=60, verdict="中性", advice="无游资数据"),
        DiscoverDimension(dim="基本面", score=70, verdict="支持", advice="估值合理"),
        DiscoverDimension(dim="舆情/风险", score=75, verdict="支持", advice="无利空"),
        DiscoverDimension(dim="行业景气", score=68, verdict="中性", advice="板块一般"),
    ]


def _position_kwargs():
    return dict(
        stock_code="600519", market_regime="震荡市：上证运行于 MA20 下方",
        total_pct=20.0,
        batches=[{"tranche": 1, "price_zone": "现价 23.5~24.0", "ratio_pct": 6,
                  "trigger_note": "回踩确认后首次建仓"}],
        stop_loss=21.5, take_profit=27.0, rationale="分批建仓逻辑",
        dimensions=_dims(),
        final_advice="综合评估：3/5 维支持，可分批建仓，总仓位 20%（不超既有 C2 上限），"
                     "止损-8%，主要风险…",
    )


def test_position_output_parses_dimensions():
    """v3.0：PositionOutput 解析 dimensions 数组 + final_advice 原文"""
    out = PositionOutput(**_position_kwargs())
    assert len(out.dimensions) == 5
    assert out.dimensions[1].dim == "资金/游资"
    assert out.dimensions[1].verdict == "中性"
    assert out.final_advice.startswith("综合评估：3/5 维支持")


def test_position_output_defaults_empty():
    """兼容：旧 LLM 输出（无 dimensions/final_advice）解析为默认值，不抛错"""
    data = _position_kwargs()
    del data["dimensions"], data["final_advice"]
    out = PositionOutput(**data)
    assert out.dimensions == [] and out.final_advice == ""


def test_sell_output_parses_dimensions():
    """v3.0：SellOutput 解析 dimensions + final_advice（游资撤离信号进资金维）"""
    out = SellOutput(
        stock_code="600519", action="partial", confidence="medium",
        reasons=["技术面破位"], exit_price_zone="反弹至 26.5 附近",
        risk_warning="继续持有风险较大", check_list=["当日是否可卖"],
        dimensions=_dims(),
        final_advice="综合评估：2/5 维偏离，建议 partial（减仓预警），止损位 21.5（成本×0.92），"
                     "主要风险…",
    )
    assert len(out.dimensions) == 5
    assert out.final_advice.startswith("综合评估：2/5 维偏离")


def test_sell_output_defaults_empty():
    """兼容：旧 LLM 输出无新字段 → 默认空，不抛错"""
    out = SellOutput(
        stock_code="600519", action="hold", confidence="low",
        reasons=["信息不足"], exit_price_zone="", risk_warning="", check_list=[])
    assert out.dimensions == [] and out.final_advice == ""


def test_insert_plan_detail_roundtrip():
    """落库闭环：insert_plan(detail=...) → list_plans 读回 detail（dimensions/final_advice/market_regime）"""
    pid = repo.insert_plan(
        "600519", "贵州茅台", "2026-08-09", 20.0,
        [{"tranche": 1, "price_zone": "23.5~24.0", "ratio_pct": 6, "trigger_note": "首仓"}],
        21.5, 27.0, "分批建仓",
        detail={"dimensions": [d.model_dump() for d in _dims()],
                "final_advice": "综合评估：3/5 维支持，可分批建仓，总仓位 20%",
                "market_regime": "震荡市"},
    )
    rows = [r for r in repo.list_plans(code="600519") if r["id"] == pid]
    assert rows, "方案未落库"
    det = rows[0]["detail"]
    assert len(det["dimensions"]) == 5
    assert det["dimensions"][0]["dim"] == "技术趋势"
    assert det["final_advice"].startswith("综合评估：3/5 维支持")
    assert det["market_regime"] == "震荡市"


def test_insert_plan_detail_optional():
    """兼容：旧调用不传 detail → 落库 detail 为空 dict，list_plans 返回 {}"""
    pid = repo.insert_plan("600518", "测试股E", "2026-08-09", 10.0, [], 9.0, 12.0, "旧调用")
    rows = [r for r in repo.list_plans(code="600518") if r["id"] == pid]
    assert rows[0]["detail"] == {}


def test_trace_plan_contains_whitebox(monkeypatch):
    """留痕：trace_plan final_conclusion 含 final_advice + dimensions 摘要（dim→verdict）"""
    from app.db.models import AiReasoningTrace
    from sqlalchemy import select

    captured = {}

    def _fake_submit(payload):
        captured["payload"] = payload

    monkeypatch.setattr(reasoning_trace, "submit", _fake_submit)
    reasoning_trace.trace_plan(
        "600519", "贵州茅台", "2026-08-09", 20.0,
        [{"tranche": 1}], 21.5, 27.0, "分批建仓", 999,
        detail={"dimensions": [d.model_dump() for d in _dims()],
                "final_advice": "综合评估：3/5 维支持"},
    )
    concl = json.loads(captured["payload"]["final_conclusion"])
    assert concl["final_advice"].startswith("综合评估：3/5 维支持")
    assert concl["dimensions"]["技术趋势"] == "支持"
    assert concl["dimensions"]["资金/游资"] == "中性"
    assert concl["plan_id"] == 999  # 旧键保留


def test_trace_sell_contains_whitebox(monkeypatch):
    """留痕：trace_sell final_conclusion 保留旧键 + final_advice + dimensions 摘要"""
    captured = {}

    def _fake_submit(payload):
        captured["payload"] = payload

    monkeypatch.setattr(reasoning_trace, "submit", _fake_submit)
    reasoning_trace.trace_sell(
        "600519", "贵州茅台", "2026-08-09",
        {"action": "partial", "confidence": "medium",
         "exit_price_zone": "9.8~10.2", "check_list": ["确认止损"],
         "dimensions": [d.model_dump() for d in _dims()],
         "final_advice": "综合评估：2/5 维偏离，建议 partial"},
    )
    concl = json.loads(captured["payload"]["final_conclusion"])
    assert concl["action"] == "partial" and concl["exit_price_zone"] == "9.8~10.2"
    assert "确认止损" in concl["check_list"]  # 旧键保留
    assert concl["final_advice"].startswith("综合评估：2/5 维偏离")
    assert concl["dimensions"]["技术趋势"] == "支持"


def test_global_base_has_capital_redlines():
    """global_base_prompt.md 游资红线 3 条铁律可见"""
    text = (Path(__file__).resolve().parents[2] / "agent_prompts" / "global_base_prompt.md").read_text(
        encoding="utf-8")
    assert "游资红线铁律" in text
    assert "权重不得超过技术面+基本面综合得分的 30%" in text
    assert "不得因游资买入而放宽止损位/仓位上限" in text
    assert "无多源验证" in text and "置信度不足" in text


def test_position_sell_prompts_have_dimensions():
    """两提示词文件 SCHEMA_DESC 已含 dimensions 数组与 final_advice"""
    base = Path(__file__).resolve().parents[2] / "agent_prompts"
    for fname, key in (("position_prompt.py", "final_advice"),
                       ("sell_prompt.py", "final_advice")):
        text = (base / fname).read_text(encoding="utf-8")
        assert '"dimensions"' in text and f'"{key}"' in text, f"{fname} 缺 {key}"
    sell = (base / "sell_prompt.py").read_text(encoding="utf-8")
    assert "2 个以上主力主体" in sell, "sell 缺双条件清仓强制规则"
    assert "对倒" in sell and "不作" in sell, "sell 缺对倒警惕规则"
