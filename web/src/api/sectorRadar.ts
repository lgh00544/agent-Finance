import { get, post } from '@/api/client'

export interface SectorRadarArticle {
  id: number
  source_scope: string
  source_type: string
  source_name: string
  title: string
  content: string
  source_url: string
  published_at: string
  sector_codes: string[]
  stock_codes: string[]
  mapping_method: string
  mapping_confidence: number
  status: string
  created_at: string
}

export interface SectorRadarInterpret {
  id: number
  polarity: 'positive' | 'negative' | 'neutral' | 'mixed' | 'uncertain'
  summary: string
  impact_mechanism: string
  impact_horizon: string
  information_score: number
  direction_confidence: number
  quote_evidence: Array<{ article_id: number; quote: string; start?: number; end?: number }>
  affected_stock_codes: string[]
  stock_relation_basis: string
  human_review_required: boolean
  validator_status: string
  created_at: string
}

export interface SectorRadarShadow {
  t1_return?: number | null
  t3_return?: number | null
  t5_return?: number | null
  direction_correct?: boolean | null
}

export interface SectorRadarSector {
  sector_code: string
  sector_name: string
}

export interface SectorRadarItem {
  article: SectorRadarArticle
  interpret?: SectorRadarInterpret | null
  shadow?: SectorRadarShadow | null
}

export interface SectorRadarResponse {
  items: SectorRadarItem[]
  sectors: SectorRadarSector[]
  total: number
}

export interface SectorRadarCollectResponse {
  sectors: number
  sectors_with_articles: number
  stock_codes_scanned: number
  stock_codes_with_articles: number
  seed_fallback_sectors: number
  articles_new: number
  articles_seen: number
  articles_skipped_low_value: number
  interprets: number
  errors: string[]
}

export const sectorRadarList = (params: {
  sector_code?: string
  days?: number
  date?: string
  source_scope?: string
}): Promise<SectorRadarResponse> => get('/sector-radar/list', params)

export const sectorRadarCollect = (body: {
  sector_code?: string
  max_sectors?: number
  max_stocks?: number
  auto_interpret?: boolean
  sleep_seconds?: number
}): Promise<SectorRadarCollectResponse> => post('/sector-radar/collect/run', body)

export const sectorRadarInterpretRun = (body: {
  sector_code?: string
  article_ids?: number[]
}): Promise<{ ok?: boolean; message?: string }> => post('/sector-radar/interpret/run', body)

export const sectorRadarFeedback = (body: {
  article_id?: number
  interpret_id?: number
  feedback_type: string
  reason?: string
}) => post('/sector-radar/feedback', body)
