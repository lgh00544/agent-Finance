import { useMemo, useState } from 'react'
import {
  App,
  Alert,
  Button,
  Card,
  Drawer,
  Input,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { portfolioAttribution, reviews, stockCycleAttribution } from '@/api/reviews'
import { candidateTradeable } from '@/api/candidates'
import { agentSuggestions, approveSuggestion, adoptSuggestion, rejectSuggestion } from '@/api/suggestions'
import { trackVerifyDates, trackVerifyList, trackVerifyStats, runTrackVerify, runTrackSuggest } from '@/api/track'
import { ChartCard } from '@/components/charts/ChartCard'
import type { EChartsOption } from 'echarts'
import { EmptyState, ErrorCard, StatCard, StatCardGrid, StatusBadge, StockLabel } from '@/components/common'
import type { AgentSuggestion, ReviewInfo, TrackVerifyRow } from '@/types'

const { Text } = Typography
const SUG_STATUS: Record<string, { label: string; color: string }> = {
  pending: { label: '待审核', color: 'orange' },
  approved: { label: '已采纳', color: 'green' },
  adopted: { label: '已采纳', color: 'green' },
  rejected: { label: '已驳回', color: 'default' },
}
// AI 自动决策记录：模块（target_agent）→ 中文
const MODULE_LABEL: Record<string, string> = {
  discover: '选股发现', score: '评分分析', position: '建仓方案',
  monitor: '持仓监控', sell: '卖出决策', review: '复盘迭代',
}

/** 复盘详情抽屉（黑盒：结论 + 交易记录 + 卖出决策 + 留痕） */
function ReviewDrawer({ r, open, onClose }: { r: ReviewInfo; open: boolean; onClose: () => void }) {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  if (!r) return null
  const fb = (r.feedback ?? {}) as Record<string, unknown>
  const suggestion = (fb.profile_suggestion ?? {}) as Record<string, unknown>

  const adopt = () => modal.confirm({
    title: '采纳建议并更新偏好档案', okText: '确认采纳',
    content: '该建议将写入偏好档案，版本+1，全部 Agent 立即生效。',
    onOk: async () => {
      try { await adoptSuggestion(r.id); message.success('已采纳'); qc.invalidateQueries({ queryKey: ['reviews'] }) }
      catch (e) { message.error(e instanceof Error ? e.message : '采纳失败') }
    },
  })
  const reject = () => modal.confirm({
    title: '驳回该建议', okText: '确认驳回', okButtonProps: { danger: true },
    content: '驳回后该建议标记为「已驳回」，不写入偏好档案；可在策略闭环建议列表重新处理。',
    onOk: async () => {
      try { await rejectSuggestion(r.id, '人工驳回'); message.success('已驳回'); qc.invalidateQueries({ queryKey: ['reviews'] }) }
      catch (e) { message.error(e instanceof Error ? e.message : '驳回失败') }
    },
  })

  return (
    <Drawer title={r.stock_name ? `${r.stock_code} ${r.stock_name}` : r.stock_code} open={open} onClose={onClose} width={600}>
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <Alert type="info" showIcon message={`离场 ${r.exit_date} · 持仓 ${r.hold_days} 天 · 盈亏 ${r.pnl_pct ?? '—'}%`} />
        <Card size="small" title="计划兑现度" style={{ background: 'var(--bg-input)' }}>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: 0 }}>{JSON.stringify(r.plan_vs_actual ?? {}, null, 2)}</pre>
        </Card>
        <Card size="small" title="经验教训" style={{ background: 'var(--bg-input)' }}>
          <div>{r.lesson || '（无）'}</div>
        </Card>
        {suggestion.field ? (
          <Card size="small" title={`交易偏好优化建议（第 ${r.suggest_iteration ?? 1} 版·${SUG_STATUS[r.suggest_status ?? '']?.label ?? '待审核'}）`}
            style={{ background: 'var(--bg-input)' }}>
            <div>修改 <code>{String(suggestion.field)}</code> → {String(suggestion.value)}</div>
            <div><Text type="secondary">{String(suggestion.reason ?? '')}</Text></div>
            {r.suggest_status === 'pending' ? (
              <div style={{ marginTop: 8 }}>
                <Space>
                  <Button type="primary" onClick={adopt}>采纳建议并更新偏好档案</Button>
                  <Button type="default" danger onClick={reject}>驳回</Button>
                </Space>
              </div>
            ) : r.suggest_status === 'adopted' ? <Text type="success">已采纳并生效</Text>
              : r.suggest_status === 'rejected' ? <Text type="secondary">已驳回</Text> : null}
          </Card>
        ) : null}
      </Space>
    </Drawer>
  )
}

