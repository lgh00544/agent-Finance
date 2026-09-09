import { get, post } from './client'

export type PaperMode = 'live_paper' | 'historical_replay'

export interface PaperQuoteState {
  quote_source?: string
  quote_time?: string
  quote_status?: string
  quote_error?: string
  quote_errors?: string[]
  missing_reason?: string
  fact_as_of?: string
}

export interface PaperAccount {
  id: number
  name?: string
  status?: 'active' | 'paused' | string
  strategy_variant?: string
  initial_cash?: number
  cash?: number
  execution_mode?: 'paper'
  source_label?: string
  real_assets_separate?: boolean
}

export interface PaperSummary extends PaperQuoteState {
  account_id: number
  cash?: number
  initial_cash?: number
  market_value?: number | null
  equity?: number | null
  pnl_amount?: number | null
  pnl_pct?: number | null
  position_count?: number
  valuation_as_of?: string
  positions?: PaperPosition[]
  execution_mode?: 'paper'
  source_label?: string
  real_assets_separate?: boolean
}

export interface PaperPosition extends PaperQuoteState {
  id: number
  stock_code: string
  name?: string
  stock_name?: string
  shares?: number
  available_shares?: number
  avg_price?: number
  cost?: number
  opened_trade_date?: string
  available_on?: string
  stop_loss?: number
  take_profit?: number
  current_price?: number | null
  market_value?: number | null
  pnl_amount?: number | null
  pnl_pct?: number | null
  metadata?: { monitor?: unknown; sell_decision?: unknown; [key: string]: unknown }
  execution_mode?: 'paper'
  source_label?: string
}

export interface PaperExecution {
  id: number
  stock_code?: string
  stock_name?: string
  side?: 'buy' | 'sell' | string
  status?: 'filled' | 'rejected' | string
  reject_reason?: string
  shares?: number
  executed_price?: number
  gross_amount?: number
  commission?: number
  stamp_tax?: number
  transfer_fee?: number
  trade_date?: string
  fact_as_of?: string
  metadata?: Record<string, unknown>
  metadata_json?: Record<string, unknown>
  mode?: PaperMode
  execution_mode?: 'paper'
  source_label?: string
}

export interface PaperToolTrace {
  tool?: string
  status?: string
  args?: Record<string, unknown>
  result?: unknown
  error?: string
}

export interface PaperContext {
  id: number
  account_id: number
  stock_code: string
  trade_date?: string
  mode?: PaperMode
  stage?: string
  facts?: Record<string, unknown>
  tool_trace?: PaperToolTrace[]
  source_refs?: Record<string, unknown>[]
  status?: string
  created_at?: string
}

export interface PaperWebEvidence {
  id: number
  stock_code?: string
  trade_date?: string
  url?: string
  domain?: string
  title?: string
  excerpt?: string
  published_at?: string
  fetched_at?: string
  fact_as_of?: string
  content_hash?: string
  status?: string
  error?: string
}

export interface PaperAlert {
  id: number
  stock_code?: string
  trade_date?: string
  severity?: string
  alert_type?: string
  message?: string
  source?: string
  context_id?: number
  created_at?: string
}

export interface PaperContextRequest {
  stock_code: string
  trade_date: string
  mode: PaperMode
  web_query?: string
  web_urls?: string[]
  historical_facts?: Record<string, unknown>
}

export interface PaperReview {
  id: number
  account_id: number
  stock_code: string
  stock_name?: string
  review_date?: string
  audit_status?: string
  audit_status_label?: string
  shadow_status?: string
  review_source?: string
  knowledge_id?: number | null
  content?: { lesson?: string; plan_vs_actual?: string; pnl_pct?: number; hold_days?: number; provenance?: Record<string, unknown>; [key: string]: unknown }
  [key: string]: unknown
}

export const paperAccounts = () => get<PaperAccount[]>('/paper/accounts')
export const createPaperAccount = (body: { name: string; initial_cash: number }) =>
  post<PaperAccount>('/paper/accounts', body)
export const paperSummary = (accountId: number) =>
  get<PaperSummary>(`/paper/accounts/${accountId}/summary`)
export const paperPositions = (accountId: number) =>
  get<PaperPosition[]>(`/paper/accounts/${accountId}/positions`)
export const paperExecutions = (accountId: number) =>
  get<PaperExecution[]>(`/paper/accounts/${accountId}/executions`)
export const paperContexts = (accountId: number) =>
  get<PaperContext[]>(`/paper/accounts/${accountId}/contexts`)
export const paperWebEvidence = (accountId: number) =>
  get<PaperWebEvidence[]>(`/paper/accounts/${accountId}/web-evidence`)
export const paperAlerts = (accountId: number) =>
  get<PaperAlert[]>(`/paper/accounts/${accountId}/alerts`)
export const collectPaperContext = (accountId: number, body: PaperContextRequest) =>
  post<PaperContext>(`/paper/accounts/${accountId}/contexts`, body)
export const monitorPaper = (accountId: number, tradeDate?: string) =>
  post<Record<string, unknown>>(`/paper/accounts/${accountId}/monitor`, { trade_date: tradeDate })
export const refreshPaperQuotes = (accountId: number) =>
  post<PaperSummary>(`/paper/accounts/${accountId}/quotes/refresh`)
export const setPaperAccountStatus = (accountId: number, status: 'active' | 'paused') =>
  post(`/paper/accounts/${accountId}/status`, { status })
export const paperReviews = (accountId?: number) =>
  get<PaperReview[]>('/paper/reviews', accountId == null ? undefined : { account_id: accountId })
export const runPaper = (accountId: number, tradeDate?: string) =>
  post<{ task_id?: string; status?: string; [key: string]: unknown }>(`/paper/accounts/${accountId}/run`, { trade_date: tradeDate ?? '' })
export const auditPaperReview = (reviewId: number) => post(`/paper/reviews/${reviewId}/ai-audit`)
export const shadowPaperReview = (reviewId: number) => post(`/paper/reviews/${reviewId}/shadow`)
