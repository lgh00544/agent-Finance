import { get, post, put } from './client'
import type { TradeProfile } from '@/types'

/** GET /api/profile */
export const getProfile = (): Promise<TradeProfile> => get('/profile')

/** PUT /api/profile */
export const putProfile = (content: Record<string, unknown>): Promise<TradeProfile> =>
  put('/profile', { content })

/** GET /api/profile/export */
export const exportProfile = (): Promise<Record<string, unknown>> => get('/profile/export')

/** POST /api/profile/import */
export const importProfile = (content: Record<string, unknown>): Promise<TradeProfile> =>
  post('/profile/import', { content })