/** 复盘列表 + 黑盒详情（点击行展开） */
function ReviewsList() {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const [drawerR, setDrawerR] = useState<ReviewInfo | null>(null)
  const [autoOpen, setAutoOpen] = useState(false)
  const [detailSug, setDetailSug] = useState<AgentSuggestion | null>(null)
  const { data: rows, isError, error, refetch } = useQuery({ queryKey: ['reviews'], queryFn: () => reviews() })
  // AI 自动决策记录（agent_suggestions 已有数据，仅可见性 + 提意见；回滚接口未上线 → disabled）
  const { data: sugs } = useQuery({ queryKey: ['agent-sug'], queryFn: () => agentSuggestions() })
  if (isError) return <ErrorCard title="复盘加载失败" message={error?.message} onRetry={() => refetch()} />
  const list = rows ?? []
  if (!list.length) return <EmptyState text="暂无复盘记录。在「持仓监控」页录入人工卖出后自动触发复盘。" icon="🔁" />

  const sugList = sugs ?? []
  const passed = sugList.filter((s) => s.status === 'approved').length
  const rejected = sugList.filter((s) => s.status === 'rejected').length
  const pending = sugList.filter((s) => s.status === 'pending').length

  const openFeedback = (s: AgentSuggestion) => {
    let reason = ''
    modal.confirm({
      title: '对这条 AI 自动决策提意见（以「驳回 + 理由」记录）',
      content: <Input.TextArea rows={3} placeholder="说明不同意的理由…" onChange={(e) => { reason = e.target.value }} />,
      okText: '提交', cancelText: '取消', okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await rejectSuggestion(s.id, reason.trim() || '人工驳回')
          message.success('已记录驳回意见')
          qc.invalidateQueries({ queryKey: ['agent-sug'] })
        } catch (e) { message.error(e instanceof Error ? e.message : '提交失败') }
      },
    })
  }

  const cols = [
    {
      title: '股票', key: 'stock', width: 180,
      render: (_: unknown, r: ReviewInfo) => <StockLabel code={r.stock_code} name={r.stock_name} />,
    },
    { title: '离场日', dataIndex: 'exit_date', width: 100 },
    { title: '持仓天数', dataIndex: 'hold_days', width: 90, render: (v: number) => v ?? '—' },
    {
      title: '盈亏', dataIndex: 'pnl_pct', width: 100,
      render: (v: number) => <Text style={{ color: (v ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }}>{v >= 0 ? '+' : ''}{v ?? 0}%</Text>,
    },
    { title: '建议状态', dataIndex: 'suggest_status', width: 90, render: (v: string) => <Tag color={SUG_STATUS[v]?.color ?? 'default'}>{SUG_STATUS[v]?.label ?? v}</Tag> },
    { title: '生成', dataIndex: 'created_at', width: 150, render: (v: string) => String(v ?? '').slice(0, 16) },
  ]

  return (
    <>
      {/* AI 自动决策 banner（reviews 为空时早退已隐藏；sugList 为空不显示统计 0 的横幅） */}
      {sugList.length ? (
        <Alert type="info" showIcon style={{ marginBottom: 10, cursor: 'pointer' }} onClick={() => setAutoOpen(true)}
          message={`🤖 AI 自动决策：近 ${sugList.length} 条 · 通过 ${passed} · 驳回 ${rejected} · 待审 ${pending}（点击查看）`} />
      ) : null}
      <Table<ReviewInfo> rowKey="id" size="small" dataSource={list} columns={cols} pagination={{ pageSize: 20 }}
        onRow={(r) => ({ onClick: () => setDrawerR(r) })} />
      <ReviewDrawer r={drawerR!} open={!!drawerR} onClose={() => setDrawerR(null)} />

      {/* AI 自动决策记录列表 */}
      <Drawer title="🤖 AI 自动决策记录" open={autoOpen} onClose={() => setAutoOpen(false)} width={640}>
        <Table size="small" rowKey="id" dataSource={sugList} pagination={{ pageSize: 10 }}
          columns={[
            { title: '时间', dataIndex: 'created_at', width: 130, render: (v: string) => String(v ?? '').slice(0, 16) },
            { title: '模块', dataIndex: 'target_agent', width: 90, render: (v: string) => <Tag>{MODULE_LABEL[String(v)] ?? v}</Tag> },
            { title: '操作', dataIndex: 'rule_name', ellipsis: true },
            { title: '状态', dataIndex: 'status', width: 76, render: (v: string) => <Tag color={SUG_STATUS[v]?.color ?? 'default'}>{SUG_STATUS[v]?.label ?? v}</Tag> },
            {
              title: '操作', key: 'ops', width: 200,
              render: (_: unknown, s: AgentSuggestion) => (
                <Space size={4}>
                  <Button size="small" onClick={() => setDetailSug(s)}>查看详情</Button>
                  <Button size="small" onClick={() => openFeedback(s)}>提意见</Button>
                  <Tooltip title="回滚功能开发中"><Button size="small" disabled>回滚</Button></Tooltip>
                </Space>
              ),
            },
          ]} />
      </Drawer>

      {/* 单条 AI 自动决策详情（查看详情） */}
      <Drawer title="🤖 AI 自动决策详情" open={!!detailSug} onClose={() => setDetailSug(null)} width={520}>
        {detailSug ? (
          <Space direction="vertical" style={{ width: '100%' }} size={10}>
            <div><Text strong>规则：</Text>{String(detailSug.rule_name ?? '')}</div>
            <div><Text strong>当前 → 建议：</Text>{String(detailSug.current_value ?? '—')} → {String(detailSug.suggested_value ?? '—')}</div>
            {detailSug.reason ? <div><Text strong>理由：</Text>{String(detailSug.reason)}</div> : null}
            {detailSug.rule_text ? (
              <Card size="small" title="规则全文" style={{ background: 'var(--bg-input)' }}>
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0 }}>{String(detailSug.rule_text)}</pre>
              </Card>
            ) : null}
          </Space>
        ) : null}
      </Drawer>
    </>
  )
}

