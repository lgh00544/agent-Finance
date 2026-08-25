import { useState } from 'react'
import { App, Button, Card, Input, Space, Table, Tabs, Tag, Typography } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { capitalView, hotMoneyFlows, hotMoneyProfiles, hotMoneyTierApply, hotMoneyWinrateIterate } from '@/api/hotMoney'
import { agentSuggestions, approveSuggestion, rejectSuggestion } from '@/api/suggestions'
import { EmptyState, ErrorCard, StockLabel } from '@/components/common'
import { moneyCn } from '@/utils/format'

const { Text } = Typography
const TIER_TONE: Record<string, string> = { 一线: 'red', 二线: 'orange', 观察: 'blue' }
const SRC_LABEL: Record<string, string> = { eastmoney: '东财', sina: '新浪', sse: '上交所', szse: '深交所' }
const SUG_STATUS: Record<string, { label: string; color: string }> = {
  pending: { label: '待审核', color: 'orange' }, approved: { label: '已采纳', color: 'green' }, rejected: { label: '已驳回', color: 'default' },
}

/** 游资档案 */
function Profiles() {
  const [q, setQ] = useState('')
  const { data: rows, isError, error, refetch } = useQuery({
    queryKey: ['hm-profiles', q], queryFn: () => hotMoneyProfiles(q, ''),
  })
  if (isError) return <ErrorCard title="游资档案加载失败" message={error?.message} onRetry={() => refetch()} />
  const list = rows ?? []
  const cols = [
    { title: '游资', dataIndex: 'actor_name', width: 140, render: (v: string) => <Text strong>{v || '未命名游资'}</Text> },
    { title: '席位', dataIndex: 'seat_code', width: 180, ellipsis: true },
    {
      title: '梯队', dataIndex: 'tier', width: 80,
      render: (v: string) => <Tag color={TIER_TONE[v] ?? 'default'}>{v ?? '观察'}</Tag>,
    },
    { title: '风格', dataIndex: 'style_tags', width: 160, render: (v: string[]) => (v ?? []).join('、') || '—' },
    { title: '擅长题材', dataIndex: 'good_themes', width: 180, render: (v: string[]) => (v ?? []).join('、') || '—' },
    {
      title: '5日胜率', dataIndex: 'win_rate_5d', width: 90,
      render: (v: number) => (v != null ? `${(v * 100).toFixed(0)}%` : '—'),
    },
  ]
  return (
    <div>
      <Input.Search placeholder="按游资名/席位搜索" style={{ width: 240, marginBottom: 10 }} onSearch={setQ} allowClear />
      <Table size="small" rowKey="id" dataSource={list} columns={cols} pagination={{ pageSize: 20 }} />
    </div>
  )
}

/** 龙虎榜流水 */
function Flows() {
  const { data: rows, isError, error, refetch } = useQuery({ queryKey: ['hm-flows'], queryFn: () => hotMoneyFlows() })
  if (isError) return <ErrorCard title="龙虎榜加载失败" message={error?.message} onRetry={() => refetch()} />
  const list = rows ?? []
  if (!list.length) return <EmptyState text="暂无龙虎榜流水。" icon="📊" />
  const cols = [
    { title: '日期', dataIndex: 'trade_date', width: 100 },
    {
      title: '标的', key: 'stock', width: 150,
      render: (_: unknown, r: Record<string, unknown>) => <StockLabel code={String(r.stock_code ?? '')} name={String(r.stock_name ?? '')} />,
    },
    { title: '口径', dataIndex: 'lhb_type', width: 60 },
    { title: '营业部', dataIndex: 'seat_name', width: 200, ellipsis: true },
    {
      title: '买入额', dataIndex: 'buy_amt', align: 'right' as const,
      render: (v: number) => <Text style={{ color: 'var(--up)' }}>{moneyCn(v)}</Text>,
    },
    {
      title: '卖出额', dataIndex: 'sell_amt', align: 'right' as const,
      render: (v: number) => <Text style={{ color: 'var(--down)' }}>{moneyCn(v)}</Text>,
    },
    {
      title: '净买额', dataIndex: 'net_buy', align: 'right' as const,
      render: (v: number) => <Text style={{ color: (v ?? 0) > 0 ? 'var(--up)' : (v ?? 0) < 0 ? 'var(--down)' : 'var(--text)' }}>{moneyCn(v)}</Text>,
    },
    { title: '数据源', dataIndex: 'source', width: 70, render: (v: string) => SRC_LABEL[v] ?? v },
  ]
  return <Table size="small" rowKey="id" dataSource={list} columns={cols} pagination={{ pageSize: 20 }} />
}

