"""Read-only registry for existing agents, tools, and workflows.

This module only exposes static metadata collected from current registries. It
must not execute agents, submit workflows, or write to storage.
"""
from __future__ import annotations

from copy import deepcopy

from app.agents import agentic_tools
from app.services.agent_chat import AGENT_CHAT_META


_AGENT_DEFAULTS: dict[str, dict] = {
    "discover": {
        "agent_type": "research_decision",
        "authority_level": "proposal",
        "outputs": ["candidate_reason", "risk_summary"],
    },
    "score": {
        "agent_type": "research_decision",
        "authority_level": "advisory",
        "outputs": ["score", "rating", "risk_items"],
    },
    "position": {
        "agent_type": "entry_orchestrator",
        "authority_level": "proposal",
        "outputs": ["position_plan", "risk_limits"],
        "human_gate_required": True,
    },
    "monitor": {
        "agent_type": "research_decision",
        "authority_level": "advisory",
        "outputs": ["holding_signal", "alert_severity"],
    },
    "sell": {
        "agent_type": "research_decision",
        "authority_level": "advisory",
        "outputs": ["sell_or_hold_advice", "risk_reason"],
        "human_gate_required": True,
    },
    "review": {
        "agent_type": "experience",
        "authority_level": "governance",
        "outputs": ["review_lesson", "rule_suggestion"],
        "human_gate_required": True,
    },
}

_COMMON_AGENT_DEFAULTS = {
    "inputs_required": [],
    "inputs_optional": [],
    "can_call": [],
    "can_reference": ["global_knowledge", "agent_knowledge", "hard_rules"],
    "cannot_do": ["execute_trade", "place_order", "cancel_order", "change_prompt_injection"],
    "knowledge_scope": "agent",
    "human_gate_required": False,
}

_WORKFLOWS = [
    {
        "workflow_id": "daily_pipeline",
        "name": "每日挖掘",
        "intent_examples": ["运行每日候选挖掘", "刷新今日候选池"],
        "steps": ["discover", "score"],
        "required_inputs": [],
        "optional_inputs": ["trade_date"],
        "allowed_entry_agents": ["discover"],
        "audit_required": False,
        "human_confirm_required": False,
        "final_responder": "discover",
    },
    {
        "workflow_id": "score",
        "name": "单股评分",
        "intent_examples": ["给某只股票评分", "分析股票五维得分"],
        "steps": ["score"],
        "required_inputs": ["stock_code"],
        "optional_inputs": ["stock_name"],
        "allowed_entry_agents": ["score"],
        "audit_required": False,
        "human_confirm_required": False,
        "final_responder": "score",
    },
    {
        "workflow_id": "position",
        "name": "分批建仓方案",
        "intent_examples": ["生成建仓计划", "这只股票怎么分批买"],
        "steps": ["position"],
        "required_inputs": ["stock_code"],
        "optional_inputs": ["stock_name", "source"],
        "allowed_entry_agents": ["position"],
        "audit_required": False,
        "human_confirm_required": True,
        "final_responder": "position",
    },
    {
        "workflow_id": "sell_decision",
        "name": "卖出决策",
        "intent_examples": ["持仓要不要卖", "判断某持仓风险"],
        "steps": ["monitor", "sell"],
        "required_inputs": ["holding_id"],
        "optional_inputs": [],
        "allowed_entry_agents": ["sell", "monitor"],
        "audit_required": False,
        "human_confirm_required": True,
        "final_responder": "sell",
    },
    {
        "workflow_id": "monitor_all",
        "name": "全量持仓实时监控",
        "intent_examples": ["巡检所有持仓", "刷新持仓告警"],
        "steps": ["monitor"],
        "required_inputs": [],
        "optional_inputs": [],
        "allowed_entry_agents": ["monitor"],
        "audit_required": False,
        "human_confirm_required": False,
        "final_responder": "monitor",
    },
    {
        "workflow_id": "market_intel",
        "name": "市场研判",
        "intent_examples": ["生成市场研判", "刷新大盘环境判断"],
        "steps": ["market_intel"],
        "required_inputs": [],
        "optional_inputs": ["trade_date"],
        "allowed_entry_agents": ["market_intel"],
        "audit_required": False,
        "human_confirm_required": False,
        "final_responder": "market_intel",
    },
    {
        "workflow_id": "portfolio_sentinel",
        "name": "组合哨兵巡检",
        "intent_examples": ["检查组合风险", "组合层面有没有异常"],
        "steps": ["portfolio_sentinel"],
        "required_inputs": [],
        "optional_inputs": [],
        "allowed_entry_agents": ["portfolio_sentinel"],
        "audit_required": False,
        "human_confirm_required": False,
        "final_responder": "portfolio_sentinel",
    },
    {
        "workflow_id": "knowledge_import",
        "name": "知识库批量导入",
        "intent_examples": ["导入方法论资料", "批量沉淀知识"],
        "steps": ["knowledge_import"],
        "required_inputs": ["items"],
        "optional_inputs": [],
        "allowed_entry_agents": ["review"],
        "audit_required": True,
        "human_confirm_required": True,
        "final_responder": "review",
    },
    {
        "workflow_id": "chat_ask",
        "name": "Agent 对话提问",
        "intent_examples": ["向某 Agent 提问", "解释已有研判"],
        "steps": ["chat_ask"],
        "required_inputs": ["agent", "question"],
        "optional_inputs": [],
        "allowed_entry_agents": list(AGENT_CHAT_META.keys()),
        "audit_required": False,
        "human_confirm_required": False,
        "final_responder": "selected_agent",
    },
]


def list_agents() -> list[dict]:
    agents = []
    for agent_id, meta in AGENT_CHAT_META.items():
        agent = {
            "agent_id": agent_id,
            "name": meta.get("name", agent_id),
            "responsibility": meta.get("scope", ""),
            "knowledge": meta.get("knowledge", ""),
            **_COMMON_AGENT_DEFAULTS,
            **_AGENT_DEFAULTS.get(agent_id, {}),
        }
        agents.append(deepcopy(agent))
    return agents


def get_agent(agent_id: str) -> dict | None:
    for agent in list_agents():
        if agent["agent_id"] == agent_id:
            return agent
    return None


def list_tools() -> list[dict]:
    tools = []
    for item in agentic_tools.TOOLS:
        fn = item.get("function", {})
        name = fn.get("name")
        if not name:
            continue
        tools.append({
            "tool_id": name,
            "name": name,
            "owner_module": "app.agents.agentic_tools",
            "description": fn.get("description", ""),
            "parameters": deepcopy(fn.get("parameters", {})),
            "tool_type": "readonly_data",
            "inputs": deepcopy(fn.get("parameters", {}).get("properties", {})),
            "outputs": "dict",
            "used_by": ["agentic_llm"],
            "cache_policy": "caller_defined",
            "failure_policy": "return_error_payload",
            "cannot_do": ["write_database", "execute_trade", "place_order", "cancel_order"],
        })
    return tools


def list_workflows() -> list[dict]:
    return deepcopy(_WORKFLOWS)


def get_system_map_summary() -> dict:
    agents = list_agents()
    tools = list_tools()
    workflows = list_workflows()
    return {
        "agents_count": len(agents),
        "tools_count": len(tools),
        "workflows_count": len(workflows),
        "agents": agents,
        "workflows": workflows,
    }

