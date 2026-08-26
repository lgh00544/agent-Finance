import { useMemo, useState } from 'react'
import { App, Button, Card, Input, Select, Space, Statistic, Table, Tabs, Tag, Typography } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { capitalView, hotMoneyFlows, hotMoneyProfiles, hotMoneyTierApply, hotMoneyTraces, hotMoneyWinrateIterate } from '@/api/hotMoney'
import { traces } from '@/api/traces'
import { agentSuggestions, approveSuggestion, rejectSuggestion } from '@/api/suggestions'
import { EmptyState, ErrorCard, StockLabel } from '@/components/common'
import { moneyCn } from '@/utils/format'
import type { HotMoneyFlow, HotMoneyProfile } from '@/types'

const { Text } = Typography
const TIER_TONE: Record<string, string> = { 一线: 'red', 二线: 'orange', 观察: 'blue' }
const SRC_LABEL: Record<string, string> = { eastmoney: '东财', sina: '新浪', sse: '上交所', szse: '深交所' }
const SUG_STATUS: Record<string, { label: string; color: string }> = {
  pending: { label: '待审核', color: 'orange' }, approved: { label: '已采纳', color: 'green' }, rejected: { label: '已驳回', color: 'default' },
}

/** 游资档案（tier 筛选 + 行展开详情） */
function Profiles() {
  const [q, setQ] = useState('')
  const [tier, setTier] = useState<string>()
  const { data: rows, isError, error, refetch } = useQuery({
    queryKey: ['hm-profiles', q, tier], queryFn: () => hotMoneyProfiles(q, tier ?? ''),
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
      <Space style={{ marginBottom: 10 }} wrap>
        <Input.Search placeholder="按游资名/席位搜索" style={{ width: 240 }} onSearch={setQ} allowClear />
        <Select placeholder="梯队筛选" style={{ width: 120 }} value={tier} onChange={setTier} allowClear
          options={[{ label: '一线', value: '一线' }, { label: '二线', value: '二线' }, { label: '观察', value: '观察' }]} />
      </Space>
      <Table size="small" rowKey="id" dataSource={list} columns={cols} pagination={{ pageSize: 20 }}
        expandable={{ expandedRowRender: (r: HotMoneyProfile) => (
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>协同席位：{(r.co_seats ?? []).join('、') || '—'}</div>
            <div>擅长题材：{(r.good_themes ?? []).join('、') || '—'}</div>
            <div>5日胜率：{r.win_rate_5d != null ? `${(r.win_rate_5d * 100).toFixed(0)}%` : '—'} · 档案更新：{String(r.updated_at ?? '—').slice(0, 16)}</div>
            <div>数据源：{String(r.source ?? '—')}</div>
          </Space>
        ) }} />
    </div>
  )
}

/** 龙虎榜流水（按日/代码筛选 + 命中游资 + 汇总） */
function Flows() {
  const [date, setDate] = useState<string>()
  const [code, setCode] = useState('')
  const { data: rows, isError, error, refetch } = useQuery({
    queryKey: ['hm-flows', date, code], queryFn: () => hotMoneyFlows(date, code),
  })
  const { data: profiles } = useQuery({ queryKey: ['hm-profiles-all'], queryFn: () => hotMoneyProfiles('', '') })
  if (isError) return <ErrorCard title="龙虎榜加载失败" message={error?.message} onRetry={() => refetch()} />
  const list = rows ?? []
  if (!list.length) return <EmptyState text="暂无龙虎榜流水。开启 DRAGON_TIGER_ENABLE 后每日 16:30 自动抓取。" icon="📊" />
  const dates = [...new Set(list.map((r) => String(r.trade_date ?? '')).filter(Boolean))].sort().reverse()
  const totalBuy = list.reduce((s, r) => s + (r.buy_amt ?? 0), 0)
  const totalSell = list.reduce((s, r) => s + (r.sell_amt ?? 0), 0)
  const matchActor = (seat: unknown): HotMoneyProfile | null => {
    const s = String(seat ?? '')
    if (!s) return null
    return (profiles ?? []).find((p) => {
      const a = String(p.actor_name ?? '')
      const c = String(p.seat_code ?? '')
      return (a && s.includes(a)) || (c && s.includes(c))
    }) ?? null
  }
  const cols = [
    { title: '日期', dataIndex: 'trade_date', width: 100 },
    {
      title: '标的', key: 'stock', width: 150,
      render: (_: unknown, r: HotMoneyFlow) => <StockLabel code={String(r.stock_code ?? '')} name={String(r.stock_name ?? '')} />,
    },
    {
      title: '命中游资', key: 'actor', width: 110,
      render: (_: unknown, r: HotMoneyFlow) => {
        const p = matchActor(r.seat_name)
        return p ? <Tag color={TIER_TONE[p.tier ?? ''] ?? 'default'}>{p.actor_name}</Tag> : '—'
      },
    },
    { title: '口径', dataIndex: 'lhb_type', width: 60 },
    { title: '营业部', dataIndex: 'seat_name', width: 190, ellipsis: true },
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
    { title: '置信度', dataIndex: 'confidence', width: 70, render: (v: number) => v != null ? v.toFixed(2) : '—' },
    { title: '上榜原因', dataIndex: 'disclosure_reason', ellipsis: true, render: (v: string) => v || '—' },
    { title: '数据源', dataIndex: 'source', width: 70, render: (v: string) => SRC_LABEL[v] ?? v },
  ]
  return (
    <>
      <Space style={{ marginBottom: 10 }} wrap>
        <Select placeholder="按日筛选" style={{ width: 130 }} value={date} onChange={setDate} allowClear
          options={dates.map((d) => ({ label: d, value: d }))} />
        <Input.Search placeholder="按代码筛选" style={{ width: 170 }} onSearch={setCode} allowClear />
      </Space>
      <Space style={{ marginBottom: 10 }} wrap size={24}>
        <Statistic title="流水条数" value={list.length} />
        <Statistic title="净买入合计" value={totalBuy} formatter={(v) => moneyCn(Number(v))} valueStyle={{ color: 'var(--up)' }} />
        <Statistic title="净卖出合计" value={totalSell} formatter={(v) => moneyCn(Number(v))} valueStyle={{ color: 'var(--down)' }} />
      </Space>
      <Table size="small" rowKey="id" dataSource={list} columns={cols} pagination={{ pageSize: 20 }} />
    </>
  )
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

/** 席位监控：选游资 → 主席位+协同席位 → 过滤龙虎榜流水 → 最近操作（净买方向 + 明细） */
function SeatMonitor() {
  const [actor, setActor] = useState<string>()
  const { data: profiles } = useQuery({ queryKey: ['hm-profiles-all'], queryFn: () => hotMoneyProfiles('', '') })
  const { data: rows } = useQuery({ queryKey: ['hm-flows-all'], queryFn: () => hotMoneyFlows() })
  const profile = (profiles ?? []).find((p) => p.actor_name === actor)
  const seats = useMemo(() => {
    if (!profile) return []
    return [String(profile.seat_code ?? ''), ...(profile.co_seats ?? []).map(String)].filter(Boolean)
  }, [profile])
  const ops = useMemo(() => {
    if (!seats.length) return []
    return (rows ?? []).filter((r) => seats.includes(String(r.seat_name ?? '')))
      .sort((a, b) => String(b.trade_date ?? '').localeCompare(String(a.trade_date ?? '')))
  }, [rows, seats])
  const netBuy = ops.reduce((s, r) => s + (r.net_buy ?? 0), 0)
  const buyAmt = ops.reduce((s, r) => s + (r.buy_amt ?? 0), 0)
  const sellAmt = ops.reduce((s, r) => s + (r.sell_amt ?? 0), 0)
  if (!(profiles ?? []).length) return <EmptyState text="暂无游资档案。" icon="👤" />
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space wrap>
        <Select placeholder="选择游资" style={{ width: 220 }} value={actor} onChange={setActor} allowClear showSearch
          optionFilterProp="label"
          options={(profiles ?? []).map((p) => ({ label: `${p.actor_name}（${p.tier ?? '观察'}）`, value: p.actor_name ?? '' }))} />
        {profile ? (
          <Tag color="blue">主席位：{profile.seat_code ?? '—'}
            {profile.co_seats?.length ? ` · 协同 ${profile.co_seats.length} 个` : ''}</Tag>
        ) : null}
      </Space>
      {!actor ? <EmptyState text="选择游资后查看其席位在龙虎榜的最近操作。" icon="👤" /> : (
        <>
          <Space style={{ marginBottom: 8 }} wrap size={24}>
            <Statistic title="操作条数" value={ops.length} />
            <Statistic title="净买入合计" value={netBuy} formatter={(v) => moneyCn(Number(v))}
              valueStyle={{ color: netBuy >= 0 ? 'var(--up)' : 'var(--down)' }} />
            <Statistic title="买入 / 卖出" value={`${moneyCn(buyAmt)} / ${moneyCn(sellAmt)}`} valueStyle={{ fontSize: 14 }} />
          </Space>
          {ops.length ? (
            <Table size="small" rowKey="id" dataSource={ops} pagination={{ pageSize: 10 }}
              columns={[
                { title: '日期', dataIndex: 'trade_date', width: 100 },
                { title: '标的', key: 'stock', width: 150, render: (_: unknown, r: HotMoneyFlow) => <StockLabel code={String(r.stock_code ?? '')} name={String(r.stock_name ?? '')} /> },
                { title: '营业部', dataIndex: 'seat_name', width: 200, ellipsis: true },
                { title: '净买额', dataIndex: 'net_buy', align: 'right' as const, render: (v: number) => <Text style={{ color: (v ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }}>{moneyCn(v)}</Text> },
                { title: '数据源', dataIndex: 'source', width: 80, render: (v: string) => SRC_LABEL[v] ?? v },
              ]} />
          ) : <EmptyState text="该游资席位暂无龙虎榜操作记录。" icon="📭" />}
        </>
      )}
    </Space>
  )
}

/** 研判留痕：hot_money 留痕列表 + 跨模块联查（通用 traces 排除自身） */
function TracesView() {
  const [code, setCode] = useState('')
  const { data: rows } = useQuery({
    queryKey: ['hm-traces', code], queryFn: () => hotMoneyTraces(code), enabled: !!code,
  })
  const { data: crossAll } = useQuery({
    queryKey: ['hm-cross', code], queryFn: () => traces(code), enabled: !!code,
  })
  const list = rows ?? []
  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Input.Search placeholder="输入股票代码查看游资研判留痕（留空看全部）" style={{ width: 320 }} onSearch={setCode} allowClear />
      {!list.length ? <EmptyState text="暂无游资研判留痕。评分/建仓等环节注入游资数据时会自动留痕（ai_reasoning_trace，source_module=hot_money）。" icon="🧾" /> : (
        <Table size="small" rowKey="trace_id" dataSource={list} pagination={{ pageSize: 10 }}
          expandable={{ expandedRowRender: (t) => {
            const tc = t as unknown as Record<string, unknown>
            const tid = tc.trace_id
            return (
              <Space direction="vertical" style={{ width: '100%' }} size={6}>
                <div style={{ fontSize: 12 }}><Text strong>留痕结论：</Text>{String(tc.final_conclusion ?? tc.summary ?? '—')}</div>
                <div style={{ fontSize: 12 }}><Text strong>模块：</Text>{String(tc.source_module ?? '—')} · <Text strong>数据源：</Text>{String(tc.data_source ?? '—')} · <Text strong>置信度：</Text>{String(tc.confidence ?? '—')}</div>
                <div style={{ fontSize: 12 }}><Text strong>跨模块联查（同标的留痕）：</Text></div>
                {(crossAll ?? []).filter((c) => String(c.trace_id ?? '') !== String(tid ?? '')).slice(0, 5).map((c) => (
                  <div key={c.trace_id} style={{ fontSize: 12 }}>- {String(c.source_module ?? '—')} · {String(c.stock_code ?? '')} · {String(c.create_time ?? '').slice(0, 16)}</div>
                ))}
                {!(crossAll ?? []).length ? <div style={{ fontSize: 12 }}>- 无同标的其他模块留痕。</div> : null}
              </Space>
            )
          } }}
          columns={[
            { title: '日期', dataIndex: 'generate_date', width: 100 },
            { title: '标的', key: 'stock', width: 150, render: (_: unknown, t) => <StockLabel code={String((t as unknown as Record<string, unknown>).stock_code ?? '')} name={String((t as unknown as Record<string, unknown>).stock_name ?? '')} /> },
            { title: '结论', key: 'concl', ellipsis: true, render: (_: unknown, t) => { const tc = t as unknown as Record<string, unknown>; return String(tc.final_conclusion ?? tc.summary ?? '') || '—' } },
            { title: '时间', dataIndex: 'create_time', width: 150, render: (v: string) => String(v ?? '').slice(0, 16) },
          ]} />
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
        { key: 'seat', label: '席位监控', children: <SeatMonitor /> },
        { key: 'trace', label: '研判留痕', children: <TracesView /> },
        { key: 'iterate', label: '胜率迭代', children: <Iterate /> },
        { key: 'capital', label: '个股资本视图', children: <CapitalViewPanel /> },
      ]} />
    </div>
  )
}

export default HotMoneyPage
