import { useState } from 'react'
import { DndContext, DragOverlay, PointerSensor, useDroppable, useSensor, useSensors, type DragEndEvent, type DragStartEvent } from '@dnd-kit/core'
import { SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { App, Button, Card, Col, Descriptions, Drawer, Input, Popover, Row, Select, Space, Tag, Typography } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { agentSuggestions, rejectSuggestion, reReviewSuggestion, ruleChanges, rollbackRuleChange } from '@/api/suggestions'
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
type RuleRow = Record<string, unknown> & { id: number; _sid: number; _sug: Record<string, unknown>; _column: string; _audit: string; _round: number }
const COLUMNS = [
  { key: 'pending', title: '待 AI 审' }, { key: 'auditing', title: 'AI 审中' }, { key: 'manual', title: '人工审' },
  { key: 'pass', title: '通过' }, { key: 'recheck', title: '驳回后待重审' },
] as const
type ColumnKey = (typeof COLUMNS)[number]['key']
const columnTitle = (key: string) => COLUMNS.find((c) => c.key === key)?.title ?? key

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
    <Space orientation="vertical" size={10} style={{ width: '100%' }}>
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

function auditLabel(v: string) {
  const m = AUDIT_TONE[v]
  return m ? <StatusBadge text={m.label} tone={m.tone} /> : <Tag>{val(v)}</Tag>
}

function RuleCardBody({ rule, onAction, onOpen }: { rule: RuleRow; onAction: (a: string, r: RuleRow) => void; onOpen: (r: RuleRow) => void }) {
  const stop = (fn: () => void) => (e: React.MouseEvent) => { e.stopPropagation(); fn() }
  return (
    <Card size="small" hoverable onClick={() => onOpen(rule)} styles={{ body: { padding: 10 }, actions: { cursor: 'default' } }}>
      <Text strong ellipsis style={{ display: 'block' }}>{val(rule.rule_name)}</Text>
      <Space wrap size={4} style={{ marginTop: 6 }}>
        <Tag>{val(rule.target_agent)}</Tag>
        <Tag color={TYPE_TONE[String(rule.rule_type)]?.color ?? 'default'}>{TYPE_TONE[String(rule.rule_type)]?.label ?? val(rule.rule_type)}</Tag>
        <Popover trigger="hover" content={<AuditPopoverContent sid={rule._sid} sug={rule._sug} />}>
          {rule._audit === 'pending' ? <Tag color="orange">待审</Tag> : auditLabel(rule._audit)}
        </Popover>
        <Tag color={STATUS[String(rule.status)]?.color ?? 'default'}>{STATUS[String(rule.status)]?.label ?? val(rule.status)}</Tag>
      </Space>
      <Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 6 }}>{String(rule.created_at ?? '').slice(0, 16) || '—'}</Text>
      <Space size={4} style={{ marginTop: 8 }}>
        {['pending', 'fail'].includes(rule._audit) ? <Button size="small" type="primary" style={{ background: 'var(--up)', borderColor: 'var(--up)' }} onClick={stop(() => onAction('reaudit', rule))}>重新审核</Button> : null}
        {rule.status === 'active' ? <Button size="small" danger onClick={stop(() => onAction('rollback', rule))}>回滚</Button> : null}
        <Button size="small" onClick={stop(() => onOpen(rule))}>查看完整</Button>
      </Space>
    </Card>
  )
}

