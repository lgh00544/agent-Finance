"""
ORM 模型 - MySQL8 / SQLite 共用同一套模型
JSON 字段用 Text 存储（SQLAlchemy JSON 在 SQLite/MySQL 均可，但 MySQL 原生 JSON 列
对 SQLAlchemy 2.0 友好；统一用 JSON 类型，SQLite 自动映射为 TEXT）。
"""
from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now()


class StockCandidate(Base):
    """每日候选池（DiscoverAgent 输出）"""
    __tablename__ = "stock_candidate"
    __table_args__ = (
        UniqueConstraint("stock_code", "trade_date", name="uq_candidate_code_date"),
        Index("ix_candidate_date_rank", "trade_date", "rank"),  # 按日期取当日候选并排序
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64))
    trade_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    rank: Mapped[int] = mapped_column(Integer, default=0)            # 候选排序（LLM 输出）
    reasons: Mapped[list] = mapped_column(JSON, default=list)        # 候选理由（LLM 输出）
    risk_notice: Mapped[list] = mapped_column(JSON, default=list)    # 风险初判（LLM 输出）
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)       # 当日原始行情快照（计算层）
    detail: Mapped[dict] = mapped_column(JSON, default=dict)         # v2.0 输出详情（信心度/三维/量能/风险/关注类型 + 增量数据）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MarketCondition(Base):
    """每日市况评分（v2.0 Discover 前置步骤）：LLM 五维打分 + 代码档位映射候选池上限"""
    __tablename__ = "market_condition"
    __table_args__ = (UniqueConstraint("trade_date", name="uq_market_condition_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    total_score: Mapped[int] = mapped_column(Integer)                # 0-50（LLM 五维求和）
    dims: Mapped[dict] = mapped_column(JSON, default=dict)           # 五维明细（LLM 输出）
    cap: Mapped[int] = mapped_column(Integer)                        # 当日候选池上限（档位映射）
    summary: Mapped[str] = mapped_column(Text, default="")           # 市况综述（LLM 输出）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class StockScore(Base):
    """评分结果（ScoreAgent 输出）"""
    __tablename__ = "stock_score"
    __table_args__ = (UniqueConstraint("stock_code", "trade_date", name="uq_score_code_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64))
    trade_date: Mapped[str] = mapped_column(String(10), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)         # 0-100（LLM 输出）
    grade: Mapped[str] = mapped_column(String(4))                    # A/B/C（LLM 输出）
    detail: Mapped[dict] = mapped_column(JSON, default=dict)         # 五维明细（LLM 输出）
    risk_list: Mapped[list] = mapped_column(JSON, default=list)      # 风险清单（LLM 输出）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class PositionPlan(Base):
    """分批建仓方案（PositionAgent 输出）"""
    __tablename__ = "position_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64))
    plan_date: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(16), default="proposed")  # proposed/accepted/expired
    total_pct: Mapped[float] = mapped_column(Float, default=0.0)     # 总仓位上限 %（LLM 输出）
    batches: Mapped[list] = mapped_column(JSON, default=list)        # 分批明细（LLM 输出）
    stop_loss: Mapped[float] = mapped_column(Float, default=0.0)     # 止损参考价（LLM 输出）
    take_profit: Mapped[float] = mapped_column(Float, default=0.0)   # 止盈参考价（LLM 输出）
    rationale: Mapped[str] = mapped_column(Text, default="")         # 建仓逻辑（LLM 输出）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Holding(Base):
    """持仓记录（人工录入，监控对象）"""
    __tablename__ = "holding"
    __table_args__ = (Index("ix_holding_status", "status"),)  # 筛选有效持仓（巡检/首页）

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64))
    entry_date: Mapped[str] = mapped_column(String(10))              # 建仓日期
    entry_price: Mapped[float] = mapped_column(Float)                # 平均建仓成本价
    shares: Mapped[int] = mapped_column(Integer)                     # 当前股数
    cost: Mapped[float] = mapped_column(Float, default=0.0)          # 总成本（元）
    stop_loss: Mapped[float] = mapped_column(Float, default=0.0)     # 止损参考价（Plan/人工）
    take_profit: Mapped[float] = mapped_column(Float, default=0.0)   # 止盈参考价
    target_pct: Mapped[float] = mapped_column(Float, default=0.0)    # 目标仓位 %
    status: Mapped[str] = mapped_column(String(16), default="holding")  # holding/exited
    plan_id: Mapped[int] = mapped_column(Integer, nullable=True)     # 关联 position_plan.id
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class TradeRecord(Base):
    """手工交易流水（买卖均由人工执行后录入，系统不做任何下单）"""
    __tablename__ = "trade_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    holding_id: Mapped[int] = mapped_column(Integer, index=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    side: Mapped[str] = mapped_column(String(8))                     # buy/sell/adjust
    price: Mapped[float] = mapped_column(Float)
    shares: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float)                     # 成交金额
    trade_date: Mapped[str] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(Text, default="")
    before_shares: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 操作前股数（K223 留痕）
    after_shares: Mapped[int | None] = mapped_column(Integer, nullable=True)   # 操作后股数（K223 留痕）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AlertLog(Base):
    """告警日志（MonitorAgent 触发，飞书推送记录）"""
    __tablename__ = "alert_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64))
    alert_type: Mapped[str] = mapped_column(String(32), index=True)  # 由 LLM 信号决定
    severity: Mapped[str] = mapped_column(String(8), default="info")  # info/warning/critical
    message: Mapped[str] = mapped_column(Text)                       # 飞书推送文案（LLM 输出）
    action: Mapped[str] = mapped_column(String(16), default="hold")  # hold/reduce/exit（LLM 输出）
    signal: Mapped[dict] = mapped_column(JSON, default=dict)         # 完整信号结构化输出
    pushed: Mapped[bool] = mapped_column(Boolean, default=False)     # 是否已推飞书
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ReviewResult(Base):
    """卖出复盘（ReviewAgent 输出）"""
    __tablename__ = "review_result"
    __table_args__ = (Index("ix_review_exit_status", "exit_date", "suggest_status"),)  # 近期复盘/待审核

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64))
    holding_id: Mapped[int] = mapped_column(Integer, index=True)
    exit_date: Mapped[str] = mapped_column(String(10))
    hold_days: Mapped[int] = mapped_column(Integer, default=0)
    pnl_pct: Mapped[float] = mapped_column(Float, default=0.0)       # 盈亏 %
    plan_vs_actual: Mapped[dict] = mapped_column(JSON, default=dict) # 计划兑现度（LLM 输出）
    lesson: Mapped[str] = mapped_column(Text, default="")            # 经验教训（LLM 输出）
    feedback: Mapped[dict] = mapped_column(JSON, default=dict)       # 筛选偏好微调建议（LLM 输出）
    # ---------- 建议驳回迭代（人工审核闭环） ----------
    suggest_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending=待审核 / adopted=已采纳 / rejected=已驳回
    reject_reason: Mapped[str] = mapped_column(Text, default="")     # 最近一次驳回原因（必填）
    suggest_iteration: Mapped[int] = mapped_column(Integer, default=1)  # 建议迭代次数（第几版）
    suggest_history: Mapped[list] = mapped_column(JSON, default=list)   # 迭代轨迹 [{iteration, suggestion, reject_reason}]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AiReasoningTrace(Base):
    """AI 研判推理链路留痕（全模块通用：discover候选池/score评分/position建仓/
    monitor持仓监控/alert告警/review复盘/sell卖出决策）

    一次生成、结构化入库、多端复用；纠察复盘Agent 的「决策黑匣子」数据源。
    同 code+generate_date+source_module 保留最新一次研判（写入覆盖，uq 约束天然支撑
    联合查询，无需重复建普通联合索引；长文本列一律不建索引）。
    """
    __tablename__ = "ai_reasoning_trace"
    __table_args__ = (
        UniqueConstraint("stock_code", "generate_date", "source_module",
                         name="uq_trace_code_date_module"),
        Index("ix_trace_module_date", "source_module", "generate_date"),  # 模块+日期批量查询
    )

    trace_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64))            # 禁止只存代码不存名称
    source_module: Mapped[str] = mapped_column(String(16), index=True)  # discover/score/position/monitor/alert/review/sell
    generate_date: Mapped[str] = mapped_column(String(10), index=True)  # 生成交易日 YYYY-MM-DD
    fact_basis: Mapped[str] = mapped_column(Text, default="")      # 事实依据层（原始客观数据，标注数据源+时间戳）
    technical_reasoning: Mapped[str] = mapped_column(Text, default="")  # 技术面推理
    capital_reasoning: Mapped[str] = mapped_column(Text, default="")    # 资金面推理
    fundamental_reasoning: Mapped[str] = mapped_column(Text, default="")  # 基本面推理
    risk_reasoning: Mapped[str] = mapped_column(Text, default="")   # 风险推导（触发条件/判定理由/影响范围）
    rule_refs: Mapped[str] = mapped_column(Text, default="")        # 引用规则清单（K 编号，逗号分隔）
    final_conclusion: Mapped[str] = mapped_column(Text, default="")  # 最终结论（评级/操作建议/目标价位）
    confidence: Mapped[float] = mapped_column(Float, default=0.0)   # 结论置信度 0-1
    data_source: Mapped[str] = mapped_column(String(64), default="")  # 数据源标识（如 行情快照+LLM 研判）
    create_time: Mapped[str] = mapped_column(String(16), default="")  # 生成时间戳 YYYY-MM-DD HH:mm
    ext_info: Mapped[str] = mapped_column(Text, default="")         # 各模块特有数据（JSON 字符串）


