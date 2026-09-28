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

/** POST /api/agent-suggestions/{id}/approve（overrideReason：AI 未通过时人工强制采纳，后端必填理由留痕） */
export const approveSuggestion = (sid: number, overrideReason?: string): Promise<Record<string, unknown>> =>
  post(`/agent-suggestions/${sid}/approve`,
    overrideReason ? { override_audit: true, override_reason: overrideReason } : undefined)

/** POST /api/agent-suggestions/{id}/adopt（硬规则需 confirm=True 二次确认；overrideReason：AI 未通过时人工强制采纳） */
export const adoptSuggestion = (sid: number, confirm = false, overrideReason?: string): Promise<Record<string, unknown>> =>
  post(`/agent-suggestions/${sid}/adopt`,
    overrideReason ? { confirm, override_audit: true, override_reason: overrideReason } : { confirm })

/** POST /api/agent-suggestions/{id}/reject */
export const rejectSuggestion = (sid: number, reason = ''): Promise<Record<string, unknown>> =>
  post(`/agent-suggestions/${sid}/reject`, reason ? { reason } : undefined)

/** POST /api/agent-suggestions/{id}/re_review */
export const reReviewSuggestion = (sid: number): Promise<Record<string, unknown>> =>
  post(`/agent-suggestions/${sid}/re_review`)

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
