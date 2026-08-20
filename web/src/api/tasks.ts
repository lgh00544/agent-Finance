import { get, post } from './client'
import type { TaskInfo } from '@/types'

/** POST /api/tasks/submit（提交后台任务，立即返回 task_id） */
export const submitTask = (kind: string, params?: Record<string, unknown>): Promise<TaskInfo> =>
  post('/tasks/submit', { kind, params: params ?? {} })

/** GET /api/tasks/recent */
export const recentTasks = (limit = 8): Promise<TaskInfo[]> =>
  get('/tasks/recent', { limit })

/** GET /api/tasks/{id} */
export const taskDetail = (tid: string): Promise<TaskInfo> => get(`/tasks/${tid}`)

/** POST /api/tasks/{id}/retry */
export const retryTask = (tid: string): Promise<{ task_id: string; status: string }> =>
  post(`/tasks/${tid}/retry`)

/** POST /api/tasks/{id}/cancel —— 后端已实现（routes.py:250-257），仅包装 */
export const cancelTask = (tid: string): Promise<{ task_id: string; status: string; canceled: boolean }> =>
  post(`/tasks/${tid}/cancel`)
