"""
Agent 公共工具：统一调教接口 + 统一 LLM 调用入口

【统一调教接口（全部 Agent 平等开放）】
0. 全局通用知识库基线（agent_prompts/global_base_prompt.md）：所有 Agent 每次任务【最先】加载，
   A股规则 / 基准本金(36943) / 系统边界 / 技术分析执行标准 / 思考推理强制准则 / 预留扩展插槽；
1. 硬性规则（HARD_RULES）：人工锁定的业务底线，所有 Agent 无条件遵守，LLM 不得放宽；
1.5 复盘采纳规则（rule_change 表，一键采纳自动落地）：人工确认后由系统动态注入——
   硬性类与 HARD_RULES 同等声明，软性类为参考权重；绝不写源码文件；
2. 个人交易偏好档案（sys_trade_profile）：所有 Agent 自动注入，页面可视化编辑即时生效；
3. 私有知识库（private_knowledge）：每个 Agent 启动任务时自动检索对应交易经验/战法资料注入。

【刚性代码逻辑】以上全部为上下文注入，不参与任何市场判断；基线/偏好/知识版本号入缓存键，
人工修改后 LLM 缓存自动失效、立即生效。
"""
import hashlib
import logging
from pathlib import Path
from typing import Type, TypeVar

from app.agents.agentic_tools import TOOLS, TOOL_FUNCS
from app.cache import cache
from app.db import repo
from app.llm.structured import ModelLevel, _model_for, call_llm_cached
from app.services import track_verify
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# ==================== 全局通用知识库基线（所有 Agent 统一加载） ====================
# agent_prompts/global_base_prompt.md：纯指令文本，每个 Agent 每次任务【最先】加载，
# 再拼接自身专属 Prompt（插槽1）与动态配置（插槽2/插槽3），互不覆盖、统一生效。
# 实时读文件：人工编辑基线后无需重启即生效（文件小，读取成本可忽略）。


def _global_base_path() -> Path:
    """基线文件路径：以 agent_prompts 包所在目录定位（本机开发与 Docker 均适用）"""
    import agent_prompts

    return Path(agent_prompts.__file__).resolve().parent / "global_base_prompt.md"


def global_base_prompt() -> str:
    """加载全局通用知识库基线文本（加载失败不阻塞主链路）"""
    try:
        return _global_base_path().read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("全局基线加载失败: %s", exc)
        return ""


def _global_base_version() -> str:
    """基线内容指纹 → 入缓存键：人工编辑基线后 LLM 缓存自动失效、立即生效"""
    content = global_base_prompt()
    if not content:
        return "none"
    return hashlib.md5(content.encode("utf-8")).hexdigest()[:8]


# ==================== 人工硬性锁定规则（统一调教接口·底线） ====================
# ★ 本区域为【人工硬性规则】编辑区：在此逐条写下你不可妥协的业务底线，
#   所有 Agent（挖掘/打分/建仓/监控/卖出/复盘）的每次任务都会强制携带本声明。
#   LLM 被约束为无条件遵守、不得放宽；规则本身只能由人工修改本文件生效。
#   示例（去掉注释符号即生效）：
#   - 禁止推荐/买入 ST、*ST、退市整理期及立案调查中的股票；
#   - 单只标的从成本价回撤超过 8% 必须触发减仓/清仓信号，不得以任何理由放宽；
#   - 商誉占净资产比例超过 50% 的公司一律回避。
HARD_RULES: list[str] = [
    # ===== 每日候选池 v2.0 强制底线（2026-08-04 人工设定，全 Agent 生效） =====
    "板块权限硬约束：创业板（300 开头）标的仅做分析、不推荐买入，"
    "若因分析价值保留在候选池，必须在风险中显著标注『仅限分析，不推荐买入』且信心度档位不得高于『谨慎观察』；"
    "科创板（688 开头）、北交所（8/4 开头）标的不纳入候选池，一律不得入选，也不得推荐买入。",
    "派发期一票否决：同时满足『5日涨幅≥15% + 主力资金净流出 + 换手率≥12% + 距52周高点≤10%』的标的，"
    "直接排除，不得进入候选池。",
    "一日游避雷：板块内共振上涨个股不足3只、或盘中涨幅收窄≥0.5% 的纯脉冲题材，不得纳入正式候选池。",
    "超买否决：单只标的 5 日累计涨幅≥15% 时，不得作为建仓推荐标的。",
]


