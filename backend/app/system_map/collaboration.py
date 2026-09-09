"""Read-only Agent collaboration allowlist.

The matrix describes permissions for display and future governance checks. It
does not intercept or change any existing workflow execution.
"""
from __future__ import annotations

from copy import deepcopy
import logging

logger = logging.getLogger(__name__)


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
    _rule(
        "paper_execution", "discover", "reference",
        conflict_policy="paper_read_only",
        reason="模拟执行只读取候选事实，不调用发现 Agent 重新选股。",
    ),
    _rule(
        "paper_execution", "score", "reference",
        conflict_policy="paper_read_only",
        reason="模拟执行只读取已落库评分，不重算评分。",
    ),
    _rule(
        "paper_execution", "position", "reference",
        conflict_policy="paper_read_only",
        reason="模拟执行只读取已有建仓计划，不生成或修改计划。",
    ),
    *[
        _rule(
            "paper_execution",
            target,
            "reference",
            conflict_policy="paper_snapshot_only",
            reason="纸面沙盒可复用分析 Agent 的快照/只读能力，但不得调用其真实写入副作用。",
        )
        for target in ("monitor", "sell", "review", "market_intel")
    ],
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


def _known_nodes() -> set[str]:
    nodes = {"chat_entry", "feishu_gateway", "portfolio_sentinel", "market_intel", "agent_suggestion"}
    for item in _COLLABORATION_RULES:
        nodes.add(item["requester_agent"])
        nodes.add(item["target_agent"])
    try:
        from app.system_map import registry
        nodes.update(agent["agent_id"] for agent in registry.list_agents())
    except Exception:  # noqa: BLE001 runtime guard must fail closed without registry
        logger.warning("系统能力地图读取失败，协作运行时检查按矩阵节点降级")
    return nodes


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


def check_collaboration(caller: str, target: str, relation: str = "call") -> dict:
    """Runtime collaboration guard result; unknown or undeclared relations fail closed."""
    caller = (caller or "").strip()
    target = (target or "").strip()
    relation = (relation or "call").strip()
    known = _known_nodes()
    unknown_caller = not caller or caller not in known
    unknown_target = not target or target not in known
    if unknown_caller or unknown_target:
        result = _forbidden_rule(caller, target, relation)
        result.update({
            "caller": caller,
            "target": target,
            "unknown": True,
            "unknown_caller": unknown_caller,
            "unknown_target": unknown_target,
            "default_denied": True,
            "reason": "未知 caller 或 target，运行时协作检查默认拒绝。",
        })
        return result
    result = can_collaborate(caller, target, relation)
    default_denied = not result["allowed"] and result.get("conflict_policy") == "deny_by_default"
    result.update({
        "caller": caller,
        "target": target,
        "unknown": False,
        "unknown_caller": False,
        "unknown_target": False,
        "default_denied": default_denied,
    })
    return result


def list_allowed_targets(agent_id: str) -> list[str]:
    """Return target IDs for all explicitly allowed relations of an Agent."""
    targets = {
        item["target_agent"]
        for item in _COLLABORATION_RULES
        if item["requester_agent"] == agent_id and item["allowed"]
    }
    return sorted(targets)
