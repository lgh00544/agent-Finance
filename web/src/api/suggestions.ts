import { get, post } from './client'
import type { AgentSuggestion, RuleChange } from '@/types'

/** GET /api/agent-suggestions */
export const agentSuggestions = (
  status?: string,
  targetAgent?: string,
): Promise<AgentSuggestion[]> =>
  get('/agent-suggestions', {
    ...(status ? { status } : {}),
    ...(targetAgent ? { target_agent: targetAgent } : {}),
  })

/** POST /api/agent-suggestions/{id}/approve */
export const approveSuggestion = (sid: number): Promise<Record<string, unknown>> =>
  post(`/agent-suggestions/${sid}/approve`)

/** POST /api/agent-suggestions/{id}/adopt（硬规则需 confirm=True 二次确认） */
export const adoptSuggestion = (sid: number, confirm = false): Promise<Record<string, unknown>> =>
  post(`/agent-suggestions/${sid}/adopt`, { confirm })

/** POST /api/agent-suggestions/{id}/reject */
export const rejectSuggestion = (sid: number, reason = ''): Promise<Record<string, unknown>> =>
  post(`/agent-suggestions/${sid}/reject`, reason ? { reason } : undefined)

/** GET /api/rule-changes */
export const ruleChanges = (
  status?: string,
  targetAgent?: string,
  suggestionId?: number,
): Promise<RuleChange[]> =>
  get('/rule-changes', {
    ...(status ? { status } : {}),
    ...(targetAgent ? { target_agent: targetAgent } : {}),
    ...(suggestionId != null ? { suggestion_id: suggestionId } : {}),
  })

/** POST /api/rule-changes/{id}/rollback（原因必填） */
export const rollbackRuleChange = (rid: number, reason: string): Promise<Record<string, unknown>> =>
  post(`/rule-changes/${rid}/rollback`, { reason })