function RuleChangeCard({ rule, onAction, onOpen }: { rule: RuleRow; onAction: (a: string, r: RuleRow) => void; onOpen: (r: RuleRow) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: `rule:${rule.id}`, data: { rule, column: rule._column } })
  const style = {
    transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0) scale(${isDragging ? 1.02 : 1})` : undefined,
    transition, opacity: isDragging ? 0.3 : 1, marginBottom: 8, cursor: isDragging ? 'grabbing' : 'grab',
    touchAction: 'none', boxShadow: isDragging ? '0 14px 30px rgba(24,144,255,0.22)' : undefined,
  }
  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <RuleCardBody rule={rule} onAction={onAction} onOpen={onOpen} />
    </div>
  )
}

function BoardColumn({ col, items, onAction, onOpen }: { col: (typeof COLUMNS)[number]; items: RuleRow[]; onAction: (a: string, r: RuleRow) => void; onOpen: (r: RuleRow) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key, data: { column: col.key } })
  return (
    <Col flex="1 1 0" style={{ minWidth: 230 }}>
      <div ref={setNodeRef} style={{ minHeight: 540 }}>
        <Card size="small" title={`${col.title} ${items.length}`}
          style={{ minHeight: 520, background: isOver ? 'rgba(24,144,255,0.12)' : 'var(--bg-card)', borderColor: isOver ? '#1677ff' : undefined, boxShadow: isOver ? '0 0 0 2px rgba(22,119,255,0.2)' : undefined }}>
          <SortableContext items={items.map((r) => `rule:${r.id}`)} strategy={verticalListSortingStrategy}>
            {items.length ? items.map((rule) => <RuleChangeCard key={rule.id} rule={rule} onAction={onAction} onOpen={onOpen} />) : <Text type="secondary">拖到这里</Text>}
          </SortableContext>
        </Card>
      </div>
    </Col>
  )
}

/** 规则变更记录页（Phase 4，最轻） */
export function RuleChangesPage() {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [agents, setAgents] = useState<string[]>([])
  const [types, setTypes] = useState<string[]>([])
  const [selected, setSelected] = useState<RuleRow | null>(null)
  const [activeRule, setActiveRule] = useState<RuleRow | null>(null)
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }))
  const { data: rows, isError, error, refetch } = useQuery({ queryKey: ['rule-changes'], queryFn: () => ruleChanges() })
  // 建议审核状态 join（60s 节流；source_suggestion_id → audit_verdict/audit_round）
  const { data: sugRows } = useQuery({
    queryKey: ['agent-suggestions-audit'], queryFn: () => agentSuggestions(),
    staleTime: 60_000, refetchInterval: 60_000, retry: 0,
  })
  const sugById = new Map((sugRows ?? []).map((s) => [s.id, s]))
  const list = rows ?? []
  const rowsView = list.map((r) => {
    const sid = Number(r.source_suggestion_id ?? 0)
    const sug = (sugById.get(sid) ?? {}) as Record<string, unknown>
    const audit = String(r.audit_verdict ?? sug.audit_verdict ?? 'pending') || 'pending'
    const round = Number(r.audit_round ?? sug.audit_round ?? 0)
    const manual = String(r.review_status ?? r.review_log_status ?? '') === 'pending'
    const column = manual ? 'manual' : audit === 'pass' ? 'pass' : audit === 'fail' ? 'recheck' : round > 0 ? 'auditing' : 'pending'
    return { ...(r as Record<string, unknown>), _sid: sid, _sug: sug, _audit: audit, _round: round, _column: column } as RuleRow
  }).filter((r) => {
    const kw = keyword.trim().toLowerCase()
    const hit = !kw || [r.rule_name, r.reason, r._sug.reason].some((x) => String(x ?? '').toLowerCase().includes(kw))
    return hit && (!agents.length || agents.includes(String(r.target_agent))) && (!types.length || types.includes(String(r.rule_type)))
  })
  const grouped = Object.fromEntries(COLUMNS.map((c) => [c.key, rowsView.filter((r) => r._column === c.key)])) as Record<string, RuleRow[]>
  const agentOptions = Array.from(new Set(rowsView.map((r) => String(r.target_agent)).filter(Boolean))).map((value) => ({ value, label: value }))

  if (isError) return (
    <div>
      <Text type="danger">加载失败：{error?.message}</Text>
      <Button onClick={() => refetch()}>重试</Button>
    </div>
  )
  if (!list.length) return <EmptyState text="暂无规则变更记录。在「交易复盘」页对规则类建议执行「一键采纳」后会在此留痕。" icon="📜" />

  const rollback = (r: { id: number; rule_name?: unknown }) => {
    let reason = ''
    modal.confirm({
      title: `回滚规则：${r.rule_name ?? '—'}`,
      content: <Input.TextArea rows={3} placeholder="回滚原因（必填留痕）" onChange={(e) => { reason = e.target.value }} />,
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
  const refresh = (sid: number) => {
    qc.invalidateQueries({ queryKey: ['rule-changes'] })
    qc.invalidateQueries({ queryKey: ['agent-suggestions-audit'] })
    qc.invalidateQueries({ queryKey: ['audit-log', 'agent_suggestion', sid] })
  }
  const failText = (e: unknown, action: string) => e instanceof Error && /405|Method Not Allowed/i.test(e.message)
    ? `${action}失败：后端服务还没加载手动审核接口，请重启后端后再试`
    : e instanceof Error ? e.message : `${action}失败`
  const reAudit = (r: RuleRow) => {
    modal.confirm({
      title: `发起 AI 重新审核：${val(r.rule_name)}`,
      content: '确认后会提交后台任务重跑这条建议的 AI 审核；完成后看板会自动刷新。',
      okText: '开始审核',
      onOk: async () => {
        try {
          await reAuditSuggestion(r._sid)
          message.success('已提交重新审核任务')
          refresh(r._sid)
        } catch (e) { message.error(failText(e, '重新审核')); return Promise.reject() }
      },
    })
  }
  const reject = (r: RuleRow) => {
    let reason = ''
    modal.confirm({
      title: `驳回建议：${val(r.rule_name)}`, okText: '确认驳回', okButtonProps: { danger: true },
      content: <Input.TextArea rows={3} placeholder="驳回原因（必填）" onChange={(e) => { reason = e.target.value }} />,
      onOk: async () => {
        if (!reason.trim()) { message.error('驳回原因必填'); return Promise.reject() }
        try { await rejectSuggestion(r._sid, reason.trim()); message.success('已驳回'); refresh(r._sid) }
        catch (e) { message.error(e instanceof Error ? e.message : '驳回失败'); return Promise.reject() }
      },
    })
  }
  const reReview = (r: RuleRow) => modal.confirm({ title: `重新进入人工审：${val(r.rule_name)}`, okText: '确认',
    content: '确认后这条已驳回建议会回到“人工审”，可以再次通过、采纳或驳回。',
    onOk: async () => { try { await reReviewSuggestion(r._sid); message.success('已回到待审核'); refresh(r._sid) } catch (e) { message.error(e instanceof Error ? e.message : '操作失败'); return Promise.reject() } } })
  const onAction = (a: string, r: RuleRow) => a === 'rollback' ? rollback(r) : a === 'reject' ? reject(r) : a === 'rereview' ? reReview(r) : reAudit(r)
  const targetColumn = (overId: string, overData?: Record<string, unknown>) => (overData?.column as ColumnKey | undefined)
    ?? (rowsView.find((row) => `rule:${row.id}` === overId)?._column as ColumnKey | undefined)
    ?? (COLUMNS.some((c) => c.key === overId) ? overId as ColumnKey : undefined)
  const dragAction = (r: RuleRow, target: ColumnKey) => {
    if (target === 'recheck') return String(r._sug.status ?? r.status) === 'pending' ? 'reject' : ''
    if (target === 'manual') return String(r._sug.status) === 'rejected' ? 'rereview' : ''
    if (target === 'pending' || target === 'auditing') return 'reaudit'
    return ''
  }
  const onDragStart = ({ active }: DragStartEvent) => setActiveRule((active.data.current?.rule as RuleRow | undefined) ?? null)
  const onDragEnd = ({ active, over }: DragEndEvent) => {
    setActiveRule(null)
    if (!over) return
    const r = active.data.current?.rule as RuleRow | undefined
    const target = targetColumn(String(over.id), over.data.current as Record<string, unknown> | undefined)
    if (!r || target === r._column) return
    if (!target || target === 'pass') { message.info('“通过”只能由 AI 审核结果产生，不能手动拖入'); return }
    const action = dragAction(r, target)
    if (!action) { message.info(target === 'recheck' ? '已生效规则不能直接拖成驳回，请使用“回滚”留痕' : '这条记录当前不能进入人工审'); return }
    message.info(`准备处理：${columnTitle(target)}`)
    onAction(action, r)
  }
  const onDragCancel = () => setActiveRule(null)

  return (
    <div>
      <Space wrap style={{ marginBottom: 10 }}>
        <Text type="secondary">全部规则变更在此全量留痕，可回滚（原因必填）</Text>
        <Input.Search allowClear placeholder="搜索规则名/原因" style={{ width: 240 }} onChange={(e) => setKeyword(e.target.value)} />
        <Select mode="multiple" allowClear placeholder="Agent" options={agentOptions} style={{ width: 180 }} value={agents} onChange={setAgents} />
        <Select mode="multiple" allowClear placeholder="类型" style={{ width: 180 }} value={types} onChange={setTypes}
          options={[{ value: 'hard', label: '硬规则' }, { value: 'soft', label: '软性' }, { value: 'profile', label: '偏好' }]} />
      </Space>
      <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd} onDragCancel={onDragCancel}>
        <Row gutter={12} wrap={false} style={{ overflowX: 'auto', paddingBottom: 8 }}>
          {COLUMNS.map((col) => <BoardColumn key={col.key} col={col} items={grouped[col.key]} onAction={onAction} onOpen={setSelected} />)}
        </Row>
        <DragOverlay>{activeRule ? <div style={{ width: 260, boxShadow: '0 18px 40px rgba(0,0,0,0.35)', transform: 'rotate(1deg)', borderRadius: 8 }}><RuleCardBody rule={activeRule} onAction={onAction} onOpen={setSelected} /></div> : null}</DragOverlay>
      </DndContext>
      <Drawer title={selected ? val(selected.rule_name) : '规则详情'} open={!!selected} onClose={() => setSelected(null)} size="large" styles={{ wrapper: { width: 720 } }} destroyOnHidden>
        {selected ? <ExpandedRuleChange r={selected} sug={selected._sug} /> : null}
      </Drawer>
    </div>
  )
}

export default RuleChangesPage
