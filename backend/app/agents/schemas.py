"""
5 个 Agent 的结构化输出模型（pydantic 严格校验，强制 JSON）
所有市场研判结论均出自 LLM，模型定义只约束结构，不含任何业务阈值。
"""
from pydantic import BaseModel, Field, field_validator, model_validator


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
    # ============ 前瞻兑现（第 5 子 Agent 收口三态） ============
    # 默认值保证旧缓存/旧输出可 parse、新逻辑缺字段不炸（同 MarketIntel v3 理由）。
    # LLM 只允许输出这三字之一，不得报涨跌幅/目标价/概率百分数（common.py 纪律）。
    horizon_bias: str = Field(default="回归", pattern="^(延续|回归|回吐)$",
        description="前瞻兑现三态：延续/回归/回吐（未来 5 日更可能延续、方向不明、还是吐回去；只看注入的【前瞻对照事实】定性，禁止输出涨跌幅数字）")
    horizon_clarity: str = Field(default="低", pattern="^(高|中|低)$",
        description="前瞻清晰度：高/中/低（关键列缺失或同类样本不足 → 低）")
    horizon_note: str = Field(default="前瞻数据不足",
        description="前瞻依据一句话（40-80 字，必须引用注入事实中的具体数字/桶，不得空话）")


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


class MarketIntelOutput(BaseModel):
    """市场研判底座输出（5 大思考维度引导的深度理解，非打分；数据缺失须明确标注不编造）"""
    phase: str = Field(description="行情阶段定性（启动/主升/分化/存量博弈/弱势…，给一句依据）")
    core_conflict: str = Field(description="核心矛盾（增量 vs 存量资金，一段话）")
    risk_appetite: str = Field(pattern="^(进取|中性|避险)$", description="风险偏好三态")
    volume_signal: dict = Field(
        description="量能信号：放量/缩量板块分布、极端天量标注（脉冲或趋势）；数据缺失明确标注")
    operative_meaning: dict = Field(
        description="操作含义：精选方向/回避方向/买点标准（参考维度，不强制）")
    next_day_watch: dict = Field(description="次日盯盘点（前向可验证的观察点）")
    summary: str = Field(description="一句话总结（供全部 agent 注入参考）")

    # v3 调整：以下 4 个新字段全部带默认值（default_factory）。
    # 原因：Prompt 方法论由 sir 另行提供，本次不注入；默认值保证 LLM 未输出时研判正常。
    # 待 sir 的 prompt 到位后，移除 default_factory 即可激活强制结构化输出。
    main_structure: dict = Field(
        default_factory=dict,
        description="主线结构三分类。包含三个 key："
                    "'进攻主线'（连续多日走强+隔夜催化源，含方向名+连续天数+催化源+一句依据）、"
                    "'接力方向'（低位放量启动+直系催化，含方向名+量倍+60日箱位+催化源+一句依据）、"
                    "'退潮方向'（资金流出+箱位验证，含方向名+箱位特征+一句依据）。"
                    "某分类无数据时填 '（今日无明确该类方向）'，不编造")
    box_view: dict = Field(
        default_factory=dict,
        description="箱位理解：重点板块的主箱位/60日箱位组合解读。"
                    "每个板块一个 key，value 含 'main_box'(主箱位%)、'box60'(60日箱位%)、"
                    "'interpretation'(解读：主升初期/出货风险/高位震荡等)。"
                    "核心认知——短箱贴顶+60日箱位低(<40%)=主升初期波段空间仍在；"
                    "长短双高(≈100%/100%)=真出货风险。只解读数据实际提供的板块，缺失标注")
    volume_character: str = Field(
        default="",
        description="量能成色定性一句话。必须引用量倍数值与口径，如"
                    "'量倍1.15温和放大，结构性行情而非全面牛市'。"
                    "禁止只写'放量/缩量'不给量级。数据缺失时写'量倍数据缺失，基于板块量比推断：...'")
    stock_verification: list = Field(
        default_factory=list,
        description="个股强度三维验证（仅主线板块内抽样≤5只）。每只含"
                    "'name'(名称)、'change_pct'(涨幅%)、'volume_ratio'(量倍)、"
                    "'box60'(60日箱位%，缺失写None)、'verdict'(真强/加速后段/放量滞涨/弱势)、"
                    "'basis'(一句依据)。数据缺失的个股也要列出，verdict标注'数据不足'")


# ================= ScoreAgent 六因子透明评分 =================
_FACTOR_NAMES = {"动量", "催化", "估值", "主线契合", "资金面", "基本面质量"}


