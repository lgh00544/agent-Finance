import { get, post } from './client'
import type { AccountPnl, AccountSummary } from '@/types'

/** GET /api/account/summary */
export const accountSummary = (): Promise<AccountSummary> => get('/account/summary')

/** GET /api/account/pnl（同花顺真实今日盈亏；未开启返回 {configured:false}） */
export const accountPnl = (): Promise<AccountPnl> => get<AccountPnl>('/account/pnl')

/** POST /api/account/baseline（保存账户基准） */
export const saveAccountBaseline = (body: Record<string, unknown>): Promise<AccountSummary> =>
  post('/account/baseline', body)
