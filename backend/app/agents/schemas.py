"""
5 个 Agent 的结构化输出模型（pydantic 严格校验，强制 JSON）
所有市场研判结论均出自 LLM，模型定义只约束结构，不含任何业务阈值。
"""
from pydantic import BaseModel, Field


# ================= DiscoverAgent 潜力发掘 =================
class DiscoverDimension(BaseModel):
    """v3.0 白盒维度归因：单维度结论（dimensions 数组元素）"""
    dim: str = Field(description="维度名（固定五维）：基本面/技术趋势/资金/游资/舆情/风险/行业景气")
    score: float = Field(default=0, ge=0, le=100, description="该维度支持度评分 0-100")
    verdict: str = Field(default="中性", description="该维度结论三态：支持/中性/风险")
    advice: str = Field(default="", description="该维度针对性建议（1 句话）")


class DiscoverCandidate(BaseModel):
    """v3.0 输出格式强制升级：白盒维度归因框架（dimensions 数组 + final_advice 主结论）+
    代码+全称成对、K202 信心度档位、三维分析、量能判定、核心风险（≥2 项）、关注类型、
    标的类型标识；旧字段（macro/meso/micro/volume/tech）降为补充说明。"""
    stock_code: str = Field(description="6 位股票代码")
    stock_name: str = Field(description="股票全称（与代码成对出现）")
    reason: str = Field(description="候选理由（结合量能/趋势/行业热度/基本面预期的研判）")
    risk_notice: str = Field(description="风险初步判断")
    stock_type: str = Field(
        pattern="^(吸筹末期-优选型|拉升初期-突破型|拉升中段-趋势型|派发期-高风险型|下跌期-反弹型|观察期-蓄势型)$",
        description="标的类型标识（威科夫阶段定位 6 类）：吸筹末期-优选型/拉升初期-突破型/"
                    "拉升中段-趋势型/派发期-高风险型/下跌期-反弹型/观察期-蓄势型")
    confidence_tier: str = Field(
        pattern="^(谨慎观察|建议关注|强烈推荐)$",
        description="K202 信心度档位：谨慎观察/建议关注/强烈推荐")
    confidence_pct: float = Field(ge=0, le=100, description="信心度百分比参考")
    dimensions: list[DiscoverDimension] = Field(default_factory=list,
        description="维度归因数组（v3.0 主结论）：五维逐项 {dim/score/verdict/advice}")
    final_advice: str = Field(default="",
        description="综合评估（v3.0 主结论）：「综合评估：N/5 维支持，结论，止损-8%，主要风险…」")
    macro_view: str = Field(description="宏观维度核心判断（补充说明）")
    meso_view: str = Field(description="中观维度核心判断（补充说明）")
    micro_view: str = Field(description="微观维度核心判断（补充说明）")
    volume_analysis: str = Field(description="量能判定：资金结构、主力动向结论（补充说明）")
    risks: list[str] = Field(min_length=2, description="核心风险清单（至少 2 项）")
    focus_type: str = Field(pattern="^(低吸|突破|观察)$", description="关注类型：低吸/突破/观察")
    tech_view: str = Field(default="",
        description="技术面研判（威科夫/量价/K线形态/谐波至少两套体系交叉验证，标注体系与支撑依据，补充说明）")
    price_levels: str = Field(default="", description="关键价位（支撑位/压力位/建议关注区间）")
    position_hint: str = Field(default="", description="操作建议（低吸/突破/观望 + 参考仓位建议）")
    rule_refs: list[str] = Field(default_factory=list,
        description="引用的规则/战法清单（K 编号、战法名、人工硬性规则），留痕可溯源")


class DiscoverOutput(BaseModel):
    """每日候选池输出"""
    market_summary: str = Field(description="当日市场环境一句话简述")
    candidates: list[DiscoverCandidate] = Field(description="候选标的列表，按优先级排序")


# ================= 市况评分（v2.0 Discover 前置步骤） =================
class MarketConditionOutput(BaseModel):
    """市况五维打分（LLM 输出各维度 0-10 分；代码仅求和 0-50 并按档位映射候选池上限，
    代码不做任何市场判断）"""
    dim_index: int = Field(ge=0, le=10, description="指数位置维度得分 0-10（大盘位置/趋势强弱）")
    dim_sector: int = Field(ge=0, le=10, description="板块结构维度得分 0-10（板块普涨共振程度）")
    dim_money: int = Field(ge=0, le=10, description="资金方向维度得分 0-10（主力资金流向）")
    dim_sentiment: int = Field(ge=0, le=10, description="情绪指标维度得分 0-10（涨跌家数/赚钱效应）")
    dim_risk: int = Field(ge=0, le=10, description="风险维度得分 0-10（风险越高得分越低）")
    summary: str = Field(description="当日市况一句话综述（含操作节奏建议）")