class PrefilterOutput(BaseModel):
    """两段式粗筛输出（LIGHT 低成本预判；保守主义：宁漏成本不可漏票）。
    keep_codes 为空 = 回退全量精打（安全阀 1，防误杀）。"""
    keep_codes: list[str] = Field(default_factory=list, description="建议精打名单（候选代码列表）")
    reason: str = Field(default="", description="一句话说明本次粗筛取舍（可空）")


class ScoreFactor(BaseModel):
    """v4.0 透明多因子评分项：每因子 0-10 + 打分依据 + 信号方向"""
    factor: str = Field(
        description="因子名（固定六因子）：动量/催化/估值/主线契合/资金面/基本面质量")
    score: int = Field(ge=0, le=10, description="该因子得分 0-10（整数）")
    reason: str = Field(
        description="打分依据（引用具体数据，如 'MA20上方多头排列，MACD金叉，5日涨幅3.2%'，中文 30-80 字）")
    signal: str = Field(
        pattern="^(看多|中性|看空)$",
        description="该因子信号方向：看多/中性/看空")


class ScoreOutput(BaseModel):
    """v4.0 六因子透明评分体系"""
    stock_code: str
    stock_name: str
    score: int = Field(ge=0, le=100,
        description="综合得分 0-100（六因子加权汇总，权重见 prompt）")
    grade: str = Field(pattern="^[ABC]$", description="综合评级 A/B/C")
    factors: list[ScoreFactor] = Field(
        description="六因子评分明细（factor/score/reason/signal），恰好 6 项")
    potential_flag: bool = Field(default=False,
        description="潜力标识：催化因子≥7 且 动量因子≤4 = 催化尚未被定价，值得重点关注")
    cross_validation_note: str = Field(default="",
        description="与 DiscoverAgent 选股逻辑的交叉验证结论（一段话，引用 Discover 理由与 Score 因子对比）")
    risk_list: list[str] = Field(description="风险清单（减持/质押/立案/业绩暴雷/估值过高等）")
    final_advice: str = Field(default="",
        description="综合评估：「综合评估：N/6 因子看多，总分 XX 分（X 级），结论，止损-8%，主要风险…」；"
                    "potential_flag=true 时追加「⚠️ 潜力标识：催化强但动量弱，可能尚未被定价」")

    @model_validator(mode="after")
    def _check_six_factors(self):
        """强校验：factors 必须恰好为六因子且名称固定。
        校验失败抛 ValidationError → 走 llm_call_json 既有重试机制（structured.py:84-131），
        不新增崩溃路径。"""
        names = [f.factor for f in self.factors]
        if len(names) != 6 or set(names) != _FACTOR_NAMES:
            raise ValueError(
                f"factors 必须恰好为六因子且名称固定，收到 {names}（期望 {sorted(_FACTOR_NAMES)}）")
        return self


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
    reduce_ratio: float | None = Field(default=None, ge=0.0, le=1.0,
        description="建议减仓比例 0.0-1.0（如 0.33=减1/3，0.5=减1/2）；仅 action=partial 时有值，"
                    "hold/sell 为 None；超出值域由 pydantic 校验拦截")
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


