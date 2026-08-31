"""P1 智能路由：正则快路径 + LIGHT LLM 结构化意图识别 + 全意图分发执行。
正则命中直接分发（省 token）；未命中走 LLM；LLM 失败/低置信回 chat 不执行。"""
import logging
import re

from app.llm.structured import ModelLevel, llm_call_json
from app.prompts.chat_router import INTENTS, SYSTEM_PROMPT, RouteIntent, user_prompt
from app.services import chat_handlers
from app.system_map import collaboration as collaboration_registry
from app.system_map import registry as system_map_registry

logger = logging.getLogger(__name__)


_NAME_SKIP = ("分析", "评分", "卖出", "评估", "看看", "帮我", "查一下")


def _target(text: str) -> tuple[str, str]:
    """提取标的：优先「名称(代码)」，再 6 位代码 + 旁侧中文名（代码前/后，排除指令动词）"""
    m = re.search(r"([一-龥]{2,6})\((\d{6})\)", text)
    if m:
        return m.group(2), m.group(1)
    m = re.search(r"(\d{6})", text)
    if not m:
        return "", ""
    code = m.group(1)
    before, after = text[:m.start()], text[m.end():]
    a = re.search(r"^[\s·,，]+([一-龥]{2,6})", after)
    b = re.search(r"([一-龥]{2,6})[\s]*$", before)
    for cand in (a, b):
        if cand and cand.group(1) not in _NAME_SKIP:
            return code, cand.group(1)
    return code, ""


_KEYWORDS = (  # 意图 → 触发词（含"跑一次"/"触发"优先级最高，先于"选股"判定）
    ("trigger", ("跑一次", "触发")),
    ("pnl", ("盈亏", "收益", "盈利")),
    ("holdings", ("查持仓", "持仓", "我的股票")),
    ("help", ("帮助", "你好", "状态")),
    ("discover", ("选股", "发现", "挖掘", "今天有什么")),
    ("market", ("大盘", "指数", "板块", "市场", "轮动")),
    ("monitor", ("告警", "监控", "预警")),
    ("review", ("复盘",)),
)


def _route_regex(text: str) -> tuple[str, dict] | None:
    """正则快路径（方案 §5.3 关键词 + teach 三意图）：高频指令零 LLM 直达"""
    t = text.strip()
    if (any(k in t for k in ("存草稿", "先存着", "开始草稿", "补一条"))
            or t in ("完成", "放弃", "继续")):
        return "draft", {}
    if any(k in t for k in ("忘掉", "删掉", "不要再说")):  # 先于 remember：忘掉 X 内可含"我持有"
        return "forget", {}
    if any(k in t for k in ("记住", "别忘了", "我持有", "我的风格")):
        return "remember", {}
    if any(k in t for k in ("教", "以后都", "永远", "改成", "设为", "改为")):
        return "teach", {"agent": chat_handlers._teach_agent(t)}
    for intent, kws in _KEYWORDS:
        if any(k in t for k in kws):
            return intent, {}
    code, name = _target(t)
    if any(k in t for k in ("分析", "评分", "评估")) and (code or name):
        return "score", {"code": code, "name": name}
    if "卖出" in t and (code or name):
        return "sell", {"code": code, "name": name}
    if any(k in t for k in ("止损", "止盈", "仓位", "风控", "红线")):
        return "teach", {"agent": chat_handlers._teach_agent(t)}  # 阈值词单现 → LLM 校验不硬拒
    return None


def _system_map_hint() -> tuple[str, dict | None]:
    """Build a compact route hint without putting the full map in the prompt."""
    try:
        summary = system_map_registry.get_system_map_summary()
        agents = ",".join(item["agent_id"] for item in summary.get("agents", []))
        workflows = ",".join(item["workflow_id"] for item in summary.get("workflows", []))
        return f"已注册 Agent: {agents}; workflow: {workflows}。未知能力按 chat 处理。", summary
    except Exception as exc:  # noqa: BLE001 map is advisory and must not break routing
        logger.warning("系统能力地图读取失败，路由按兼容路径继续: %s", exc)
        return "系统能力地图暂不可用，按已有意图兼容路由。", None


