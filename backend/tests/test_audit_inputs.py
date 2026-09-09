"""审核材料和缓存契约；数据库、LLM 均以替身隔离。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from agent_prompts import audit_prompt
from app.agents import audit


def _suggestion(**changes):
    data = dict(
        id=17, review_id=8, target_agent="discover", target_kind="prompt",
        rule_type="soft", priority="medium", rule_name="波动观察",
        current_value="保持观察", suggested_value="仅做观察提示",
        rule_text="回撤超过 8% 的标的不允许入池", problem_desc="整体胜率低",
        reason="期望减少亏损", evidence="汇总胜率 20%",
        expected_effect="改善胜率", risk_note="可能错失机会",
        suggestion_source="template", file_path="agent_prompts/discover_prompt.py",
        insert_position="观察规则", conflict_note="", dedup_note="",
    )
    data.update(changes)
    return SimpleNamespace(**data)


@pytest.fixture
def sources(monkeypatch):
    rules = [
        {"id": 1, "target_agent": "discover", "rule_type": "soft",
         "rule_name": "已有观察", "rule_text": "观察风险，不排除候选"},
        {"id": 2, "target_agent": "all", "rule_type": "hard",
         "rule_name": "全局规则", "rule_text": "禁止自动交易"},
        {"id": 3, "target_agent": "", "rule_type": "soft",
         "rule_name": "历史兼容", "rule_text": "旧观察项"},
        {"id": 4, "target_agent": "score", "rule_type": "soft",
         "rule_name": "评分专属", "rule_text": "分数应有依据"},
    ]
    calls = []
    monkeypatch.setattr(audit.repo, "get_active_rules", lambda: deepcopy(rules))
    monkeypatch.setattr(audit, "agent_call", lambda **kwargs: calls.append(kwargs))
    return rules, calls


@pytest.mark.parametrize("target, expected", [
    ("discover", [1, 2, 3]), ("score", [2, 3, 4]), ("all", [2, 3]), ("", [2, 3]),
])
def test_collect_full_material_and_existing_scope(sources, target, expected):
    suggestion = _suggestion(target_agent=target)
    before = vars(suggestion).copy()
    data = audit.collect_audit(suggestion)
    assert {key: data[key] for key in before} == before
    assert [rule["id"] for rule in data["active_rules"]] == expected
    assert vars(suggestion) == before
    assert data["rule_text"] != data["suggested_value"]


def test_actual_prompt_exposes_conflicting_summary_body_and_rule_sources(sources):
    _, calls = sources
    audit.llm_audit(_suggestion())
    prompt = calls[0]["user_prompt"]
    for material in ("仅做观察提示", "回撤超过 8% 的标的不允许入池", "template",
                     '"target_kind": "prompt"', '"rule_type": "soft"',
                     '"review_id": 8', "观察风险，不排除候选", "禁止自动交易"):
        assert material in prompt
    assert "分数应有依据" not in prompt


@pytest.mark.parametrize("field, replacement", [
    ("rule_text", "完整正文已改变"), ("target_kind", "profile"),
    ("rule_type", "hard"), ("evidence", "新增分组证据"),
    ("suggestion_source", "llm"),
])
def test_cache_invalidates_when_same_suggestion_material_changes(sources, field, replacement):
    _, calls = sources
    suggestion = _suggestion()
    audit.llm_audit(suggestion)
    audit.llm_audit(suggestion)
    assert calls[0]["cache_key"] == calls[1]["cache_key"]
    setattr(suggestion, field, replacement)
    audit.llm_audit(suggestion)
    assert calls[2]["cache_key"] != calls[0]["cache_key"]


def test_cache_tracks_effective_rules_without_widening_scope(sources):
    rules, calls = sources
    audit.llm_audit(_suggestion())
    rules[0]["rule_text"] = "同一规则 ID 的正文更新"
    audit.llm_audit(_suggestion())
    rules[3]["rule_text"] = "其他 Agent 的正文更新"
    audit.llm_audit(_suggestion())
    assert calls[0]["cache_key"] != calls[1]["cache_key"]
    assert calls[1]["cache_key"] == calls[2]["cache_key"]


def test_cache_tracks_prompts_round_and_dissent(sources, monkeypatch):
    _, calls = sources
    suggestion = _suggestion()
    audit.llm_audit(suggestion)
    audit.llm_re_audit(suggestion, "缺覆盖损失")
    audit.llm_re_audit(suggestion, "缺恢复条件")
    monkeypatch.setattr(audit_prompt, "SYSTEM_PROMPT", audit_prompt.SYSTEM_PROMPT + "补充审核")
    audit.llm_re_audit(suggestion, "缺恢复条件")
    builder = audit_prompt.build_user_prompt
    monkeypatch.setattr(audit_prompt, "build_user_prompt", lambda data: builder(data) + "新材料格式")
    audit.llm_re_audit(suggestion, "缺恢复条件")
    assert len({call["cache_key"] for call in calls}) == 5
    assert "缺覆盖损失" in calls[1]["user_prompt"]


def test_existing_rules_read_failure_does_not_call_model(sources, monkeypatch):
    _, calls = sources

    def unavailable():
        raise RuntimeError("rules unavailable")

    monkeypatch.setattr(audit.repo, "get_active_rules", unavailable)
    with pytest.raises(RuntimeError, match="rules unavailable"):
        audit.llm_audit(_suggestion())
    assert calls == []


def test_prompt_requires_effect_evidence_and_preserves_manual_gate():
    prompt = audit_prompt.SYSTEM_PROMPT
    for condition in ("汇总胜率", "利润因子", "分组/对照", "策略/规则版本", "比较基准",
                      "候选覆盖损失", "复盘后才知道的最大回撤", "决策当时可获取",
                      "恢复条件", "到期条件", "旧规则处置", "不得伪造 K 编号",
                      "仍须人工确认", "摘要、正文", "不得凭常识强行通过"):
        assert condition in prompt
