"""
Agent 专属对话服务（Agent 对话页后端）

三类交互，全部复用现有底层能力（agent_call 统一段序注入 / 双模型路由 / 异步任务 / 知识库）：
1. 文字提问答疑：基于该 Agent 专属知识库 + 全局通用知识库回答，标注依据来源与信心度，不越界；
2. 规则调教反馈：按验证流程校验用户提案（对照硬性规则/核心方法论/现有知识冲突），
   输出「采纳/部分采纳/维持原规则」结论与依据；采纳规则自动沉淀到该 Agent 私有知识库；
   硬性规则（HARD_RULES）与核心方法论只读，对话无权修改；
3. 多模态上传学习：MiniMax 识别图片（失败降级本地 PaddleOCR）→ DeepSeek 提炼知识点并
   建议标签 → 返回确认摘要（未落库）→ 用户确认/修正标签后存入对应 Agent 知识库。

【刚性代码逻辑】本模块只做：知识注入、LLM 调用、消息落库；全部判定与结论由 LLM 结构化输出。
"""
import hashlib
import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from app.agents import common
from app.db import repo
from app.llm.structured import ModelLevel

logger = logging.getLogger(__name__)

# ==================== 六 Agent 元信息（页面标注 + 对话系统提示） ====================

AGENT_CHAT_META: dict[str, dict] = {
    "discover": {
        "name": "选股发现 Agent",
        "scope": "全市场候选挖掘：快照硬过滤 → 指标计算 → LLM 初选 → 新闻核验 → 最终候选确认，"
                 "输出候选理由与风险初判。",
        "knowledge": "全局通用知识库基线 + 人工硬性规则 + 个人交易偏好档案 + "
                     "私有知识库（discover）+ 分职能战法知识库（discover.md/counter_examples.md）",
    },
    "score": {
        "name": "评分分析 Agent",
        "scope": "单股五维评分（基本面/技术趋势/资金/舆情/行业景气）0-100，A/B/C 分级与风险清单，"
                 "研判依据标注。",
        "knowledge": "全局通用知识库基线 + 人工硬性规则 + 个人交易偏好档案 + "
                     "私有知识库（score）+ 分职能战法知识库（score.md）",
    },
    "position": {
        "name": "建仓方案 Agent",
        "scope": "分批建仓方案：4 档分批区间、每档资金配比、总仓位上限（依市场强弱动态调整）、"
                 "止损止盈参考；所有交易必须人工执行。",
        "knowledge": "全局通用知识库基线 + 人工硬性规则 + 个人交易偏好档案 + "
                     "私有知识库（position）",
    },
    "monitor": {
        "name": "持仓监控 Agent",
        "scope": "持仓实时监控：实时行情 + 最新公告 + 指标 → 持有/减仓/清仓信号与严重度，"
                 "告警推送去重。",
        "knowledge": "全局通用知识库基线 + 人工硬性规则 + 个人交易偏好档案 + "
                     "私有知识库（monitor）+ 分职能战法知识库（monitor.md）",
    },
    "sell": {
        "name": "卖出决策 Agent",
        "scope": "持仓标的卖出决策：止损纪律/趋势破坏/目标兑现/突发利空综合研判，输出卖出或持有建议；"
                 "卖出必须由人工执行。",
        "knowledge": "全局通用知识库基线 + 人工硬性规则 + 个人交易偏好档案 + "
                     "私有知识库（sell）+ 分职能战法知识库（sell.md）",
    },
    "review": {
        "name": "复盘迭代 Agent",
        "scope": "卖出复盘：入场逻辑兑现度、盈亏核心原因、经验教训、偏好回流与优化建议；"
                 "建议生效必须先经人工审核。",
        "knowledge": "全局通用知识库基线 + 人工硬性规则 + 个人交易偏好档案 + "
                     "私有知识库（review）+ 分职能战法知识库（review.md/counter_examples.md）",
    },
}

AGENT_TAGS = list(AGENT_CHAT_META.keys())

_VERDICT_LABELS = {"adopted": "采纳", "partial": "部分采纳", "maintained": "维持原规则"}


