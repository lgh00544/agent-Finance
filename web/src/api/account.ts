import { get, post } from './client'
import type { AccountPnl, AccountSummary, TodayPnlEstimate } from '@/types'

/** GET /api/account/summary */
export const accountSummary = (): Promise<AccountSummary> => get('/account/summary')

// === DISABLED 2026-09-16: 同花顺账本登录态不可用（见 同花顺模块下线_方案.md §三 解注释路径）===
/** GET /api/account/pnl（同花顺真实今日盈亏；已下线，后端返 410） */
export const accountPnl = (): Promise<AccountPnl> => get<AccountPnl>('/account/pnl')

/** POST /api/account/pnl/refresh（重新读取 DSH 凭证并即时验证；已下线，后端返 410） */
export const refreshAccountPnl = (): Promise<AccountPnl> => post<AccountPnl>('/account/pnl/refresh')
// === /DISABLED ===

/** GET /api/account/today-pnl-estimate（今日盈亏推算；口径：现价−昨收 × 股数） */
export const todayPnlEstimate = (): Promise<TodayPnlEstimate> => get<TodayPnlEstimate>('/account/today-pnl-estimate')

/** POST /api/account/baseline（保存账户基准） */
export const saveAccountBaseline = (body: Record<string, unknown>): Promise<AccountSummary> =>
  post('/account/baseline', body)