def hard_rules_section() -> str:
    """人工硬性规则 → prompt 声明文本（无规则时返回空）"""
    if not HARD_RULES:
        return ""
    rules = "\n".join(f"{i}. {r}" for i, r in enumerate(HARD_RULES, 1))
    return (
        "【人工硬性锁定规则（Hard Rules）】以下为人工设定的业务底线，优先级最高：\n"
        f"{rules}\n"
        "你必须无条件遵守以上规则，不得以任何理由放宽、绕过或忽略；"
        "若你的研判与硬性规则冲突，以硬性规则为准并明确说明冲突点；"
        "这些规则只能由人工修改配置后变更，你没有权限自行调整。"
    )


def dynamic_rules_section() -> str:
    """复盘采纳规则（一键采纳自动落地）→ prompt 注入文本：
    硬规则与 HARD_RULES 同等声明（无条件遵守），软规则为参考权重（非死条件）；
    规则由 DB 动态注入（rule_change 表，绝不写源码文件）。无生效规则时返回空。"""
    try:
        rules = repo.get_active_rules()
    except Exception as exc:  # noqa: BLE001 规则读取失败不阻塞主链路
        logger.warning("复盘采纳规则读取失败: %s", exc)
        return ""
    if not rules:
        return ""
    hard = [r for r in rules if r.get("rule_type") == "hard"]
    soft = [r for r in rules if r.get("rule_type") != "hard"]
    parts = []
    if hard:
        lines = "\n".join(f"{i}. {r.get('rule_text', '')}" for i, r in enumerate(hard, 1))
        parts.append(
            "【复盘采纳规则·硬性（人工审核后自动生效）】以下规则经人工确认后由系统自动生效，"
            "优先级与人工硬性锁定规则等同：\n" + lines + "\n"
            "你必须无条件遵守以上规则，不得以任何理由放宽、绕过或忽略；"
            "若与人工硬性规则冲突，以人工硬性规则为准并说明冲突点。"
        )
    if soft:
        lines = "\n".join(f"{i}. {r.get('rule_text', '')}" for i, r in enumerate(soft, 1))
        parts.append(
            "【复盘采纳规则·参考权重（人工审核后自动生效）】以下规则经人工确认后由系统自动生效，"
            "作为研判参考权重（非死条件）：\n" + lines + "\n"
            "与硬性规则冲突时以硬性规则为准，动态调整须在输出中标注理由。"
        )
    return "\n\n".join(parts)


def _rule_version() -> str:
    """复盘采纳规则指纹 → 入缓存键：采纳/回滚后当日 LLM 缓存自动失效"""
    try:
        return repo.rule_version()
    except Exception:  # noqa: BLE001 指纹失败不阻塞主链路
        return "0:0"


def profile_section() -> str:
    """个人交易偏好档案 → prompt 注入文本"""
    content = repo.get_trade_profile_content()
    if not content:
        return ""
    lines = [f"- {k}: {v}" for k, v in content.items() if v is not None and v != ""]
    return "\n".join(lines) if lines else ""


def knowledge_section(agent: str, docs: list | None = None) -> tuple[str, list]:
    """私有交易经验/战法知识库 → prompt 注入文本（统一运行机制：任务启动自动检索）。

    返回 (注入文本, docs)；docs=[{id, number, title}]（number=注入段中的 1..N，
    供 agent_chat 做"编号→知识id"映射回吐）。
    命中计量：检索到 docs 时批量 bump hit_count（只加不自减；失败仅 warning 不阻塞主链路）。
    docs 由调用方预取传入时（agent_chat）直接拼文本，不再检索、不重复计量。"""
    from app.services.vector_store import get_vector_store

    if docs is None:
        try:
            docs = get_vector_store().search_knowledge(agent, top_k=5)
        except Exception as exc:  # noqa: BLE001 知识检索失败不阻塞主链路
            logger.warning("私有知识检索失败 %s: %s", agent, exc)
            return "", []
        if not docs:
            return "", []
        # 命中计量：批量一次 UPDATE（失败仅 warning，不阻塞主链路）
        try:
            repo.bump_knowledge_hits([d["id"] for d in docs])
        except Exception as exc:  # noqa: BLE001 计量失败不阻塞主链路
            logger.warning("私有知识命中计量失败（降级跳过）: %s", exc)
    elif not docs:
        return "", []

    numbered: list[dict] = []
    lines: list[str] = []
    for i, d in enumerate(docs, start=1):
        numbered.append({"id": int(d["id"]), "number": i, "title": str(d.get("title") or "")})
        lines.append(f"{i}.【{d['title']}】{d['content']}")
    text = ("【你的私有交易经验/战法参考】(编号与本段一致，若在研判/回答中采用了某条，"
            "必须在\"引用的知识\"里回吐其编号；与硬性规则冲突以硬性规则为准)\n" + "\n".join(lines))
    return text, numbered


