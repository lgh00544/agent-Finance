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
