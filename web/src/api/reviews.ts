import { get, post } from './client'
import type { ReviewInfo } from '@/types'

/** GET /api/reviews */
export const reviews = (code?: string, limit?: number): Promise<ReviewInfo[]> =>
  get('/reviews', {
    ...(code ? { code } : {}),
    ...(limit != null ? { limit } : {}),
  })

/** POST /api/reviews/{id}/adopt */
export const adoptReview = (rid: number): Promise<Record<string, unknown>> =>
  post(`/reviews/${rid}/adopt`)

/** POST /api/reviews/{id}/reject（原因必填） */
export const rejectReview = (rid: number, reason: string): Promise<Record<string, unknown>> =>
  post(`/reviews/${rid}/reject`, { reason })

/** GET /api/portfolio_attribution（组合归因：曲线 + 贡献者 + 拖累分析） */
export const portfolioAttribution = (days = 30): Promise<{
  portfolio_curve?: Array<{ date: string; total_pnl_pct: number | null }>
  contributors?: Array<{ stock_code: string; stock_name?: string; contribution_pct: number | null; pnl_amount: number | null; holding_days: number | null }>
  drag_analysis?: string | null
}> => get('/portfolio_attribution', { days })

/** GET /api/stock_cycle_attribution/{code}（单股周期复利） */
export const stockCycleAttribution = (code: string): Promise<{
  stock_code?: string
  has_history?: boolean
  cycle_count?: number
  closed_cycle_count?: number
  unrealized_cycles?: number
  total_pnl?: number | null
  avg_hold_days?: number | null
  win_rate?: number | null
  drag_rate?: number | null
  best_cycle?: { entry_date?: string; pnl?: number | null; hold_days?: number | null } | null
  worst_cycle?: { entry_date?: string; pnl?: number | null; hold_days?: number | null } | null
}> => get(`/stock_cycle_attribution/${code}`)
