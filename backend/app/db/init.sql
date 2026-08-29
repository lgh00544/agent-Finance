-- ============================================================
-- MySQL 初始化 DDL（docker compose mysql 容器首次启动自动执行）
-- 与 backend/app/db/models.py 的 ORM 结构一致
-- ============================================================

CREATE TABLE IF NOT EXISTS stock_candidate (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(16) NOT NULL,
    stock_name VARCHAR(64) NOT NULL,
    trade_date VARCHAR(10) NOT NULL,
    rank INT NOT NULL DEFAULT 0,
    reasons JSON NULL,
    risk_notice JSON NULL,
    snapshot JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_candidate_code_date (stock_code, trade_date),
    KEY idx_candidate_date (trade_date),
    KEY ix_candidate_date_rank (trade_date, rank)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stock_score (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(16) NOT NULL,
    stock_name VARCHAR(64) NOT NULL,
    trade_date VARCHAR(10) NOT NULL,
    score FLOAT NOT NULL DEFAULT 0,
    grade VARCHAR(4) NOT NULL,
    detail JSON NULL,
    risk_list JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_score_code_date (stock_code, trade_date),
    KEY idx_score_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS position_plan (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(16) NOT NULL,
    stock_name VARCHAR(64) NOT NULL,
    plan_date VARCHAR(10) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'proposed',
    total_pct FLOAT NOT NULL DEFAULT 0,
    batches JSON NULL,
    stop_loss FLOAT NOT NULL DEFAULT 0,
    take_profit FLOAT NOT NULL DEFAULT 0,
    rationale TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_plan_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS holding (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(16) NOT NULL,
    stock_name VARCHAR(64) NOT NULL,
    entry_date VARCHAR(10) NOT NULL,
    entry_price FLOAT NOT NULL,
    shares INT NOT NULL,
    cost FLOAT NOT NULL DEFAULT 0,
    stop_loss FLOAT NOT NULL DEFAULT 0,
    take_profit FLOAT NOT NULL DEFAULT 0,
    target_pct FLOAT NOT NULL DEFAULT 0,
    status VARCHAR(16) NOT NULL DEFAULT 'holding',
    plan_id INT NULL,
    note TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_holding_code (stock_code),
    KEY ix_holding_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS trade_record (
    id INT AUTO_INCREMENT PRIMARY KEY,
    holding_id INT NOT NULL,
    stock_code VARCHAR(16) NOT NULL,
    side VARCHAR(8) NOT NULL,
    price FLOAT NOT NULL,
    shares INT NOT NULL,
    amount FLOAT NOT NULL,
    trade_date VARCHAR(10) NOT NULL,
    note TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_trade_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS alert_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(16) NOT NULL,
    stock_name VARCHAR(64) NOT NULL,
    alert_type VARCHAR(32) NOT NULL,
    severity VARCHAR(8) NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    action VARCHAR(16) NOT NULL DEFAULT 'hold',
    signal JSON NULL,
    pushed TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_alert_code (stock_code),
    KEY idx_alert_type (alert_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS review_result (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(16) NOT NULL,
    stock_name VARCHAR(64) NOT NULL,
    holding_id INT NOT NULL,
    exit_date VARCHAR(10) NOT NULL,
    hold_days INT NOT NULL DEFAULT 0,
    pnl_pct FLOAT NOT NULL DEFAULT 0,
    plan_vs_actual JSON NULL,
    lesson TEXT NULL,
    feedback JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_review_code (stock_code),
    KEY ix_review_exit_status (exit_date, suggest_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS news_article (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(16) NOT NULL,
    stock_name VARCHAR(64) NOT NULL DEFAULT '',
    title VARCHAR(512) NOT NULL,
    content TEXT NULL,
    source VARCHAR(64) NOT NULL DEFAULT '',
    url VARCHAR(512) NOT NULL DEFAULT '',
    published_at VARCHAR(32) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_news_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS agent_preference (
    id INT AUTO_INCREMENT PRIMARY KEY,
    version INT NOT NULL DEFAULT 1,
    content JSON NULL,
    source_review_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sys_trade_profile (
    id INT PRIMARY KEY,
    version INT NOT NULL DEFAULT 1,
    content JSON NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS agent_suggestion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    review_id INT NOT NULL,
    target_agent VARCHAR(16) NOT NULL,
    target_kind VARCHAR(16) NOT NULL DEFAULT 'profile',
    rule_name VARCHAR(128) NOT NULL,
    current_value TEXT NULL,
    suggested_value TEXT NULL,
    reason TEXT NULL,
    evidence TEXT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_suggestion_review (review_id),
    KEY idx_suggestion_status (status),
    -- v2 一键采纳落地信息（LLM 输出；soft/hard 由代码侧校验后注入）
    priority VARCHAR(8) NOT NULL DEFAULT 'medium',
    rule_type VARCHAR(8) NOT NULL DEFAULT 'soft',
    problem_desc TEXT NULL,
    rule_text TEXT NULL,
    expected_effect TEXT NULL,
    risk_note TEXT NULL,
    file_path VARCHAR(255) NULL,
    insert_position VARCHAR(32) NULL,
    conflict_note TEXT NULL,
    dedup_note TEXT NULL,
    -- 建议来源标记（llm=LLM生成 / template=确定性模板兜底，选股验证统计）
    suggestion_source VARCHAR(16) NOT NULL DEFAULT 'llm',
    KEY idx_suggestion_source (suggestion_source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 复盘采纳规则变更记录（一键采纳自动落地：规则存库、agent_call 动态注入，绝不写源码文件）
-- 与 backend/app/db/models.py 的 RuleChange 一致；file_path/insert_position 仅展示元数据
CREATE TABLE IF NOT EXISTS rule_change (
    id INT AUTO_INCREMENT PRIMARY KEY,
    source_suggestion_id INT NOT NULL,
    review_id INT NOT NULL DEFAULT 0,
    stock_code VARCHAR(16) NOT NULL DEFAULT '',
    stock_name VARCHAR(64) NOT NULL DEFAULT '',
    target_agent VARCHAR(16) NOT NULL DEFAULT '',
    rule_type VARCHAR(8) NOT NULL DEFAULT 'soft',
    rule_name VARCHAR(128) NOT NULL DEFAULT '',
    rule_text TEXT NULL,
    priority VARCHAR(8) NOT NULL DEFAULT 'medium',
    before_text TEXT NULL,
    after_text TEXT NULL,
    reason TEXT NULL,
    evidence TEXT NULL,
    expected_effect TEXT NULL,
    risk_note TEXT NULL,
    file_path VARCHAR(255) NULL,
    insert_position VARCHAR(32) NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    rollback_reason TEXT NULL,
    rollback_time VARCHAR(16) NULL,
    operator VARCHAR(32) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_rule_change_status (status),
    KEY idx_rule_change_agent (target_agent),
    KEY idx_rule_change_suggestion (source_suggestion_id),
    KEY idx_rule_change_review (review_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- AI 研判推理链路留痕（全模块通用：discover/score/position/monitor/alert/review/sell）
-- 与 backend/app/db/models.py 的 AiReasoningTrace 一致；长文本列不建索引
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_reasoning_trace (
    trace_id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(16) NOT NULL,
    stock_name VARCHAR(64) NOT NULL,
    source_module VARCHAR(16) NOT NULL,
    generate_date VARCHAR(10) NOT NULL,
    fact_basis LONGTEXT NULL,
    technical_reasoning LONGTEXT NULL,
    capital_reasoning LONGTEXT NULL,
    fundamental_reasoning LONGTEXT NULL,
    risk_reasoning LONGTEXT NULL,
    rule_refs TEXT NULL,
    final_conclusion LONGTEXT NULL,
    confidence FLOAT NOT NULL DEFAULT 0,
    data_source VARCHAR(64) NOT NULL DEFAULT '',
    create_time VARCHAR(16) NOT NULL DEFAULT '',
    ext_info LONGTEXT NULL,
    UNIQUE KEY uq_trace_code_date_module (stock_code, generate_date, source_module),
    KEY idx_trace_module_date (source_module, generate_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 通用审核 Agent 留痕（audit_log：辩证审核结果，批1 只审 agent_suggestion）
-- 与 backend/app/db/models.py 的 AuditLog 一致；evidence_refs JSON 存 list[str]
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    target_type VARCHAR(24) NOT NULL DEFAULT 'agent_suggestion',
    target_id INT NOT NULL,
    round INT NOT NULL DEFAULT 1,
    verdict VARCHAR(8) NOT NULL DEFAULT 'pending',
    confidence INT NOT NULL DEFAULT 0,
    support_view LONGTEXT NULL,
    dissent_view LONGTEXT NULL,
    boundary_cases LONGTEXT NULL,
    evidence_refs LONGTEXT NULL,
    audit_model VARCHAR(32) NOT NULL DEFAULT '',
    reasoning LONGTEXT NULL,
    duration_ms INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_audit_target (target_type, target_id),
    KEY idx_audit_verdict (verdict),
    KEY idx_audit_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 候选池标的 T+N 自动追踪验证（选股效果闭环·代码侧客观统计）
-- 与 backend/app/db/models.py 的 CandidateTrackVerify 一致；t3/t5/t10 不足时为 NULL 表示未到期
CREATE TABLE IF NOT EXISTS candidate_track_verify (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stock_code VARCHAR(16) NOT NULL,
    stock_name VARCHAR(64) NOT NULL,
    select_date VARCHAR(10) NOT NULL,
    select_rating VARCHAR(16) NOT NULL DEFAULT '',
    base_close_price FLOAT NOT NULL DEFAULT 0,
    t3_pct FLOAT NULL,
    t5_pct FLOAT NULL,
    t10_pct FLOAT NULL,
    max_drawdown FLOAT NULL,
    verify_result JSON NULL,
    is_finished INT NOT NULL DEFAULT 0,
    update_time VARCHAR(16) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_track_code_date (stock_code, select_date),
    KEY idx_track_code (stock_code),
    KEY idx_track_status (is_finished, select_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 首页今日热门板块快照（5 分钟一次落库；首页只读，DB 兜底解决 akshare 失败 5 灰条）
-- 与 backend/app/db/models.py 的 SectorSnapshot 一致
CREATE TABLE IF NOT EXISTS sector_snapshot (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,                -- YYYY-MM-DD（与 stock_candidate 一致）
    sector_name VARCHAR(64) NOT NULL,
    change_pct FLOAT NOT NULL,
    leading_stock_name VARCHAR(64) NOT NULL DEFAULT '',
    leading_stock_code VARCHAR(16) NOT NULL DEFAULT '',
    source VARCHAR(8) NOT NULL DEFAULT '',           -- 'em' / 'sina' / 'mix'
    rank_no INT NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_sector_date_name (trade_date, sector_name),
    KEY ix_sector_date_rank (trade_date, rank_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 持仓实时价快照（每 5 分钟腾讯批量落库；持仓监控页 DB 兜底解决东财全市场 hang 超时）
-- 与 backend/app/db/models.py 的 QuoteSnapshot 一致；stock_code 唯一，新鲜度由 updated_at 判定
CREATE TABLE IF NOT EXISTS quote_snapshot (
    id INT PRIMARY KEY AUTO_INCREMENT,
    stock_code VARCHAR(10) NOT NULL,
    name VARCHAR(64) NOT NULL DEFAULT '',
    price DECIMAL(10,3) NOT NULL DEFAULT 0,
    change_pct FLOAT NULL,
    source VARCHAR(8) NOT NULL DEFAULT '',           -- 'tencent' / 'universe'
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_quote_code (stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 派发期自动判定结果（每日 15:30 落库；Monitor/Sell/Score 注入参考；6 维快照 JSON）
-- 与 backend/app/db/models.py 的 DistributionPhaseLog 一致
CREATE TABLE IF NOT EXISTS distribution_phase_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,
    symbol VARCHAR(16) NOT NULL,
    phase INT NOT NULL DEFAULT 0,
    phase_label VARCHAR(16) NOT NULL DEFAULT '',
    confidence VARCHAR(8) NOT NULL DEFAULT '',
    six_dim JSON NULL,
    missing_data JSON NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_dist_date_symbol (trade_date, symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ──── 批次E 资本视图（游资真接入）；与 backend/app/db/models.py 四表一致 ────
-- 游资维度：单标的单日命中游资（近30日窗口聚合；『三维表』之游资维）
CREATE TABLE IF NOT EXISTS capital_actor (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,
    stock_code VARCHAR(16) NOT NULL,
    actor_name VARCHAR(32) NOT NULL,
    seat_code VARCHAR(64) NOT NULL DEFAULT '',
    tier VARCHAR(8) NOT NULL DEFAULT '观察',
    net_buy DOUBLE NOT NULL DEFAULT 0,
    days_active INT NOT NULL DEFAULT 0,
    source VARCHAR(16) NOT NULL DEFAULT 'sse_only',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_cap_actor_dcn (trade_date, stock_code, actor_name),
    KEY ix_cap_actor_code_date (stock_code, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 龙虎榜维度：单标的单日龙虎榜汇总（股票级净买 + 龙头席位；『三维表』之龙虎榜维）
CREATE TABLE IF NOT EXISTS dragon_tiger (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,
    stock_code VARCHAR(16) NOT NULL,
    stock_name VARCHAR(64) NOT NULL DEFAULT '',
    lhb_type VARCHAR(8) NOT NULL DEFAULT '1d',
    net_buy DOUBLE NOT NULL DEFAULT 0,
    buy_amt DOUBLE NOT NULL DEFAULT 0,
    sell_amt DOUBLE NOT NULL DEFAULT 0,
    top_seat VARCHAR(64) NOT NULL DEFAULT '',
    top_seat_net DOUBLE NOT NULL DEFAULT 0,
    disclosure_reason VARCHAR(128) NOT NULL DEFAULT '',
    confidence DOUBLE NOT NULL DEFAULT 0.8,
    source VARCHAR(16) NOT NULL DEFAULT 'sse_only',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_dt_date_code (trade_date, stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 资金流维度：单标的单日主力/大中小单净额（『三维表』之资金流维）
CREATE TABLE IF NOT EXISTS capital_flow (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,
    stock_code VARCHAR(16) NOT NULL,
    main_net_inflow DOUBLE NOT NULL DEFAULT 0,
    super_large_net DOUBLE NOT NULL DEFAULT 0,
    large_net DOUBLE NOT NULL DEFAULT 0,
    medium_net DOUBLE NOT NULL DEFAULT 0,
    small_net DOUBLE NOT NULL DEFAULT 0,
    source VARCHAR(16) NOT NULL DEFAULT 'sse_only',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_cf_date_code (trade_date, stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 资本视图统计：单标的单日 30 日聚合快照（K189 对倒/协调/胜率/盈亏比/题材共振；徽章 + Agent 注入）
CREATE TABLE IF NOT EXISTS capital_stats (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,
    stock_code VARCHAR(16) NOT NULL,
    wash_suspect TINYINT(1) NOT NULL DEFAULT 0,
    coordination VARCHAR(8) NOT NULL DEFAULT '数据不足',
    win_rate DOUBLE NULL,
    payoff_ratio DOUBLE NULL,
    avg_hold_days DOUBLE NULL,
    theme_resonance TINYINT(1) NULL,
    source VARCHAR(16) NOT NULL DEFAULT 'sse_only',
    missing_data JSON NULL,
    raw_json JSON NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_cs_date_code (trade_date, stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 板块轮动分析·全板块每日快照（收盘 15:35 落库；与 sector_snapshot 并存不替代）
-- 与 backend/app/db/models.py 的 SectorDailySnapshot 一致；东财缺失字段如实 NULL（K227）
CREATE TABLE IF NOT EXISTS sector_daily_snapshot (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,
    sector_name VARCHAR(64) NOT NULL,
    change_pct FLOAT NOT NULL,
    rank_no INT NOT NULL,
    up_count INT NULL,
    down_count INT NULL,
    volume_ratio FLOAT NULL,
    turnover_rate FLOAT NULL,
    leading_stock_name VARCHAR(64) NOT NULL DEFAULT '',
    leading_stock_code VARCHAR(16) NOT NULL DEFAULT '',
    leading_chg FLOAT NULL,
    source VARCHAR(8) NOT NULL DEFAULT 'em',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_sd_date_name (trade_date, sector_name),
    KEY ix_sd_date_rank (trade_date, rank_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 板块轮动·轮动指标快照（批次 B 状态机结果，trade_date 唯一）
-- 与 backend/app/db/models.py 的 SectorDailyRankLog 一致
CREATE TABLE IF NOT EXISTS sector_daily_rank_log (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,
    rotation_state VARCHAR(16) NOT NULL,
    churn_rate FLOAT NULL,
    top5_overlap INT NULL,
    mainline_sector VARCHAR(64) NULL,
    notes VARCHAR(255) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_rd_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 板块轮动·启动归因（批次 C 子 Agent 输出；reason_chain 证据链 K227）
-- 与 backend/app/db/models.py 的 SectorLaunchReason 一致
CREATE TABLE IF NOT EXISTS sector_launch_reason (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,
    sector_name VARCHAR(64) NOT NULL,
    rank_no INT NOT NULL,
    reason_tags VARCHAR(128) NOT NULL DEFAULT '',
    reason_text TEXT NULL,
    reason_chain TEXT NULL,
    evidence JSON NULL,
    confidence FLOAT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_lr_date_name (trade_date, sector_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 行情结构与板块轮动前瞻·整体结构预测（C'，每日 15:40）
CREATE TABLE IF NOT EXISTS sector_regime_forecast (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,
    current_regime VARCHAR(16) NOT NULL,
    regime_stage VARCHAR(16) NOT NULL DEFAULT 'unknown',
    regime_confidence FLOAT NULL,
    forward_bias_t1 VARCHAR(32) NOT NULL DEFAULT 'uncertain',
    forward_bias_t3 VARCHAR(32) NOT NULL DEFAULT 'uncertain',
    forward_bias_t5 VARCHAR(32) NOT NULL DEFAULT 'uncertain',
    evidence JSON NULL,
    notes VARCHAR(255) NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_srf_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 行情结构与板块轮动前瞻·板块级预测（D'，每日 15:45）
CREATE TABLE IF NOT EXISTS sector_forward_forecast (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,
    sector_name VARCHAR(64) NOT NULL,
    rank_no INT NOT NULL,
    stage VARCHAR(16) NOT NULL DEFAULT 'unknown',
    continuation_prob FLOAT NULL,
    exhaustion_risk FLOAT NULL,
    chase_risk FLOAT NULL,
    switch_candidate TINYINT(1) NOT NULL DEFAULT 0,
    regime VARCHAR(16) NOT NULL DEFAULT 'unknown',
    forward_bias VARCHAR(32) NOT NULL DEFAULT 'uncertain',
    forecast_horizon VARCHAR(4) NOT NULL DEFAULT 't1',
    evidence JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_sff_date_name_horizon (trade_date, sector_name, forecast_horizon)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 行情结构与板块轮动前瞻·后验验证（E'-1，每日 16:05）
CREATE TABLE IF NOT EXISTS sector_forecast_verify (
    id INT PRIMARY KEY AUTO_INCREMENT,
    forecast_date VARCHAR(10) NOT NULL,
    verify_horizon VARCHAR(4) NOT NULL,
    verify_date VARCHAR(10) NULL,
    regime_hit TINYINT(1) NULL,
    top5_continue_rate FLOAT NULL,
    mainline_hit TINYINT(1) NULL,
    regime_forecast VARCHAR(16) NULL,
    miss_reason VARCHAR(64) NOT NULL DEFAULT '',
    detail JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_sfv_date_horizon (forecast_date, verify_horizon)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE sector_forward_forecast ADD COLUMN sector_tag VARCHAR(16) NOT NULL DEFAULT 'none';

CREATE TABLE IF NOT EXISTS sector_next_hot (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,
    sector_name VARCHAR(64) NOT NULL,
    rank_no INT NOT NULL,
    hot_score FLOAT NOT NULL,
    expected_horizon_days INT NOT NULL,
    confidence FLOAT NOT NULL,
    trigger_evidence JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_snh_date_name (trade_date, sector_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
