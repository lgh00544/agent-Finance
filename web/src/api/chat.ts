import { get, post, upload, UPLOAD_CHAT_TIMEOUT } from './client'
import type { ChatAgentMeta, ChatMessage } from '@/types'

/** GET /api/agent-chat/agents */
export const chatAgents = (): Promise<ChatAgentMeta[]> => get('/agent-chat/agents')

/** GET /api/agent-chat/history（message_type 可选：batch=批量验证对话） */
export const chatHistory = (agent: string, limit = 50, messageType?: string): Promise<ChatMessage[]> =>
  get('/agent-chat/history', {
    agent,
    limit,
    ...(messageType ? { message_type: messageType } : {}),
  })

/** POST /api/agent-chat/batch-ask（异步任务，返回 task_id） */
export const batchAsk = (
  scope: string,
  codes: string[],
  question: string,
  date = '',
): Promise<{ task_id: string }> =>
  post('/agent-chat/batch-ask', { scope, codes, question, date })

/** POST /api/agent-chat/batch-adjust/apply */
export const applyBatchAdjust = (batchId: number): Promise<Record<string, unknown>> =>
  post('/agent-chat/batch-adjust/apply', { batch_id: batchId })

/** POST /api/agent-chat/batch-adjust/{id}/rollback */
export const rollbackBatchAdjust = (batchId: number, reason = ''): Promise<Record<string, unknown>> =>
  post(`/agent-chat/batch-adjust/${batchId}/rollback`, { reason })

/** POST /api/agent-chat/ask（异步任务） */
export const chatAsk = (agent: string, question: string): Promise<{ task_id: string }> =>
  post('/agent-chat/ask', { agent, question })

/** POST /api/agent-chat/rules（异步任务） */
export const chatRule = (agent: string, proposal: string): Promise<{ task_id: string }> =>
  post('/agent-chat/rules', { agent, proposal })

/** POST /api/agent-chat/learn（multipart 上传，params 带 agent、data 带 description，timeout 60s） */
export const chatLearn = (
  agent: string,
  imageBytes: Blob,
  filename: string,
  description = '',
): Promise<Record<string, unknown>> =>
  upload(
    '/agent-chat/learn',
    imageBytes,
    filename,
    { agent },
    { description },
    UPLOAD_CHAT_TIMEOUT,
  )

/** POST /api/agent-chat/learn/confirm */
export const chatLearnConfirm = (
  agent: string,
  entries: Array<Record<string, unknown>>,
): Promise<Record<string, unknown>> =>
  post('/agent-chat/learn/confirm', { agent, entries })
