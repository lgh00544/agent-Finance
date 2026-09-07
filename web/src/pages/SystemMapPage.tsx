import { useMemo, useState } from 'react'
import { Alert, Button, Card, Descriptions, Drawer, Empty, Form, Input, Select, Space, Table, Tabs, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useQuery } from '@tanstack/react-query'
import {
  systemMapAgent,
  systemMapAgents,
  systemMapCanCollaborate,
  systemMapCollaboration,
  systemMapHealth,
  systemMapSummary,
  systemMapTools,
  systemMapWorkflows,
} from '@/api/systemMap'
import { EmptyState, ErrorCard, StatCard } from '@/components/common'
import type {
  SystemMapAgent,
  SystemMapCanCollaborateResult,
  SystemMapCollaborationRule,
  SystemMapHealth,
  SystemMapHealthModule,
  SystemMapMigrationSummary,
  SystemMapTool,
  SystemMapWorkflow,
} from '@/types'

const { Paragraph, Text, Title } = Typography

const TAB_DESCRIPTIONS: Record<string, string> = {
  summary: '总览：整体能力概览与数字指标。',
  agents: 'Agent 能力：查看每个 Agent 的职责、权限、知识范围、输入输出与可调用关系。',
  workflows: 'Workflow：人机协作流程，定义 Agent 任务入口与确认要求（如立即研判需要后台跑 1-2 分钟）。',
  tools: '只读工具：ReAct 数据查询工具，Agent 推理时调用，只读不写。',
  collaboration: '协作矩阵：Agent 间显式声明的协作关系（白名单）。未声明的调用默认禁止（fail-closed）。',
  health: '运行状态：实际运行数据，包括任务执行次数、成功率、最近运行时间等。',
}

const RELATIONS = ['call', 'reference', 'propose_change']
const DEFAULT_FORBIDDEN_ROW: SystemMapCollaborationRule & { _synthetic?: boolean } = {
  requester_agent: '未声明调用方',
  target_agent: '未声明目标',
  relation: '未声明关系',
  allowed: false,
  max_depth: 0,
  conflict_policy: 'deny_by_default',
  audit_required: false,
  reason: '协作矩阵未声明的调用方 / 目标 / 关系默认禁止。',
  _synthetic: true,
}

const asList = (value: unknown): string[] => {
  if (Array.isArray(value)) return value.map((item) => String(item ?? '').trim()).filter(Boolean)
  const text = String(value ?? '').trim()
  return text ? [text] : []
}

const text = (value: unknown, fallback = '—') => {
  const s = String(value ?? '').trim()
  return s || fallback
}
const ENUM_LABELS: Record<string, string> = {
  research_decision: '研究决策（research_decision）', entry_orchestrator: '入口编排（entry_orchestrator）',
  experience: '经验治理（experience）', proposal: '提议权限（proposal）', advisory: '咨询权限（advisory）',
  governance: '治理权限（governance）', readonly_data: '只读数据（readonly_data）',
  return_error_payload: '返回错误载荷（return_error_payload）', deny_by_default: '默认拒绝（deny_by_default）',
  call: '调用（call）', reference: '引用（reference）', propose_change: '提议变更（propose_change）',
  agent: 'Agent 专属（agent）', market: '市场范围（market）', selected_agent: '指定 Agent（selected_agent）',
  discover: '发现研判（discover）', score: '评分（score）', position: '建仓（position）',
  monitor: '监控（monitor）', sell: '卖出（sell）', review: '复盘（review）',
  market_intel: '市场研判（market_intel）', portfolio_sentinel: '组合哨兵（portfolio_sentinel）',
}
const enumText = (value: unknown, fallback = '—') => {
  const raw = text(value, fallback)
  return ENUM_LABELS[raw] ?? raw
}

function TagList({ value, color }: { value: unknown; color?: string }) {
  const items = asList(value)
  if (!items.length) return <Text type="secondary">—</Text>
  return (
    <Space size={[4, 4]} wrap>
      {items.map((item) => <Tag key={item} color={color}>{enumText(item)}</Tag>)}
    </Space>
  )
}

function CompactValue({ value }: { value: unknown }) {
  if (Array.isArray(value)) return <TagList value={value} />
  if (value && typeof value === 'object') {
    return (
      <Space size={[4, 4]} wrap>
        {Object.keys(value as Record<string, unknown>).map((key) => <Tag key={key}>{key}</Tag>)}
      </Space>
    )
  }
  return <Text>{text(value)}</Text>
}

function BoolTag({ value, trueText, falseText }: { value?: boolean; trueText: string; falseText: string }) {
  return <Tag color={value ? 'orange' : 'green'}>{value ? trueText : falseText}</Tag>
}