# ================= 通用审核 Agent（批1：辩证审核 agent_suggestion 建议） =================
class AuditOutput(BaseModel):
    """辩证审核裁决：强制正反辩论 + 具体反例 + 边界场景 + 基础库引用"""
    verdict: str = Field(description="pass/fail：fail=建议有实质缺陷需重思考")
    confidence: int = Field(description="置信度 0-100")
    support_view: str = Field(description="支持意见，≥30 字")
    dissent_view: str = Field(description="反对意见，≥50 字且必含 1 个具体反例/场景")
    boundary_cases: str = Field(default="", description="边界场景（什么情况下结论会失效），≥30 字")
    evidence_refs: list[str] = Field(default_factory=list,
        description="证据引用，至少 1 条，格式 K223 / knowledge_id=42 / rule_change#15")
    one_line_summary: str = Field(description="一句话摘要，≤40 字")

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, v):
        if isinstance(v, float) and 0 <= v <= 1:
            return round(v * 100)
        return v

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def _normalize_evidence_refs(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [v]
        return v


# ================= PortfolioSentinel 组合哨兵（组合级风控，与 MonitorAgent 零耦合） =================
class SectorAlert(BaseModel):
    """板块退潮预警（LLM 研判：板块是否从强势转弱势/量比显著下降）"""
    stock_code: str = Field(description="6 位股票代码")
    stock_name: str = Field(description="股票名称")
    sector: str = Field(description="所属板块")
    sector_change_pct: float | None = Field(default=None, description="板块当日涨跌幅 %（数据缺失为 null）")
    sector_volume_ratio: float | None = Field(default=None, description="板块量比（数据缺失为 null）")
    alert_level: str = Field(pattern="^(高|中|低)$", description="预警级别：高/中/低")
    reason: str = Field(description="预警理由（引用具体数据；数据不足时如实标注「数据不足」不编造）")


class TimeStopAlert(BaseModel):
    """时间止损预警（LLM 研判：持仓天数超过偏好周期一半且浮盈亏在 ±2% 内=横盘建议退出）"""
    stock_code: str = Field(description="6 位股票代码")
    stock_name: str = Field(description="股票名称")
    holding_days: int = Field(description="持仓天数")
    pnl_pct: float | None = Field(default=None, description="当前浮盈亏 %（现价缺失为 null）")
    verdict: str = Field(description="结论（如 建议退出/继续持有观察）")
    reason: str = Field(description="研判理由（引用持仓天数与盈亏数据）")


class PortfolioRisk(BaseModel):
    """组合风险快照（代码纯数学计算，非 LLM 输出）"""
    total_pnl_pct: float | None = Field(default=None, description="组合总盈亏 %（Σ市值-Σ成本）/Σ成本")
    max_sector_pct: float | None = Field(default=None, description="最大板块持仓占比 %（集中度）")
    drawdown_alert: bool = Field(description="组合回撤预警（总盈亏 < -3%）")
    concentration_alert: bool = Field(description="集中度预警（同板块持仓合计占总市值 > 40%）")


class ActionSuggestion(BaseModel):
    """行动建议（仅供参考，人工执行）"""
    stock_code: str = Field(description="6 位股票代码")
    suggestion: str = Field(description="行动建议（如 减仓/离场/观望/继续持有）")
    reason: str = Field(description="建议理由")


class PortfolioSentinelOutput(BaseModel):
    """组合哨兵输出（LIGHT 模型高频巡检）"""
    sector_alerts: list[SectorAlert] = Field(default_factory=list,
        description="板块退潮预警列表（无预警输出空列表，绝不为了输出而输出）")
    time_stop_alerts: list[TimeStopAlert] = Field(default_factory=list,
        description="时间止损预警列表（无预警输出空列表）")
    portfolio_risk: PortfolioRisk = Field(description="组合风险快照（代码已算好，LLM 原文透传）")
    overall_assessment: str = Field(description="一句话组合风险评估（引用组合盈亏/集中度/板块信号）")
    action_suggestions: list[ActionSuggestion] = Field(default_factory=list,
        description="行动建议列表（仅供参考，人工执行）")


class TrackVerifyOutput(BaseModel):
    """选股验证统计建议输出（候选池 T+N 追踪验证 Agent 输出）
    建议仅作为提案，必须经人工审核确认后生效（走 agent_suggestions 审核闭环）"""
    summary_note: str = Field(default="", description="本轮统计要点自评（一句话）")
    agent_suggestions: list[AgentSuggestionItem] = Field(default_factory=list,
        description="选股规则优化建议（基于统计事实；无显著异常时输出空列表，绝不为了输出而输出）")


# ==================== 经验沉淀闭环：LLM 抽取草稿 / 冲突判定 ====================

class ExperienceDraft(BaseModel):
    """经验抽取草稿（Worker 离线识别输出；pydantic 严格校验，强制 JSON）
    仅约束结构，不含任何业务阈值；impact/confidence 的裁定见 route_draft。"""
    worth: bool = Field(description="是否含可沉淀经验")
    title: str = Field(default="", description="经验标题")
    body: str = Field(default="", description="经验正文（具体、可复用、严禁编造）")
    stage: str = Field(default="选股", description="选股|建仓|持仓")
    tags: list[str] = Field(default_factory=list, description="标签（板块/形态/指标）")
    impact: str = Field(default="low", description="high|low（涉及规则/标准修改→high；纯观测→low）")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="抽取置信度 0-1")
    reason: str = Field(default="", description="为何值得沉淀")


class RouteConflict(BaseModel):
    """冲突判定结果（自动合并前 LLM 两段式判定第二段）"""
    conflict: bool = Field(default=False, description="是否存在结论相反的经验")
    conflicting_ids: list[int] = Field(default_factory=list, description="冲突候选经验 id")
    reason: str = Field(default="", description="冲突判断依据（一句话）")
