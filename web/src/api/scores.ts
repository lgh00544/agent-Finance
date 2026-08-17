import { get, post } from './client'
import type { StockScoreInfo } from '@/types'

/** GET /api/scores */
export const scores = (
  code?: string,
  date?: string,
  limit?: number,
): Promise<StockScoreInfo[]> =>
  get('/scores', {
    ...(code ? { code } : {}),
    ...(date ? { date } : {}),
    ...(limit != null ? { limit } : {}),
  })

/** POST /api/score/{code}（触发评分后台任务） */
export const triggerScore = (code: string): Promise<{ task_id: string }> =>
  post(`/score/${code}`, { stock_code: code })