const MODULE_LABELS: Record<string, string> = {
  system_map: '系统能力地图',
  knowledge: '知识库',
  shadow: '影子记录 / 失败重放',
  experience_memory: '经验沉淀',
  rule_change_audit: '规则变更审计',
  collaboration: '协作矩阵',
  database_migration: '数据库迁移',
  registration_integrity: '注册完整性',
}
const FIELD_LABELS: Record<string, string> = {
  total: '总条目数', total_hits: '总命中数', agents: 'Agent 数', workflows: 'Workflow 数', tools: '工具数',
  active: '活跃条目', archived: '已归档', expired: '已过期', unknown_status: '未知状态', shadow: '影子数',
  unfinished_t_plus_n: '待补算 L+N', unfinished_lplus_n: '待补算 L+N', backfilled: '已回填',
  failed_or_error: '失败/错误', pending_review: '待审核', rolled_back: '已回滚', rejected: '已驳回',
  expired_by_time: '按时间过期', pending_queue: '待处理队列', processing_queue: '处理中队列', failed_queue: '失败队列',
  suggestions_total: '建议总数', pending: '待审核', ai_pending: 'AI 待审', ai_failed: 'AI 失败',
  manual_pending: '人工待审', active_rules: '生效规则', rolled_back_rules: '已回滚规则', audit_logs: '审计日志',
  explicit_allowed: '明确允许', explicit_rules: '明确规则', default_forbidden_estimate: '默认禁止估算',
  runtime_rejections: '运行时拒绝', unknown_callers: '未知调用方', unknown_targets: '未知目标方',
}
const fieldLabel = (key: string) => {
  if (FIELD_LABELS[key]) return FIELD_LABELS[key]
  if (/^active_\d+$/.test(key)) return `活跃 ${key.slice(7)}`
  if (key.startsWith('curator_')) return '策展字段'
  if (key.startsWith('soft_')) return '软文字段'
  if (key.startsWith('hard_')) return '硬规则字段'
  if (key.startsWith('audit_')) return '审计字段'
  if (key.startsWith('collaboration')) return '协作字段'
  return '其他字段'
}
const fieldValue = (value: unknown) => {
  if (value == null || value === '') return '—'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function allowedTone(allowed?: boolean) {
  return allowed ? { color: 'green', label: '允许' } : { color: 'red', label: '默认禁止' }
}

function estimateDefaultForbidden(agents: SystemMapAgent[], rules: SystemMapCollaborationRule[]) {
  const nodes = new Set<string>()
  agents.forEach((agent) => nodes.add(agent.agent_id))
  rules.forEach((rule) => {
    nodes.add(rule.requester_agent)
    nodes.add(rule.target_agent)
  })
  const relationSet = new Set([...RELATIONS, ...rules.map((rule) => rule.relation)])
  const total = nodes.size * Math.max(nodes.size - 1, 0) * relationSet.size
  const explicit = new Set(rules.map((rule) => `${rule.requester_agent}->${rule.target_agent}:${rule.relation}`)).size
  return Math.max(total - explicit, 0)
}

function SummaryTab({
  summary,
  agents,
  workflows,
  tools,
  collaboration,
}: {
  summary?: { agents_count?: number; workflows_count?: number; tools_count?: number }
  agents: SystemMapAgent[]
  workflows: SystemMapWorkflow[]
  tools: SystemMapTool[]
  collaboration: SystemMapCollaborationRule[]
}) {
  const defaultForbidden = estimateDefaultForbidden(agents, collaboration)
  const allowedCount = collaboration.filter((rule) => rule.allowed).length
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, minmax(0, 1fr))', gap: 12, margin: '8px 0 16px' }}>
        <Tooltip title="8 个业务决策单元：Discover / Score / Position / Monitor / Sell / Review / MarketCondition / MarketIntel"><span style={{ minWidth: 0 }}><StatCard label="Agent" value={summary?.agents_count ?? agents.length} tone="info" sub="8 个业务决策单元" /></span></Tooltip>
        <Tooltip title="9 个人机协作流程，含立即研判、立即分析、生成建议等任务入口"><span style={{ minWidth: 0 }}><StatCard label="Workflow" value={summary?.workflows_count ?? workflows.length} tone="mute" sub="9 个人机协作流程" /></span></Tooltip>
        <Tooltip title="12 个 ReAct 数据查询工具，供 Agent 推理时使用，不写不改"><span style={{ minWidth: 0 }}><StatCard label="只读工具" value={summary?.tools_count ?? tools.length} tone="ok" sub="12 个 ReAct 工具" /></span></Tooltip>
        <Tooltip title="显式声明允许的 Agent 间调用/引用关系数；绿色表示已审批"><span style={{ minWidth: 0 }}><StatCard label="允许协作" value={allowedCount} tone="ok" sub="显式声明的协作数" /></span></Tooltip>
        <Tooltip title="未声明的潜在协作关系数；红色表示禁止，与白名单互斥"><span style={{ minWidth: 0 }}><StatCard label="默认禁止" value={defaultForbidden} tone="warn" sub="未声明即禁止" /></span></Tooltip>
        <Tooltip title="本页面只读；治理/规则修改请走 Agent 对话或人工审核流程"><span style={{ minWidth: 0 }}><StatCard label="红线状态" value="只读" tone="err" sub="本页只读" /></span></Tooltip>
      </div>
      <Alert
        type="info"
        showIcon
        message="系统治理看板仅展示后端只读 System Map 与协作矩阵；未声明协作关系默认禁止，规则、知识、记忆和交易动作仍走原有人工/审计边界。"
      />
    </Space>
  )
}