/** 选股准确率验证（track verify，直调） */
function TrackVerify() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [date, setDate] = useState<string>()
  const [sortKey, setSortKey] = useState<string>('rating-date')

  const { data: dates } = useQuery({ queryKey: ['tv-dates'], queryFn: () => trackVerifyDates() })
  const { data: rows } = useQuery({
    queryKey: ['tv-list', date],
    queryFn: () => trackVerifyList(date ?? ''),
    enabled: !!date || !!dates?.length,
  })
  const { data: stats } = useQuery({ queryKey: ['tv-stats'], queryFn: () => trackVerifyStats('t5') })

  // —— 新增：按 select_date 批量跨查 candidate_tradeable，构建徽章索引 —— 只读
  const distinctDates = useMemo(() => {
    const s = new Set<string>()
    for (const r of rows ?? []) {
      const sd = String(r.select_date ?? '')
      if (sd) s.add(sd)
    }
    return Array.from(s)
  }, [rows])

  const tradeableQueries = useQueries({
    queries: distinctDates.map((d) => ({
      queryKey: ['candidate-tradeable', d],
      queryFn: () => candidateTradeable(d, 200),
      enabled: distinctDates.length > 0,
      staleTime: 60_000,
      retry: 1,
    })),
  })

  const tradeableMap = useMemo(() => {
    const m = new Map<string, Record<string, unknown>>()
    for (const q of tradeableQueries) {
      const d = String(q.data?.date ?? '')
      for (const it of (q.data?.items ?? [])) {
        const code = String(it.stock_code ?? '')
        if (code && d) m.set(`${d}_${code}`, it)
      }
    }
    return m
  }, [tradeableQueries])

  // —— 新增：排序（前端 stable sort，不动后端默认顺序）
  const sortedRows = useMemo(() => {
    const arr = [...(rows ?? [])]
    const ratingWeight = (v: unknown): number => {
      const r = String(v ?? '').trim()
      if (r === 'A') return 0
      if (r === 'B') return 1
      if (r === 'C') return 2
      return 3
    }
    const getPct = (r: TrackVerifyRow, k: string): number | null => {
      const v = (r as Record<string, unknown>)[k]
      if (v == null) return null
      const n = typeof v === 'number' ? v : Number(v)
      return Number.isFinite(n) ? n : null
    }
    if (sortKey === 'rating-date') {
      arr.sort((a, b) => {
        const ra = ratingWeight(a.select_rating)
        const rb = ratingWeight(b.select_rating)
        if (ra !== rb) return ra - rb
        return String(a.select_date ?? '').localeCompare(String(b.select_date ?? ''))
      })
    } else if (sortKey === 'date-rating') {
      arr.sort((a, b) => {
        const da = String(a.select_date ?? '')
        const db = String(b.select_date ?? '')
        if (da !== db) return db.localeCompare(da)  // 选中日降序
        return ratingWeight(a.select_rating) - ratingWeight(b.select_rating)
      })
    } else if (sortKey === 't5-desc') {
      arr.sort((a, b) => (getPct(b, 't5_pct') ?? -999) - (getPct(a, 't5_pct') ?? -999))
    } else if (sortKey === 'dd-desc') {
      arr.sort((a, b) => (Number(b.max_drawdown ?? -999)) - (Number(a.max_drawdown ?? -999)))
    }
    return arr
  }, [rows, sortKey])

  const wr = stats?.win_rate
  const avg = stats?.avg_pct
  const runVerify = async () => { try { await runTrackVerify(false); message.success('T+N 验证已提交后台'); qc.invalidateQueries({ queryKey: ['tv-list'] }) } catch (e) { message.error(e instanceof Error ? e.message : '失败') } }
  const runSuggest = async () => { try { await runTrackSuggest(); message.success('建议生成已提交后台') } catch (e) { message.error(e instanceof Error ? e.message : '失败') } }

  // 徽章样式：与 CandidatesPage 的 st-badge 系列同源
  const renderBadge = (sd: string, code: string) => {
    const it = tradeableMap.get(`${sd}_${code}`)
    const label = String(it?.label ?? '')
    if (!label) return <span style={{ color: '#bbb' }}>—</span>
    const tone = label === '可建仓' ? 'ok' : label === '建议关注' ? 'info' : 'mute'
    return <StatusBadge text={label} tone={tone} />
  }

  return (
    <div>
      <Space style={{ marginBottom: 10 }} wrap>
        <Select placeholder="选择日期" style={{ width: 140 }} value={date ?? dates?.[0]} onChange={setDate}
          options={(dates ?? []).map((d) => ({ label: d, value: d }))} />
        <Select
          placeholder="排序"
          style={{ width: 200 }}
          value={sortKey}
          onChange={setSortKey}
          options={[
            { label: '评级 A→C + 选中日', value: 'rating-date' },
            { label: '选中日降序 + 评级', value: 'date-rating' },
            { label: 'T+5 涨跌幅 高→低', value: 't5-desc' },
            { label: '最大回撤 高→低', value: 'dd-desc' },
          ]}
        />
        <Button onClick={runVerify}>手动验证（T+N）</Button>
        <Button onClick={runSuggest}>生成建议</Button>
      </Space>
      <StatCardGrid>
        <StatCard label="胜率" value={wr != null ? `${wr.toFixed(1)}%` : '无数据'}
          tone={wr != null ? (wr >= 50 ? 'ok' : wr < 40 ? 'err' : 'warn') : 'mute'}
          sub={`盈利 ${stats?.wins ?? 0} 笔 / 共 ${stats?.n ?? 0} 笔`} />
        <StatCard label="平均涨幅" value={avg != null ? `${avg >= 0 ? '+' : ''}${avg.toFixed(2)}%` : '无数据'}
          tone={avg != null ? (avg > 0 ? 'up' : avg < 0 ? 'down' : 'mute') : 'mute'} />
        <StatCard label="盈亏比" value={stats?.pl_ratio != null ? stats.pl_ratio.toFixed(2) : '—'} tone="mute" />
        <StatCard label="样本量" value={stats?.n ?? 0} tone="mute" sub="T+5 已到期" />
      </StatCardGrid>
      <Table size="small" rowKey="id" dataSource={sortedRows} pagination={{ pageSize: 10 }}
        columns={[
          { title: '股票', key: 'stock', render: (_: unknown, r: TrackVerifyRow) => <StockLabel code={String(r.stock_code ?? '')} name={String(r.stock_name ?? '')} /> },
          { title: '评级', dataIndex: 'select_rating', width: 70, render: (v: unknown) => String(v ?? '').trim() || '—' },
          {
            title: '建仓级别',
            key: 'tradeable_label',
            width: 110,
            render: (_: unknown, r: TrackVerifyRow) =>
              renderBadge(String(r.select_date ?? ''), String(r.stock_code ?? '')),
          },
          { title: '选中日', dataIndex: 'select_date', width: 100 },
          { title: 'T+3', dataIndex: 't3_pct', width: 70, render: (v: unknown) => v != null ? `${v}%` : '—' },
          { title: 'T+5', dataIndex: 't5_pct', width: 70, render: (v: unknown) => v != null ? `${v}%` : '—' },
          { title: 'T+10', dataIndex: 't10_pct', width: 80, render: (v: unknown) => v != null ? `${v}%` : '—' },
          { title: '最大回撤%', dataIndex: 'max_drawdown', width: 90, render: (v: unknown) => v ?? '—' },
        ]} />
    </div>
  )
}