# ==================== LLM 结构化输出 Schema ====================

class ChatAnswer(BaseModel):
    """文字提问答疑输出：数据标源、无绝对化表述、标注信心度"""
    answer: str = Field(description="对用户问题的回答（中文）")
    confidence: int = Field(description="信心度 0-100，数据充分且明确时取高值，存疑时取低值")
    sources: list[str] = Field(default_factory=list,
                               description="回答依据的来源清单（如：全局基线/硬性规则第N条/"
                                           "私有知识库《标题》/分职能战法知识库/公开行情数据）")
    scope_note: str = Field(default="",
                            description="职责边界说明：问题超出本 Agent 领域时明确说明不属于本领域，不越界作答")


class RuleFeedback(BaseModel):
    """规则调教校验输出：不盲从，先校验后给结论"""
    verdict: str = Field(description="结论：adopted=采纳 / partial=部分采纳（需调整） / maintained=维持原规则")
    reason: str = Field(description="结论依据（对照硬性规则/核心方法论/现有知识冲突的核查结果）")
    rule_title: str = Field(default="", description="建议沉淀到知识库的规则标题（采纳/部分采纳时填写）")
    rule_content: str = Field(default="", description="建议沉淀到知识库的规则正文（采纳/部分采纳时填写）")
    conflict_note: str = Field(default="", description="与硬性规则/核心方法论/风控底线的冲突核查说明")


class LearnPoint(BaseModel):
    """多模态学习提炼出的单个知识点（建议标签，用户可修正）"""
    title: str = Field(description="知识点标题")
    content: str = Field(description="知识点正文（提炼后完整保留要点）")
    tags: list[str] = Field(default_factory=list, description="建议标签（如：K线战法/风控纪律/资金面/消息面）")
    agent_tag: str = Field(default="all", description="建议沉淀目标 Agent（与当前对话 Agent 一致或 all）")


class LearnExtract(BaseModel):
    """图片学习提炼总输出"""
    summary: str = Field(description="确认摘要：识别内容概述 + 共提炼几个知识点 + 建议标签概览")
    points: list[LearnPoint] = Field(default_factory=list, description="提炼出的知识点列表")


# ==================== 对话系统提示（拼接在 agent_call 固定段序之后） ====================

_CHAT_SYSTEM_PROMPT = """你是本 Agent 领域的专属对话助手。基于注入给你的全部上下文
（全局通用知识库基线 / 人工硬性规则 / 个人交易偏好档案 / 私有知识库 / 分职能战法知识库）回答用户问题。

回答要求：
0. 输出必须为合法 JSON（json_object 模式），由系统解析后展示，不要在 JSON 外附加任何说明文字；
1. 只回答本 Agent 职责范围内的问题；问题超出职责范围时在 scope_note 中明确说明「不属于本领域」，并简述可咨询哪个 Agent，不越界作答；
2. 数据标源：关键结论必须标注依据来源（sources 字段），如「硬性规则第N条」「私有知识库《标题》」「分职能战法知识库」「公开行情数据」；
3. 无绝对化表述：禁止「一定/必然/稳赚」等绝对化用语，不确定性用「可能/倾向/需跟踪」表达；
4. 标注信心度：数据充分且结论明确时 confidence 取 80-95；部分依据或主观推断取 50-75；依据不足时取 30-50 并明确说明；
5. 风控底线不突破：任何建议不得违反人工硬性规则与风控底线（止损纪律/仓位上限/派发期一票否决等）；
6. 涉及具体标的时：不给出确定的买卖指令，只做分析参考，交易必须人工决策并执行；
7. 回答使用中文，简洁专业，可直接阅读。"""


def _chat_user_prompt(question: str, meta: dict) -> str:
    return (f"用户向【{meta['name']}】提问：\n{question}\n\n"
            f"请基于你的职责范围与知识体系回答，遵循回答要求。")


# ==================== 规则调教校验提示 ====================

