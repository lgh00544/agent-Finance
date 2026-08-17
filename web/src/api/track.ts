import { get, post } from './client'
import type { TrackVerifyRow, TrackVerifyStats } from '@/types'

/** GET /api/track/verify/list */
export const trackVerifyList = (
  selectDate = '',
  rating = '',
  status = '',
  limit = 200,
): Promise<TrackVerifyRow[]> =>
  get('/track/verify/list', {
    ...(selectDate ? { select_date: selectDate } : {}),
    ...(rating ? { rating } : {}),
    ...(status && status !== 'all' ? { status } : {}),
    ...(limit !== 200 ? { limit } : {}),
  })

/** GET /api/track/verify/dates */
export const trackVerifyDates = (limit = 30): Promise<string[]> =>
  get('/track/verify/dates', { limit })

/** GET /api/track/verify/stats（period: t3/t5/t10） */
export const trackVerifyStats = (period = 't5'): Promise<TrackVerifyStats> =>
  get('/track/verify/stats', { period })

/** POST /api/track/verify/run（backfill=True 历史回填，幂等） */
export const runTrackVerify = (backfill = false): Promise<Record<string, unknown>> =>
  post('/track/verify/run', { backfill })

/** POST /api/track/verify/suggest */
export const runTrackSuggest = (): Promise<Record<string, unknown>> =>
  post('/track/verify/suggest')