/** 复盘建议列表（agent_suggestions） */
function Suggestions() {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const { data: rows } = useQuery({ queryKey: ['agent-sug'], queryFn: () => agentSuggestions() })
  const list = rows ?? []
  if (!list.length) return <EmptyState text="暂无优化建议。" icon="💡" />

  const act = (r: (typeof list)[number], action: 'approve' | 'adopt' | 'reject') => {
    const confirmMap: Record<string, { title: string; fn: () => Promise<unknown> }> = {
      approve: { title: `确认采纳建议：${r.rule_name}`, fn: () => approveSuggestion(r.id) },
      adopt: { title: `应用生效：${r.rule_name}（硬规则需二次确认）`, fn: () => adoptSuggestion(r.id, r.rule_type === 'hard') },
      reject: { title: `驳回建议：${r.rule_name}`, fn: () => rejectSuggestion(r.id, '人工驳回') },
    }
    modal.confirm({
      title: confirmMap[action].title,
      okText: '确认', okButtonProps: action === 'reject' ? { danger: true } : { type: 'primary' as const },
      onOk: async () => {
        try {
          await confirmMap[action].fn()
          message.success('已提交')
          qc.invalidateQueries({ queryKey: ['agent-sug'] })
        } catch (e) { message.error(e instanceof Error ? e.message : '操作失败') }
      },
    })
  }

  return (
    <Table size="small" rowKey="id" dataSource={list} pagination={{ pageSize: 10 }}
      columns={[
        { title: 'Agent', dataIndex: 'target_agent', width: 100 },
        { title: '规则', dataIndex: 'rule_name', ellipsis: true },
        { title: '当前→建议', key: 'val', width: 160, render: (_: unknown, r: (typeof list)[number]) => <Text>{(r.current_value ?? '—')} → {r.suggested_value ?? '—'}</Text> },
        { title: '状态', dataIndex: 'status', width: 80, render: (v: string) => <Tag color={SUG_STATUS[v]?.color ?? 'default'}>{SUG_STATUS[v]?.label ?? v}</Tag> },
        {
          title: '操作', key: 'ops', width: 200,
          render: (_: unknown, r: (typeof list)[number]) => (
            <Space size={4}>
              {r.status === 'pending' ? (r.target_kind === 'profile'
                ? <Button size="small" onClick={() => act(r, 'approve')}>采纳</Button>
                : <Button size="small" onClick={() => act(r, 'adopt')}>应用生效</Button>
              ) : null}
              {r.status === 'pending' ? <Button size="small" onClick={() => act(r, 'reject')}>驳回</Button> : null}
            </Space>
          ),
        },
      ]} />
  )
}

