"""Read-only consistency checks for System Map registration sources.

The checker compares existing registries and runtime entry metadata. It does
not execute Agents, workflows, tools, database statements, or external calls.
"""
from __future__ import annotations

from datetime import datetime


SYSTEM_NODES = frozenset({
    "market_intel", "portfolio_sentinel", "chat_entry", "feishu_gateway",
    "audit", "agent_suggestion",
})
ENTRY_CAPABILITIES = frozenset({"chat_ask", "knowledge_import"})
HANDLER_AGENT_ALIASES = {"market": "market_intel", "trigger": "discover"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _issue(kind: str, severity: str, source: str, item: str, message: str,
           expected, actual) -> dict:
    return {
        "kind": kind,
        "severity": severity,
        "source": source,
        "item": item,
        "message": message,
        "expected": expected,
        "actual": actual,
    }


def _schema_tool_ids(tools) -> set[str]:
    ids = set()
    for item in tools:
        name = (item.get("function") or {}).get("name") if isinstance(item, dict) else None
        if name:
            ids.add(str(name))
    return ids


def _source_snapshot() -> dict:
    """Read the current facts without invoking any executable entry point."""
    from app.agents import agentic_tools
    from app.graph import graphs
    from app.services import agent_chat, chat_handlers
    from app.system_map import collaboration, registry

    return {
        "agent_meta": set(agent_chat.AGENT_CHAT_META),
        "graph_agents": set(graphs._BUILDERS),
        "registry_agents": {
            str(item.get("agent_id")) for item in registry.list_agents()
            if item.get("agent_id")
        },
        "handlers": set(chat_handlers._HANDLERS),
        "intent_targets": dict(chat_handlers._INTENT_TARGETS),
        "tools_schema": _schema_tool_ids(agentic_tools.TOOLS),
        "tool_funcs": set(agentic_tools.TOOL_FUNCS),
        "workflows": registry.list_workflows(),
        "collaboration_rules": collaboration.list_collaboration_rules(),
    }


def _check_sources(sources: dict) -> list[dict]:
    issues: list[dict] = []
    declared_agents = set(sources["agent_meta"])
    runtime_agents = set(sources["graph_agents"])
    registry_agents = set(sources["registry_agents"])
    actual_agents = declared_agents | runtime_agents
    executable_agents = runtime_agents | {
        HANDLER_AGENT_ALIASES.get(handler, handler)
        for handler in sources["handlers"]
        if HANDLER_AGENT_ALIASES.get(handler, handler) in actual_agents
    }
    known_nodes = actual_agents | SYSTEM_NODES
    known_capabilities = known_nodes | ENTRY_CAPABILITIES

    for agent in sorted(actual_agents - registry_agents):
        issues.append(_issue(
            "agent_missing_registry", "error", "agent_meta/graph_agents", agent,
            "真实 Agent 没有对应的 System Map 注册。", True, False,
        ))
    for agent in sorted(registry_agents - executable_agents):
        issues.append(_issue(
            "agent_missing_handler", "error", "registry_agents", agent,
            "System Map 注册了 Agent，但没有可确认的 Agent 执行入口。",
            sorted(executable_agents), agent,
        ))

    for workflow in sources["workflows"]:
        workflow_id = str(workflow.get("workflow_id") or "")
        for step in workflow.get("steps") or []:
            step = str(step)
            if step not in known_capabilities:
                issues.append(_issue(
                    "workflow_unknown_step", "error", "registry_workflows",
                    f"{workflow_id}:{step}", "Workflow step 未在 Agent、系统节点或入口能力中声明。",
                    sorted(known_capabilities), step,
                ))
        for entry in workflow.get("allowed_entry_agents") or []:
            entry = str(entry)
            if entry not in known_nodes:
                issues.append(_issue(
                    "workflow_unknown_entry_agent", "error", "registry_workflows",
                    f"{workflow_id}:{entry}", "Workflow 入口引用了未知 Agent 或系统节点。",
                    sorted(known_nodes), entry,
                ))

    for rule in sources["collaboration_rules"]:
        for field, kind in (("requester_agent", "collaboration_unknown_node"),
                            ("target_agent", "collaboration_unknown_node")):
            node = str(rule.get(field) or "")
            if node not in known_nodes:
                issues.append(_issue(
                    kind, "error", "collaboration_rules",
                    f"{rule.get('requester_agent', '')}->{rule.get('target_agent', '')}",
                    "协作矩阵引用了未声明的节点。", sorted(known_nodes), node,
                ))

    schema_ids = set(sources["tools_schema"])
    function_ids = set(sources["tool_funcs"])
    for tool in sorted(schema_ids - function_ids):
        issues.append(_issue(
            "tool_schema_without_function", "error", "agentic_tools", tool,
            "工具 schema 已登记，但 TOOL_FUNCS 没有对应函数。", True, False,
        ))
    for tool in sorted(function_ids - schema_ids):
        issues.append(_issue(
            "tool_function_without_schema", "error", "agentic_tools", tool,
            "TOOL_FUNCS 有函数，但 TOOLS 没有对应 schema。", True, False,
        ))

    for intent, target in sorted(sources["intent_targets"].items()):
        target = str(target or "")
        if not target or target not in known_nodes:
            issues.append(_issue(
                "intent_unknown_target", "error", "chat_handlers._INTENT_TARGETS", intent,
                "Intent target 缺失或指向未知 Agent/系统节点。", sorted(known_nodes), target,
            ))

    return issues


def check_system_map_integrity() -> dict:
    """Return a read-only registration integrity result."""
    checked_at = _now()
    source_names = [
        "agent_meta", "graph_agents", "registry_agents", "handlers",
        "intent_targets", "tools_schema", "tool_funcs", "workflows",
        "collaboration_rules",
    ]
    try:
        sources = _source_snapshot()
        if not sources:
            return {
                "status": "unknown",
                "checked_at": checked_at,
                "summary": {"issue_count": 0, "error_count": 0,
                            "attention_count": 0, "source_count": 0},
                "issues": [],
                "sources": source_names,
                "reason": "当前无法确认注册完整性",
            }
        issues = _check_sources(sources)
    except Exception as exc:  # noqa: BLE001 preserve source failures for health
        issue = _issue(
            "source_read_error", "error", "system_map_sources", "sources",
            "System Map 完整性事实来源读取失败。", "all sources readable", str(exc),
        )
        return {
            "status": "error",
            "checked_at": checked_at,
            "summary": {"issue_count": 1, "error_count": 1,
                        "attention_count": 0, "source_count": 0},
            "issues": [issue],
            "sources": source_names,
        }

    errors = [item for item in issues if item["severity"] == "error"]
    attention = [item for item in issues if item["severity"] != "error"]
    status = "error" if errors else "attention" if attention else "healthy"
    return {
        "status": status,
        "checked_at": checked_at,
        "summary": {
            "issue_count": len(issues),
            "error_count": len(errors),
            "attention_count": len(attention),
            "source_count": len(source_names),
        },
        "issues": issues,
        "sources": source_names,
    }


get_registration_integrity = check_system_map_integrity
