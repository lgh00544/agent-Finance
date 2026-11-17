import { get, post } from './client'

export interface FactorIcRow {
  id: number
  factor_id: string
  factor_name: string
  category: string
  period: string
  ic: number | null
  ir: number | null
  hit_rate: number
  sample_size: number
  abs_ic: number
  rank_in_category: number
  status: string
}

export const factorIcHistory = (factorId?: string, period?: string, limit = 50): Promise<FactorIcRow[]> =>
  get('/factor-ic-history', { ...(factorId ? { factor_id: factorId } : {}), ...(period ? { period } : {}), limit })

export interface FactorStatusRow {
  factor_id: string
  status: 'proposed' | 'active' | 'deprecated'
  reason: string | null
  decided_by: string
  updated_at: string | null
}

export const getFactorStatus = (): Promise<FactorStatusRow[]> => get('/factor-status')

export const decideFactorStatus = (fid: string, status: 'active' | 'deprecated', reason = ''): Promise<unknown> =>
  post(`/factor-registry/${fid}/status`, { status, reason })

export interface FactorCandidate {
  id: number
  candidate_id: string
  name: string
  category: string
  hypothesis: string
  formula: string
  data_requirements: string[]
  expected_edge: string
  risk_note: string
  validation_result: Record<string, unknown>
  status: string
}

export const proposeFactorCandidates = (context = '', limit = 5): Promise<FactorCandidate[]> =>
  post('/factor-candidates/propose', { context, limit })

export const getPendingCandidates = (limit = 50): Promise<FactorCandidate[]> =>
  get('/factor-candidates/pending', { limit })
