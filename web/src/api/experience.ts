import { get, post } from './client'
import type { Experience, ExperienceConfig, PendingExperience } from '@/types'

/**
 * 经验沉淀闭环 API（对齐 streamlit/api_client.py 文件尾「经验沉淀闭环」分区）
 * 注意：GET /experience/search 参数名是 query（非 q），k 默认 50，仅返回 active。
 */

/** GET /api/experience/pending（M1 沉淀队列） */
export const getExperiencePending = (
  status?: string,
  stage?: string,
  limit = 50,
): Promise<PendingExperience[]> =>
  get('/experience/pending', {
    limit,
    ...(status ? { status } : {}),
    ...(stage ? { stage } : {}),
  })

/** POST /api/experience/worker/run（M1 立即触发识别；409=同类任务执行中→ConflictError） */
export const runExperienceWorker = (): Promise<{ task_id: string; label: string; status: string }> =>
  post('/experience/worker/run')

/** GET /api/experience/list（M2/M4 列表；status=auto_merged 过滤） */
export const getExperienceList = (
  status?: string,
  stage?: string,
  autoMerged?: number,
  limit = 100,
): Promise<Experience[]> =>
  get('/experience/list', {
    limit,
    ...(status ? { status } : {}),
    ...(stage ? { stage } : {}),
    ...(autoMerged != null ? { auto_merged: autoMerged } : {}),
  })

/** GET /api/experience/search（参数名 query；仅返回 active；k 默认 50） */
export const searchExperience = (
  stage?: string,
  query?: string,
  k = 50,
): Promise<Experience[]> =>
  get('/experience/search', {
    k,
    ...(stage ? { stage } : {}),
    ...(query ? { query } : {}),
  })

/** GET /api/experience/config（返回值全 string，前端负责 number 化） */
export const getExperienceConfig = (): Promise<ExperienceConfig> => get('/experience/config')

/** POST /api/experience/config（key-value 热加载；key 须为已知配置项） */
export const setExperienceConfig = (config: Record<string, string>): Promise<{ ok: boolean }> =>
  post('/experience/config', { config })

/** GET /api/experience/{eid}（含 source_summary / source_task_id） */
export const getExperienceDetail = (eid: number): Promise<Experience> =>
  get(`/experience/${eid}`)

/** POST /api/experience/{eid}/review（action=approve/reject，note 驳回必填；400/409→ConflictError） */
export const reviewExperience = (eid: number, action: string, note = ''): Promise<{ id: number; status: string }> =>
  post(`/experience/${eid}/review`, { action, note })

/** POST /api/experience/{eid}/rollback（仅 active+auto_merged 可回滚；409→ConflictError） */
export const rollbackExperience = (eid: number): Promise<{ id: number; status: string }> =>
  post(`/experience/${eid}/rollback`)