/** 胜率迭代 + 分档 */
function Iterate() {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const iterate = () => modal.confirm({
    title: '运行游资胜率迭代',
    content: '触发后将统计各游资历史信号胜率并生成建议（pending 待审核，需人工确认后生效）。',
    okText: '运行（耗时较长）',
    onOk: async () => {
      try { await hotMoneyWinrateIterate(); message.success('迭代完成，建议已落待审核队列'); qc.invalidateQueries({ queryKey: ['agent-sug'] }) }
      catch (e) { message.error(e instanceof Error ? e.message : '迭代失败') }
    },
  })
  return (
    <Card size="small" title="游资梯队建议（全部待人工审核，绝不自动生效）" style={{ background: 'var(--bg-input)' }}>
      <Space style={{ marginBottom: 8 }}>
        <Button type="primary" onClick={iterate}>运行胜率迭代</Button>
      </Space>
      <SuggestList />
    </Card>
  )
}

function SuggestList() {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const { data: rows } = useQuery({ queryKey: ['agent-sug'], queryFn: () => agentSuggestions() })
  const list = (rows ?? []).filter((s) => String(s.rule_name ?? '').includes('游资'))
  if (!list.length) return <EmptyState text="暂无游资梯队建议。" icon="💡" />
  const act = (r: (typeof list)[number], action: 'approve' | 'reject') => modal.confirm({
    title: action === 'approve' ? `采纳建议：${r.rule_name}` : `驳回建议：${r.rule_name}`,
    okText: '确认', okButtonProps: action === 'reject' ? { danger: true } : { type: 'primary' as const },
    onOk: async () => {
      try {
        if (action === 'approve') {
          try { await approveSuggestion(r.id) } catch { message.error('审核未通过'); return }
          try { await hotMoneyTierApply(r.id) } catch { message.error('审核已过但档位应用失败，请到游资追踪页重试'); return }
          message.success('已采纳')
        }
        else { await rejectSuggestion(r.id, '人工驳回'); message.info('已驳回') }
        qc.invalidateQueries({ queryKey: ['agent-sug'] })
      } catch (e) { message.error(e instanceof Error ? e.message : '操作失败') }
    },
  })
  return (
    <Table size="small" rowKey="id" dataSource={list} pagination={false}
      columns={[
        { title: 'Agent', dataIndex: 'target_agent', width: 90 },
        { title: '规则', dataIndex: 'rule_name', ellipsis: true },
        { title: '当前→建议', key: 'val', width: 140, render: (_: unknown, r: (typeof list)[number]) => <Text>{(r.current_value ?? '—')} → {r.suggested_value ?? '—'}</Text> },
        { title: '状态', dataIndex: 'status', width: 80, render: (v: string) => <Tag color={SUG_STATUS[v]?.color ?? 'default'}>{SUG_STATUS[v]?.label ?? v}</Tag> },
        {
          title: '操作', key: 'ops', width: 130,
          render: (_: unknown, r: (typeof list)[number]) => r.status === 'pending' ? (
            <Space size={4}>
              <Button size="small" onClick={() => act(r, 'approve')}>采纳</Button>
              <Button size="small" onClick={() => act(r, 'reject')}>驳回</Button>
            </Space>
          ) : null,
        },
      ]} />
  )
}

