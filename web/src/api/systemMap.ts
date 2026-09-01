import { get } from './client'
import type {
  SystemMapAgent,
  SystemMapAllowedTargets,
  SystemMapCanCollaborateResult,
  SystemMapCollaborationRule,
  SystemMapHealth,
  SystemMapSummary,
  SystemMapTool,
  SystemMapWorkflow,
} from '@/types'

export const systemMapSummary = (): Promise<SystemMapSummary> => get('/system-map')

export const systemMapHealth = (): Promise<SystemMapHealth> => get('/system-map/health')

export const systemMapAgents = (): Promise<SystemMapAgent[]> => get('/system-map/agents')

export const systemMapAgent = (agentId: string): Promise<SystemMapAgent> =>
  get(`/system-map/agents/${encodeURIComponent(agentId)}`)

export const systemMapTools = (): Promise<SystemMapTool[]> => get('/system-map/tools')

export const systemMapWorkflows = (): Promise<SystemMapWorkflow[]> => get('/system-map/workflows')

export const systemMapCollaboration = (): Promise<SystemMapCollaborationRule[]> =>
  get('/system-map/collaboration')

export const systemMapAllowedTargets = (agentId: string): Promise<SystemMapAllowedTargets> =>
  get(`/system-map/agents/${encodeURIComponent(agentId)}/allowed-targets`)

export const systemMapCanCollaborate = (
  requester: string,
  target: string,
  relation: string,
): Promise<SystemMapCanCollaborateResult> =>
  get('/system-map/can-collaborate', { requester, target, relation })