def _knowledge_version() -> str:
    """知识库+经验变更感知（k{count}:{max_id}:e{ecount}:{emax_id}），入缓存键
    使知识/经验更新后 LLM 缓存自动失效；经验表新增/修改由 max_id 递增感知"""
    try:
        count, max_id = repo.knowledge_version()
        return f"k{count}:{max_id}:{repo.experience_version()}"
    except Exception:  # noqa: BLE001
        return "k0:0:e0:0"


def experience_section(agent: str) -> str:
    """自动沉淀经验参考注入（仅 active；auto_merged 项带「·自动」标记；限量 ≤5 条每条 ≤200 字）。
    与私有知识库（人工）共存不冲突：experience 是自动沉淀经验库，注入段独立标注，避免混同。"""
    stage_map = {"discover": "选股", "score": "选股", "position": "建仓",
                 "monitor": "持仓", "sell": "持仓", "review": "持仓"}
    try:
        items = repo.search_experience(stage=stage_map.get(agent, "选股"), k=5)
    except Exception as exc:  # noqa: BLE001 经验检索失败不阻塞主链路
        logger.warning("经验检索注入失败: %s", exc)
        return ""
    if not items:
        return ""
    lines = []
    for it in items:
        tag = "·自动" if it.get("auto_merged") else ""
        body = str(it.get("body") or "")[:200]
        lines.append(f"- {it['title']}（置信 {it['confidence']:.2f}{tag}）\n  {body}")
    return "\n\n【历史经验参考（自动沉淀，仅供参考）】\n" + "\n".join(lines)


# ==================== 分职能战法知识库（方法论文本沉淀，插槽1实现） ====================
# agent_prompts/knowledge/：按 Agent 拆分的战法知识 md 文件（人工可编辑），
# 由 agent_call 在私有知识库之后、Agent 专属 Prompt 之前注入；
# 内容指纹入缓存键：人工编辑知识文件后 LLM 缓存自动失效、立即生效。
_AGENT_KNOWLEDGE_FILES: dict[str, list[str]] = {
    "discover": ["discover.md", "counter_examples.md"],
    "discover_final": ["discover.md", "counter_examples.md"],
    "market_condition": ["market.md"],
    "score": ["score.md"],
    "monitor": ["monitor.md"],
    "sell": ["sell.md"],
    "review": ["review.md", "counter_examples.md"],
}


def _agent_knowledge_text(agent: str) -> str:
    """分职能战法知识库：按 Agent 读取对应 md 文件拼接（缺失不阻塞）"""
    files = _AGENT_KNOWLEDGE_FILES.get(agent)
    if not files:
        return ""
    kb_dir = _global_base_path().resolve().parent / "knowledge"
    parts = []
    for fname in files:
        try:
            text = (kb_dir / fname).read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 知识文件缺失不阻塞主链路
            logger.warning("战法知识文件 %s 加载失败: %s", fname, exc)
            continue
        if text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def _agent_knowledge_version(agent: str) -> str:
    """分职能知识内容指纹 → 入缓存键：编辑知识文件后 LLM 缓存自动失效"""
    text = _agent_knowledge_text(agent)
    if not text:
        return "a-"
    return "a" + hashlib.md5(text.encode("utf-8")).hexdigest()[:8]


def _fingerprint_key(agent: str, cache_key: str) -> str:
    """版本指纹缓存键：基线/偏好/知识/战法/规则 任一版本变更 → 键变 → 缓存自动失效。"""
    version = repo.get_trade_profile().version
    return (f"{cache_key}:v{version}:{_knowledge_version()}:g{_global_base_version()}:"
            f"{_agent_knowledge_version(agent)}:r{_rule_version()}")