function AgentDrawer({ agent, onClose }: { agent: SystemMapAgent | null; onClose: () => void }) {
  const detail = useQuery({
    queryKey: ['system-map-agent', agent?.agent_id],
    queryFn: () => systemMapAgent(agent!.agent_id),
    enabled: !!agent?.agent_id,
    retry: 0,
  })
  const row = detail.data ?? agent
  return (
    <Drawer title={row ? `${text(row.name)} · ${row.agent_id}` : 'Agent 详情'} open={!!agent} width={720} onClose={onClose} destroyOnHidden>
      {detail.isError ? (
        <Alert type="error" showIcon message="Agent 详情不存在或后端不可用" description={detail.error.message} />
      ) : row ? (
        <Descriptions size="small" column={1} items={[
          { label: '职责（responsibility）', children: text(row.responsibility) },
          { label: 'Agent 类型（agent_type）', children: enumText(row.agent_type) },
          { label: '权限等级（authority_level）', children: enumText(row.authority_level) },
          { label: '知识范围（knowledge_scope）', children: enumText(row.knowledge_scope) },
          { label: '知识（knowledge）', children: text(row.knowledge) },
          { label: '必填输入（inputs_required）', children: <TagList value={row.inputs_required} /> },
          { label: '可选输入（inputs_optional）', children: <TagList value={row.inputs_optional} /> },
          { label: '输出（outputs）', children: <TagList value={row.outputs} color="blue" /> },
          { label: '可引用（can_reference）', children: <TagList value={row.can_reference} color="cyan" /> },
          { label: '可调用（can_call）', children: <TagList value={row.can_call} color="green" /> },
          { label: '不可做（cannot_do）', children: <TagList value={row.cannot_do} color="red" /> },
          { label: '人工门禁（human_gate_required）', children: <BoolTag value={row.human_gate_required} trueText="需要人工门禁" falseText="不要求人工门禁" /> },
        ]} />
      ) : (
        <Empty description="未选择 Agent" />
      )}
    </Drawer>
  )
}

function AgentsTab({ agents }: { agents: SystemMapAgent[] }) {
  const [selected, setSelected] = useState<SystemMapAgent | null>(null)
  if (!agents.length) return <EmptyState text="暂无 Agent 注册信息。" />
  const columns: ColumnsType<SystemMapAgent> = [
    { title: '智能体（Agent）', dataIndex: 'name', width: 150, render: (_: unknown, row) => <Space direction="vertical" size={0}><Text strong>{text(row.name)}</Text><Text type="secondary">{row.agent_id}</Text></Space> },
    { title: '责任', dataIndex: 'responsibility', render: (v) => <Paragraph ellipsis={{ rows: 2, expandable: true }}>{text(v)}</Paragraph> },
    { title: '类型/权限', key: 'type', width: 150, render: (_: unknown, row) => <Space direction="vertical" size={2}><Tag>{enumText(row.agent_type)}</Tag><Tag color="blue">{enumText(row.authority_level)}</Tag></Space> },
    { title: '知识范围', dataIndex: 'knowledge_scope', width: 130, render: (v) => <Tag color="cyan">{enumText(v)}</Tag> },
    { title: '可引用', dataIndex: 'can_reference', render: (v) => <TagList value={v} color="cyan" /> },
    { title: '可调用', dataIndex: 'can_call', render: (v) => <TagList value={v} color="green" /> },
    { title: '不可做', dataIndex: 'cannot_do', render: (v) => <TagList value={v} color="red" /> },
    { title: '人工门禁', dataIndex: 'human_gate_required', width: 110, render: (v) => <BoolTag value={!!v} trueText="需要" falseText="不需要" /> },
  ]
  return (
    <>
      <Table<SystemMapAgent> rowKey="agent_id" size="small" columns={columns} dataSource={agents} pagination={{ pageSize: 10 }} onRow={(row) => ({ onClick: () => setSelected(row) })} scroll={{ x: 1180 }} />
      <AgentDrawer agent={selected} onClose={() => setSelected(null)} />
    </>
  )
}

function WorkflowsTab({ workflows }: { workflows: SystemMapWorkflow[] }) {
  if (!workflows.length) return <EmptyState text="暂无 Workflow 注册信息。" />
  const columns: ColumnsType<SystemMapWorkflow> = [
    { title: '工作流（Workflow）', dataIndex: 'name', width: 170, render: (_: unknown, row) => <Space direction="vertical" size={0}><Text strong>{text(row.name)}</Text><Text type="secondary">{row.workflow_id}</Text></Space> },
    { title: '示例意图', dataIndex: 'intent_examples', render: (v) => <TagList value={v} /> },
    { title: '步骤', dataIndex: 'steps', render: (v) => <TagList value={v} color="blue" /> },
    { title: '必填输入', dataIndex: 'required_inputs', render: (v) => <TagList value={v} color="orange" /> },
    { title: '可选输入', dataIndex: 'optional_inputs', render: (v) => <TagList value={v} /> },
    { title: '入口 Agent', dataIndex: 'allowed_entry_agents', render: (v) => <TagList value={v} color="cyan" /> },
    { title: '治理状态', key: 'gate', width: 180, render: (_: unknown, row) => <Space wrap><BoolTag value={row.audit_required} trueText="需审核" falseText="仅分析/查询" /><BoolTag value={row.human_confirm_required} trueText="需人工确认" falseText="无需人工确认" /></Space> },
    { title: '最终响应（final_responder）', dataIndex: 'final_responder', width: 130, render: (v) => <Tag>{enumText(v)}</Tag> },
  ]
  return <Table<SystemMapWorkflow> rowKey="workflow_id" size="small" columns={columns} dataSource={workflows} pagination={{ pageSize: 10 }} scroll={{ x: 1180 }} />
}

