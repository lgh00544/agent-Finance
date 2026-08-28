import { get } from './client'
import type { AgentSuggestion } from '@/types'

export interface AuditStat {
  pending: number
  pass: number
  fail: number
  total: number
}

/** 建议 audit_verdict（空字符串视为未审/pending） */
function _verdict(r: AgentSuggestion): string {
  return String((r as unknown as Record<string, unknown>).audit_verdict ?? '')
}

/** GET /api/agent-suggestions → 客户端聚合 audit_verdict 三态统计 */
export const getAuditStats = async (): Promise<AuditStat> => {
  const rows = await get<AgentSuggestion[]>('/agent-suggestions')
  const stat: AuditStat = { pending: 0, pass: 0, fail: 0, total: rows?.length ?? 0 }
  for (const r of rows ?? []) {
    const v = _verdict(r)
    if (v === 'pass') stat.pass++
    else if (v === 'fail') stat.fail++
    else stat.pending++
  }
  return stat
}

/** GET /api/agent-suggestions → 待审建议（audit_verdict 空/pending） */
export const getAuditPending = async (): Promise<AgentSuggestion[]> => {
  const rows = await get<AgentSuggestion[]>('/agent-suggestions')
  return (rows ?? []).filter((r) => {
    const v = _verdict(r)
    return v === '' || v === 'pending'
  })
}

/** GET /api/audit-log（后端端点待批 1C 接线；404 返回 null 诚实降级，不崩） */
export const getAuditLog = async (
  targetType: string,
  targetId: number,
): Promise<Record<string, unknown> | null> => {
  try {
    return await get<Record<string, unknown>>('/audit-log', {
      target_type: targetType,
      target_id: targetId,
    })
  } catch {
    return null
  }
}
