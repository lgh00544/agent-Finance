/** 核心数据类型（对齐后端返回字段；字段名与 streamlit/api_client.py 取值一致） */

// ===== 系统 / 任务 =====
export interface HealthInfo {
  status: string
  [k: string]: unknown
}
export interface SystemStatus {
  [k: string]: unknown
}
export interface LlmStats {
  requests?: number
  hit_rate_pct?: number | null
  hit_tokens?: number
  miss_tokens?: number
  models?: Array<{ model: string; calls: number; pct: number }>
  checked_at?: string
  [k: string]: unknown
}
export interface DatasourceStats {
  requests?: number
  failures?: number
  success_rate_pct?: number | null
  degraded_use?: number
  recoveries?: number
  kinds?: Array<{ kind: string; current_source: string }>
  checked_at?: string
  [k: string]: unknown
}
export interface TaskInfo {
  task_id: string
  kind: string
  label: string
  status: 'pending' | 'running' | 'done' | 'failed'
  error?: string | null
  result?: unknown
  submitted_at?: string
  started_at?: string | null
  finished_at?: string | null
}

// ===== 行情 / 市况 / 研判 =====
export interface IndexItem {
  name?: string
  code?: string
  price?: number | null
  change_pct?: number | null
}
export interface MarketIndices {
  indices?: IndexItem[]
  updated_at?: string
  [k: string]: unknown
}
export interface MarketConditionInfo {
  trade_date?: string
  total_score?: number
  band?: string
  cap?: number
  dims?: Record<string, unknown>
  summary?: string
  created_at?: string
  [k: string]: unknown
}
export interface MarketIntelInfo {
  trade_date?: string
  phase?: string
  core_conflict?: string
  risk_appetite?: string
  volume_signal?: Record<string, unknown>
  operative_meaning?: Record<string, unknown>
  next_day_watch?: Record<string, unknown>
  summary?: string
  raw?: Record<string, unknown>
  created_at?: string
  [k: string]: unknown
}
export interface HotSector {
  board_name?: string
  change_pct?: number | null
  leading_code?: string
  leading_stock?: string
  [k: string]: unknown
}

// ===== 账户 =====
export interface AccountSummary {
  total_asset?: number | null
  total_cost?: number | null
  pnl_amount?: number | null
  pnl_pct?: number | null
  position_pct?: number | null
  available_cash?: number | null
  source?: string
  baseline?: Record<string, unknown>
  [k: string]: unknown
}

// ===== 候选 / 评分 / 建仓 / 持仓 =====
export interface Candidate {
  id?: number
  stock_code: string
  stock_name?: string
  trade_date: string
  rank?: number
  reasons?: string[]
  risk_notice?: string[]
  snapshot?: Record<string, unknown>
  detail?: Record<string, unknown>
  created_at?: string
  [k: string]: unknown
}
export interface CandidateTradeable {
  date?: string
  count?: number
  plan_candidate_count?: number
  total?: number
  items?: Array<Record<string, unknown>>
  [k: string]: unknown
}
export interface StockScoreInfo {
  id?: number
  stock_code: string
  stock_name?: string
  trade_date: string
  score?: number
  grade?: string
  detail?: Record<string, unknown>
  risk_list?: unknown[]
  created_at?: string
  [k: string]: unknown
}
export interface PositionPlan {
  id?: number
  stock_code: string
  stock_name?: string
  plan_date?: string
  status?: string
  total_pct?: number
  batches?: unknown[]
  stop_loss?: number
  take_profit?: number
  rationale?: string
  detail?: Record<string, unknown>
  source?: string
  created_at?: string
  [k: string]: unknown
}
export interface Holding {
  id: number
  stock_code: string
  stock_name?: string
  entry_date?: string
  entry_price?: number
  shares?: number
  current_price?: number | null
  stop_loss?: number | null
  take_profit?: number | null
  target_pct?: number | null
  market_value?: number | null
  pnl_amount?: number | null
  pnl_pct?: number | null
  status?: string
  /** 前端去重合并标记：当前有效 / 重复录入（已自动忽略） / 历史买入 */
  _dedupe_status?: string
  created_at?: string
  [k: string]: unknown
}
export interface HoldingQuotes {
  quote_time?: string
  total_capital?: number
  rows?: Holding[]
  quote_error?: string
  [k: string]: unknown
}
export interface HoldingSignal {
  action?: string
  severity?: string
  message?: string
  confidence?: number | null
  alert_type?: string
  [k: string]: unknown
}
export interface SellDecisionInfo {
  action?: string
  confidence?: string
  reduce_ratio?: number | null
  dimensions?: unknown[]
  final_advice?: string
  reasons?: string[]
  exit_price_zone?: string
  risk_warning?: string
  [k: string]: unknown
}

