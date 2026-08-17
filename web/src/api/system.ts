import { get, post } from './client'
import type {
  DatasourceStats,
  HealthInfo,
  LlmStats,
  SystemStatus,
} from '@/types'

/** GET /api/health */
export const health = (): Promise<HealthInfo> => get('/health')

/** GET /api/system/status */
export const systemStatus = (): Promise<SystemStatus> => get('/system/status')

/** GET /api/dashboard（首页看板聚合） */
export const dashboard = (): Promise<Record<string, unknown>> => get('/dashboard')

/** GET /api/jobs/status */
export const jobStatus = (): Promise<Record<string, unknown>> => get('/jobs/status')

/** GET /api/llm/stats */
export const llmStats = (): Promise<LlmStats> => get('/llm/stats')

/** GET /api/datasource/stats */
export const datasourceStats = (): Promise<DatasourceStats> => get('/datasource/stats')

/** POST /api/jobs/discover/run（手动触发每日挖掘） */
export const runDiscover = (): Promise<Record<string, unknown>> => post('/jobs/discover/run')
