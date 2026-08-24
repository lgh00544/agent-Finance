import { useState } from 'react'
import { App, Button, Card, Form, Input, Popconfirm, Select, Table, Tabs, Tag, Typography } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { addKnowledge, batchImportKnowledge, deleteKnowledge, knowledge } from '@/api/knowledge'
import { EmptyState } from '@/components/common'

const { Text } = Typography
const AGENTS = ['all', 'discover', 'score', 'position', 'monitor', 'sell', 'review']
const AGENT_LABEL: Record<string, string> = {
  all: '全部 Agent', discover: '选股发现', score: '评分分析', position: '建仓方案',
  monitor: '持仓监控', sell: '卖出决策', review: '复盘迭代',
}

/** 新增知识 */
function AddPanel() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [form] = Form.useForm()
  const submit = async (v: { title: string; content: string; agent_tag: string }) => {
    try {
      await addKnowledge(v.title, v.content, v.agent_tag)
      message.success('已保存，对应 Agent 下次任务自动注入')
      form.resetFields()
      qc.invalidateQueries({ queryKey: ['knowledge'] })
    } catch (e) { message.error(e instanceof Error ? e.message : '保存失败') }
  }
  return (
    <Card size="small" style={{ background: 'var(--bg-input)' }}>
      <Form form={form} layout="vertical" onFinish={submit} initialValues={{ agent_tag: 'all' }}>
        <Form.Item name="title" label="标题 *" rules={[{ required: true, message: '标题不能为空' }]}>
          <Input placeholder="如：放量突破战法的确认条件" />
        </Form.Item>
        <Form.Item name="agent_tag" label="适用 Agent *">
          <Select options={AGENTS.map((a) => ({ label: AGENT_LABEL[a], value: a }))} />
        </Form.Item>
        <Form.Item name="content" label="正文 *（你的经验/战法/心得）" rules={[{ required: true, message: '正文不能为空' }]}>
          <Input.TextArea rows={6} placeholder="如：放量突破必须满足 ①换手率 5%-15% ②突破前缩量整理 ③..." />
        </Form.Item>
        <Button type="primary" htmlType="submit">保存（立即生效）</Button>
      </Form>
    </Card>
  )
}

/** 批量导入 */
function BatchPanel() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const submit = async (v: { agent_tag: string; text: string }) => {
    const items: Array<Record<string, unknown>> = []
    for (const block of (v.text ?? '').split(/\n\s*\n/)) {
      const lines = block.split('\n').map((l) => l.trim()).filter(Boolean)
      if (lines.length >= 2) items.push({ title: lines[0], content: lines.slice(1).join('\n'), agent_tag: v.agent_tag })
    }
    if (!items.length) { message.warning('未解析出有效条目（每条首行标题+正文，空行分隔）'); return }
    try {
      await batchImportKnowledge(items)
      message.success(`已提交 ${items.length} 条批量导入任务`)
      form.resetFields()
    } catch (e) { message.error(e instanceof Error ? e.message : '导入失败') }
  }
  return (
    <Card size="small" style={{ background: 'var(--bg-input)' }}>
      <Form form={form} onFinish={submit} initialValues={{ agent_tag: 'all' }} layout="vertical">
        <Form.Item name="agent_tag" label="批量适用 Agent">
          <Select options={AGENTS.map((a) => ({ label: AGENT_LABEL[a], value: a }))} />
        </Form.Item>
        <Form.Item name="text" label="粘贴文本（空行分隔多条；每条第一行为标题）">
          <Input.TextArea rows={10} placeholder={'放量突破战法确认条件\n①换手率 5%-15% ②突破前缩量整理 ③板块共振\n\n止损纪律\n买入后跌破关键支撑位无条件离场'} />
        </Form.Item>
        <Button type="primary" htmlType="submit">批量导入（异步执行）</Button>
      </Form>
    </Card>
  )
}

/** 知识条目列表 */
function ListPanel() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [filter, setFilter] = useState('全部')
  const { data: rows } = useQuery({ queryKey: ['knowledge'], queryFn: knowledge })
  const list = (rows ?? []).filter((r) => filter === '全部' || r.agent_tag === filter)
  if (!rows?.length) return <EmptyState text="暂无知识条目。写入第一条战法后，各 Agent 即可自动引用。" icon="📚" />
  const del = async (id: number) => {
    try { await deleteKnowledge(id); message.success('已删除，对应 Agent 缓存自动失效'); qc.invalidateQueries({ queryKey: ['knowledge'] }) }
    catch (e) { message.error(e instanceof Error ? e.message : '删除失败') }
  }
  return (
    <div>
      <Select value={filter} onChange={setFilter} style={{ width: 140, marginBottom: 10 }}
        options={[{ label: '全部 Agent', value: '全部' }, ...AGENTS.map((a) => ({ label: AGENT_LABEL[a], value: a }))]} />
      <Table size="small" rowKey="id" dataSource={list} pagination={{ pageSize: 20 }}
        columns={[
          { title: '标题', dataIndex: 'title', ellipsis: true },
          { title: '适用', dataIndex: 'agent_tag', width: 100, render: (v: string) => <Tag color={v === 'all' ? 'blue' : 'default'}>{AGENT_LABEL[v] ?? v}</Tag> },
          {
            title: '内容', dataIndex: 'content', ellipsis: true,
            render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{String(v ?? '').slice(0, 60)}</Text>,
          },
          { title: '创建', dataIndex: 'created_at', width: 150, render: (v: string) => String(v ?? '').slice(0, 16) },
          { title: '命中', dataIndex: 'hit_count', width: 70, render: (v: number) => <Text type="secondary">{v ?? 0}</Text> },
          { title: '最近使用', dataIndex: 'last_used_at', width: 150, render: (v: string | null) => (v ? String(v).slice(0, 16) : '—') },
          {
            title: '操作', key: 'ops', width: 80,
            render: (_: unknown, r: { id: number }) => (
              <Popconfirm title="确认删除该条目？" okText="删除" cancelText="取消" onConfirm={() => del(r.id)}>
                <Button size="small" danger>删除</Button>
              </Popconfirm>
            ),
          },
        ]} />
    </div>
  )
}

/** 交易知识库页（Phase 4） */
export function KnowledgePage() {
  return (
    <Tabs items={[
      { key: 'add', label: '新增条目', children: <AddPanel /> },
      { key: 'batch', label: '批量导入', children: <BatchPanel /> },
      { key: 'list', label: '知识条目', children: <ListPanel /> },
    ]} />
  )
}

export default KnowledgePage