// ===== 留痕 / 告警 / 复盘 =====
export interface AiTrace {
  trace_id: number
  stock_code?: string
  stock_name?: string
  generate_date?: string
  source_module?: string
  final_conclusion?: string
  capital_reasoning?: string
  risk_reasoning?: string
  create_time?: string
  confidence?: number | null
  data_source?: string
  [k: string]: unknown
}
export interface AlertInfo {
  id: number
  stock_code: string
  stock_name?: string
  alert_type?: string
  severity?: string
  action?: string
  message?: string
  created_at?: string
  pushed?: boolean
  signal?: Record<string, unknown>
  source?: string
  [k: string]: unknown
}
export interface ReviewInfo {
  id: number
  stock_code: string
  stock_name?: string
  exit_date?: string
  hold_days?: number
  pnl_pct?: number
  lesson?: string
  plan_vs_actual?: Record<string, unknown>
  feedback?: Record<string, unknown>
  suggest_status?: string
  suggest_iteration?: number
  suggest_history?: unknown[]
  created_at?: string
  [k: string]: unknown
}

// ===== 建议 / 规则 =====
export interface AgentSuggestion {
  id: number
  target_agent?: string
  rule_name?: string
  rule_type?: string
  current_value?: string
  suggested_value?: string
  reason?: string
  evidence?: string
  status?: 'pending' | 'approved' | 'rejected'
  review_id?: number | null
  created_at?: string
  [k: string]: unknown
}
export interface RuleChange {
  id: number
  target_agent?: string
  rule_name?: string
  rule_type?: string
  after_text?: string
  status?: 'active' | 'rolled_back'
  review_id?: number | null
  created_at?: string
  [k: string]: unknown
}

// ===== 验证 =====
export interface TrackVerifyRow {
  id?: number
  stock_code?: string
  stock_name?: string
  select_date?: string
  t3_pct?: number | null
  t5_pct?: number | null
  t10_pct?: number | null
  max_drawdown?: number | null
  is_finished?: number
  [k: string]: unknown
}
export interface TrackVerifyStats {
  n?: number
  wins?: number
  losses?: number
  win_rate?: number | null
  avg_pct?: number | null
  pl_ratio?: number | null
  avg_max_dd?: number | null
  anomalies?: unknown[]
  [k: string]: unknown
}

// ===== 偏好 / 知识库 =====
export interface TradeProfile {
  version?: number
  content?: Record<string, unknown>
  [k: string]: unknown
}
export interface KnowledgeItem {
  id: number
  title: string
  content: string
  agent_tag?: string
  created_at?: string
  [k: string]: unknown
}

// ===== 游资 =====
export interface HotMoneyProfile {
  id: number
  actor_name?: string
  seat_code?: string
  tier?: string
  style_tags?: string[]
  good_themes?: string[]
  co_seats?: string[]
  win_rate_5d?: number | null
  updated_at?: string
  source?: string
  [k: string]: unknown
}
export interface HotMoneyFlow {
  id: number
  trade_date?: string
  stock_code?: string
  stock_name?: string
  lhb_type?: string
  seat_name?: string
  buy_amt?: number
  sell_amt?: number
  net_buy?: number
  confidence?: number
  source?: string
  disclosure_reason?: string
  [k: string]: unknown
}

// ===== 对话 =====
export interface ChatAgentMeta {
  agent: string
  name: string
  scope?: string
  knowledge?: string
  [k: string]: unknown
}
export interface ChatMessage {
  id?: number
  agent?: string
  question?: string
  message_type?: string
  answer?: string
  confidence?: number | null
  sources?: unknown
  scope_note?: string
  meta?: Record<string, unknown>
  created_at?: string
  [k: string]: unknown
}

/** 批量验证对话：任务结果（ask_batch 返回标量结果） */
export interface BatchAskResult {
  user_msg_id?: number
  assistant_msg_id?: number
  batch_id?: number
  scope?: string
  date?: string
  count?: number
  answer?: string
  confidence?: number
  sources?: string
  scope_note?: string
  [k: string]: unknown
}

/** 批量验证对话：助理消息完整 meta（含共性/差异/建议/调整方案，按 assistant_msg_id 回查） */
export interface BatchAskMeta {
  scope?: string
  date?: string
  count?: number
  scope_note?: string
  adjust_plan?: Array<Record<string, unknown>>
  common_points?: string[]
  differences?: string[]
  suggestions?: string[]
  confidence?: number
  sources?: string[]
  [k: string]: unknown
}

// ===== 经验沉淀 =====
export interface PendingExperience {
  id: number
  task_id?: string | null
  stage?: string
  summary?: string | null
  artifacts_ref?: string | null
  status?: 'pending' | 'processing' | 'done'
  error?: string | null
  created_at?: string
}
export interface Experience {
  id: number
  title: string
  body: string
  stage?: string
  tags?: string | null
  impact?: 'high' | 'low'
  confidence?: number
  auto_merged?: number
  source_pending_id?: number | null
  status?: 'pending_review' | 'active' | 'rejected' | 'rolled_back'
  created_at?: string
  last_reviewed_at?: string | null
  /** detail 附加（get_experience_detail） */
  source_summary?: string | null
  source_task_id?: string | null
}
export interface ExperienceConfig {
  worker_cron?: string
  worker_model?: string
  confidence_threshold?: string
  auto_merge_enabled?: string
  worker_sleep_sec?: string
  digest_backlog_threshold?: string
}

// ===== OCR =====
export interface OcrStatus {
  enabled?: boolean
  available?: boolean
  reason?: string
  [k: string]: unknown
}
export interface OcrResult {
  recognized?: Array<Record<string, unknown>>
  account?: Record<string, unknown>
  raw_text?: string
  [k: string]: unknown
}
