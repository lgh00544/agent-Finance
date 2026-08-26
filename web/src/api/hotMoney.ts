import { get, post } from './client'
import type { CapitalView, HotMoneyFlow, HotMoneyProfile } from '@/types'

/** GET /api/hot-money/profiles（q=模糊搜索、tier=档位过滤） */
export const hotMoneyProfiles = (q = '', tier = ''): Promise<HotMoneyProfile[]> =>
  get('/hot-money/profiles', {
    ...(q ? { q } : {}),
    ...(tier ? { tier } : {}),
  })

/** GET /api/hot-money/flows */
export const hotMoneyFlows = (
  date?: string,
  code?: string,
  lhbType = '1d',
  limit = 500,
): Promise<HotMoneyFlow[]> =>
  get('/hot-money/flows', {
    limit,
    ...(date ? { date } : {}),
    ...(code ? { code } : {}),
    ...(lhbType ? { lhb_type: lhbType } : {}),
  })

/** GET /api/hot-money/traces */
export const hotMoneyTraces = (code?: string, limit = 50): Promise<Array<Record<string, unknown>>> =>
  get('/hot-money/traces', {
    limit,
    ...(code ? { code } : {}),
  })

/** POST /api/hot-money/win-rate-iteration（只生成建议，人工审核后生效） */
export const hotMoneyWinrateIterate = (): Promise<Record<string, unknown>> =>
  post('/hot-money/win-rate-iteration')

/** POST /api/hot-money/tier/apply（仅 approved 建议可应用） */
export const hotMoneyTierApply = (suggestionId: number): Promise<Record<string, unknown>> =>
  post('/hot-money/tier/apply', { suggestion_id: suggestionId })

/** GET /api/capital_view/{code}（K189 对倒 + 游资活跃 + 30日统计；force 穿透当日缓存） */
export const capitalView = (code: string, force = false): Promise<CapitalView> =>
  get(`/capital_view/${code}`, force ? { force: true } : {})