def build_agent_context(agent: str, system_prompt: str, user_prompt: str,
                        with_profile: bool = True, with_knowledge: bool = True,
                        knowledge_docs: list | None = None,
                        target_label: str = "") -> tuple[str, str]:
    """统一上下文拼接（agent_call / agentic_call 共用，agentic 不裸传 SYSTEM_PROMPT）：
    sys 段固定序：全局基线→硬性规则→复盘采纳→偏好档案→私有知识→经验→战法→专属 Prompt；
    user 段注入标的标识 + 市场研判参考 + 选股表现回顾。返回 (sys_prompt, user_prompt)。"""
    if target_label:
        user_prompt = f"【本次研判标的】{target_label}\n\n{user_prompt}"
    sections: list[str] = []
    # 拼接位0 · 全局通用知识库基线（最先加载，所有 Agent 统一生效）
    base = global_base_prompt()
    if base:
        sections.append(base)
    # 拼接位1 · 人工硬性锁定规则（统一调教接口·底线）
    rules_section = hard_rules_section()
    if rules_section:
        sections.append(rules_section)
    # 拼接位1.5 · 复盘采纳规则（一键采纳自动落地：DB 动态注入，绝不写源码文件）
    adopted = dynamic_rules_section()
    if adopted:
        sections.append(adopted)
    # 拼接位2 · 个性化交易体系 = 个人交易偏好档案（动态配置）
    if with_profile:
        section = profile_section()
        if section:
            sections.append(
                "【用户个人交易偏好档案】（你的研判必须尊重用户这些偏好，"
                "如有冲突需在输出中说明）\n" + section
            )
    # 拼接位3 · 私有知识库检索结果注入（knowledge_docs 由调用方预取时使用，避免重复检索/重复计量）
    if with_knowledge:
        section, _docs = knowledge_section(agent, docs=knowledge_docs)
        if section:
            sections.append(section)
    # 拼接位3.1 · 自动沉淀经验参考（仅 active 限量注入；与私有知识库共存不冲突）
    exp_section = experience_section(agent)
    if exp_section:
        sections.append(exp_section)
    # 拼接位3.5 · 分职能战法知识库（方法论文本沉淀，参考权重非死条件）
    kb_text = _agent_knowledge_text(agent)
    if kb_text:
        sections.append(
            "【分职能战法知识库】（沉淀自《潜力股发掘方法论》，全部条目为参考权重，"
            "不是死条件；与硬性规则冲突时以硬性规则为准，动态调整须在输出中标注理由）\n"
            + kb_text
        )
    # 拼接位4 · 分职能 Agent 专属 Prompt（独立存放、可单独修改）
    if system_prompt:
        sections.append(system_prompt)
    sys_prompt = "\n\n".join(sections)

    # 拼接位5 · 市场研判底座参考（共享注入：全部 agent 的参考维度，不强制改变任何判级；
    # 当日已有 market_intel 时注入压缩参考文本，无则跳过；读库零额外 LLM 调用）
    try:
        mi = repo.get_latest_market_intel()
    except Exception:  # noqa: BLE001 注入失败不影响主链路
        mi = None
    if mi:
        op = mi.get("operative_meaning") or {}
        # 摘要版：dict/list 值（箱位理解/个股验证）不拼 Python repr 到 prompt
        op_brief = "；".join(
            f"{k}:{v if isinstance(v, str) else ('...' if v else '（空）')}"
            for k, v in list(op.items())[:6])
        vs = mi.get("volume_signal") or {}
        ms = vs.get("主线结构") or {}
        # 主线结构可能是 dict 也可能是字符串，做类型防御
        if isinstance(ms, dict):
            main_brief = "；".join(f"{k}:{v}" for k, v in list(ms.items())[:3])
        elif isinstance(ms, str):
            main_brief = ms
        else:
            main_brief = ""
        vc = vs.get("量能成色") or "（无）"
        user_prompt = (
            f"{user_prompt}\n\n【市场研判参考（{mi.get('trade_date')}，参考维度不强制）】"
            f"阶段定性：{mi.get('phase')}；核心矛盾：{mi.get('core_conflict')}；"
            f"风险偏好：{mi.get('risk_appetite')}；"
            f"主线结构：{main_brief or '（无）'}；量能成色：{vc}；"
            f"操作含义：{op_brief or '（无）'}；一句话总结：{mi.get('summary')}"
        )

    # 拼接位5.5 · 选股表现回顾（仅 discover/discover_final；客观统计，参考不强制，不改变规则）
    if agent in ("discover", "discover_final"):
        try:
            perf_summary = track_verify.get_selection_performance_summary("t5")
        except Exception as exc:  # noqa: BLE001 注入失败不阻塞主链路
            logger.warning("选股表现回顾注入失败（跳过）: %s", exc)
            perf_summary = ""
        if perf_summary:
            user_prompt = (
                f"{user_prompt}\n\n"
                f"【选股表现回顾】（近 20 只有到期数据的候选，客观统计，参考信息不改变已有规则）\n"
                f"{perf_summary}"
            )

    return sys_prompt, user_prompt


