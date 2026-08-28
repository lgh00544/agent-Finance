"""
ORM 模型 - MySQL8 / SQLite 共用同一套模型
JSON 字段用 Text 存储（SQLAlchemy JSON 在 SQLite/MySQL 均可，但 MySQL 原生 JSON 列
对 SQLAlchemy 2.0 友好；统一用 JSON 类型，SQLite 自动映射为 TEXT）。
"""
from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class SafeJSON(TypeDecorator):
    """容错 JSON 类型：历史数据/迁移遗留可能写入空串，读取时视为 None 而非抛
    JSONDecodeError（曾致 /api/reviews 500）。写侧行为与原生 JSON 完全一致。"""
    impl = JSON
    cache_ok = True

    def result_processor(self, dialect, coltype):
        impl_proc = self.impl.result_processor(dialect, coltype)

        def process(value):
            if isinstance(value, str) and not value.strip():
                return None
            return impl_proc(value) if impl_proc is not None else value

        return process


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
    reasons: Mapped[list] = mapped_column(SafeJSON, default=list)        # 候选理由（LLM 输出）
    risk_notice: Mapped[list] = mapped_column(SafeJSON, default=list)    # 风险初判（LLM 输出）
    snapshot: Mapped[dict] = mapped_column(SafeJSON, default=dict)       # 当日原始行情快照（计算层）
    detail: Mapped[dict] = mapped_column(SafeJSON, default=dict)         # v2.0 输出详情（信心度/三维/量能/风险/关注类型 + 增量数据）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class CandidateTrackVerify(Base):
    """候选池标的 T+N 自动追踪验证（选股效果闭环·代码侧客观统计）
    口径：T+N 涨跌幅 = (选中日后第 N 个交易日收盘 / 选中日收盘基准 − 1) × 100；
    最大回撤 = 相对 base_close_price 的区间最低收盘回撤（services/track_verify.py 注释）。
    is_finished: 0=追踪中 / 1=已到期收尾（T+10 数据齐全即收尾）。
    factor_scores: 因子评分快照（仅因子回测校准闭环用，旧数据为空）。"""
    __tablename__ = "candidate_track_verify"
    __table_args__ = (
        UniqueConstraint("stock_code", "select_date", name="uq_track_code_date"),
        Index("ix_track_status", "is_finished", "select_date"),  # 未完成遍历 + 日期排序
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64))
    select_date: Mapped[str] = mapped_column(String(10), index=True)  # 选中日 YYYY-MM-DD
    select_rating: Mapped[str] = mapped_column(String(16), default="")  # A/B/C 或 confidence_tier 原文
    base_close_price: Mapped[float] = mapped_column(Float, default=0.0)  # 选中日收盘基准价
    t3_pct: Mapped[float | None] = mapped_column(Float, nullable=True)   # T+3 涨跌幅 %（不足=null）
    t5_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    t10_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)  # 相对基准最大回撤 %
    verify_result: Mapped[dict] = mapped_column(SafeJSON, default=dict)     # 周期胜负/回撤明细（见服务层）
    factor_scores: Mapped[dict | None] = mapped_column(SafeJSON, nullable=True)  # 因子评分快照（仅因子回测校准闭环用，旧数据为空）
    is_finished: Mapped[int] = mapped_column(Integer, default=0)        # 0=追踪中 / 1=已到期收尾
    update_time: Mapped[str] = mapped_column(String(16), default="")    # YYYY-MM-DD HH:mm
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ForwardViewHistory(Base):
    """前瞻判断快照（预测性选股 2.5：discover 前瞻三态落库 → T+5 回填校准闭环）。
    forward_view: 强/中性/弱（由 horizon_bias 映射：延续→强/回归→中性/回吐→弱）；
    forward_signals: 触发前瞻结论的对照事实（position/money/peer/history 摘要）；
    accuracy_bucket: 回填后判定 correct/wrong/neutral（§3.5 口径）。"""
    __tablename__ = "forward_view_history"
    __table_args__ = (
        UniqueConstraint("trade_date", "stock_code", name="uq_fwd_date_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    forward_view: Mapped[str] = mapped_column(String(16))  # 强/中性/弱
    forward_signals: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    # 回填字段
    t5_pct_actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    t5_filled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 校准字段
    accuracy_bucket: Mapped[str | None] = mapped_column(String(16), nullable=True)  # correct/wrong/neutral


class MarketCondition(Base):
    """每日市况评分（v2.0 Discover 前置步骤）：LLM 五维打分 + 代码档位映射候选池上限"""
    __tablename__ = "market_condition"
    __table_args__ = (UniqueConstraint("trade_date", name="uq_market_condition_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    total_score: Mapped[int] = mapped_column(Integer)                # 0-50（LLM 五维求和）
    dims: Mapped[dict] = mapped_column(SafeJSON, default=dict)           # 五维明细（LLM 输出）
    cap: Mapped[int] = mapped_column(Integer)                        # 当日候选池上限（档位映射）
    summary: Mapped[str] = mapped_column(Text, default="")           # 市况综述（LLM 输出）
    # 选中日后下一交易日沪深300收盘涨跌幅 %；None=未回填/非交易日（准确率闭环数据沉淀）
    next_day_index_pct: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MarketIntel(Base):
    """市场研判底座（每日收盘后 1 次 + 手动入口）：阶段定性/核心矛盾/风险偏好/量能信号/
    操作含义/次日盯盘点，作为全部 agent 的参考维度注入（只新增表，不迁移不改旧表）"""
    __tablename__ = "market_intel"
    __table_args__ = (UniqueConstraint("trade_date", name="uq_market_intel_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD 唯一
    phase: Mapped[str] = mapped_column(String(128), default="")       # 阶段定性（启动/主升/分化/存量博弈…）
    core_conflict: Mapped[str] = mapped_column(Text, default="")     # 核心矛盾
    risk_appetite: Mapped[str] = mapped_column(String(16), default="")  # 风险偏好（进取/中性/避险）
    volume_signal: Mapped[dict] = mapped_column(SafeJSON, default=dict)  # 板块量比明细+放量/缩量分布
    operative_meaning: Mapped[dict] = mapped_column(SafeJSON, default=dict)  # 操作含义（精选/回避/买点标准）
    next_day_watch: Mapped[dict] = mapped_column(SafeJSON, default=dict)  # 次日盯盘点
    summary: Mapped[str] = mapped_column(Text, default="")           # 一句话总结（供注入参考）
    raw: Mapped[dict] = mapped_column(SafeJSON, default=dict)        # 全部输入原始数据（可追溯）
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
    detail: Mapped[dict] = mapped_column(SafeJSON, default=dict)         # 五维明细（LLM 输出）
    risk_list: Mapped[list] = mapped_column(SafeJSON, default=list)      # 风险清单（LLM 输出）
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
    batches: Mapped[list] = mapped_column(SafeJSON, default=list)        # 分批明细（LLM 输出）
    stop_loss: Mapped[float] = mapped_column(Float, default=0.0)     # 止损参考价（LLM 输出）
    take_profit: Mapped[float] = mapped_column(Float, default=0.0)   # 止盈参考价（LLM 输出）
    rationale: Mapped[str] = mapped_column(Text, default="")         # 建仓逻辑（LLM 输出）
    detail: Mapped[dict] = mapped_column(SafeJSON, default=dict)         # v3.0 白盒扩展（dimensions/final_advice/market_regime/quant）
    source: Mapped[str] = mapped_column(String(16), default="manual", index=True)  # candidate/manual（来源标记）
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
    high_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # 持仓期最高价（移动止盈线基准；旧数据 NULL 降级以当前价为基准）
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
    signal: Mapped[dict] = mapped_column(SafeJSON, default=dict)         # 完整信号结构化输出
    pushed: Mapped[bool] = mapped_column(Boolean, default=False)     # 是否已推飞书
    source: Mapped[str] = mapped_column(String(32), default="monitor")  # 告警来源标记 monitor/portfolio_sentinel
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
    plan_vs_actual: Mapped[dict] = mapped_column(SafeJSON, default=dict) # 计划兑现度（LLM 输出）
    lesson: Mapped[str] = mapped_column(Text, default="")            # 经验教训（LLM 输出）
    feedback: Mapped[dict] = mapped_column(SafeJSON, default=dict)       # 筛选偏好微调建议（LLM 输出）
    # ---------- 建议驳回迭代（人工审核闭环） ----------
    suggest_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending=待审核 / adopted=已采纳 / rejected=已驳回
    reject_reason: Mapped[str] = mapped_column(Text, default="")     # 最近一次驳回原因（必填）
    suggest_iteration: Mapped[int] = mapped_column(Integer, default=1)  # 建议迭代次数（第几版）
    suggest_history: Mapped[list] = mapped_column(SafeJSON, default=list)   # 迭代轨迹 [{iteration, suggestion, reject_reason}]
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
    content: Mapped[dict] = mapped_column(SafeJSON, default=dict)        # 偏好内容（LLM 输出）
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
    content: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class PrivateKnowledge(Base):
    """私有交易经验/战法知识库（人工录入；各 Agent 任务启动时自动检索注入参考上下文）"""
    __tablename__ = "private_knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text, default="")
    # 适用 Agent：discover/score/position/monitor/sell/review/all（all=全部 Agent 通用）
    agent_tag: Mapped[str] = mapped_column(String(32), index=True, default="all")
    # 决策级归因·命中计量：检索注入 + 对话显式引用累计（只加不自减，便于看历史累计）；last_used_at 最近命中时间
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SellDecision(Base):
    """卖出决策（SellAgent 输出；决策仅供参考，卖出必须由人工执行）"""
    __tablename__ = "sell_decision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    holding_id: Mapped[int] = mapped_column(Integer, index=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64))
    decision: Mapped[dict] = mapped_column(SafeJSON, default=dict)   # 完整决策结构化输出（LLM 输出）
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


class AccountPnlSnapshot(Base):
    """同花顺投资账本真实账户今日盈亏快照（P0 数据通道；默认 ths_pnl_enable=false 不采集）

    trade_date+ts 唯一，upsert 幂等（R5 防重复采集/误报）；
    失败快照写 error 字段，不伪造 0 值（R1 token 过期标记 token_expired）。
    """
    __tablename__ = "account_pnl_snapshot"
    __table_args__ = (UniqueConstraint("trade_date", "ts", name="uq_account_pnl_date_ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True)   # YYYY-MM-DD
    ts: Mapped[str] = mapped_column(String(32))                       # 当日采集时间 HH:MM:SS
    pnl_yk: Mapped[float | None] = mapped_column(Float, nullable=True)   # 今日盈亏额（元）
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # 今日盈亏（%）
    sh_pct: Mapped[float | None] = mapped_column(Float, nullable=True)   # 上证指数涨跌幅（%）
    chart_data: Mapped[list] = mapped_column(SafeJSON, default=list)     # 当日分时曲线 [{t, v}]
    source: Mapped[str] = mapped_column(String(32), default="ths")       # 数据来源 ths
    error: Mapped[str] = mapped_column(Text, default="")                 # 失败原因（空=成功）
    token_expired: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


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
    reject_reason: Mapped[str] = mapped_column(Text, default="")        # 人工驳回原因（审核留痕）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    # ---------- 建议质量增强（一键采纳自动落地 v2，LLM 输出完整落地信息） ----------
    priority: Mapped[str] = mapped_column(String(8), default="medium")   # 高/中/低 high/medium/low
    rule_type: Mapped[str] = mapped_column(String(8), default="soft")    # soft=提示词软规则 / hard=代码硬规则
    problem_desc: Mapped[str] = mapped_column(Text, default="")   # 当前问题说明（场景缺陷 + 触发案例）
    rule_text: Mapped[str] = mapped_column(Text, default="")      # 优化后完整规则条文（可直接落地生效）
    expected_effect: Mapped[str] = mapped_column(Text, default="")  # 预期效果（量化指标）
    risk_note: Mapped[str] = mapped_column(Text, default="")      # 规则生效副作用与注意事项
    file_path: Mapped[str] = mapped_column(String(255), default="")  # 应归属文件（仅展示元数据，不写文件）
    insert_position: Mapped[str] = mapped_column(String(32), default="")  # 建议插入位置（仅展示元数据）
    conflict_note: Mapped[str] = mapped_column(Text, default="")   # 代码侧冲突校验拦截说明（非空=拦截）
    dedup_note: Mapped[str] = mapped_column(Text, default="")      # 代码侧去重校验拦截说明（非空=拦截）
    suggestion_source: Mapped[str] = mapped_column(String(16), default="llm", index=True)  # llm=LLM生成 / template=确定性模板兜底（选股验证统计）
    # ---------- 通用审核 Agent（批1）：辩证审核状态，只写 audit_log + 本 3 字段 ----------
    audit_verdict: Mapped[str] = mapped_column(String(8), default="pending", index=True)  # pending/pass/fail
    audit_round: Mapped[int] = mapped_column(Integer, default=0)   # 0=未审 1=首审 2=重审（不超 2）
    last_audit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 最近一次 audit_log.id


class AuditLog(Base):
    """通用审核 Agent 辩证审核留痕（批1：只审 agent_suggestion；只写本表 + 原表 audit 字段，不改原表其它）"""
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_target", "target_type", "target_id"),
        Index("ix_audit_verdict", "verdict"),
        Index("ix_audit_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_type: Mapped[str] = mapped_column(String(24), default="agent_suggestion")  # agent_suggestion/pending_experience/rule_change/review_result
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    round: Mapped[int] = mapped_column(Integer, default=1)   # 1=首审 2=重审
    verdict: Mapped[str] = mapped_column(String(8), default="pending")  # pending/pass/fail
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    support_view: Mapped[str] = mapped_column(Text, default="")
    dissent_view: Mapped[str] = mapped_column(Text, default="")        # 强制非空 ≥50 字且含具体反例
    boundary_cases: Mapped[str] = mapped_column(Text, default="")
    evidence_refs: Mapped[list] = mapped_column(SafeJSON, default=list)  # list[str]，≥1 条
    audit_model: Mapped[str] = mapped_column(String(32), default="")
    reasoning: Mapped[str] = mapped_column(Text, default="")           # LLM 原始 JSON 全文
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class RuleChange(Base):
    """复盘采纳规则变更记录（一键采纳自动落地：规则存库、agent_call 动态注入）

    采纳 = 写入一条 status=active 的记录 → 所有 Agent 下次任务自动携带（版本指纹入缓存键
    → LLM 缓存自动失效）；回滚 = 状态置 rolled_back + 原因留痕，全程可追溯。
    file_path/insert_position 为 LLM 声明的归属元数据，仅展示，绝不写入源码文件。
    """
    __tablename__ = "rule_change"
    __table_args__ = (
        Index("ix_rule_change_status", "status"),
        Index("ix_rule_change_agent", "target_agent"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_suggestion_id: Mapped[int] = mapped_column(Integer, index=True)  # 来源建议（agent_suggestion.id）
    review_id: Mapped[int] = mapped_column(Integer, index=True, default=0)  # 来源复盘
    stock_code: Mapped[str] = mapped_column(String(16), default="")
    stock_name: Mapped[str] = mapped_column(String(64), default="")
    target_agent: Mapped[str] = mapped_column(String(16), default="")  # discover/score/position/monitor/sell/review
    rule_type: Mapped[str] = mapped_column(String(8), default="soft")  # soft/hard
    rule_name: Mapped[str] = mapped_column(String(128), default="")    # 规则名称
    rule_text: Mapped[str] = mapped_column(Text, default="")           # 生效的完整规则条文
    priority: Mapped[str] = mapped_column(String(8), default="medium")
    before_text: Mapped[str] = mapped_column(Text, default="")   # 采纳前生效规则摘要（变更对比）
    after_text: Mapped[str] = mapped_column(Text, default="")    # 采纳后生效规则全文（变更对比）
    reason: Mapped[str] = mapped_column(Text, default="")        # 建议理由
    evidence: Mapped[str] = mapped_column(Text, default="")      # 事实依据
    expected_effect: Mapped[str] = mapped_column(Text, default="")
    risk_note: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(255), default="")
    insert_position: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(16), default="active")  # active=生效中 / rolled_back=已回滚
    rollback_reason: Mapped[str] = mapped_column(Text, default="")
    rollback_time: Mapped[str] = mapped_column(String(16), default="")  # YYYY-MM-DD HH:mm
    operator: Mapped[str] = mapped_column(String(32), default="")  # 操作人（单机自部署固定本机用户）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


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
    role: Mapped[str] = mapped_column(String(16))                # user / assistant
    message_type: Mapped[str] = mapped_column(String(16), default="qa")  # qa/rule/learn
    content: Mapped[str] = mapped_column(Text, default="")
    verdict: Mapped[str] = mapped_column(String(16), default="")  # adopted/partial/maintained（rule 类型）
    knowledge_id: Mapped[int] = mapped_column(Integer, nullable=True)  # 沉淀知识条目 ID
    meta: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class HotMoneyProfile(Base):
    """游资档案（基础字典，低频更新；席位消歧：一席位只映射一个主力游资）

    co_seats: 协同游资关联（JSON），与 seat_code 唯一约束解耦——同一主力游资的
    协同席位用该字段表达，不占用独立 seat_code 唯一映射。
    源文件席位名仅为示例（base_file/游资大佬追踪体系），真实席位以龙虎榜为准，
    种子数据只作模糊匹配参考。
    """
    __tablename__ = "hot_money_profile"
    __table_args__ = (UniqueConstraint("seat_code", name="uq_hot_money_seat"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_name: Mapped[str] = mapped_column(String(32), index=True)   # 游资名（赵老哥/章盟主…）
    seat_code: Mapped[str] = mapped_column(String(64))                # 营业部名称（唯一映射）
    tier: Mapped[str] = mapped_column(String(8), default="观察")       # 一线/二线/观察
    style_tags: Mapped[list] = mapped_column(SafeJSON, default=list)      # 操作风格标签（高位接力/题材龙头…）
    good_themes: Mapped[list] = mapped_column(SafeJSON, default=list)     # 擅长题材
    co_seats: Mapped[list] = mapped_column(SafeJSON, default=list)        # 协同游资/协同席位（不破坏 seat_code 唯一性）
    source: Mapped[str] = mapped_column(String(16), default="手动")    # 手动/LLM识别/同花顺
    win_rate_5d: Mapped[float | None] = mapped_column(Float, nullable=True)  # 信号后5日上涨胜率（代码统计事实，非人工判定）
    last_review_at: Mapped[str] = mapped_column(String(16), default="")      # 最近一次胜率迭代时间 YYYY-MM-DD HH:mm
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class CandidateTradeable(Base):
    """候选池可建仓标记（每日落库·历史可追溯；硬性三条件 code 判定，口径见 services/candidate_tradeable.py）
    三条件：c1=评级 A/B、c2=有建仓方案且现价∈首仓区间、c3=无重大利空（HARD_RULES + LLM risks 清单）。
    label: 可建仓 / 建议关注 / 观察；block_reason 记录未命中原因（无方案/买点未到/现价缺失/重大利空）。"""
    __tablename__ = "candidate_tradeable"
    __table_args__ = (
        UniqueConstraint("stock_code", "trade_date", name="uq_tradeable_code_date"),
        Index("ix_tradeable_date", "trade_date", "is_tradeable"),  # 按日统计可建仓数
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64))
    trade_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    tier: Mapped[str] = mapped_column(String(8), default="")        # A/B/C（effective，含人工覆盖）
    is_tradeable: Mapped[int] = mapped_column(Integer, default=0)   # 1=可建仓 / 0=否
    label: Mapped[str] = mapped_column(String(16), default="建议关注")  # 可建仓/建议关注/观察
    plan_exists: Mapped[int] = mapped_column(Integer, default=0)    # 1=有建仓方案
    price_zone: Mapped[str] = mapped_column(String(64), default="") # 首仓买入区间原文
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)  # 判定用现价
    cond_grade: Mapped[int] = mapped_column(Integer, default=0)     # 1=评级达标
    cond_price: Mapped[int] = mapped_column(Integer, default=0)     # 1=买点在区间内
    cond_risk: Mapped[int] = mapped_column(Integer, default=0)      # 1=无重大利空
    block_reason: Mapped[str] = mapped_column(Text, default="")     # 未命中原因（可读文本）
    detail: Mapped[dict] = mapped_column(JSON, default=dict)        # 判定快照（区间/现价/来源）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class CandidateAdjust(Base):
    """候选评级/标签人工覆盖（批量对话「确认生效」写入；不改 detail JSON，可回滚）
    生效后 ensure_tradeable 以 tier_override 作为 effective_tier 重判；回滚即删除本行。"""
    __tablename__ = "candidate_adjust"
    __table_args__ = (UniqueConstraint("stock_code", "trade_date", name="uq_adjust_code_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64))
    trade_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    tier_override: Mapped[str] = mapped_column(String(8), default="")  # 覆盖后的 A/B/C
    label_override: Mapped[str] = mapped_column(String(16), default="")  # 覆盖后的展示标签
    reason: Mapped[str] = mapped_column(Text, default="")            # 调整理由（LLM 输出）
    operator: Mapped[str] = mapped_column(String(32), default="")    # 操作人
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class BatchAdjust(Base):
    """批量对话调整留痕（状态机 pending→applied→rolled_back，全程可追溯）
    adjust_plan: [{stock_code, new_tier, new_label, reason, evidence}]（LLM 输出）；
    before/after_snapshot: 应用前后该批候选 effective 快照（对比留痕）。"""
    __tablename__ = "batch_adjust"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), default="all")    # all/tradeable/A/B/C/manual
    scope_codes: Mapped[list] = mapped_column(JSON, default=list)    # 提问范围标的清单
    question: Mapped[str] = mapped_column(Text, default="")          # 触发调整的提问
    trade_date: Mapped[str] = mapped_column(String(10), index=True)  # 关联候选批次日期
    adjust_plan: Mapped[list] = mapped_column(JSON, default=list)    # 调整方案（LLM 输出）
    before_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # 应用前 effective 快照
    after_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)   # 应用后 effective 快照
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/applied/rolled_back
    rollback_reason: Mapped[str] = mapped_column(Text, default="")
    rollback_time: Mapped[str] = mapped_column(String(16), default="")  # YYYY-MM-DD HH:mm
    operator: Mapped[str] = mapped_column(String(32), default="")    # 操作人
    chat_user_msg_id: Mapped[int] = mapped_column(Integer, default=0)  # 关联 agent_chat_message.id
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class LhbOriginalFlow(Base):
    """龙虎榜原始流水（口径硬隔离：lhb_type='1d'单日 / '3d'三日累计，防 K227 误读）

    confidence: 数据置信度（官方龙虎榜=1.0 / 第三方=0.8 / 社区=0.5）；
    多源校验在 services/hot_money.py 完成（≥2 源且差值<10% 采信，否则标置信度不足仅参考）。
    注入 LLM 时字段强制带口径后缀（lhb_1d_net_buy / lhb_3d_net_buy），LLM 不得自行推导口径。
    """
    __tablename__ = "lhb_original_flow"
    __table_args__ = (
        Index("ix_lhb_date_code_type", "trade_date", "stock_code", "lhb_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True)   # YYYY-MM-DD
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    stock_name: Mapped[str] = mapped_column(String(64), default="")
    lhb_type: Mapped[str] = mapped_column(String(4), default="1d")    # 1d=单日 / 3d=三日累计
    disclosure_reason: Mapped[str] = mapped_column(String(64), default="")  # 涨跌幅偏离/换手率/振幅/连续涨停…
    seat_name: Mapped[str] = mapped_column(String(64), default="")    # 营业部名称
    buy_amt: Mapped[float] = mapped_column(Float, default=0.0)
    sell_amt: Mapped[float] = mapped_column(Float, default=0.0)
    net_buy: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)     # 官方=1.0/第三方=0.8/社区=0.5
    source: Mapped[str] = mapped_column(String(16), default="eastmoney")  # sse/szse/eastmoney
    multi_source_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # 第二源上榜确认采信
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


# ==================== 经验沉淀闭环（自动识别 → 分层审核 → 检索注入） ====================
# 时间戳统一用 DateTime + _now()（datetime），与全库既有惯例一致；
# 原执行指令草案用 String(24)+_now() 会存 datetime 对象到 VARCHAR 列，按实际代码惯例修正。


class PendingExperience(Base):
    """经验沉淀待处理队列（热路径单行写入，离线 Worker 消费）
    status: pending(待处理) / processing(Worker 认领中) / done(已处理，含失败=done+error)"""
    __tablename__ = "pending_experience"
    __table_args__ = (
        Index("ix_pending_status_id", "status", "id"),   # 认领批次按状态+ID 顺序
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str | None] = mapped_column(String(64))          # 来源任务标识 kind:trade_date
    stage: Mapped[str] = mapped_column(String(8))                    # 选股/建仓/持仓
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    summary: Mapped[str | None] = mapped_column(Text)                # 热路径摘要（零分析）
    artifacts_ref: Mapped[str | None] = mapped_column(Text)          # 产物引用（记录 ID，非全文）
    status: Mapped[str] = mapped_column(String(12), default="pending")
    error: Mapped[str | None] = mapped_column(Text)                  # Worker 失败原因（done+error 表示）


class Experience(Base):
    """沉淀经验（四态：pending_review 待审核 / active 已生效 / rejected 驳回 / rolled_back 已回滚）
    auto_merged=1 表示低影响自动合并（可回滚 + 留痕 review_log）。"""
    __tablename__ = "experience"
    __table_args__ = (
        Index("ix_experience_status_stage", "status", "stage"),
        Index("ix_experience_stage_id", "stage", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128))
    body: Mapped[str] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(String(8))
    tags: Mapped[str | None] = mapped_column(Text)                   # JSON 数组或逗号分隔
    impact: Mapped[str] = mapped_column(String(8), default="low")    # high/low
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    auto_merged: Mapped[int] = mapped_column(Integer, default=0)
    source_pending_id: Mapped[int | None] = mapped_column(
        ForeignKey("pending_experience.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReviewLog(Base):
    """审核留痕（approve/reject/auto_merge/rollback，可追溯）"""
    __tablename__ = "review_log"
    __table_args__ = (
        Index("ix_reviewlog_exp", "experience_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experience_id: Mapped[int | None] = mapped_column(
        ForeignKey("experience.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(32))                  # approve/reject/auto_merge/rollback/strictness_freeze
    reviewer: Mapped[str] = mapped_column(String(16))                # sir/auto
    at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    note: Mapped[str | None] = mapped_column(Text)


class WorkerRun(Base):
    """Worker 运行记录（每次消费批次的开始/结束/处理数/状态）"""
    __tablename__ = "worker_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(12), default="running")  # running/success/failed
    error: Mapped[str | None] = mapped_column(Text)


class ExperienceConfig(Base):
    """经验沉淀设置中心（key-value 热加载，改后无需重启；M5 前端设置落地）"""
    __tablename__ = "experience_config"

    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SectorSnapshot(Base):
    """首页今日热门板块快照（5 分钟一次落库；首页只读）

    表结构：sector_snapshot
    作用：解决 akshare 实时接口 14% 失败率导致首页 5 灰条（DB 兜底永远有值）
    """
    __tablename__ = "sector_snapshot"
    __table_args__ = (
        UniqueConstraint("trade_date", "sector_name", name="uq_sector_date_name"),
        Index("ix_sector_date_rank", "trade_date", "rank_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    sector_name: Mapped[str] = mapped_column(String(64), nullable=False)
    change_pct: Mapped[float] = mapped_column(Float, nullable=False)
    leading_stock_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    leading_stock_code: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    source: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    rank_no: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SectorDailySnapshot(Base):
    """全板块每日快照（收盘 15:35 落库；批次 B 轮动判定底座，与 sector_snapshot 并存不替代）
    """
    __tablename__ = "sector_daily_snapshot"
    __table_args__ = (
        UniqueConstraint("trade_date", "sector_name", name="uq_sd_date_name"),
        Index("ix_sd_date_rank", "trade_date", "rank_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    sector_name: Mapped[str] = mapped_column(String(64), nullable=False)
    change_pct: Mapped[float] = mapped_column(Float, nullable=False)
    rank_no: Mapped[int] = mapped_column(Integer, nullable=False)
    up_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    down_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    turnover_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    leading_stock_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    leading_stock_code: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    leading_chg: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(8), nullable=False, default="em")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SectorDailyRankLog(Base):
    """轮动指标快照（批次 B 状态机结果，trade_date 唯一；notes 存批次 D 规律文本）
    """
    __tablename__ = "sector_daily_rank_log"
    __table_args__ = (
        UniqueConstraint("trade_date", name="uq_rd_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False)
    rotation_state: Mapped[str] = mapped_column(String(16), nullable=False)
    churn_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    top5_overlap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mainline_sector: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SectorLaunchReason(Base):
    """板块启动归因（批次 C 子 Agent 输出；reason_chain 为 LLM 推导证据链，K227 证据须真实）
    """
    __tablename__ = "sector_launch_reason"
    __table_args__ = (
        UniqueConstraint("trade_date", "sector_name", name="uq_lr_date_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False)
    sector_name: Mapped[str] = mapped_column(String(64), nullable=False)
    rank_no: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_tags: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    reason_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_chain: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SectorRegimeForecast(Base):
    """行情结构与板块轮动前瞻（C' 多窗口结构识别，每个交易日一条）"""
    __tablename__ = "sector_regime_forecast"
    __table_args__ = (
        UniqueConstraint("trade_date", name="uq_srf_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    current_regime: Mapped[str] = mapped_column(String(16), nullable=False)
    regime_stage: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    regime_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    forward_bias_t1: Mapped[str] = mapped_column(String(32), nullable=False, default="uncertain")
    forward_bias_t3: Mapped[str] = mapped_column(String(32), nullable=False, default="uncertain")
    forward_bias_t5: Mapped[str] = mapped_column(String(32), nullable=False, default="uncertain")
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class QuoteSnapshot(Base):
    """持仓实时价快照（每 5 分钟腾讯批量落库；持仓监控页 DB 兜底，首页热路径 <50ms）

    表结构：quote_snapshot；stock_code 唯一，新鲜度由 updated_at 判定（within_minutes）。
    作用：解决东财全市场快照单点 hang 10-20s 导致前端 15s 超时（DB 快照永远秒回）
    """
    __tablename__ = "quote_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class DistributionPhaseLog(Base):
    """派发期自动判定结果（每日 15:30 收盘后落库；Monitor/Sell/Score 注入参考）

    表结构：distribution_phase_log；(trade_date, symbol) 唯一，6 维快照 JSON 承载。
    """
    __tablename__ = "distribution_phase_log"
    __table_args__ = (
        UniqueConstraint("trade_date", "symbol", name="uq_dist_date_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    phase: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    phase_label: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    confidence: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    six_dim: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    missing_data: Mapped[list] = mapped_column(SafeJSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class CapitalActor(Base):
    """游资维度：单标的单日命中游资（近30日窗口聚合；『三维表』之游资维）
    表结构：capital_actor；(trade_date, stock_code, actor_name) 唯一。
    数据来自 lhb_original_flow 席位命中 hot_money_profile（未知营业部不硬绑，留 LLM 研判占位）。"""
    __tablename__ = "capital_actor"
    __table_args__ = (
        UniqueConstraint("trade_date", "stock_code", "actor_name", name="uq_cap_actor_dcn"),
        Index("ix_cap_actor_code_date", "stock_code", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    stock_code: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(32), nullable=False)
    seat_code: Mapped[str] = mapped_column(String(64), default="")
    tier: Mapped[str] = mapped_column(String(8), default="观察")
    net_buy: Mapped[float] = mapped_column(Float, default=0.0)
    days_active: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(16), default="sse_only")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class DragonTiger(Base):
    """龙虎榜维度：单标的单日龙虎榜汇总（股票级净买 + 龙头席位；『三维表』之龙虎榜维）
    表结构：dragon_tiger；(trade_date, stock_code) 唯一，rollup 自 lhb_original_flow 股票级行。"""
    __tablename__ = "dragon_tiger"
    __table_args__ = (UniqueConstraint("trade_date", "stock_code", name="uq_dt_date_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    stock_code: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(64), default="")
    lhb_type: Mapped[str] = mapped_column(String(8), default="1d")
    net_buy: Mapped[float] = mapped_column(Float, default=0.0)
    buy_amt: Mapped[float] = mapped_column(Float, default=0.0)
    sell_amt: Mapped[float] = mapped_column(Float, default=0.0)
    top_seat: Mapped[str] = mapped_column(String(64), default="")   # 净买额最大席位
    top_seat_net: Mapped[float] = mapped_column(Float, default=0.0)
    disclosure_reason: Mapped[str] = mapped_column(String(128), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    source: Mapped[str] = mapped_column(String(16), default="sse_only")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class CapitalFlow(Base):
    """资金流维度：单标的单日主力/大中小单净额（『三维表』之资金流维）
    表结构：capital_flow；(trade_date, stock_code) 唯一，来源 akshare 个股资金流（严格当日）。"""
    __tablename__ = "capital_flow"
    __table_args__ = (UniqueConstraint("trade_date", "stock_code", name="uq_cf_date_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    stock_code: Mapped[str] = mapped_column(String(16), nullable=False)
    main_net_inflow: Mapped[float] = mapped_column(Float, default=0.0)
    super_large_net: Mapped[float] = mapped_column(Float, default=0.0)
    large_net: Mapped[float] = mapped_column(Float, default=0.0)
    medium_net: Mapped[float] = mapped_column(Float, default=0.0)
    small_net: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(16), default="sse_only")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class CapitalStats(Base):
    """资本视图统计：单标的单日 30 日聚合快照（K189 对倒/协调/胜率/盈亏比/题材共振；徽章 + Agent 注入）
    表结构：capital_stats；(trade_date, stock_code) 唯一。缺数据 → null + missing_data 明列（K227）。"""
    __tablename__ = "capital_stats"
    __table_args__ = (UniqueConstraint("trade_date", "stock_code", name="uq_cs_date_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    stock_code: Mapped[str] = mapped_column(String(16), nullable=False)
    wash_suspect: Mapped[bool] = mapped_column(Boolean, default=False)
    coordination: Mapped[str] = mapped_column(String(8), default="数据不足")
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    payoff_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_hold_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    theme_resonance: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="sse_only")
    missing_data: Mapped[list] = mapped_column(SafeJSON, default=list)
    raw_json: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