function ToolsTab({ tools }: { tools: SystemMapTool[] }) {
  if (!tools.length) return <EmptyState text="暂无只读工具注册信息。" />
  const columns: ColumnsType<SystemMapTool> = [
    { title: '工具（Tool）', dataIndex: 'tool_id', width: 190, render: (v, row) => <Space direction="vertical" size={0}><Text strong>{text(v)}</Text><Text type="secondary">{text(row.owner_module)}</Text></Space> },
    { title: '描述', dataIndex: 'description', render: (v) => <Paragraph ellipsis={{ rows: 2, expandable: true }}>{text(v)}</Paragraph> },
    { title: '类型（tool_type）', dataIndex: 'tool_type', width: 130, render: (v) => <Tag color="green">{enumText(v, 'readonly_data')}</Tag> },
    { title: '输入', dataIndex: 'inputs', render: (v) => <CompactValue value={v} /> },
    { title: '输出', dataIndex: 'outputs', width: 100, render: (v) => <CompactValue value={v} /> },
    { title: '使用方', dataIndex: 'used_by', render: (v) => <TagList value={v} color="cyan" /> },
    { title: '失败降级（failure_policy）', dataIndex: 'failure_policy', width: 160, render: (v) => <Tag color="orange">{enumText(v)}</Tag> },
    { title: '不可做', dataIndex: 'cannot_do', render: (v) => <TagList value={v} color="red" /> },
  ]
  return (
    <Space direction="vertical" size={10} style={{ width: '100%' }}>
      <Alert type="info" showIcon message="只读 ReAct 工具仅返回数据或错误载荷（error payload）；本页不提供工具执行、交易或业务写库入口。" />
      <Table<SystemMapTool> rowKey="tool_id" size="small" columns={columns} dataSource={tools} pagination={{ pageSize: 10 }} scroll={{ x: 1180 }} />
    </Space>
  )
}

function CollaborationQuery({ agentOptions, relationOptions }: { agentOptions: Array<{ value: string; label: string }>; relationOptions: Array<{ value: string; label: string }> }) {
  const [params, setParams] = useState({ requester: '', target: '', relation: 'call' })
  const [submitted, setSubmitted] = useState<typeof params | null>(null)
  const incomplete = !params.requester.trim() || !params.target.trim() || !params.relation.trim()
  const result = useQuery({
    queryKey: ['system-map-can-collaborate', submitted],
    queryFn: () => systemMapCanCollaborate(submitted!.requester, submitted!.target, submitted!.relation),
    enabled: !!submitted,
    retry: 0,
  })
  const data = result.data as SystemMapCanCollaborateResult | undefined
  const tone = allowedTone(data?.allowed)
  return (
    <Card size="small" title="只读协作查询" style={{ background: 'var(--bg-input)' }}>
      <Space direction="vertical" size={10} style={{ width: '100%' }}>
        <Form layout="inline">
          <Form.Item label="调用方（caller/requester）">
            <Select showSearch allowClear style={{ width: 190 }} placeholder="选择或输入智能体（Agent）" options={agentOptions} value={params.requester || undefined} onChange={(v) => setParams((prev) => ({ ...prev, requester: v ?? '' }))} onSearch={(v) => setParams((prev) => ({ ...prev, requester: v }))} />
          </Form.Item>
          <Form.Item label="目标（target）">
            <Select showSearch allowClear style={{ width: 190 }} placeholder="选择或输入目标（target）" options={agentOptions} value={params.target || undefined} onChange={(v) => setParams((prev) => ({ ...prev, target: v ?? '' }))} onSearch={(v) => setParams((prev) => ({ ...prev, target: v }))} />
          </Form.Item>
          <Form.Item label="关系（relation）">
            <Select showSearch style={{ width: 170 }} options={relationOptions} value={params.relation} onChange={(v) => setParams((prev) => ({ ...prev, relation: v }))} onSearch={(v) => setParams((prev) => ({ ...prev, relation: v }))} />
          </Form.Item>
          <Button type="primary" disabled={incomplete} loading={result.isFetching} onClick={() => setSubmitted(params)}>查询</Button>
        </Form>
        {incomplete ? <Alert type="warning" showIcon message="请完整填写调用方、目标和关系后再查询。" /> : null}
        {result.isError ? <Alert type="error" showIcon message="协作查询失败" description={result.error.message} /> : null}
        {data ? (
          <Descriptions size="small" column={2} items={[
            { label: '允许（allowed）', children: <Tag color={tone.color}>{tone.label}</Tag> },
            { label: '调用方（caller）', children: text(data.caller ?? data.requester_agent) },
            { label: '目标（target）', children: text(data.target ?? data.target_agent) },
            { label: '关系（relation）', children: enumText(data.relation) },
            { label: '原因（reason）', children: text(data.reason) },
            { label: '未知调用方（unknown_caller）', children: String(!!data.unknown_caller) },
            { label: '未知目标（unknown_target）', children: String(!!data.unknown_target) },
            { label: '默认禁止（default_denied）', children: String(!!data.default_denied) },
          ]} />
        ) : null}
      </Space>
    </Card>
  )
}

