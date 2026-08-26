"""经验沉淀闭环·批2：EXTRACT_SYSTEM「持续信号」维度（prompt 文本级校验，不调 LLM）"""
from agent_prompts.experience_prompt import EXTRACT_SYSTEM


def test_regular_signal_worth_false_not_forced():
    """常规信号（count=1）不被持续信号规则强加 worth：原「无明显经验→worth=false」保留 + 规则带 count≥3 门槛"""
    assert "无明显可复用经验 → worth=false" in EXTRACT_SYSTEM
    assert "count ≥ 3" in EXTRACT_SYSTEM


def test_regular_signal_worth_true_preserved():
    """常规 high/low 判定规则未被删改：真实经验仍可标 worth=true"""
    assert "涉及交易规则/研判标准/Agent 建议的修改或新增 → impact=\"high\"" in EXTRACT_SYSTEM
    assert "纯观测类（某标的在某形态下的走势规律）且可验证 → impact=\"low\"" in EXTRACT_SYSTEM
    assert "禁止 hallucination" in EXTRACT_SYSTEM


def test_persistent_signal_rule_present():
    """持续信号维度生效：count≥3 → worth=true，title/body/tags/impact/confidence 形态要求齐备"""
    assert "持续信号" in EXTRACT_SYSTEM
    assert "count ≥ 3" in EXTRACT_SYSTEM
    assert "title 必须含「持续信号」" in EXTRACT_SYSTEM
    assert "tags 必须包含 \"持续信号\" + stock_code" in EXTRACT_SYSTEM
    assert "impact=low" in EXTRACT_SYSTEM
    assert "confidence=0.5~0.7" in EXTRACT_SYSTEM
