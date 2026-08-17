import { get, post } from './client'
import type { PositionPlan } from '@/types'

/** GET /api/positions（建仓计划列表） */
export const plans = (code?: string, limit?: number): Promise<PositionPlan[]> =>
  get('/positions', {
    ...(code ? { code } : {}),
    ...(limit != null ? { limit } : {}),
  })

/** POST /api/positions/plan（创建建仓方案后台任务） */
export const createPlan = (code: string, name = ''): Promise<{ task_id: string }> =>
  post('/positions/plan', { stock_code: code, stock_name: name })