# ================= ScoreAgent 多维打分 =================
class ScoreDimension(BaseModel):
    """v3.0 白盒维度归因：单维度结论（资金流向维度内部体现游资信号）"""
    dim: str = Field(description="维度名（固定五维）：基本面/技术趋势/资金流向/舆情风险/行业景气")
    score: int = Field(ge=0, le=100, description="该维度得分 0-100")
    verdict: str = Field(default="中性", description="该维度结论三态：支持/中性/风险")
    advice: str = Field(default="", description="该维度针对性建议（1 句话，引用具体数据）")


class ScoreOutput(BaseModel):
    stock_code: str
    stock_name: str
    score: int = Field(ge=0, le=100, description="综合得分 0-100")
    grade: str = Field(pattern="^[ABC]$", description="综合评级 A/B/C")
    dimensions: list[ScoreDimension] = Field(description="五个维度评分明细（dim/score/verdict/advice）")
    risk_list: list[str] = Field(description="风险清单（减持/质押/立案/业绩暴雷/估值过高等）")
    final_advice: str = Field(default="",
        description="综合评估（v3.0）：「综合评估：N/5 维支持，总分 XX 分（X 级），结论，止损-8%，主要风险…」")


# ================= PositionAgent 仓位规划 =================
class PositionBatch(BaseModel):
    tranche: int = Field(description="第几批（1-4）")
    price_zone: str = Field(description="该批建议价格区间（如 '现价 23.5~24.0' 或 '回踩 MA20 22.3~22.8'）")
    ratio_pct: float = Field(gt=0, le=100, description="该批占总资金比例 %")
    trigger_note: str = Field(description="该批建仓触发条件说明")


class PositionOutput(BaseModel):
    stock_code: str
    market_regime: str = Field(description="当前市场强弱判断（如 强势/震荡/弱势）及其依据")
    total_pct: float = Field(gt=0, le=100, description="总仓位上限 %（结合评分与市场强弱动态调整）")
    batches: list[PositionBatch] = Field(description="分批建仓明细（3-4 批）")
    stop_loss: float = Field(gt=0, description="初始止损参考价")
    take_profit: float = Field(gt=0, description="止盈参考价")
    rationale: str = Field(description="建仓逻辑说明")
    dimensions: list[DiscoverDimension] = Field(default_factory=list,
        description="维度归因数组（v3.0 主结论）：五维逐项 {dim/score/verdict/advice}")
    final_advice: str = Field(default="",
        description="综合评估（v3.0 主结论）：「综合评估：N/5 维支持，可分批建仓，总仓位 X%，止损-8%，主要风险…」")


# ================= MonitorAgent 持仓监控 =================
class MonitorOutput(BaseModel):
    action: str = Field(pattern="^(hold|reduce|exit)$", description="建议：hold=持有 / reduce=减仓 / exit=清仓")
    severity: str = Field(pattern="^(info|warning|critical)$", description="严重度")
    alert_type: str = Field(description="触发类型（如 触及止损/趋势破位/突发利空/触及止盈/政策变动/常规跟踪）")
    message: str = Field(description="推送给用户的告警文案（含关键数据）")
    reasons: list[str] = Field(description="研判依据（引用具体数据）")
    key_levels: dict[str, float] = Field(description="当前关注的关键价位（如 支撑/压力/止损/止盈）")


# ================= SellAgent 卖出决策 =================
class SellOutput(BaseModel):
    """卖出决策输出（决策仅供参考，卖出由人工执行）"""
    stock_code: str
    action: str = Field(pattern="^(hold|partial|sell)$",
                        description="建议：hold=继续持有 / partial=部分减仓 / sell=卖出清仓")
    confidence: str = Field(pattern="^(high|medium|low)$", description="决策置信度")
    reasons: list[str] = Field(description="决策依据（引用具体数据与近期监控信号）")
    exit_price_zone: str = Field(description="建议卖出价格区间或触发条件（如 '反弹至 26.5 附近' / '跌破 24.8 离场'）")
    risk_warning: str = Field(description="继续持有的主要风险提示")
    check_list: list[str] = Field(description="人工卖出前需核对事项（仓位/税费/资金安排等）")
    dimensions: list[DiscoverDimension] = Field(default_factory=list,
        description="维度归因数组（v3.0 主结论）：五维逐项 {dim/score/verdict/advice}")
    final_advice: str = Field(default="",
        description="综合评估（v3.0 主结论）：「综合评估：N/5 维偏离，建议动作，止损位（成本×0.92），主要风险…」")


