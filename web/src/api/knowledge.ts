import { get, post } from './client'
import type { KnowledgeItem } from '@/types'

/** GET /api/knowledge */
export const knowledge = (): Promise<KnowledgeItem[]> => get('/knowledge')

/** POST /api/knowledge（新增条目） */
export const addKnowledge = (title: string, content: string, agentTag: string): Promise<{ id: number }> =>
  post('/knowledge', { title, content, agent_tag: agentTag })

/** POST /api/knowledge/{id}/delete */
export const deleteKnowledge = (kid: number): Promise<Record<string, unknown>> =>
  post(`/knowledge/${kid}/delete`)

/** POST /api/knowledge/batch-import */
export const batchImportKnowledge = (items: Array<Record<string, unknown>>): Promise<Record<string, unknown>> =>
  post('/knowledge/batch-import', { items })