_RULE_SYSTEM_PROMPT = """你是【规则校验员】：用户向本 Agent 提出规则修改/新增提案时，你不盲从，
必须先完成验证流程再给结论。验证流程：

1. 冲突核查（对照注入的上下文）：
   a. 与「人工硬性锁定规则（Hard Rules）」冲突 → 一律维持原规则；硬性规则只能由人工修改，你没有权限调整；
   b. 涉及「全局通用知识库基线」中的核心方法论与风控底线（止损纪律/仓位上限/派发期否决等）→ 一律维持原规则，
      核心方法论只读，任何对话不得修改；
   c. 与私有知识库/分职能战法知识库已有规则冲突 → 说明冲突点，按「新提案信息更充分且不违反 a/b 才可采纳」处理；
   d. 提案表述不清、无法验证、或依赖无法获取的数据 → 维持原规则，说明理由。

2. 合理性与完备性：提案是否符合交易常识、是否可执行、是否会给系统引入不可验证的主观阈值。

3. 结论（verdict）：
   - adopted：提案合理且不与 a/b 冲突，与现有知识无冲突或新提案更优；
   - partial：提案方向合理但需要调整（如补充边界条件、修正表述），rule_content 中给出调整后的版本；
   - maintained：与硬性规则/核心方法论冲突，或无法验证、表述不清、引入风险。

4. 采纳/部分采纳时：rule_content 写成可直接沉淀到知识库的规则正文（含适用边界与例外说明），
   rule_title 写清晰标题；maintained 时两者留空。

输出必须是结构化 JSON（verdict/reason/rule_title/rule_content/conflict_note），全部中文。"""


def _rule_user_prompt(agent: str, proposal: str, meta: dict) -> str:
    return (f"用户向【{meta['name']}】提交规则提案：\n{proposal}\n\n"
            f"请按验证流程给出结论。若判定维持原规则，reason 中必须说明具体冲突或不可验证的原因；"
            f"不得以「无法判断」类模糊表述带过。")


# ==================== 多模态学习提示 ====================

_LEARN_MM_PROMPT = (
    "你是股票交易知识提炼助手。请完整识别这张图片的内容（K线图、战法文档、交易心得等），"
    "提取其中的核心知识点，逐条列出。要求：\n"
    "1. 保留原文关键数字、价位、规则表述，不臆造内容；\n"
    "2. 按知识点分条，每条包含：标题、要点内容；\n"
    "3. 图片若含图表，描述其形态特征与信号含义（如：放量突破、跌破支撑等）；\n"
    "4. 若内容包含主观心得或未经证实的方法，注明其性质（心得/方法/经验）。\n"
    "用中文输出，条理清晰。"
)

_LEARN_STRUCTURE_SYSTEM = """你是知识整理助手：将多模态识别出的原始文本整理为结构化知识点，用于沉淀到 Agent 知识库。

要求：
0. 输出必须为合法 JSON（json_object 模式），不要输出 JSON 之外的任何文字；
1. 按内容主题切分为独立知识点（每条 1 个主题），去除重复与无关内容；
2. title 简洁（≤30字），content 完整保留要点（关键数字/价位/规则表述不得遗漏）；
3. tags 给出 2-4 个标签（如：K线战法/风控纪律/资金面/消息面/仓位管理/心态纪律）；
4. agent_tag 建议沉淀目标 Agent（discover/score/position/monitor/sell/review/all，默认为当前对话 Agent）；
5. 主观心得类内容在 content 末尾注明「（主观心得，仅供参考）」；
6. summary 一句话概括识别内容与提炼结果。"""


# ==================== 服务函数 ====================

def _record(agent: str, role: str, content: str, message_type: str = "qa",
            verdict: str = "", knowledge_id: int | None = None, meta: dict | None = None) -> int:
    try:
        return repo.add_chat_message(agent, role, content, message_type,
                                     verdict=verdict, knowledge_id=knowledge_id, meta=meta or {})
    except Exception as exc:  # noqa: BLE001 历史记录失败不阻塞主流程
        logger.warning("对话历史落库失败: %s", exc)
        return 0


