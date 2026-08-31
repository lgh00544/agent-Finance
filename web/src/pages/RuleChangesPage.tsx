import { App, Button, Descriptions, Popover, Space, Table, Tag, Typography } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { agentSuggestions, ruleChanges, rollbackRuleChange } from '@/api/suggestions'
import { getAuditLogFull, reAuditSuggestion } from '@/api/audit'
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

const val = (v: unknown) => String(v ?? '').trim() || '—'
const desc = (items: Array<[string, string | number]>) => <Descriptions size="small" column={1} items={items.map(([label, children]) => ({ label, children }))} />

function AuditPopoverContent({ sid, sug }: { sid: number; sug: Record<string, unknown> }) {
  const { data: log } = useQuery({ queryKey: ['audit-log', 'agent_suggestion', sid], queryFn: () => getAuditLogFull('agent_suggestion', sid), enabled: !!sid, staleTime: 30_000, retry: 0 })
  const ruleText = val(sug.rule_text) === val(sug.suggested_value) ? '—' : val(sug.rule_text)
  return (
    <div style={{ width: 520, maxHeight: 480, overflow: 'auto' }}>
      <Text strong>原建议</Text>
      <Descriptions size="small" column={1}>
        <Descriptions.Item label="规则名">{val(sug.rule_name)}</Descriptions.Item>
        <Descriptions.Item label="当前值">{val(sug.current_value)}</Descriptions.Item>
        <Descriptions.Item label="建议值">{val(sug.suggested_value)}</Descriptions.Item>
        <Descriptions.Item label="原因">{val(sug.reason)}</Descriptions.Item>
        <Descriptions.Item label="依据">{val(sug.evidence)}</Descriptions.Item>
        <Descriptions.Item label="问题">{val(sug.problem_desc)}</Descriptions.Item>
        <Descriptions.Item label="规则条文">{ruleText}</Descriptions.Item>
        <Descriptions.Item label="风险">{val(sug.risk_note)}</Descriptions.Item>
        <Descriptions.Item label="状态">{val(sug.status)} / {val(sug.reject_reason)} / {val(sug.created_at)}</Descriptions.Item>
      </Descriptions>
      <Text strong>AI 审核</Text>
      {!log ? (
        <Text type="secondary">未审核 — 等待 03:30 cron 或手动 audit_pending(cutoff_id=0)</Text>
      ) : (
        <Descriptions size="small" column={1}>
          <Descriptions.Item label="结论">{val(log.verdict)} / 第{val(log.round)}轮 / {val(log.confidence)}</Descriptions.Item>
          <Descriptions.Item label="支持">{val(log.support_view)}</Descriptions.Item>
          <Descriptions.Item label="反对">{val(log.dissent_view)}</Descriptions.Item>
          <Descriptions.Item label="边界">{val(log.boundary_cases)}</Descriptions.Item>
          <Descriptions.Item label="证据">{Array.isArray(log.evidence_refs) ? log.evidence_refs.join(', ') : val(log.evidence_refs)}</Descriptions.Item>
          <Descriptions.Item label="模型">{val(log.audit_model)} / {val(log.created_at)}</Descriptions.Item>
          <Descriptions.Item label="原始JSON"><Typography.Paragraph ellipsis={{ rows: 3, expandable: true }}>{val(log.reasoning).slice(0, 300)}</Typography.Paragraph></Descriptions.Item>
        </Descriptions>
      )}
    </div>
  )
}