function CollaborationTab({ agents, rules }: { agents: SystemMapAgent[]; rules: SystemMapCollaborationRule[] }) {
  const [filters, setFilters] = useState({ requester: '', target: '', relation: '', allowed: '' })
  const rows = useMemo(() => [...rules, DEFAULT_FORBIDDEN_ROW], [rules])
  const nodeValues = Array.from(new Set([
    ...agents.map((agent) => agent.agent_id),
    ...rules.flatMap((rule) => [rule.requester_agent, rule.target_agent]),
  ].filter(Boolean))).sort()
  const relationValues = Array.from(new Set([...RELATIONS, ...rules.map((rule) => rule.relation)])).sort()
  const agentOptions = nodeValues.map((value) => ({ value, label: enumText(value) }))
  const relationOptions = relationValues.map((value) => ({ value, label: enumText(value) }))
  const filtered = rows.filter((rule) => (
    (!filters.requester || rule.requester_agent === filters.requester)
    && (!filters.target || rule.target_agent === filters.target)
    && (!filters.relation || rule.relation === filters.relation || rule.relation === '未声明关系')
    && (!filters.allowed || String(rule.allowed) === filters.allowed)
  ))
  const columns: ColumnsType<SystemMapCollaborationRule & { _synthetic?: boolean }> = [
    { title: '请求方（requester）', dataIndex: 'requester_agent', width: 160, render: (v, row) => <Tag color={row._synthetic ? 'red' : 'blue'}>{text(v)}</Tag> },
    { title: '目标（target）', dataIndex: 'target_agent', width: 150, render: (v, row) => <Tag color={row._synthetic ? 'red' : 'cyan'}>{text(v)}</Tag> },
    { title: '关系（relation）', dataIndex: 'relation', width: 150, render: (v) => <Tag>{enumText(v)}</Tag> },
    { title: '允许（allowed）', dataIndex: 'allowed', width: 120, render: (v) => { const tone = allowedTone(!!v); return <Tag color={tone.color}>{tone.label}</Tag> } },
    { title: '最大深度（max_depth）', dataIndex: 'max_depth', width: 100 },
    { title: '冲突策略（conflict_policy）', dataIndex: 'conflict_policy', width: 220, render: (v) => enumText(v) },
    { title: '需审计（audit_required）', dataIndex: 'audit_required', width: 130, render: (v) => <BoolTag value={!!v} trueText="需要" falseText="不需要" /> },
    { title: '原因（reason）', dataIndex: 'reason', render: (v) => <Paragraph ellipsis={{ rows: 2, expandable: true }}>{text(v)}</Paragraph> },
  ]
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Alert type="warning" showIcon message="协作矩阵采用显式白名单（allowlist）；任何未声明调用方 / 目标 / 关系都按默认禁止处理。" />
      <Space wrap>
        <Input.Search allowClear placeholder="调用方（caller）" style={{ width: 180 }} onSearch={(v) => setFilters((prev) => ({ ...prev, requester: v.trim() }))} />
        <Select allowClear placeholder="目标（target）" style={{ width: 180 }} options={agentOptions} value={filters.target || undefined} onChange={(v) => setFilters((prev) => ({ ...prev, target: v ?? '' }))} />
        <Select allowClear placeholder="关系（relation）" style={{ width: 180 }} options={relationOptions} value={filters.relation || undefined} onChange={(v) => setFilters((prev) => ({ ...prev, relation: v ?? '' }))} />
        <Select allowClear placeholder="允许（allowed）" style={{ width: 150 }} value={filters.allowed || undefined} onChange={(v) => setFilters((prev) => ({ ...prev, allowed: v ?? '' }))} options={[{ value: 'true', label: '允许' }, { value: 'false', label: '默认禁止' }]} />
      </Space>
      <Table rowKey={(row) => `${row.requester_agent}-${row.target_agent}-${row.relation}`} size="small" columns={columns} dataSource={filtered} pagination={{ pageSize: 12 }} scroll={{ x: 1250 }} />
      <CollaborationQuery agentOptions={agentOptions} relationOptions={relationOptions} />
    </Space>
  )
}

