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
    KEY idx_candidate_date (trade_date)
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
    KEY idx_holding_code (stock_code)
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
    KEY idx_review_code (stock_code)
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