function ExpandedRuleChange({ r, sug }: { r: Record<string, unknown>; sug: Record<string, unknown> }) {
  const sid = Number(r.source_suggestion_id ?? 0)
  const { data: log } = useQuery({ queryKey: ['audit-log', 'agent_suggestion', sid], queryFn: () => getAuditLogFull('agent_suggestion', sid), enabled: !!sid, staleTime: 30_000, retry: 0 })
  const verdict = String(sug.audit_verdict || r.audit_verdict || 'pending')
  const ruleText = val(sug.rule_text) === val(sug.suggested_value) ? '—' : val(sug.rule_text)
  return (
    <Space direction="vertical" size={10} style={{ width: '100%' }}>
      <div><Text strong>原建议</Text>{desc([
        ['规则名', val(sug.rule_name ?? r.rule_name)], ['当前值', val(sug.current_value)], ['建议值', val(sug.suggested_value ?? r.after_text)], ['原因', val(sug.reason)], ['依据', val(sug.evidence)], ['问题', val(sug.problem_desc)], ['规则条文', ruleText], ['风险', val(sug.risk_note)], ['状态', `${val(sug.status)} / ${val(sug.reject_reason)}`],
      ])}</div>
      <div><Text strong>AI 审核</Text>{desc(!log || verdict === 'pending'
        ? [['结论', '⏳ 未审核 — 等待 03:30 cron 或点击右上方“重新审核”按钮手动触发'], ['轮次', val(sug.audit_round ?? r.audit_round ?? 0)]]
        : [['结论', `${val(log.verdict)} / 第${val(log.round)}轮 / ${val(log.confidence)}`], ['支持', val(log.support_view)], ['反对', val(log.dissent_view)], ['边界', val(log.boundary_cases)], ['证据', Array.isArray(log.evidence_refs) ? log.evidence_refs.join(', ') : val(log.evidence_refs)], ['模型', `${val(log.audit_model)} / ${val(log.created_at)}`], ['原始 reasoning', val(log.reasoning).slice(0, 300)]])}</div>
      <div><Text strong>变更记录元信息</Text>{desc([['来源复盘', val(r.review_id)], ['创建时间', val(r.created_at)]])}</div>
    </Space>
  )
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
  const reAudit = (r: Record<string, unknown>) => {
    const sid = Number(r.source_suggestion_id ?? 0)
    modal.confirm({
      title: `重新审核建议：${val(r.rule_name)}`, okText: '重新审核',
      onOk: async () => {
        try {
          await reAuditSuggestion(sid)
          message.success('已触发重新审核')
          qc.invalidateQueries({ queryKey: ['agent-suggestions-audit'] })
          qc.invalidateQueries({ queryKey: ['audit-log', 'agent_suggestion', sid] })
        } catch (e) { message.error(e instanceof Error ? e.message : '重新审核失败'); return Promise.reject() }
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
      title: 'AI 审核', key: 'audit', width: 130,
      render: (_: unknown, r: Record<string, unknown>) => {
        const sid = Number(r.source_suggestion_id ?? 0)
        const sug = (sugById.get(sid) ?? r) as unknown as Record<string, unknown>
        const v = String(sug.audit_verdict ?? 'pending')
        const m = AUDIT_TONE[v]
        if (!m) return <Text type="secondary">—</Text>
        return (
          <Popover trigger="hover" content={<AuditPopoverContent sid={sid} sug={sug} />}>
            {v === 'pending' ? <Tag color="orange">⏳ 待审</Tag>
              : <StatusBadge text={m.label} tone={m.tone} />}
          </Popover>
        )
      },
    },
    { title: '时间', dataIndex: 'created_at', width: 150, render: (v: string) => String(v ?? '').slice(0, 16) },
    {
      title: '操作', key: 'ops', width: 160,
      render: (_: unknown, r: Record<string, unknown>) => r.status === 'active' ? (
        <Space size={4}>
          <Button size="small" danger onClick={() => rollback(r as { id: number; rule_name?: string })}>回滚</Button>
          {['pending', 'fail'].includes(String(r.audit_verdict ?? 'pending')) ? <Button size="small" type="default" onClick={() => reAudit(r)}>重新审核</Button> : null}
        </Space>
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
            <ExpandedRuleChange r={r as Record<string, unknown>} sug={(sugById.get(Number(r.source_suggestion_id ?? 0)) ?? r) as Record<string, unknown>} />
          ),
        }} />
    </div>
  )
}

export default RuleChangesPage