def _require_agent(agent: str) -> dict:
    meta = AGENT_CHAT_META.get(agent)
    if not meta:
        raise ValueError(f"未知 Agent: {agent}（可选：{'/'.join(AGENT_TAGS)}）")
    return meta


def ask_agent(agent: str, question: str) -> dict:
    """文字提问答疑：agent_call 固定段序注入知识，ttl=0 不命中缓存（交互即时性）"""
    meta = _require_agent(agent)
    if not question or not question.strip():
        raise ValueError("问题不能为空")
    key = f"chat:{agent}:{hashlib.md5(question.strip().encode('utf-8')).hexdigest()[:10]}"
    answer = common.agent_call(
        agent=agent, cache_key=key, system_prompt=_CHAT_SYSTEM_PROMPT,
        user_prompt=_chat_user_prompt(question.strip(), meta),
        schema=ChatAnswer, ttl_seconds=0, model_level=ModelLevel.DEEP)
    sources_text = "；".join(s for s in answer.sources if s) or "未标注具体来源"
    payload = {"answer": answer.answer, "confidence": answer.confidence,
               "sources": sources_text, "scope_note": answer.scope_note}
    user_mid = _record(agent, "user", question.strip(), "qa")
    _record(agent, "assistant", answer.answer, "qa", meta={"confidence": answer.confidence,
                                                           "sources": answer.sources,
                                                           "scope_note": answer.scope_note,
                                                           "user_msg_id": user_mid})
    return payload


def rule_feedback(agent: str, proposal: str) -> dict:
    """规则调教校验：验证后给结论；采纳/部分采纳自动沉淀到该 Agent 私有知识库。
    硬性规则与核心方法论只读——校验提示已强制维持原规则，且本函数无任何写提示词/硬规则的代码路径。"""
    meta = _require_agent(agent)
    if not proposal or not proposal.strip():
        raise ValueError("规则提案不能为空")
    key = f"rule:{agent}:{hashlib.md5(proposal.strip().encode('utf-8')).hexdigest()[:10]}"
    feedback = common.agent_call(
        agent=agent, cache_key=key, system_prompt=_RULE_SYSTEM_PROMPT,
        user_prompt=_rule_user_prompt(agent, proposal.strip(), meta),
        schema=RuleFeedback, ttl_seconds=0, model_level=ModelLevel.DEEP)

    verdict = feedback.verdict if feedback.verdict in ("adopted", "partial", "maintained") else "maintained"
    knowledge_id = None
    if verdict in ("adopted", "partial") and feedback.rule_title and feedback.rule_content:
        knowledge_id = repo.add_knowledge(
            f"[对话沉淀·{meta['name']}] {feedback.rule_title.strip()}",
            feedback.rule_content.strip(), agent_tag=agent)
        logger.info("规则采纳沉淀: agent=%s verdict=%s knowledge_id=%s", agent, verdict, knowledge_id)

    payload = {"verdict": verdict, "verdict_label": _VERDICT_LABELS[verdict],
               "reason": feedback.reason, "conflict_note": feedback.conflict_note,
               "rule_title": feedback.rule_title, "rule_content": feedback.rule_content,
               "knowledge_id": knowledge_id}
    user_mid = _record(agent, "user", proposal.strip(), "rule")
    _record(agent, "assistant", feedback.reason, "rule",
            verdict=verdict, knowledge_id=knowledge_id,
            meta={"rule_title": feedback.rule_title, "conflict_note": feedback.conflict_note,
                  "user_msg_id": user_mid})
    return payload


