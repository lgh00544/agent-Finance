import { get, post } from './client'
import type { Holding, HoldingQuotes, HoldingSignal } from '@/types'

/** GET /api/holdings */
export const holdings = (status?: string): Promise<Holding[]> =>
  get('/holdings', status ? { status } : undefined)

/** GET /api/holdings/quotes（持仓列表视图：实时行情 + 参考风控位） */
export const holdingQuotes = (): Promise<HoldingQuotes> => get('/holdings/quotes')

/** POST /api/holdings（人工录入建仓） */
export const addHolding = (body: Record<string, unknown>): Promise<Holding> =>
  post('/holdings', body)

/** POST /api/holdings/{id}/exit（减仓/清仓） */
export const exitHolding = (hid: number, body: Record<string, unknown>): Promise<Record<string, unknown>> =>
  post(`/holdings/${hid}/exit`, body)

/** POST /api/holdings/{id}/add（手动加仓） */
export const holdingAdd = (hid: number, body: Record<string, unknown>): Promise<Record<string, unknown>> =>
  post(`/holdings/${hid}/add`, body)

/** POST /api/holdings/{id}/cost（手动成本修正，原因必填） */
export const holdingCost = (hid: number, body: Record<string, unknown>): Promise<Record<string, unknown>> =>
  post(`/holdings/${hid}/cost`, body)

/** GET /api/holdings/{id}/trades（操作流水） */
export const holdingTrades = (hid: number): Promise<Array<Record<string, unknown>>> =>
  get(`/holdings/${hid}/trades`)

/** POST /api/holdings/{id}/monitor（立即执行监控） */
export const monitorHolding = (hid: number): Promise<{ signal?: HoldingSignal }> =>
  post(`/holdings/${hid}/monitor`)

/** POST /api/holdings/{id}/sell-decision（生成卖出决策后台任务） */
export const sellDecision = (hid: number): Promise<{ task_id: string }> =>
  post(`/holdings/${hid}/sell-decision`)

/** GET /api/holdings/{id}/sell-decisions（卖出决策历史） */
export const sellDecisions = (hid: number): Promise<Array<Record<string, unknown>>> =>
  get(`/holdings/${hid}/sell-decisions`)

/** GET /api/holdings/take-profit-plan（止盈/仓位计划） */
export const takeProfitPlan = (force = false): Promise<{ rows?: Array<Record<string, unknown>> }> =>
  get('/holdings/take-profit-plan', force ? { force: true } : undefined)

/** GET /api/red_line_check（持仓红线扫描：C1/C2/C3/K139 四色徽章数据源） */
export const redLineCheck = (): Promise<{ rows?: Array<Record<string, unknown>> }> =>
  get('/red_line_check')
