import { get, post } from './client'
import type { AccountSummary } from '@/types'

/** GET /api/account/summary */
export const accountSummary = (): Promise<AccountSummary> => get('/account/summary')

/** POST /api/account/baseline（保存账户基准） */
export const saveAccountBaseline = (body: Record<string, unknown>): Promise<AccountSummary> =>
  post('/account/baseline', body)