def agent_call(agent: str, cache_key: str, system_prompt: str, user_prompt: str,
               schema: Type[T], ttl_seconds: int = 86400,
               with_profile: bool = True, with_knowledge: bool = True,
               model_level: ModelLevel = ModelLevel.DEEP,
               knowledge_docs: list | None = None) -> T:
    """统一 LLM 调用：固定段序拼接 + 版本指纹入缓存键。

    system prompt 段序（永久固定，利于服务端前缀缓存命中）：
    全局通用知识库基线 → 硬性规则 HARD_RULES → 个人交易偏好档案 → 私有知识库检索结果
    → 分职能战法知识库（方法论文本沉淀） → Agent 专属 Prompt
    （动态数据一律在 user 段，前置段同版本内 100% 重复）。

    model_level 声明场景等级：LIGHT=高频轻量（初筛/巡检），DEEP=深度复杂（默认）。"""
    sys_prompt, user_prompt = build_agent_context(
        agent, system_prompt, user_prompt, with_profile=with_profile,
        with_knowledge=with_knowledge, knowledge_docs=knowledge_docs)
    return call_llm_cached(agent, _fingerprint_key(agent, cache_key),
                           sys_prompt, user_prompt, schema, ttl_seconds=ttl_seconds,
                           model_level=model_level)


def agentic_call(agent: str, cache_key: str, system_prompt: str, user_prompt: str,
                 schema: Type[T], ttl_seconds: int = 86400,
                 with_profile: bool = True, with_knowledge: bool = True,
                 model_level: ModelLevel = ModelLevel.DEEP,
                 knowledge_docs: list | None = None,
                 target_label: str = "") -> tuple[T, dict]:
    """agentic 平行通道：build_agent_context 拼上下文 → ReAct 只读工具环（max_rounds=8）。
    产物校验通过 → 结果与单式共用缓存键回写；任一环节失败（None）→ 回退单发，不抛异常。"""
    from app.llm.agentic import run_agentic_judge

    sys_prompt, user_prompt = build_agent_context(
        agent, system_prompt, user_prompt, with_profile=with_profile,
        with_knowledge=with_knowledge, knowledge_docs=knowledge_docs,
        target_label=target_label)
    full_key = _fingerprint_key(agent, cache_key)
    result, trace = run_agentic_judge(
        sys_prompt, user_prompt, schema, TOOLS, TOOL_FUNCS,
        max_rounds=8, model_level=model_level)
    if result is not None:
        cache.set_llm_json(f"{agent}:{_model_for(model_level)}",
                           full_key, result.model_dump(), ttl_seconds)
        return result, trace
    logger.warning("AGENTIC_FALLBACK: agent=%s key=%s 回退单发", agent, cache_key)
    return call_llm_cached(agent, full_key, sys_prompt, user_prompt, schema,
                           ttl_seconds=ttl_seconds, model_level=model_level), {}


def summarize_agentic_trace(trace: dict) -> tuple[str, str]:
    """把 agentic 环过程日志压成两行摘要：思考轨迹 + 工具调用轨迹（供留痕）。"""
    steps = trace.get("trace") or []
    thinking = [s.get("text", "") for s in steps if s.get("kind") == "thinking"]
    tools = [f"轮{s.get('round')} {s.get('tool')}({s.get('args')})"
             for s in steps if s.get("kind") == "tool"]
    return "；".join(thinking), "；".join(tools)