const HEALTH_STATUS: Record<string, { label: string; color: string }> = {
  healthy: { label: '正常', color: 'green' },
  attention: { label: '需关注', color: 'orange' },
  error: { label: '错误', color: 'red' },
  unknown: { label: '未知', color: 'default' },
}

function HealthStatus({ status }: { status?: string }) {
  const item = HEALTH_STATUS[status ?? 'unknown'] ?? HEALTH_STATUS.unknown
  return <Tag color={item.color}>{item.label}</Tag>
}

function HealthFields({ values, limit }: { values?: Record<string, unknown>; limit?: number }) {
  const entries = Object.entries(values ?? {})
  if (!entries.length) return <Text type="secondary">暂无可用字段</Text>
  const renderEntries = (items: Array<[string, unknown]>) => (
    <Descriptions size="small" column={2} items={items.map(([key, value]) => {
      const numeric = typeof value === 'number' && value > 0
      return {
        key,
        label: fieldLabel(key),
        children: <Text style={numeric ? { color: 'var(--err)', fontWeight: 600 } : undefined}>{fieldValue(value)}</Text>,
      }
    })} />
  )
  const visible = limit ? entries.slice(0, limit) : entries
  return (
    <>
      {renderEntries(visible)}
      {limit && entries.length > limit ? <details><summary>查看其余 {entries.length - limit} 项</summary>{renderEntries(entries.slice(limit))}</details> : null}
    </>
  )
}

function HealthCounts({ counts, compact }: { counts?: Record<string, number | null>; compact?: boolean }) {
  const entries = Object.entries(counts ?? {})
  if (!entries.length) return <Text type="secondary">暂无可用统计</Text>
  return <HealthFields values={Object.fromEntries(entries)} limit={compact ? 3 : undefined} />
}

function MigrationColumns({ summary, label }: { summary?: SystemMapMigrationSummary; label: string }) {
  const added = summary?.added ?? []
  const existing = summary?.existing ?? []
  return (
    <Descriptions.Item label={label}>
      <Space direction="vertical" size={2}>
        <Text>新增 {added.length}，已存在 {existing.length}</Text>
        {added.length ? <Text type="secondary">新增列：{added.join('、')}</Text> : null}
        {existing.length ? <Text type="secondary">已存在列：{existing.join('、')}</Text> : null}
        {!added.length && !existing.length ? <Text type="secondary">暂无迁移摘要</Text> : null}
      </Space>
    </Descriptions.Item>
  )
}

function DatabaseMigrationDetails({ module }: { module: SystemMapHealthModule }) {
  const unknown = module.status === 'unknown'
  const message = unknown
    ? (module.reason ?? '当前没有迁移快照，请重启服务后确认')
    : module.status === 'error'
      ? '迁移失败，请查看日志'
      : '本进程已完成迁移'
  return (
    <Card size="small" style={{ background: 'var(--bg-input)' }}>
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        <Space wrap>
          <Text strong>数据库迁移</Text>
          <HealthStatus status={module.status} />
          <Text type="secondary">{message}</Text>
        </Space>
        <Descriptions size="small" column={{ xs: 1, sm: 2, md: 3 }}>
          <Descriptions.Item label="数据库后端">{text(module.backend, 'unknown')}</Descriptions.Item>
          <Descriptions.Item label="数据库身份">
            {text(module.database ?? module.sqlite_path_digest, 'unknown')}
          </Descriptions.Item>
          <Descriptions.Item label="最近初始化">{text(module.initialized_at, 'unknown')}</Descriptions.Item>
          <MigrationColumns summary={module.knowledge} label="Knowledge 目标列" />
          <MigrationColumns summary={module.experience} label="Experience 目标列" />
        </Descriptions>
        {module.last_error && module.status === 'error' ? (
          <Alert type="error" showIcon message="迁移失败，请查看日志" description={module.last_error} />
        ) : null}
        {unknown ? <Alert type="warning" showIcon message={message} /> : null}
      </Space>
    </Card>
  )
}

function RegistrationIntegrityDetails({ module }: { module: SystemMapHealthModule }) {
  const issues = module.issues ?? []
  const summary = module.summary ?? {}
  const message = module.status === 'healthy'
    ? '未发现登记不一致'
    : module.status === 'unknown'
      ? '当前无法确认'
      : '发现需要处理的问题'
  return (
    <Card size="small" style={{ background: 'var(--bg-input)' }}>
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        <Space wrap>
          <Text strong>System Map 注册完整性</Text>
          <HealthStatus status={module.status} />
          <Text type="secondary">{message}</Text>
          {module.checked_at ? <Text type="secondary">检查于 {module.checked_at}</Text> : null}
        </Space>
        <Space size={[4, 4]} wrap>
          <Tag>来源 {summary.source_count ?? 'unknown'}</Tag>
          <Tag color={issues.length ? 'orange' : undefined}>问题 {summary.issue_count ?? issues.length}</Tag>
          <Tag color={summary.error_count ? 'red' : undefined}>错误 {summary.error_count ?? 'unknown'}</Tag>
          <Tag>需关注 {summary.attention_count ?? 'unknown'}</Tag>
        </Space>
        {module.sources?.length ? <Text type="secondary">事实来源：{module.sources.join('、')}</Text> : null}
        {issues.length ? (
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            {issues.map((issue, index) => (
              <Alert
                key={`${issue.kind ?? 'issue'}-${issue.item ?? index}`}
                type={issue.severity === 'error' ? 'error' : 'warning'}
                showIcon
                message={`${issue.kind ?? 'integrity_issue'}：${issue.item ?? 'unknown'}`}
                description={(
                  <Space direction="vertical" size={2}>
                    <Text>{issue.message ?? '登记信息存在差异'}</Text>
                    <Text type="secondary">来源：{text(issue.source, 'unknown')}</Text>
                    <Text type="secondary">预期：{text(issue.expected, 'unknown')}；实际：{text(issue.actual, 'unknown')}</Text>
                  </Space>
                )}
              />
            ))}
          </Space>
        ) : <Text type="secondary">未发现登记不一致。</Text>}
      </Space>
    </Card>
  )
}

