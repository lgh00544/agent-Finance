"""
Agent 公共工具：统一调教接口 + 统一 LLM 调用入口

【统一调教接口（全部 Agent 平等开放）】
0. 全局通用知识库基线（agent_prompts/global_base_prompt.md）：所有 Agent 每次任务【最先】加载，
   A股规则 / 基准本金(36943) / 系统边界 / 技术分析执行标准 / 思考推理强制准则 / 预留扩展插槽；
1. 硬性规则（HARD_RULES）：人工锁定的业务底线，所有 Agent 无条件遵守，LLM 不得放宽；
2. 个人交易偏好档案（sys_trade_profile）：所有 Agent 自动注入，页面可视化编辑即时生效；
3. 私有知识库（private_knowledge）：每个 Agent 启动任务时自动检索对应交易经验/战法资料注入。

【刚性代码逻辑】以上全部为上下文注入，不参与任何市场判断；基线/偏好/知识版本号入缓存键，
人工修改后 LLM 缓存自动失效、立即生效。
"""
import hashlib
import logging
from pathlib import Path
from typing import Type, TypeVar

from app.db import repo
from app.llm.structured import ModelLevel, call_llm_cached
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


def profile_section() -> str:
    """个人交易偏好档案 → prompt 注入文本"""
    content = repo.get_trade_profile_content()
    if not content:
        return ""
    lines = [f"- {k}: {v}" for k, v in content.items() if v is not None and v != ""]
    return "\n".join(lines) if lines else ""


def knowledge_section(agent: str) -> str:
    """私有交易经验/战法知识库 → prompt 注入文本（统一运行机制：任务启动自动检索）"""
    from app.services.vector_store import get_vector_store

    try:
        docs = get_vector_store().search_knowledge(agent, top_k=5)
    except Exception as exc:  # noqa: BLE001 知识检索失败不阻塞主链路
        logger.warning("私有知识检索失败 %s: %s", agent, exc)
        return ""
    if not docs:
        return ""
    lines = [f"- 【{d['title']}】{d['content']}" for d in docs]
    return ("【你的私有交易经验/战法参考】（来自个人知识库，请结合这些经验进行研判，"
            "若与硬性规则冲突以硬性规则为准）\n" + "\n".join(lines))


def _knowledge_version() -> str:
    """知识库变更感知（数量+最大ID），入缓存键使知识更新后 LLM 缓存自动失效"""
    try:
        count, max_id = repo.knowledge_version()
        return f"k{count}:{max_id}"
    except Exception:  # noqa: BLE001
        return "k0:0"


def agent_call(agent: str, cache_key: str, system_prompt: str, user_prompt: str,
               schema: Type[T], ttl_seconds: int = 86400,
               with_profile: bool = True, with_knowledge: bool = True,
               model_level: ModelLevel = ModelLevel.DEEP) -> T:
    """统一 LLM 调用：固定段序拼接 + 版本指纹入缓存键。

    system prompt 段序（永久固定，利于服务端前缀缓存命中）：
    全局通用知识库基线 → 硬性规则 HARD_RULES → 个人交易偏好档案 → 私有知识库检索结果
    → Agent 专属 Prompt（动态数据一律在 user 段，前置段同版本内 100% 重复）。

    model_level 声明场景等级：LIGHT=高频轻量（初筛/巡检），DEEP=深度复杂（默认）。"""
    sections: list[str] = []
    # 拼接位0 · 全局通用知识库基线（最先加载，所有 Agent 统一生效）
    base = global_base_prompt()
    if base:
        sections.append(base)
    # 拼接位1 · 人工硬性锁定规则（统一调教接口·底线）
    rules_section = hard_rules_section()
    if rules_section:
        sections.append(rules_section)
    # 拼接位2 · 个性化交易体系 = 个人交易偏好档案（动态配置）
    if with_profile:
        section = profile_section()
        if section:
            sections.append(
                "【用户个人交易偏好档案】（你的研判必须尊重用户这些偏好，"
                "如有冲突需在输出中说明）\n" + section
            )
    # 拼接位3 · 私有知识库检索结果注入
    if with_knowledge:
        section = knowledge_section(agent)
        if section:
            sections.append(section)
    # 拼接位4 · 分职能 Agent 专属 Prompt（独立存放、可单独修改）
    if system_prompt:
        sections.append(system_prompt)
    sys_prompt = "\n\n".join(sections)

    version = repo.get_trade_profile().version
    return call_llm_cached(agent,
                           f"{cache_key}:v{version}:{_knowledge_version()}:g{_global_base_version()}",
                           sys_prompt, user_prompt, schema, ttl_seconds=ttl_seconds,
                           model_level=model_level)
