import { get } from './client'
import type { Candidate, CandidateTradeable } from '@/types'

/** GET /api/candidates */
export const candidates = (date?: string, limit?: number): Promise<Candidate[]> =>
  get('/candidates', { date, limit })

/** GET /api/candidates/dates */
export const candidateDates = (limit = 30): Promise<string[]> =>
  get('/candidates/dates', { limit })

/** GET /api/candidates/tradeable */
export const candidateTradeable = (date?: string, limit = 200): Promise<CandidateTradeable> =>
  get('/candidates/tradeable', { date, limit })

/** GET /api/candidate/concentration（候选集中度） */
export const candidateConcentration = (date?: string): Promise<Record<string, unknown>> =>
  get('/candidate/concentration', date ? { date } : undefined)

/** GET /api/stocks/names（批量补名，codes 数组） */
export const stockNames = (codes: string[]): Promise<Record<string, string>> =>
  get('/stocks/names', { codes: codes.join(',') })