function HealthModuleRow({ module }: { module: SystemMapHealthModule }) {
  if (module.module === 'database_migration') return <DatabaseMigrationDetails module={module} />
  if (module.module === 'registration_integrity') return <RegistrationIntegrityDetails module={module} />
  const semantic = module.semantics as Record<string, unknown> | undefined
  const runtimeStats = module.runtime_rejection_stats as Record<string, unknown> | undefined
  const failed = Number(module.counts?.failed_or_error ?? 0) > 0
  return (
    <Card size="small" bodyStyle={{ padding: '10px 12px' }} style={{ background: 'var(--bg-input)', borderColor: failed ? 'var(--err)' : undefined }}>
      <Space direction="vertical" size={6} style={{ width: '100%' }}>
        <Space size={6} style={{ width: '100%' }}>
          <Text strong>{MODULE_LABELS[module.module] ?? '治理模块'}</Text>
          <HealthStatus status={module.status} />
          {module.updated_at ? <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>刷新于 {module.updated_at}</Text> : null}
        </Space>
        <HealthCounts counts={module.counts} compact />
        {module.last_error ? <Alert type="error" showIcon message={<Text style={{ fontSize: 12 }}>{module.last_error}</Text>} /> : null}
        {runtimeStats?.status === 'unknown' ? <Alert type="warning" showIcon message={String(runtimeStats.reason ?? '当前无运行时拒绝统计接口')} /> : null}
        {semantic ? (
          <HealthFields values={semantic} limit={3} />
        ) : null}
      </Space>
    </Card>
  )
}

function HealthTab({ query }: { query: ReturnType<typeof useQuery<SystemMapHealth>> }) {
  if (query.isError) {
    return <ErrorCard title="治理健康度加载失败" message={query.error.message} detail="旧后端可能尚未提供 /api/system-map/health；不会用 0 或 healthy 代替失败。" onRetry={() => { void query.refetch() }} />
  }
  if (query.isLoading) return <Card loading style={{ background: 'var(--bg-input)' }} />
  const data = query.data
  if (!data) return <EmptyState text="健康度接口没有返回数据，当前状态未知。" />
  const modules = Object.values(data.modules ?? {})
  const standaloneModules = modules.filter((module) => ['database_migration', 'registration_integrity'].includes(module.module))
  const regularModules = modules.filter((module) => !standaloneModules.includes(module))
  const hasMigrationModule = !!data.modules?.database_migration
  const displayStatus = hasMigrationModule ? data.status : 'unknown'
  const migration = data.modules?.database_migration ?? {
    module: 'database_migration',
    status: 'unknown' as const,
    reason: '旧后端未提供迁移状态，请重启服务后确认',
  }
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, minmax(0, 1fr))', gap: 12, margin: '8px 0 16px' }}>
        <Tooltip title="绿色：模块当前健康，能正常产出数据"><span style={{ minWidth: 0 }}><StatCard label="总体状态" value={<HealthStatus status={displayStatus} />} sub="健康度总览" /></span></Tooltip>
        <Tooltip title="蓝色：最近有数据写入或刷新，可观察"><span style={{ minWidth: 0 }}><StatCard label="已读取模块" value={`${data.healthy_modules ?? 0}/${data.module_count ?? modules.length}`} tone="info" sub="已读/总数" /></span></Tooltip>
        <Tooltip title="橙色：命中数异常或近 24h 无更新"><span style={{ minWidth: 0 }}><StatCard label="需关注" value={data.attention_modules ?? 0} tone="warn" sub="命中异常或 24h 无更新" /></span></Tooltip>
        <Tooltip title="红色：含 failed_or_error > 0，需排查"><span style={{ minWidth: 0 }}><StatCard label="错误模块" value={data.error_modules ?? 0} tone="err" sub="含失败/错误" /></span></Tooltip>
        <Tooltip title="默认色：unknown_status > 0，状态待人工核对"><span style={{ minWidth: 0 }}><StatCard label="未知模块" value={data.unknown_modules ?? 0} tone="mute" sub="状态待核对" /></span></Tooltip>
        <Tooltip title="健康度数据的最近刷新时间，仅供查看"><span style={{ minWidth: 0 }}><StatCard label="最近刷新" value={text(data.updated_at)} tone="mute" sub="只读快照时间" /></span></Tooltip>
      </div>
      <Alert
        type={displayStatus === 'healthy' ? 'success' : displayStatus === 'error' ? 'error' : 'warning'}
        showIcon
        message="健康度只观察已有数据，不修改任何状态。active Knowledge 才进入正式注入；Shadow、Memory/Experience 不进入正式 prompt 或硬规则。"
      />
      {data.last_errors?.length ? (
        <Alert type="error" showIcon message="最近错误摘要" description={<Space direction="vertical">{data.last_errors.map((item, index) => <Text key={`${item.module}-${index}`}>{item.module}: {item.error}</Text>)}</Space>} />
      ) : null}
      {!data.modules?.database_migration ? <HealthModuleRow module={migration} /> : null}
      {standaloneModules.map((module) => <HealthModuleRow key={module.module} module={module} />)}
      {!modules.length ? <EmptyState text="没有模块健康数据，当前状态未知。" /> : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 12 }}>
          {regularModules.map((module) => <HealthModuleRow key={module.module} module={module} />)}
        </div>
      )}
    </Space>
  )
}

