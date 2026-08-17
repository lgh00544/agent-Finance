import { get } from './client'
import type { HotSector, IndexItem, MarketConditionInfo, MarketIntelInfo } from '@/types'

/** GET /api/market/indices（三大指数） */
export const marketIndices = (): Promise<{ indices?: IndexItem[]; updated_at?: string }> =>
  get('/market/indices')

/** GET /api/market/indices/history */
export const indexHistory = (days = 90): Promise<{ items?: Array<Record<string, unknown>> }> =>
  get('/market/indices/history', { days })

/** GET /api/market/hot-sectors（今日热门板块） */
export const hotSectors = (): Promise<{ sectors?: HotSector[]; updated_at?: string }> =>
  get('/market/hot-sectors')

/** GET /api/market-condition（市况评分） */
export const marketCondition = (): Promise<MarketConditionInfo | null> => get('/market-condition')

/** GET /api/market_intel */
export const marketIntel = (date?: string): Promise<MarketIntelInfo> =>
  get('/market_intel', date ? { date } : undefined)

/** GET /api/market_intel/dates */
export const marketIntelDates = (limit = 30): Promise<string[]> =>
  get('/market_intel/dates', { limit })