# ================= ReviewAgent 卖出复盘 =================
class ProfileSuggestion(BaseModel):
    """交易偏好优化建议（前端提供一键采纳/驳回，采纳后更新 sys_trade_profile）"""
    field: str = Field(description="建议修改的偏好字段名（如 单票仓位上限/选股倾向/风控容忍度）")
    value: object = Field(description="建议的新值")
    reason: str = Field(description="建议理由（引用本次复盘事实）")


class AgentSuggestionItem(BaseModel):
    """对指定 Agent 规则/参数的优化建议（策略闭环·复盘进化）
    ⚠️ 任何建议仅作为提案，必须经人工审核确认后生效，禁止自动、无监督修改。
    一键采纳自动落地 v2：prompt 类建议须给出 rule_text 完整规则条文（可落地生效），
    由系统写入 rule_change 表经 agent_call 管道动态注入（绝不写源码文件）。"""
    target_agent: str = Field(description="建议针对的 Agent：discover/score/position/monitor/sell/review")
    target_kind: str = Field(
        pattern="^(profile|prompt)$",
        description="生效方式：profile=直接写入个人交易偏好档案（字段级）；"
                    "prompt=规则类建议，rule_text 给出完整规则条文，人工确认后由系统自动注入")
    rule_name: str = Field(description="规则/参数名称（如 单票仓位上限 或 'Monitor 趋势破位判定标准'）")
    current_value: str = Field(description="当前值（现有规则的现状表述）")
    suggested_value: str = Field(description="建议值（优化要点摘要，供列表速览）")
    reason: str = Field(description="建议理由（引用本次交易落地表现）")
    evidence: str = Field(description="事实依据（如 入场逻辑与走势偏差的具体数据）")
    # ---------- v2 一键采纳落地信息（prompt 类必填） ----------
    rule_type: str = Field(default="soft", pattern="^(soft|hard)$",
        description="规则类型：soft=提示词软规则（参考权重）；hard=代码硬规则（全局底线，无条件遵守）")
    priority: str = Field(default="medium", pattern="^(high|medium|low)$",
        description="优先级：high=高（紧急）/medium=中/low=低")
    rule_text: str = Field(default="",
        description="优化后的完整规则条文（可直接落地的规则原文，与 HARD_RULES/提示词规则格式一致，"
                    "禁止『建议增加…』等无执行语义的表述；prompt 类建议必填）")
    problem_desc: str = Field(default="",
        description="当前问题说明（现有规则的具体缺陷精准到场景 + 本次复盘触发的案例与影响）")
    expected_effect: str = Field(default="",
        description="预期效果（量化：胜率/盈亏比/回撤等指标维度）与影响范围（业务环节/标的类型）")
    risk_note: str = Field(default="",
        description="规则生效的副作用/风险提示与注意事项")
    file_path: str = Field(default="",
        description="规则应归属的文件路径（如 agent_prompts/monitor_prompt.py 或 common.py HARD_RULES；"
                    "仅展示元数据，系统绝不写源码文件）")
    insert_position: str = Field(default="",
        description="建议插入位置（新增/替换/补充到哪条规则之下；仅展示元数据）")


class ReviewOutput(BaseModel):
    plan_vs_actual: dict = Field(description="建仓原始逻辑 vs 实际走势兑现情况：{入场逻辑, 兑现程度, 关键偏差, 复盘结论}")
    lesson: str = Field(description="本次交易的经验教训")
    feedback: dict = Field(description="对后续筛选规则的偏好微调建议：{偏好, 调整方向, 理由}")
    profile_suggestion: ProfileSuggestion | None = Field(default=None,
        description="对个人交易偏好档案的优化建议（可采纳/驳回）")
    agent_suggestions: list[AgentSuggestionItem] = Field(default_factory=list,
        description="对全链路各 Agent 规则/参数的优化建议（仅提案，必须人工审核确认后生效）")
    hot_money_review: dict | None = Field(default=None,
        description="游资信号有效性回溯结论（失败标的复盘时输出）：{classification, signal_effective, "
                    "basis, weight_suggestion}；无游资信号可回溯时输出 null。只留痕，不直接改任何配置")


class TrackVerifyOutput(BaseModel):
    """选股验证统计建议输出（候选池 T+N 追踪验证 Agent 输出）
    建议仅作为提案，必须经人工审核确认后生效（走 agent_suggestions 审核闭环）"""
    summary_note: str = Field(default="", description="本轮统计要点自评（一句话）")
    agent_suggestions: list[AgentSuggestionItem] = Field(default_factory=list,
        description="选股规则优化建议（基于统计事实；无显著异常时输出空列表，绝不为了输出而输出）")
