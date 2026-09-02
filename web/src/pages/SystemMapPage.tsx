import { useMemo, useState } from 'react'
import { Alert, Button, Card, Descriptions, Drawer, Empty, Form, Input, Select, Space, Table, Tabs, Tag, Typography } from 'antd'
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
import { EmptyState, ErrorCard, StatCard, StatCardGrid } from '@/components/common'
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

const RELATIONS = ['call', 'reference', 'propose_change']
const DEFAULT_FORBIDDEN_ROW: SystemMapCollaborationRule & { _synthetic?: boolean } = {
  requester_agent: '未声明 caller',
  target_agent: '未声明 target',
  relation: '未声明关系',
  allowed: false,
  max_depth: 0,
  conflict_policy: 'deny_by_default',
  audit_required: false,
  reason: '协作矩阵未声明的 caller / target / relation 默认禁止。',
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

function TagList({ value, color }: { value: unknown; color?: string }) {
  const items = asList(value)
  if (!items.length) return <Text type="secondary">—</Text>
  return (
    <Space size={[4, 4]} wrap>
      {items.map((item) => <Tag key={item} color={color}>{item}</Tag>)}
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
      <StatCardGrid>
        <StatCard label="Agent" value={summary?.agents_count ?? agents.length} tone="info" sub="只读注册表" />
        <StatCard label="Workflow" value={summary?.workflows_count ?? workflows.length} tone="mute" sub="入口与确认要求" />
        <StatCard label="只读工具" value={summary?.tools_count ?? tools.length} tone="ok" sub="ReAct 数据工具" />
        <StatCard label="允许协作" value={allowedCount} tone="ok" sub="显式声明" />
        <StatCard label="默认禁止" value={defaultForbidden} tone="warn" sub="按当前节点/关系估算" />
        <StatCard label="红线状态" value="只读" tone="err" sub="前端无治理写入口" />
      </StatCardGrid>
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
          { label: 'responsibility', children: text(row.responsibility) },
          { label: 'agent_type', children: text(row.agent_type) },
          { label: 'authority_level', children: text(row.authority_level) },
          { label: 'knowledge_scope', children: text(row.knowledge_scope) },
          { label: 'knowledge', children: text(row.knowledge) },
          { label: 'inputs_required', children: <TagList value={row.inputs_required} /> },
          { label: 'inputs_optional', children: <TagList value={row.inputs_optional} /> },
          { label: 'outputs', children: <TagList value={row.outputs} color="blue" /> },
          { label: 'can_reference', children: <TagList value={row.can_reference} color="cyan" /> },
          { label: 'can_call', children: <TagList value={row.can_call} color="green" /> },
          { label: 'cannot_do', children: <TagList value={row.cannot_do} color="red" /> },
          { label: 'human_gate_required', children: <BoolTag value={row.human_gate_required} trueText="需要人工门禁" falseText="不要求人工门禁" /> },
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
    { title: 'Agent', dataIndex: 'name', width: 150, render: (_: unknown, row) => <Space direction="vertical" size={0}><Text strong>{text(row.name)}</Text><Text type="secondary">{row.agent_id}</Text></Space> },
    { title: '责任', dataIndex: 'responsibility', render: (v) => <Paragraph ellipsis={{ rows: 2, expandable: true }}>{text(v)}</Paragraph> },
    { title: '类型/权限', key: 'type', width: 150, render: (_: unknown, row) => <Space direction="vertical" size={2}><Tag>{text(row.agent_type)}</Tag><Tag color="blue">{text(row.authority_level)}</Tag></Space> },
    { title: '知识范围', dataIndex: 'knowledge_scope', width: 130, render: (v) => <Tag color="cyan">{text(v)}</Tag> },
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
    { title: 'Workflow', dataIndex: 'name', width: 170, render: (_: unknown, row) => <Space direction="vertical" size={0}><Text strong>{text(row.name)}</Text><Text type="secondary">{row.workflow_id}</Text></Space> },
    { title: '示例意图', dataIndex: 'intent_examples', render: (v) => <TagList value={v} /> },
    { title: '步骤', dataIndex: 'steps', render: (v) => <TagList value={v} color="blue" /> },
    { title: '必填输入', dataIndex: 'required_inputs', render: (v) => <TagList value={v} color="orange" /> },
    { title: '可选输入', dataIndex: 'optional_inputs', render: (v) => <TagList value={v} /> },
    { title: '入口 Agent', dataIndex: 'allowed_entry_agents', render: (v) => <TagList value={v} color="cyan" /> },
    { title: '治理状态', key: 'gate', width: 180, render: (_: unknown, row) => <Space wrap><BoolTag value={row.audit_required} trueText="需审核" falseText="仅分析/查询" /><BoolTag value={row.human_confirm_required} trueText="需人工确认" falseText="无需人工确认" /></Space> },
    { title: '最终响应', dataIndex: 'final_responder', width: 130, render: (v) => <Tag>{text(v)}</Tag> },
  ]
  return <Table<SystemMapWorkflow> rowKey="workflow_id" size="small" columns={columns} dataSource={workflows} pagination={{ pageSize: 10 }} scroll={{ x: 1180 }} />
}

function ToolsTab({ tools }: { tools: SystemMapTool[] }) {
  if (!tools.length) return <EmptyState text="暂无只读工具注册信息。" />
  const columns: ColumnsType<SystemMapTool> = [
    { title: 'Tool', dataIndex: 'tool_id', width: 190, render: (v, row) => <Space direction="vertical" size={0}><Text strong>{text(v)}</Text><Text type="secondary">{text(row.owner_module)}</Text></Space> },
    { title: '描述', dataIndex: 'description', render: (v) => <Paragraph ellipsis={{ rows: 2, expandable: true }}>{text(v)}</Paragraph> },
    { title: '类型', dataIndex: 'tool_type', width: 130, render: (v) => <Tag color="green">{text(v, 'readonly_data')}</Tag> },
    { title: '输入', dataIndex: 'inputs', render: (v) => <CompactValue value={v} /> },
    { title: '输出', dataIndex: 'outputs', width: 100, render: (v) => <CompactValue value={v} /> },
    { title: '使用方', dataIndex: 'used_by', render: (v) => <TagList value={v} color="cyan" /> },
    { title: '失败降级', dataIndex: 'failure_policy', width: 160, render: (v) => <Tag color="orange">{text(v)}</Tag> },
    { title: '不可做', dataIndex: 'cannot_do', render: (v) => <TagList value={v} color="red" /> },
  ]
  return (
    <Space direction="vertical" size={10} style={{ width: '100%' }}>
      <Alert type="info" showIcon message="只读 ReAct 工具仅返回数据或 error payload；本页不提供工具执行、交易或业务写库入口。" />
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
          <Form.Item label="caller/requester">
            <Select showSearch allowClear style={{ width: 190 }} placeholder="选择或输入 Agent" options={agentOptions} value={params.requester || undefined} onChange={(v) => setParams((prev) => ({ ...prev, requester: v ?? '' }))} onSearch={(v) => setParams((prev) => ({ ...prev, requester: v }))} />
          </Form.Item>
          <Form.Item label="target">
            <Select showSearch allowClear style={{ width: 190 }} placeholder="选择或输入 target" options={agentOptions} value={params.target || undefined} onChange={(v) => setParams((prev) => ({ ...prev, target: v ?? '' }))} onSearch={(v) => setParams((prev) => ({ ...prev, target: v }))} />
          </Form.Item>
          <Form.Item label="relation">
            <Select showSearch style={{ width: 170 }} options={relationOptions} value={params.relation} onChange={(v) => setParams((prev) => ({ ...prev, relation: v }))} onSearch={(v) => setParams((prev) => ({ ...prev, relation: v }))} />
          </Form.Item>
          <Button type="primary" disabled={incomplete} loading={result.isFetching} onClick={() => setSubmitted(params)}>查询</Button>
        </Form>
        {incomplete ? <Alert type="warning" showIcon message="请完整填写 caller、target 和 relation 后再查询。" /> : null}
        {result.isError ? <Alert type="error" showIcon message="协作查询失败" description={result.error.message} /> : null}
        {data ? (
          <Descriptions size="small" column={2} items={[
            { label: 'allowed', children: <Tag color={tone.color}>{tone.label}</Tag> },
            { label: 'caller', children: text(data.caller ?? data.requester_agent) },
            { label: 'target', children: text(data.target ?? data.target_agent) },
            { label: 'relation', children: text(data.relation) },
            { label: 'reason', children: text(data.reason) },
            { label: 'unknown_caller', children: String(!!data.unknown_caller) },
            { label: 'unknown_target', children: String(!!data.unknown_target) },
            { label: 'default_denied', children: String(!!data.default_denied) },
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
  const agentOptions = nodeValues.map((value) => ({ value, label: value }))
  const relationOptions = relationValues.map((value) => ({ value, label: value }))
  const filtered = rows.filter((rule) => (
    (!filters.requester || rule.requester_agent === filters.requester)
    && (!filters.target || rule.target_agent === filters.target)
    && (!filters.relation || rule.relation === filters.relation || rule.relation === '未声明关系')
    && (!filters.allowed || String(rule.allowed) === filters.allowed)
  ))
  const columns: ColumnsType<SystemMapCollaborationRule & { _synthetic?: boolean }> = [
    { title: 'caller/requester', dataIndex: 'requester_agent', width: 160, render: (v, row) => <Tag color={row._synthetic ? 'red' : 'blue'}>{text(v)}</Tag> },
    { title: 'target', dataIndex: 'target_agent', width: 150, render: (v, row) => <Tag color={row._synthetic ? 'red' : 'cyan'}>{text(v)}</Tag> },
    { title: 'relation', dataIndex: 'relation', width: 150, render: (v) => <Tag>{text(v)}</Tag> },
    { title: 'allowed', dataIndex: 'allowed', width: 120, render: (v) => { const tone = allowedTone(!!v); return <Tag color={tone.color}>{tone.label}</Tag> } },
    { title: 'max_depth', dataIndex: 'max_depth', width: 100 },
    { title: 'conflict_policy', dataIndex: 'conflict_policy', width: 220, render: (v) => text(v) },
    { title: 'audit_required', dataIndex: 'audit_required', width: 130, render: (v) => <BoolTag value={!!v} trueText="需要" falseText="不需要" /> },
    { title: 'reason', dataIndex: 'reason', render: (v) => <Paragraph ellipsis={{ rows: 2, expandable: true }}>{text(v)}</Paragraph> },
  ]
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Alert type="warning" showIcon message="协作矩阵采用显式 allowlist；任何未声明 caller / target / relation 都按默认禁止处理。" />
      <Space wrap>
        <Input.Search allowClear placeholder="caller" style={{ width: 180 }} onSearch={(v) => setFilters((prev) => ({ ...prev, requester: v.trim() }))} />
        <Select allowClear placeholder="target" style={{ width: 180 }} options={agentOptions} value={filters.target || undefined} onChange={(v) => setFilters((prev) => ({ ...prev, target: v ?? '' }))} />
        <Select allowClear placeholder="relation" style={{ width: 180 }} options={relationOptions} value={filters.relation || undefined} onChange={(v) => setFilters((prev) => ({ ...prev, relation: v ?? '' }))} />
        <Select allowClear placeholder="allowed" style={{ width: 150 }} value={filters.allowed || undefined} onChange={(v) => setFilters((prev) => ({ ...prev, allowed: v ?? '' }))} options={[{ value: 'true', label: '允许' }, { value: 'false', label: '默认禁止' }]} />
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

function HealthCounts({ counts }: { counts?: Record<string, number | null> }) {
  const entries = Object.entries(counts ?? {})
  if (!entries.length) return <Text type="secondary">暂无可用统计</Text>
  return (
    <Space size={[4, 4]} wrap>
      {entries.map(([key, value]) => (
        <Tag key={key}>{key}: {value == null ? 'unknown' : value}</Tag>
      ))}
    </Space>
  )
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
  return (
    <Card size="small" style={{ background: 'var(--bg-input)' }}>
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        <Space wrap>
          <Text strong>{module.module}</Text>
          <HealthStatus status={module.status} />
          {module.updated_at ? <Text type="secondary">刷新于 {module.updated_at}</Text> : null}
        </Space>
        <HealthCounts counts={module.counts} />
        {module.last_error ? <Alert type="error" showIcon message="模块读取失败" description={module.last_error} /> : null}
        {runtimeStats?.status === 'unknown' ? <Alert type="warning" showIcon message={String(runtimeStats.reason ?? '当前无运行时拒绝统计接口')} /> : null}
        {semantic ? (
          <Space size={[4, 4]} wrap>
            {Object.entries(semantic).map(([key, value]) => <Tag key={key}>{key}: {String(value)}</Tag>)}
          </Space>
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
  const hasMigrationModule = !!data.modules?.database_migration
  const displayStatus = hasMigrationModule ? data.status : 'unknown'
  const displayComplete = hasMigrationModule && !!data.complete
  const migration = data.modules?.database_migration ?? {
    module: 'database_migration',
    status: 'unknown' as const,
    reason: '旧后端未提供迁移状态，请重启服务后确认',
  }
  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <StatCardGrid>
        <StatCard label="总体状态" value={<HealthStatus status={displayStatus} />} sub={displayComplete ? '数据完整' : '存在 unknown 或错误'} />
        <StatCard label="已读取模块" value={`${data.healthy_modules ?? 0}/${data.module_count ?? modules.length}`} tone="info" sub="真实接口返回" />
        <StatCard label="需关注" value={data.attention_modules ?? 0} tone="warn" sub="有积压或失败数据" />
        <StatCard label="错误模块" value={data.error_modules ?? 0} tone="err" sub="读取异常" />
        <StatCard label="未知模块" value={data.unknown_modules ?? 0} tone="mute" sub="空数据或接口缺口" />
        <StatCard label="最近刷新" value={text(data.updated_at)} tone="mute" />
      </StatCardGrid>
      <Alert
        type={displayStatus === 'healthy' ? 'success' : displayStatus === 'error' ? 'error' : 'warning'}
        showIcon
        message="健康度只观察已有数据，不修改任何状态。active Knowledge 才进入正式注入；Shadow、Memory/Experience 不进入正式 prompt 或硬规则。"
      />
      {data.last_errors?.length ? (
        <Alert type="error" showIcon message="最近错误摘要" description={<Space direction="vertical">{data.last_errors.map((item, index) => <Text key={`${item.module}-${index}`}>{item.module}: {item.error}</Text>)}</Space>} />
      ) : null}
      {!data.modules?.database_migration ? <HealthModuleRow module={migration} /> : null}
      {!modules.length ? <EmptyState text="没有模块健康数据，当前状态未知。" /> : modules.map((module) => <HealthModuleRow key={module.module} module={module} />)}
    </Space>
  )
}

export function SystemMapPage() {
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
      <Card loading={loading} style={{ background: 'var(--bg-card)' }}>
        <Tabs
          items={[
            { key: 'summary', label: '总览', children: <SummaryTab summary={summary.data} agents={agentRows} workflows={workflowRows} tools={toolRows} collaboration={collaborationRows} /> },
            { key: 'agents', label: 'Agent 能力', children: <AgentsTab agents={agentRows} /> },
            { key: 'workflows', label: 'Workflow', children: <WorkflowsTab workflows={workflowRows} /> },
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