def learn_from_image(agent: str, image_bytes: bytes, filename: str = "upload.png") -> dict:
    """多模态上传学习：MiniMax 识别（失败降级本地 PaddleOCR）→ DeepSeek 提炼知识点并建议标签。
    仅返回确认摘要，不落库；由 confirm_learn 在用户确认/修正标签后写入知识库。"""
    meta = _require_agent(agent)
    raw_text = _extract_image_text(image_bytes, filename)
    if not raw_text or not raw_text.strip():
        raise ValueError("图片识别结果为空，请更换更清晰的图片重试")
    key = f"learn:{agent}:{hashlib.md5(raw_text.encode('utf-8')).hexdigest()[:10]}"
    extract = common.agent_call(
        agent=agent, cache_key=key, system_prompt=_LEARN_STRUCTURE_SYSTEM,
        user_prompt=(f"以下为从图片中识别出的原始文本（可能含识别噪声）：\n\n{raw_text[:6000]}\n\n"
                     f"请整理为结构化知识点，建议沉淀目标为 {agent} 知识库。"),
        schema=LearnExtract, ttl_seconds=0, model_level=ModelLevel.DEEP)

    points = []
    for p in extract.points:
        if not p.title or not p.content:
            continue
        points.append({"title": p.title.strip(), "content": p.content.strip(),
                       "tags": [t for t in (p.tags or []) if t],
                       "agent_tag": (p.agent_tag or agent) if (p.agent_tag or agent) in
                       AGENT_CHAT_META or (p.agent_tag or "all") == "all" else agent})
    if not points:
        raise ValueError("未能从图片中提炼出有效知识点，请更换更清晰的图片重试")

    payload = {"summary": extract.summary or f"共提炼 {len(points)} 个知识点",
               "points_json": json.dumps(points, ensure_ascii=False),
               "raw_text": raw_text[:2000],
               "engine": _LAST_ENGINE}
    _record(agent, "user", f"[多模态学习] 上传图片：{filename}（识别引擎：{_LAST_ENGINE}）", "learn")
    _record(agent, "assistant", payload["summary"], "learn",
            meta={"point_count": len(points), "points": points})
    return payload


_LAST_ENGINE = "minimax"


def _extract_image_text(image_bytes: bytes, filename: str) -> str:
    """图片文本识别：MiniMax 多模态优先，失败/未配置降级本地 PaddleOCR"""
    global _LAST_ENGINE
    from app.services.multimodal import get_multimodal_client
    try:
        client = get_multimodal_client()
        if client is not None:
            text = client.analyze_image(image_bytes, _LEARN_MM_PROMPT, max_tokens=4096)
            if text and text.strip():
                _LAST_ENGINE = "minimax"
                return _clean_mm_text(text)
            logger.warning("MiniMax 识别返回空，降级本地 OCR")
    except Exception as exc:  # noqa: BLE001 多模态失败不阻塞主链路
        logger.warning("MiniMax 识别失败（降级本地 OCR）: %s", str(exc)[:160])
    from app.services import ocr as ocr_service
    try:
        result = ocr_service._recognize_local(image_bytes, filename)
        raw = result.get("raw_text") or ""
        if raw.strip():
            _LAST_ENGINE = "paddleocr"
            return raw[:6000]
    except Exception as exc:  # noqa: BLE001
        logger.warning("本地 OCR 也失败: %s", str(exc)[:160])
    return ""


def _clean_mm_text(text: str) -> str:
    """清理 MiniMax 输出中的代码围栏与思考痕迹"""
    text = re.sub(r"```(?:json|markdown|text)?", "", text)
    return text.strip()


def confirm_learn(agent: str, entries: list[dict]) -> dict:
    """用户确认（或修正标签后）将知识点写入对应 Agent 知识库"""
    _require_agent(agent)
    if not entries:
        raise ValueError("确认条目不能为空")
    saved = []
    for item in entries:
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        tag = str(item.get("agent_tag") or agent).strip()
        if not title or not content:
            continue
        tag = tag if tag in AGENT_CHAT_META or tag == "all" else agent
        kid = repo.add_knowledge(f"[图片沉淀·{AGENT_CHAT_META[agent]['name']}] {title}", content, agent_tag=tag)
        saved.append({"knowledge_id": kid, "title": title, "agent_tag": tag})
    if not saved:
        raise ValueError("没有可保存的有效条目")
    _record(agent, "assistant",
            f"已确认将 {len(saved)} 个知识点沉淀到知识库：{', '.join(s['title'] for s in saved[:5])}",
            "learn", meta={"saved": saved})
    return {"saved": saved, "count": len(saved)}