class NewsArticle(Base):
    """新闻/公告原始文本（真源数据；Qdrant 仅做其向量索引，dev 模式 SQL LIKE 检索）"""
    __tablename__ = "news_article"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64), default="")
    title: Mapped[str] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(64), default="")      # 来源（东财/新浪...）
    url: Mapped[str] = mapped_column(String(512), default="")
    published_at: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AgentPreference(Base):
    """LLM 复盘反馈回流档案（ReviewAgent 写入，注入后续 Discover/Score prompt）"""
    __tablename__ = "agent_preference"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, default=1)         # 版本号递增
    content: Mapped[dict] = mapped_column(JSON, default=dict)        # 偏好内容（LLM 输出）
    source_review_id: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class TradeProfile(Base):
    """个人交易偏好档案（sys_trade_profile，单行配置 id=1）
    系统启动全局加载，所有 Agent 调用 LLM 时自动注入上下文。
    字段全部外部化，禁止硬编码选股风格；version 递增使 LLM 缓存自动失效。
    """
    __tablename__ = "sys_trade_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class PrivateKnowledge(Base):
    """私有交易经验/战法知识库（人工录入；各 Agent 任务启动时自动检索注入参考上下文）"""
    __tablename__ = "private_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text, default="")
    # 适用 Agent：discover/score/position/monitor/sell/review/all（all=全部 Agent 通用）
    agent_tag: Mapped[str] = mapped_column(String(32), index=True, default="all")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SellDecision(Base):
    """卖出决策（SellAgent 输出；决策仅供参考，卖出必须由人工执行）"""
    __tablename__ = "sell_decision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    holding_id: Mapped[int] = mapped_column(Integer, index=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64))
    decision: Mapped[dict] = mapped_column(JSON, default=dict)   # 完整决策结构化输出（LLM 输出）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AccountBaseline(Base):
    """账户基准快照（券商持仓截图 OCR 提取的总资产/可用资金/仓位比例，人工确认后保存）

    每次确认保存插入一行（保留历史），读取最新一条作为顶部栏账户展示的权威值；
    无基准时顶部栏按 TOTAL_CAPITAL + 持仓盈亏估算并明确标注「估算」。
    """
    __tablename__ = "account_baseline"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    total_asset: Mapped[float] = mapped_column(Float, default=0.0)   # 总资产（元）
    available_cash: Mapped[float] = mapped_column(Float, default=0.0)  # 可用资金（元）
    position_pct: Mapped[float] = mapped_column(Float, default=0.0)  # 整体仓位占比 %
    source: Mapped[str] = mapped_column(String(32), default="ocr")   # ocr / manual
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AgentSuggestion(Base):
    """复盘进化Agent 输出的各 Agent 规则/参数优化建议（策略闭环）
    状态机：pending → approved/rejected；任何生效必须先经人工审核确认。
    target_kind 决定采纳后的生效方式：
      profile = 直接写入个人交易偏好档案（sys_trade_profile，字段级）；
      prompt  = 需人工修改 agent_prompts/ 对应提示词文件或 common.py HARD_RULES。"""
    __tablename__ = "agent_suggestion"
    __table_args__ = (Index("ix_suggestion_status", "status"),)  # 待审核建议查询（首页/策略闭环）

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(Integer, index=True)
    target_agent: Mapped[str] = mapped_column(String(16), index=True)  # discover/score/position/monitor/sell/review
    target_kind: Mapped[str] = mapped_column(String(16), default="profile")  # profile/prompt
    rule_name: Mapped[str] = mapped_column(String(128))                # 规则/参数名称
    current_value: Mapped[str] = mapped_column(Text, default="")       # 当前值
    suggested_value: Mapped[str] = mapped_column(Text, default="")     # 建议值
    reason: Mapped[str] = mapped_column(Text, default="")              # 建议理由
    evidence: Mapped[str] = mapped_column(Text, default="")            # 事实依据
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class AgentChatMessage(Base):
    """Agent 专属对话历史（Agent 对话页：问答/规则调教/多模态学习，全程可回溯）

    message_type: qa=文字提问 / rule=规则调教 / learn=多模态学习
    verdict: 规则调教结论 adopted/partial/maintained（仅 rule 类型有值）
    knowledge_id: 规则调教采纳后沉淀到的知识条目 ID（可空）
    meta: JSON 附加信息（依据来源/信心度/标签等，展示与审计用）
    """
    __tablename__ = "agent_chat_message"
    __table_args__ = (Index("ix_chat_agent_time", "agent", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent: Mapped[str] = mapped_column(String(16), index=True)   # discover/score/position/monitor/sell/review
    role: Mapped[str] = mapped_column(String(8))                 # user / assistant
    message_type: Mapped[str] = mapped_column(String(16), default="qa")  # qa/rule/learn
    content: Mapped[str] = mapped_column(Text, default="")
    verdict: Mapped[str] = mapped_column(String(16), default="")  # adopted/partial/maintained（rule 类型）
    knowledge_id: Mapped[int] = mapped_column(Integer, nullable=True)  # 沉淀知识条目 ID
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