def _route_metadata(intent: str, params: dict, hint: str) -> tuple[str, dict, str]:
    """Annotate a route with map metadata while keeping dispatch-compatible params."""
    target_agent = params.get("target_agent") or ""
    workflow_id = params.get("workflow_id") or ""
    if not target_agent:
        target_agent = {
            "score": "score",
            "sell": "sell",
            "discover": "discover",
            "monitor": "monitor",
            "review": "review",
            "market": "market_intel",
        }.get(intent, "")
    if not workflow_id:
        workflow_id = {
            "score": "score",
            "sell": "sell_decision",
            "discover": "daily_pipeline",
            "monitor": "monitor_all",
            "market": "market_intel",
        }.get(intent, "")
    required_params = list(params.get("required_params") or [])
    permission_note = params.get("permission_note") or ""
    if target_agent:
        permission = collaboration_registry.can_collaborate("chat_entry", target_agent, "call")
        permission_note = permission["reason"] if permission["allowed"] else "未注册协作关系，已按兼容路径处理。"
    metadata = {
        "target_agent": target_agent,
        "workflow_id": workflow_id,
        "required_params": required_params,
        "permission_note": permission_note,
    }
    enriched = {**params, **metadata}
    if permission_note:
        hint = f"{hint}\n权限：{permission_note}" if hint else f"权限：{permission_note}"
    return intent, enriched, hint


def _validate_route(intent: str, params: dict, hint: str, summary: dict | None) -> tuple[str, dict, str]:
    """Fail closed for unknown map capabilities; preserve legacy behavior if map is unavailable."""
    if summary is None:
        return _route_metadata(intent, params, hint)
    agent_ids = {item["agent_id"] for item in summary.get("agents", [])}
    workflow_ids = {item["workflow_id"] for item in summary.get("workflows", [])}
    target_agent = params.get("target_agent") or ""
    workflow_id = params.get("workflow_id") or ""
    if (target_agent and target_agent not in agent_ids) or (workflow_id and workflow_id not in workflow_ids):
        logger.info("路由返回未注册能力 agent=%s workflow=%s，降级 chat", target_agent, workflow_id)
        return "chat", {"code": params.get("code", ""), "name": params.get("name", ""),
                         "agent": "", "target_agent": "", "workflow_id": "",
                         "required_params": [],
                         "permission_note": "未注册能力，已降级为 chat。"}, \
            "未注册能力，已降级为 chat。"
    return _route_metadata(intent, params, hint)


def route(text: str, prev: str = "") -> tuple[str, dict, str]:
    """意图判定 → (intent, params, reply_hint)；失败/低置信回 chat"""
    m = _route_regex(text)
    if m:
        return _validate_route(m[0], m[1], "", _system_map_hint()[1])
    try:
        system_hint, summary = _system_map_hint()
        result = llm_call_json(SYSTEM_PROMPT, f"{system_hint}\n{user_prompt(text, prev)}", RouteIntent,
                               max_tokens=200, model_level=ModelLevel.LIGHT)
        params = {"code": result.params.code, "name": result.params.name,
                  "agent": result.params.agent, "target_agent": result.target_agent,
                  "workflow_id": result.workflow_id,
                  "required_params": result.required_params,
                  "permission_note": result.permission_note}
        if result.intent in INTENTS:
            return _validate_route(result.intent, params, result.reply_hint, summary)
        logger.info("意图路由 LLM 返回未知意图 %s → 回 chat", result.intent)
    except Exception as exc:  # noqa: BLE001 LLM 失败回退 chat，不抛
        logger.warning("意图路由 LLM 调用失败: %s", exc)
    return "chat", {"code": "", "name": "", "agent": "", "target_agent": "",
                     "workflow_id": "", "required_params": [], "permission_note": ""}, ""


def route_and_execute(text: str, prev: str, open_id: str) -> str:
    """bridge 入口：路由 → 分发执行 → 返回即时回复文本（长任务内部已提交异步回推）"""
    intent, params, hint = route(text, prev)
    return chat_handlers.dispatch(text, intent, params, hint, open_id)
