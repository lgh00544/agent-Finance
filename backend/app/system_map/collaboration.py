"""Read-only Agent collaboration allowlist.

The matrix describes permissions for display and future governance checks. It
does not intercept or change any existing workflow execution.
"""
from __future__ import annotations

from copy import deepcopy


def _rule(
    requester_agent: str,
    target_agent: str,
    relation: str,
    *,
    max_depth: int = 1,
    conflict_policy: str = "target_authority_wins",
    audit_required: bool = False,
    reason: str,
) -> dict:
    return {
        "requester_agent": requester_agent,
        "target_agent": target_agent,
        "relation": relation,
        "allowed": True,
        "max_depth": max_depth,
        "conflict_policy": conflict_policy,
        "audit_required": audit_required,
        "reason": reason,
    }


_COLLABORATION_RULES = [
    *[
        _rule(
            "feishu_gateway",
            target,
            "call",
            conflict_policy="entry_only_no_override",
            reason="飞书入口只能调用业务 Agent 并汇总结果。",
        )
        for target in ("discover", "score", "position", "monitor", "sell", "review", "market_intel")
    ],
    *[
        _rule(
            "chat_entry",
            target,
            "call",
            conflict_policy="entry_only_no_override",
            reason="对话入口只能调用业务 Agent 并汇总结果。",
        )
        for target in ("discover", "score", "position", "monitor", "sell", "review", "market_intel")
    ],
    _rule(
        "score", "discover", "reference",
        reason="评分可参考候选发现证据，但不能无条件覆盖自己的评分。",
    ),
    _rule(
        "score", "market_intel", "reference",
        reason="评分可参考市场环境研判。",
    ),
    _rule(
        "score", "portfolio_sentinel", "reference",
        reason="评分可参考组合级风险信息。",
    ),
    _rule(
        "sell", "monitor", "reference",
        reason="卖出决策可参考持仓监控信号。",
    ),
    _rule(
        "sell", "market_intel", "reference",
        reason="卖出决策可参考市场环境研判。",
    ),
    _rule(
        "sell", "portfolio_sentinel", "reference",
        reason="卖出决策可参考组合级风险信息。",
    ),
    _rule(
        "monitor", "portfolio_sentinel", "reference",
        reason="持仓监控可参考组合级风险信息。",
    ),
    *[
        _rule(
            "review",
            target,
            "propose_change",
            conflict_policy="suggestion_requires_audit_and_human_gate",
            audit_required=True,
            reason="复盘只能向业务 Agent 提出规则建议，不能直接修改规则。",
        )
        for target in ("discover", "score", "position", "monitor", "sell")
    ],
    _rule(
        "audit", "agent_suggestion", "reference",
        conflict_policy="audit_only_no_mutation",
        reason="审核 Agent 只能读取建议作为审核对象，不能自行修改规则。",
    ),
]

_RULE_INDEX = {
    (item["requester_agent"], item["target_agent"], item["relation"]): item
    for item in _COLLABORATION_RULES
}


def _forbidden_rule(requester_agent: str, target_agent: str, relation: str) -> dict:
    return {
        "requester_agent": requester_agent,
        "target_agent": target_agent,
        "relation": relation,
        "allowed": False,
        "max_depth": 0,
        "conflict_policy": "deny_by_default",
        "audit_required": False,
        "reason": "未注册的协作关系默认禁止。",
    }


def list_collaboration_rules() -> list[dict]:
    """Return the explicit collaboration allowlist without live side effects."""
    return deepcopy(_COLLABORATION_RULES)


def can_collaborate(requester_agent: str, target_agent: str, relation: str) -> dict:
    """Resolve one relation, defaulting to a stable forbidden result."""
    if requester_agent == target_agent:
        return _forbidden_rule(requester_agent, target_agent, relation)
    result = _RULE_INDEX.get((requester_agent, target_agent, relation))
    return deepcopy(result) if result is not None else _forbidden_rule(
        requester_agent, target_agent, relation
    )


def list_allowed_targets(agent_id: str) -> list[str]:
    """Return target IDs for all explicitly allowed relations of an Agent."""
    targets = {
        item["target_agent"]
        for item in _COLLABORATION_RULES
        if item["requester_agent"] == agent_id and item["allowed"]
    }
    return sorted(targets)