export function SystemMapPage() {
  const [activeTab, setActiveTab] = useState('summary')
  const summary = useQuery({ queryKey: ['system-map-summary'], queryFn: systemMapSummary, retry: 0 })
  const agents = useQuery({ queryKey: ['system-map-agents'], queryFn: systemMapAgents, retry: 0 })
  const workflows = useQuery({ queryKey: ['system-map-workflows'], queryFn: systemMapWorkflows, retry: 0 })
  const tools = useQuery({ queryKey: ['system-map-tools'], queryFn: systemMapTools, retry: 0 })
  const collaboration = useQuery({ queryKey: ['system-map-collaboration'], queryFn: systemMapCollaboration, retry: 0 })
  const health = useQuery<SystemMapHealth>({ queryKey: ['system-map-health'], queryFn: systemMapHealth, retry: 0 })
  const queries = [summary, agents, workflows, tools, collaboration]
  const loading = queries.some((query) => query.isLoading)
  const failed = queries.find((query) => query.isError)
  const retryAll = () => [...queries, health].forEach((query) => { void query.refetch() })
  const agentRows = agents.data ?? summary.data?.agents ?? []
  const workflowRows = workflows.data ?? summary.data?.workflows ?? []
  const toolRows = tools.data ?? summary.data?.tools ?? []
  const collaborationRows = collaboration.data ?? []

  if (failed?.isError) {
    return <ErrorCard title="系统能力地图加载失败" message={failed.error.message} detail="后端不可用时页面不会伪造默认成功数据。" onRetry={retryAll} />
  }

  return (
    <div>
      <Space direction="vertical" size={6} style={{ width: '100%', marginBottom: 12 }}>
        <Title level={4} style={{ margin: 0 }}>系统治理 / 能力地图</Title>
        <Text type="secondary">只读查看 Agent、Workflow、ReAct 工具与协作矩阵。</Text>
      </Space>
      <Card size="small" title="系统治理 · 能力地图" style={{ marginBottom: 12, background: 'var(--bg-card)' }}>
        <Space direction="vertical" size={6} style={{ width: '100%' }}>
          <Text>本看板只读展示后端 System Map 与协作矩阵。系统共 8 个 Agent（业务决策单元）+ 9 个 Workflow（人机协作流程）+ 12 个只读数据工具；Agent 之间的显式协作关系通过协作矩阵声明，<Text strong>未声明的关系默认禁止</Text>（fail-closed）。所有规则 / 知识 / 记忆 / 交易动作仍走原人工+审计边界，本页面<strong>不提供任何治理写入口</strong>。</Text>
          <Text type="secondary">使用建议：先看总览了解全貌 → 进入「Agent 能力」看每个 Agent 职责 → 进入「协作矩阵」看 Agent 间关系 → 进入「运行状态」看实际运行数据。</Text>
        </Space>
      </Card>
      <Card loading={loading} style={{ background: 'var(--bg-card)' }}>
        <Alert type="info" showIcon message={TAB_DESCRIPTIONS[activeTab]} style={{ marginBottom: 12 }} />
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            { key: 'summary', label: '总览', children: <SummaryTab summary={summary.data} agents={agentRows} workflows={workflowRows} tools={toolRows} collaboration={collaborationRows} /> },
            { key: 'agents', label: '智能体能力（Agent）', children: <AgentsTab agents={agentRows} /> },
            { key: 'workflows', label: '工作流（Workflow）', children: <WorkflowsTab workflows={workflowRows} /> },
            { key: 'tools', label: '只读工具', children: <ToolsTab tools={toolRows} /> },
            { key: 'collaboration', label: '协作矩阵', children: <CollaborationTab agents={agentRows} rules={collaborationRows} /> },
            { key: 'health', label: '运行状态', children: <HealthTab query={health} /> },
          ]}
        />
      </Card>
    </div>
  )
}

export default SystemMapPage
