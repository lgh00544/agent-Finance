import { get } from './client'
import type { HotSector, IndexItem, MarketConditionInfo, MarketIntelInfo, SectorPattern, SectorRotationInfo } from '@/types'

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

/** GET /api/market/sector-rotation（当日板块轮动：状态+top10+归因） */
export const sectorRotation = (date?: string): Promise<SectorRotationInfo> =>
  get('/market/sector-rotation', date ? { date } : undefined)

/** GET /api/market/sector-patterns（多窗口规律） */
export const sectorPatterns = (): Promise<{ patterns?: Record<string, SectorPattern> }> =>
  get('/market/sector-patterns')