/** 组合复盘（批次H）：顶部组合曲线 + 中部贡献者瀑布 + 底部周期复利表 */
function PortfolioAttributionView() {
  const { data: attr } = useQuery({
    queryKey: ['portfolio-attribution'],
    queryFn: () => portfolioAttribution(30),
  })
  const curve = attr?.portfolio_curve ?? []
  const contributors = attr?.contributors ?? []
  // 默认选中：最负贡献者（最大拖累者）优先，其次第一只
  const [code, setCode] = useState<string | undefined>()
  const cur = code ?? contributors.find((c) => (c.contribution_pct ?? 0) < 0)?.stock_code
    ?? contributors[0]?.stock_code
  const { data: cycle } = useQuery({
    queryKey: ['stock-cycle', cur],
    queryFn: () => stockCycleAttribution(cur ?? ''),
    enabled: !!cur,
  })

  if (!curve.length && !contributors.length) {
    return <EmptyState text="暂无持仓数据。录入建仓并刷新行情后即可查看组合归因。" icon="📊" />
  }

  const curveOption: EChartsOption = {
    tooltip: { trigger: 'axis', formatter: (p: unknown) => {
      const it = (p as Array<{ axisValue: string; data: number }>)[0]
      return `${it.axisValue}：组合盈亏 ${it.data >= 0 ? '+' : ''}${it.data.toFixed(2)}%`
    } },
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: curve.map((c) => c.date), axisLabel: { color: '#9ca3af' } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%', color: '#9ca3af' }, splitLine: { lineStyle: { color: 'rgba(60,80,120,0.2)' } } },
    series: [{
      type: 'line', data: curve.map((c) => c.total_pnl_pct), smooth: true,
      symbol: 'circle', symbolSize: 5,
      itemStyle: { color: '#3b82f6' },
      areaStyle: { color: 'rgba(59,130,246,0.15)' },
    }],
  }
  const waterfallOption: EChartsOption = {
    tooltip: { trigger: 'axis', formatter: (p: unknown) => {
      const it = (p as Array<{ name: string; value: number }>)[0]
      return `${it.name}：贡献 ${it.value >= 0 ? '+' : ''}${it.value.toFixed(2)}%`
    } },
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: contributors.map((c) => c.stock_code), axisLabel: { color: '#9ca3af', rotate: 30 } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%', color: '#9ca3af' }, splitLine: { lineStyle: { color: 'rgba(60,80,120,0.2)' } } },
    series: [{
      type: 'bar',
      data: contributors.map((c) => ({
        value: c.contribution_pct ?? 0,
        itemStyle: { color: (c.contribution_pct ?? 0) >= 0 ? '#ef4444' : '#10b981', borderRadius: 2 },
      })),
      barWidth: 22,
    }],
  }
  const cycRows = [
    { k: '总盈亏（元）', v: cycle?.total_pnl != null ? cycle.total_pnl.toFixed(2) : '—' },
    { k: '平均持仓天数', v: cycle?.avg_hold_days != null ? String(cycle.avg_hold_days) : '—' },
    { k: '历史胜率', v: cycle?.win_rate != null ? `${cycle.win_rate}%` : '—' },
    { k: '历史拖累率', v: cycle?.drag_rate != null ? `${cycle.drag_rate}%` : '—' },
    { k: '周期数', v: `${cycle?.cycle_count ?? 0}（已了结 ${cycle?.closed_cycle_count ?? 0}）` },
    { k: '最佳周期', v: cycle?.best_cycle ? `${cycle.best_cycle.entry_date ?? '—'} ${cycle.best_cycle.pnl != null ? cycle.best_cycle.pnl.toFixed(2) : '—'} 元` : '—' },
    { k: '最差周期', v: cycle?.worst_cycle ? `${cycle.worst_cycle.entry_date ?? '—'} ${cycle.worst_cycle.pnl != null ? cycle.worst_cycle.pnl.toFixed(2) : '—'} 元` : '—' },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      {attr?.drag_analysis ? <Alert type="warning" showIcon message={attr.drag_analysis} /> : null}
      <ChartCard title="组合盈亏曲线（近 30 日，当前持仓视角）" option={curveOption} />
      <ChartCard title="各持仓贡献度（正绿 / 负红，% 相对总成本）" option={waterfallOption} />
      <Card size="small" title="周期复利（历史多次操作汇总）" style={{ background: 'var(--bg-card)' }}>
        <Space wrap style={{ marginBottom: 8 }}>
          <Select placeholder="选择股票" style={{ width: 200 }} value={cur} onChange={setCode}
            options={contributors.map((c) => ({ label: `${c.stock_code} ${c.stock_name ?? ''}`.trim(), value: c.stock_code }))} />
          {cycle && !cycle.has_history ? <Tag color="default">该股无历史操作记录</Tag> : null}
        </Space>
        <Table<{ k: string; v: string }> size="small" rowKey="k" pagination={false}
          dataSource={cycRows}
          columns={[
            { title: '指标', dataIndex: 'k', width: 160 },
            { title: '值', dataIndex: 'v', render: (v: string) => <Text>{v}</Text> },
          ]} />
      </Card>
    </Space>
  )
}

/** 交易复盘页（Phase 4 黑盒规范） */
export function ReviewsPage() {
  return (
    <div>
      <Tabs items={[
        { key: 'attr', label: '组合复盘', children: <PortfolioAttributionView /> },
        { key: 'reviews', label: '每日复盘报告', children: <ReviewsList /> },
        { key: 'track', label: '选股效果验证', children: <TrackVerify /> },
        { key: 'sug', label: '策略闭环建议', children: <Suggestions /> },
      ]} />
    </div>
  )
}

export default ReviewsPage
