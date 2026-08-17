import { get } from './client'
import type { AlertInfo } from '@/types'

/** GET /api/alerts */
export const alerts = (limit?: number): Promise<AlertInfo[]> =>
  get('/alerts', limit != null ? { limit } : undefined)
