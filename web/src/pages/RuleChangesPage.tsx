import { useState } from 'react'
import { App, Button, Space, Table, Tag, Tooltip, Typography } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { agentSuggestions, ruleChanges, rollbackRuleChange } from '@/api/suggestions'
import { getAuditLog } from '@/api/audit'
import { EmptyState, StatusBadge } from '@/components/common'

const { Text } = Typography

const STATUS: Record<string, { label: string; color: string }> = {
  active: { label: '生效中', color: 'green' },
  rolled_back: { label: '已回滚', color: 'default' },
}
/** rule_type_label 语义 */
const TYPE_TONE: Record<string, { label: string; color: string }> = {
  hard: { label: '硬规则', color: 'red' },
  soft: { label: '软性', color: 'orange' },
  profile: { label: '偏好', color: 'blue' },
}
/** AI 审核三态（复用 StatusBadge tone：pending 待审 / ok 已过 / err 驳回） */
const AUDIT_TONE: Record<string, { label: string; tone: string }> = {
  pending: { label: '待审', tone: 'pending' },
  pass: { label: '已过', tone: 'ok' },
  fail: { label: '驳回', tone: 'err' },
}

/** 规则变更记录页（Phase 4，最轻） */
export function RuleChangesPage() {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const { data: rows, isError, error, refetch } = useQuery({ queryKey: ['rule-changes'], queryFn: () => ruleChanges() })
  // 建议审核状态 join（60s 节流；source_suggestion_id → audit_verdict/audit_round）
  const { data: sugRows } = useQuery({
    queryKey: ['agent-suggestions-audit'], queryFn: () => agentSuggestions(),
    staleTime: 60_000, refetchInterval: 60_000, retry: 0,
  })
  const sugById = new Map((sugRows ?? []).map((s) => [s.id, s]))
  // hover 懒取该建议最新审核记录（dissent_view 摘要；未审核 404 → 降级行内 verdict/round）
  const [hoverSid, setHoverSid] = useState<number | null>(null)
  const { data: hoverLog } = useQuery({
    queryKey: ['audit-log', hoverSid],
    queryFn: () => getAuditLog('agent_suggestion', hoverSid as number),
    enabled: hoverSid != null,
    staleTime: 60_000, retry: 0,
  })

  if (isError) return (
    <div>
      <Text type="danger">加载失败：{error?.message}</Text>
      <Button onClick={() => refetch()}>重试</Button>
    </div>
  )
  const list = rows ?? []
  if (!list.length) return <EmptyState text="暂无规则变更记录。在「交易复盘」页对规则类建议执行「一键采纳」后会在此留痕。" icon="📜" />

  const rollback = (r: { id: number; rule_name?: string }) => {
    let reason = ''
    modal.confirm({
      title: `回滚规则：${r.rule_name ?? '—'}`,
      content: (
        <textarea
          rows={3} style={{ width: '100%', background: 'var(--bg-input)', color: 'var(--text)', border: '1px solid var(--border)', padding: 8, borderRadius: 6 }}
          placeholder="回滚原因（必填留痕），回车键危险操作" onChange={(e) => { reason = e.target.value }} />
      ),
      okText: '确认回滚', okButtonProps: { danger: true },
      onOk: async () => {
        if (!reason.trim()) { message.error('回滚原因必填'); return Promise.reject() }
        try {
          await rollbackRuleChange(r.id, reason.trim())
          message.success('已回滚，全部 Agent 立即停止携带该规则')
          qc.invalidateQueries({ queryKey: ['rule-changes'] })
        } catch (e) { message.error(e instanceof Error ? e.message : '回滚失败'); return Promise.reject() }
      },
    })
  }

  const cols = [
    { title: '归属 Agent', dataIndex: 'target_agent', width: 100, render: (v: string) => <Text strong>[{v ?? '—'}]</Text> },
    { title: '规则名', dataIndex: 'rule_name', ellipsis: true },
    {
      title: '类型', dataIndex: 'rule_type', width: 80,
      render: (v: string) => <Tag color={TYPE_TONE[v]?.color ?? 'default'}>{TYPE_TONE[v]?.label ?? v ?? 'soft'}</Tag>,
    },
    { title: '变更后内容', dataIndex: 'after_text', ellipsis: true, render: (v: string) => String(v ?? '').slice(0, 60) },
    {
      title: '状态', dataIndex: 'status', width: 90,
      render: (v: string) => <Tag color={STATUS[v]?.color ?? 'default'}>{STATUS[v]?.label ?? v}</Tag>,
    },
    {
      title: 'AI 审核', key: 'audit', width: 90,
      render: (_: unknown, r: Record<string, unknown>) => {
        const sid = Number(r.source_suggestion_id ?? 0)
        const sug = sugById.get(sid)
        if (!sug) return <Text type="secondary">—</Text>
        const v = String((sug as unknown as Record<string, unknown>).audit_verdict ?? '')
        const m = AUDIT_TONE[v]
        if (!m) return <Text type="secondary">—</Text>
        const round = String((sug as unknown as Record<string, unknown>).audit_round ?? '')
        const dissent = hoverSid === sid && hoverLog
          ? `[${String(hoverLog.verdict ?? '')}] 第${String(hoverLog.round ?? round)}轮: ${String(hoverLog.dissent_view ?? '').slice(0, 40)}...`
          : `[${m.label}] 第${round || '?'}轮`
        return (
          <Tooltip onOpenChange={(o) => setHoverSid(o ? sid : null)} title={dissent}>
            <StatusBadge text={m.label} tone={m.tone} />
          </Tooltip>
        )
      },
    },
    { title: '时间', dataIndex: 'created_at', width: 150, render: (v: string) => String(v ?? '').slice(0, 16) },
    {
      title: '操作', key: 'ops', width: 90,
      render: (_: unknown, r: { id: number; status?: string; rule_name?: string }) => r.status === 'active' ? (
        <Button size="small" danger onClick={() => rollback(r)}>回滚</Button>
      ) : null,
    },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 10 }}>
        <Text type="secondary">全部规则变更在此全量留痕，可回滚（原因必填）</Text>
      </Space>
      <Table size="small" rowKey="id" dataSource={list} columns={cols} pagination={{ pageSize: 20 }}
        expandable={{
          expandedRowRender: (r) => (
            <div>
              <div><b>变更后：</b>{r.after_text}</div>
              <div><Text type="secondary">来源复盘 {r.review_id ?? '—'} · 归属 {r.target_agent ?? '—'}</Text></div>
            </div>
          ),
        }} />
    </div>
  )
}

export default RuleChangesPage