/** 个股资本视图（K189 对倒 · 游资活跃 · 30日统计；读 /api/capital_view/{code}） */
function CapitalViewPanel() {
  const [code, setCode] = useState('')
  const { data, isError, error, refetch } = useQuery({
    queryKey: ['capital-view', code],
    queryFn: () => capitalView(code),
    enabled: code.length === 6,
  })
  if (isError) return <ErrorCard title="资本视图加载失败" message={error?.message} onRetry={() => refetch()} />
  const actors = data?.recent_actors ?? []
  const stats: Record<string, number | null> = data?.stats_30d ?? {}
  const badge = data?.wash_suspect ? { color: 'red', text: '对倒嫌疑（K189）' }
    : actors.length ? { color: 'gold', text: '游资关注' }
    : { color: 'default', text: '无数据' }
  const coordTone: Record<string, string> = { '多游资同买': 'red', '单家动作': 'orange', '无显著动作': 'default', '数据不足': 'default' }
  const winRate = stats['胜率']
  const rr = stats['盈亏比']
  const holdDays = stats['平均持仓天数']
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Input.Search placeholder="输入6位股票代码，如 600519" style={{ width: 260 }} onSearch={setCode} allowClear />
      {!code && <EmptyState text="输入股票代码查看个股资本视图。" icon="🏛️" />}
      {code.length === 6 && !isError && !data && <EmptyState text="资本视图加载中…" icon="⏳" />}
      {data && (
        <>
          <Space wrap>
            <Tag color={badge.color}>{badge.text}</Tag>
            <Tag color={coordTone[data.coordination ?? ''] ?? 'default'}>{data.coordination || '—'}</Tag>
            {data.theme_resonance ? <Tag color="blue">板块共振</Tag> : null}
            <Text type="secondary">数据源 {data.source || '—'} · {data.trade_date || '—'}</Text>
          </Space>
          <Table size="small" rowKey={(r) => String(r.name ?? r.seat ?? '')} dataSource={actors} pagination={false}
            columns={[
              { title: '游资', dataIndex: 'name', width: 120, render: (v: string) => <Text strong>{v || '—'}</Text> },
              { title: '席位', dataIndex: 'seat', width: 200, ellipsis: true, render: (v: string) => v || '—' },
              { title: '梯队', dataIndex: 'tier', width: 80, render: (v: string) => <Tag color={TIER_TONE[v] ?? 'default'}>{v ?? '—'}</Tag> },
              { title: '净买额', dataIndex: 'net_buy', align: 'right' as const, render: (v: number) => (v != null ? moneyCn(v) : '—') },
              { title: '活跃天数', dataIndex: 'days_active', width: 80, render: (v: number) => v ?? '—' },
            ]}
            locale={{ emptyText: '30日无活跃游资（数据不足，不编造）。' }} />
          <Card size="small" title="30日游资统计（stats_30d）" style={{ background: 'var(--bg-input)' }}>
            <Space wrap>
              <Text>胜率：{winRate != null ? `${(winRate * 100).toFixed(0)}%` : '—'}</Text>
              <Text>盈亏比：{rr != null ? rr.toFixed(2) : '—'}</Text>
              <Text>平均持仓天数：{holdDays != null ? `${holdDays.toFixed(1)}天` : '—'}</Text>
            </Space>
          </Card>
        </>
      )}
    </Space>
  )
}

/** 游资追踪页（Phase 4） */
export function HotMoneyPage() {
  return (
    <div>
      <Tabs items={[
        { key: 'profile', label: '游资档案', children: <Profiles /> },
        { key: 'flow', label: '龙虎榜流水', children: <Flows /> },
        { key: 'iterate', label: '胜率迭代', children: <Iterate /> },
        { key: 'capital', label: '个股资本视图', children: <CapitalViewPanel /> },
      ]} />
    </div>
  )
}

export default HotMoneyPage
