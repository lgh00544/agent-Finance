import { get } from './client'
import type { AiTrace } from '@/types'

/** GET /api/traces（轻量列表，code/date/module/limit 可选） */
export const traces = (
  code?: string,
  date?: string,
  module?: string,
  limit = 50,
): Promise<AiTrace[]> =>
  get('/traces', {
    ...(code ? { code } : {}),
    ...(date ? { date } : {}),
    ...(module ? { module } : {}),
    limit,
  })

/** GET /api/traces/{id} */
export const traceDetail = (traceId: number): Promise<Record<string, unknown>> =>
  get(`/traces/${traceId}`)
