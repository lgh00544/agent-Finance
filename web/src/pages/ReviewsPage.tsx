import { useEffect, useMemo, useState } from 'react'
import {
  App,
  Alert,
  Button,
  Card,
  Col,
  Collapse,
  Drawer,
  Input,
  List,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { get } from '@/api/client'
import { portfolioAttribution, reviews, stockCycleAttribution } from '@/api/reviews'
import { candidateTradeable } from '@/api/candidates'
import { agentSuggestions, approveSuggestion, adoptSuggestion, rejectSuggestion } from '@/api/suggestions'
import { trackVerifyDates, trackVerifyList, trackVerifyStats, runTrackVerify, runTrackSuggest } from '@/api/track'
import { traceDetail, traces } from '@/api/traces'
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

// ===== 工单9：period 时间范围筛选（1m/3m/6m/12m/all）=====
const PERIOD_OPTIONS = [
  { label: '全部', value: 'all' },
  { label: '近 1 月', value: '1m' },
  { label: '近 3 月', value: '3m' },
  { label: '近 6 月', value: '6m' },
  { label: '近 12 月', value: '12m' },
]
const PERIOD_DAYS: Record<string, number> = { '1m': 30, '3m': 90, '6m': 180, '12m': 365 }

function periodToRange(period: string): { start: string; end: string } {
  const days = PERIOD_DAYS[period]
  if (!days) return { start: '', end: '' }
  const end = new Date()
  const start = new Date(end.getTime() - days * 86_400_000)
  return { start: start.toISOString().slice(0, 10), end: end.toISOString().slice(0, 10) }
}

interface DailySummaryPayload {
  days: number
  current: { date?: string; pnl_pct?: number | null; pnl_amount?: number; market_value?: number }
  series: Array<{ date: string; pnl_pct: number }>
  top_gainers: Array<{ code: string; name: string; pnl_pct: number }>
  top_losers: Array<{ code: string; name: string; pnl_pct: number }>
  summary_text?: string
}

/** 复盘详情抽屉（黑盒：结论 + 交易记录 + 卖出决策 + 留痕 + 多日盈亏曲线） */
function ReviewDrawer({ r, open, onClose }: { r: ReviewInfo; open: boolean; onClose: () => void }) {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const { data: klines } = useQuery({
    queryKey: ['review-kline', r?.stock_code, r?.exit_date],
    queryFn: async () => {
      const end = String(r?.exit_date ?? '')
      if (!end) return []
      const s = new Date(end)
      s.setDate(s.getDate() - 30)
      const res = await get<{ klines: Array<Record<string, unknown>> }>(`/kline/${r?.stock_code}`, {
        start: s.toISOString().slice(0, 10), end,
      })
      return res.klines ?? []
    },
    enabled: open && !!r?.stock_code && !!r?.exit_date,
  })
  const { data: traceRows } = useQuery({
    queryKey: ['review-traces', r?.stock_code, r?.exit_date],
    queryFn: () => traces(r?.stock_code, String(r?.exit_date ?? ''), undefined, 20),
    enabled: open && !!r?.stock_code,
  })
  // 批5 留痕展开：点开才单查 traceDetail → 解析 ext_info，渲染 agentic 思考/工具轨迹（非 agentic 仅回退摘要）
  const [expandedTrace, setExpandedTrace] = useState<number | null>(null)
  const [traceExt, setTraceExt] = useState<Record<string, unknown> | null>(null)
  useEffect(() => { setExpandedTrace(null); setTraceExt(null) }, [r?.id])
  const toggleTraceDetail = async (id: number) => {
    if (expandedTrace === id) { setExpandedTrace(null); return }
    setExpandedTrace(id); setTraceExt(null)
    try {
      const res = await traceDetail(id)
      const raw = res.ext_info
      let ex: Record<string, unknown> = {}
      if (typeof raw === 'string') { try { ex = JSON.parse(raw) } catch { ex = {} } }
      else if (raw && typeof raw === 'object') { ex = raw as Record<string, unknown> }
      setTraceExt(ex)
    } catch { setTraceExt(null) }
  }
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

  const klineRows = klines ?? []
  const klineOption: EChartsOption | null = klineRows.length ? {
    tooltip: { trigger: 'axis' },
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: klineRows.map((k) => String(k.date ?? '')), axisLabel: { color: '#9ca3af' } },
    yAxis: { type: 'value', axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: 'rgba(60,80,120,0.2)' } } },
    series: [{ type: 'line', data: klineRows.map((k) => Number(k.close) || 0), smooth: true, symbol: 'none',
      itemStyle: { color: '#3b82f6' }, areaStyle: { color: 'rgba(59,130,246,0.15)' } }],
  } : null

  return (
    <Drawer title={r.stock_name ? `${r.stock_code} ${r.stock_name}` : r.stock_code} open={open} onClose={onClose} width={620}>
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <Alert type="info" showIcon message={`离场 ${r.exit_date} · 持仓 ${r.hold_days} 天 · 盈亏 ${r.pnl_pct ?? '—'}%`} />
        <StatCardGrid>
          <StatCard label="离场盈亏" value={`${(r.pnl_pct ?? 0) >= 0 ? '+' : ''}${r.pnl_pct ?? 0}%`} tone={(r.pnl_pct ?? 0) >= 0 ? 'up' : 'down'} sub="相对成本" />
          <StatCard label="持仓天数" value={r.hold_days ?? 0} tone="mute" sub="建仓→离场" />
          <StatCard label="离场日期" value={String(r.exit_date ?? '—')} tone="mute" sub="触发复盘" />
          <StatCard label="计划兑现" value={r.plan_vs_actual ? '已记录' : '无'} tone={r.plan_vs_actual ? 'ok' : 'mute'} sub="建仓计划对照" />
        </StatCardGrid>
        {klineOption ? (
          <ChartCard title={`多日盈亏曲线（${r.stock_code} 离场前 30 日收盘）`} option={klineOption} height={220} />
        ) : null}
        <Card size="small" title="计划兑现度" style={{ background: 'var(--bg-input)' }}>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: 0 }}>{JSON.stringify(r.plan_vs_actual ?? {}, null, 2)}</pre>
        </Card>
        <Card size="small" title="经验教训" style={{ background: 'var(--bg-input)' }}>
          <div>{r.lesson || '（无）'}</div>
        </Card>
        <Card size="small" title="推理留痕（ai_reasoning_trace · 该股该日）" style={{ background: 'var(--bg-input)' }}>
          {traceRows?.length ? (
            <List size="small" dataSource={traceRows} renderItem={(t) => {
              const tc = t as unknown as Record<string, unknown>
              const isOpen = expandedTrace === t.trace_id
              const ex = traceExt ?? {}
              const thinking = isOpen && typeof ex.model_thinking === 'string' && ex.model_thinking
                ? String(ex.model_thinking) : ''
              const tools = isOpen && typeof ex.tool_trace === 'string' && ex.tool_trace
                ? String(ex.tool_trace) : ''
              return (
                <List.Item>
                  <div style={{ width: '100%' }}>
                    <Space wrap>
                      <Tag>{String(tc.source_module ?? '—')}</Tag>
                      <Text type="secondary" style={{ fontSize: 12 }}>{String(tc.create_time ?? '').slice(0, 16)}</Text>
                      <Button type="link" size="small" style={{ padding: 0, fontSize: 12 }}
                        onClick={() => toggleTraceDetail(t.trace_id)}>
                        {isOpen ? '收起轨迹' : '展开轨迹'}
                      </Button>
                    </Space>
                    <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 4 }}>
                      {String(tc.summary ?? '') || String(tc.final_conclusion ?? '—').slice(0, 140)}
                    </div>
                    {isOpen && (thinking || tools) ? (
                      <Collapse size="small" ghost style={{ marginTop: 8 }} items={[
                        ...(thinking ? [{ key: 'thinking', label: '🧠 思考轨迹',
                          children: <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: 0 }}>{thinking}</pre> }] : []),
                        ...(tools ? [{ key: 'tools', label: '🛠 工具执行轨迹',
                          children: <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: 0 }}>{tools}</pre> }] : []),
                      ]} />
                    ) : null}
                  </div>
                </List.Item>
              )
            }} />
          ) : <EmptyState text="无该股推理留痕（可能未触发研判或数据未落库）。" icon="🧾" />}
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
        <Card size="small" title="复盘建议闭环" style={{ background: 'var(--bg-input)' }}>
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            <Text type="secondary">① 人工卖出 → 自动触发 ReviewAgent 复盘（盈亏归因 + 经验教训 + 偏好建议）</Text>
            <Text type="secondary">② 产出偏好优化建议 → 人工审核「采纳并更新偏好档案」/「驳回」</Text>
            <Text type="secondary">③ 采纳后偏好档案版本 +1，全部 Agent 立即生效；驳回以「驳回 + 理由」留痕可追溯</Text>
            <Alert type="warning" showIcon message="所有 Agent 优化建议必须经人工审核确认后才生效，系统绝不自动、无监督修改任何策略与参数。" />
          </Space>
        </Card>
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
  const adoptedCount = sugList.filter((s) => String(s.status) === 'adopted').length
  const winCount = list.filter((r) => (r.pnl_pct ?? 0) > 0).length
  const avgPnl = list.length ? list.reduce((s, r) => s + (r.pnl_pct ?? 0), 0) / list.length : 0
  const winRate = list.length ? (winCount / list.length) * 100 : null
  const avgHold = list.length ? list.reduce((s, r) => s + (r.hold_days ?? 0), 0) / list.length : 0

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
    {
      title: '周期', key: 'cycle', width: 80,
      render: (_: unknown, r: ReviewInfo) => {
        const days = r.hold_days ?? 0
        return <Tooltip title={`持仓 ${days} 天（建仓→离场）`}><Tag color={days >= 20 ? 'gold' : days >= 10 ? 'blue' : 'default'}>{days >= 20 ? '长线' : days >= 10 ? '波段' : '短线'}</Tag></Tooltip>
      },
    },
    { title: '持仓天数', dataIndex: 'hold_days', width: 90, render: (v: number) => v ?? '—' },
    {
      title: '盈亏', dataIndex: 'pnl_pct', width: 100,
      render: (v: number, r: ReviewInfo) => (
        <Tooltip title={r.lesson ? `经验教训：${r.lesson}` : '无经验教训'}>
          <Text style={{ color: (v ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }}>{v >= 0 ? '+' : ''}{v ?? 0}%</Text>
        </Tooltip>
      ),
    },
    {
      title: '建议状态', dataIndex: 'suggest_status', width: 110,
      render: (v: string) => (
        <Tooltip title={v === 'pending' ? '待人工审核' : v === 'adopted' ? '已采纳并生效' : v === 'approved' ? '已通过待应用' : v === 'rejected' ? '已驳回' : v}>
          <Tag color={SUG_STATUS[v]?.color ?? 'default'}>{SUG_STATUS[v]?.label ?? v}</Tag>
        </Tooltip>
      ),
    },
    { title: '生成', dataIndex: 'created_at', width: 150, render: (v: string) => String(v ?? '').slice(0, 16) },
    { title: '经验教训', dataIndex: 'lesson', ellipsis: true, render: (v: unknown) => v ? <Text type="secondary" ellipsis>{String(v)}</Text> : <Text type="secondary">—</Text> },
  ]

  return (
    <>
      <Alert type="info" showIcon style={{ marginBottom: 10 }}
        message="复盘闭环：人工卖出 → 自动触发 ReviewAgent 复盘（盈亏归因 + 经验教训 + 偏好建议）→ 建议经人工审核后回流全部 Agent。点击行查看详情（含多日盈亏曲线与推理留痕）。" />
      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
        复盘由「持仓监控」页人工记录卖出自动触发；本页仅展示已落库的复盘结论与聚合统计，不做任何二次判断。数据全部来自后端复盘结果，前端只读展示。
      </Text>
      {/* AI 自动决策 banner（reviews 为空时早退已隐藏；sugList 为空不显示统计 0 的横幅） */}
      <StatCardGrid>
        <StatCard label="复盘笔数" value={list.length} tone="mute" sub="已了结并自动复盘" />
        <StatCard label="平均盈亏" value={`${avgPnl >= 0 ? '+' : ''}${avgPnl.toFixed(2)}%`} tone={avgPnl >= 0 ? 'up' : 'down'} sub="单笔 % 均值" />
        <StatCard label="胜率" value={winRate != null ? `${winRate.toFixed(1)}%` : '—'} tone={winRate != null ? (winRate >= 50 ? 'ok' : 'warn') : 'mute'} sub="盈亏>0 占比" />
        <StatCard label="平均持仓天数" value={avgHold.toFixed(1)} tone="mute" sub="建仓→离场周期" />
        <StatCard label="建议采纳率" value={sugList.length ? `${(((adoptedCount + passed) / sugList.length) * 100).toFixed(0)}%` : '—'} tone="mute" sub="(采纳+通过)/建议总数" />
      </StatCardGrid>
      {sugList.length ? (
        <Alert type="info" showIcon style={{ marginBottom: 10, marginTop: 10, cursor: 'pointer' }} onClick={() => setAutoOpen(true)}
          message={`🤖 AI 自动决策：近 ${sugList.length} 条 · 通过 ${passed} · 采纳 ${adoptedCount} · 驳回 ${rejected} · 待审 ${pending}（点击查看）`} />
      ) : null}
      <Table<ReviewInfo> rowKey="id" size="small" dataSource={list} columns={cols} pagination={{ pageSize: 20 }}
        onRow={(r) => ({ onClick: () => setDrawerR(r) })} />
      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
        共 {list.length} 条复盘记录，点击行查看详情（含多日盈亏曲线与推理留痕）；建议状态列悬停可查看处置提示。
      </Text>
      <Insights list={list} />
      <CycleSummary list={list} />
      <DisciplineCheck list={list} />
      <DecisionTimeline list={sugList} />
      <Card size="small" title="复盘使用提示" style={{ marginTop: 10, background: 'var(--bg-input)' }}>
        <Space direction="vertical" style={{ width: '100%' }} size={4}>
          <Text type="secondary">• 「持仓监控」页记录卖出后自动触发复盘，无需手动提交</Text>
          <Text type="secondary">• 建议采纳 = 写入偏好档案立即生效（版本 +1）；驳回 = 留痕且不生效</Text>
          <Text type="secondary">• 复盘结论回流：偏好注入全部 Agent + 评分历史胜率维度参考</Text>
          <Text type="secondary">• 本页统计均为展示层聚合，不二次计算、不参与任何交易决策</Text>
        </Space>
      </Card>
      <ReviewDrawer r={drawerR!} open={!!drawerR} onClose={() => setDrawerR(null)} />

      {/* AI 自动决策记录列表 */}
      <Drawer title="🤖 AI 自动决策记录" open={autoOpen} onClose={() => setAutoOpen(false)} width={640}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
          以下为 ReviewAgent 全链路优化建议（偏好 / 提示词 / 硬规则），全部需人工审核确认后才生效；驳回以「驳回 + 理由」留痕可追溯。回滚功能开发中暂不可用。
        </Text>
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

/** 复盘洞察：盈亏区间分布 + 持仓周期分布 + 最佳/最差一笔（纯展示，从复盘列表统计） */
function Insights({ list }: { list: ReviewInfo[] }) {
  const pnlBuckets = (() => {
    const b = new Map<string, number>()
    for (const r of list) {
      const p = r.pnl_pct ?? 0
      const k = p >= 10 ? '+10% 以上' : p >= 0 ? '0 ~ +10%' : p >= -10 ? '-10% ~ 0' : '-10% 以下'
      b.set(k, (b.get(k) ?? 0) + 1)
    }
    return Array.from(b)
  })()
  const holdBuckets = (() => {
    const b = new Map<string, number>()
    for (const r of list) {
      const d = r.hold_days ?? 0
      const k = d >= 30 ? '30 天以上' : d >= 15 ? '15~30 天' : d >= 7 ? '7~15 天' : '7 天以内'
      b.set(k, (b.get(k) ?? 0) + 1)
    }
    return Array.from(b)
  })()
  const best = list.reduce((a, r) => ((r.pnl_pct ?? -999) > (a?.pnl_pct ?? -999) ? r : a), null as ReviewInfo | null)
  const worst = list.reduce((a, r) => ((r.pnl_pct ?? 999) < (a?.pnl_pct ?? 999) ? r : a), null as ReviewInfo | null)
  const totalPnl = list.reduce((s, r) => s + (r.pnl_pct ?? 0), 0)
  const distOption: EChartsOption | null = pnlBuckets.length ? {
    tooltip: { trigger: 'axis' },
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: pnlBuckets.map(([k]) => k), axisLabel: { color: '#9ca3af' } },
    yAxis: { type: 'value', axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: 'rgba(60,80,120,0.2)' } } },
    series: [{ type: 'bar', data: pnlBuckets.map(([, n]) => n), barWidth: 28,
      itemStyle: { color: '#8b5cf6', borderRadius: 2 } }],
  } : null
  return (
    <Card size="small" title="复盘洞察" style={{ marginTop: 10, background: 'var(--bg-input)' }}>
      <Space direction="vertical" style={{ width: '100%' }} size={10}>
        <Space wrap>
          <Text type="secondary">盈亏分布：</Text>
          {pnlBuckets.map(([k, n]) => <Tag key={k}>{k} {n}</Tag>)}
          {!pnlBuckets.length ? <Text type="secondary">无</Text> : null}
        </Space>
        <Space wrap>
          <Text type="secondary">持仓周期：</Text>
          {holdBuckets.map(([k, n]) => <Tag key={k}>{k} {n}</Tag>)}
          {!holdBuckets.length ? <Text type="secondary">无</Text> : null}
        </Space>
        <Row gutter={16}>
          <Col span={8}>
            <Statistic title="累计盈亏 %" value={totalPnl.toFixed(2)}
              valueStyle={{ color: totalPnl >= 0 ? 'var(--up)' : 'var(--down)' }} />
          </Col>
          <Col span={8}>
            <Statistic title="最佳一笔" value={best ? `${best.pnl_pct ?? 0}%` : '—'}
              valueStyle={{ color: 'var(--up)' }} suffix={best ? best.stock_name : undefined} />
          </Col>
          <Col span={8}>
            <Statistic title="最差一笔" value={worst ? `${worst.pnl_pct ?? 0}%` : '—'}
              valueStyle={{ color: 'var(--down)' }} suffix={worst ? worst.stock_name : undefined} />
          </Col>
        </Row>
        {distOption ? <ChartCard title="盈亏区间分布（笔数）" option={distOption} height={200} /> : null}
        <Text type="secondary" style={{ fontSize: 12 }}>
          洞察仅基于已复盘记录统计，样本量偏小时结论需谨慎；「-8% 以下」占比高提示止损纪律需加强，「+10% 以上」占比高提示趋势持仓策略有效。
        </Text>
        <Text type="secondary" style={{ fontSize: 12 }}>
          持仓周期标签口径：短线 &lt;10 天 · 波段 10~19 天 · 长线 ≥20 天；分组汇总见下方「周期表现汇总」。
        </Text>
      </Space>
    </Card>
  )
}

/** 周期表现汇总：按持仓周期分组统计胜率/平均盈亏（纯展示） */
function CycleSummary({ list }: { list: ReviewInfo[] }) {
  const cycles = (() => {
    const g = new Map<string, ReviewInfo[]>()
    for (const r of list) {
      const d = r.hold_days ?? 0
      const k = d >= 20 ? '长线(≥20天)' : d >= 10 ? '波段(10~19天)' : '短线(<10天)'
      g.set(k, [...(g.get(k) ?? []), r])
    }
    return Array.from(g).map(([k, rs]) => {
      const win = rs.filter((x) => (x.pnl_pct ?? 0) > 0).length
      const avg = rs.reduce((s, x) => s + (x.pnl_pct ?? 0), 0) / rs.length
      return { key: k, count: rs.length, winRate: rs.length ? (win / rs.length) * 100 : 0, avgPnl: avg }
    }).sort((a, b) => a.key.localeCompare(b.key))
  })()
  if (!cycles.length) return null
  return (
    <Card size="small" title="周期表现汇总（按持仓周期分组）" style={{ marginTop: 10, background: 'var(--bg-input)' }}>
      <Table<{ key: string; count: number; winRate: number; avgPnl: number }> size="small" rowKey="key" dataSource={cycles} pagination={false}
        columns={[
          { title: '周期', dataIndex: 'key', width: 160 },
          { title: '笔数', dataIndex: 'count', width: 80 },
          { title: '胜率', dataIndex: 'winRate', width: 100, render: (v: number) => `${v.toFixed(1)}%` },
          { title: '平均盈亏', dataIndex: 'avgPnl', render: (v: number) => <Text style={{ color: v >= 0 ? 'var(--up)' : 'var(--down)' }}>{v >= 0 ? '+' : ''}{v.toFixed(2)}%</Text> },
          { title: '结论参考', key: 'note', render: (_: unknown, r: { winRate: number; avgPnl: number }) =>
            <Text type="secondary">{r.winRate >= 50 && r.avgPnl > 0 ? '该周期打法有效，可延续' : r.avgPnl < 0 ? '该周期平均亏损，需复盘调参' : '中性，样本积累中'}</Text> },
        ]} />
    </Card>
  )
}

/** 交易纪律检查：从复盘记录检查止损/持仓纪律（纯统计展示，不触发任何判断） */
function DisciplineCheck({ list }: { list: ReviewInfo[] }) {
  const stats = (() => {
    const overLoss = list.filter((r) => (r.pnl_pct ?? 0) <= -8)
    const bigWin = list.filter((r) => (r.pnl_pct ?? 0) >= 15)
    const shortHold = list.filter((r) => (r.hold_days ?? 0) <= 3)
    const longHold = list.filter((r) => (r.hold_days ?? 0) >= 40)
    return { total: list.length, overLoss: overLoss.length, bigWin: bigWin.length,
      shortHold: shortHold.length, longHold: longHold.length,
      lossAvg: overLoss.length ? overLoss.reduce((s, r) => s + (r.pnl_pct ?? 0), 0) / overLoss.length : 0 }
  })()
  if (!stats.total) return null
  return (
    <Card size="small" title="交易纪律检查（复盘视角，仅统计展示）" style={{ marginTop: 10, background: 'var(--bg-input)' }}>
      <StatCardGrid>
        <StatCard label="超 -8% 亏损" value={stats.overLoss} tone={stats.overLoss ? 'err' : 'ok'} sub={`均值 ${stats.lossAvg.toFixed(2)}%`} />
        <StatCard label="大赚 ≥15%" value={stats.bigWin} tone="ok" sub="建议复盘归因" />
        <StatCard label="超短线 ≤3天" value={stats.shortHold} tone="warn" sub="追涨杀跌风险" />
        <StatCard label="长持 ≥40天" value={stats.longHold} tone="mute" sub="占用资金周期" />
      </StatCardGrid>
      <Text type="secondary" style={{ fontSize: 12 }}>
        纪律参考：单笔止损参考 -8%（全局基线），超阈值需归因是否严格执行；超短线高频操作通常胜率与盈亏比双低。
      </Text>
    </Card>
  )
}

/** AI 决策采纳流水（按时间倒序展示建议状态；纯展示，改状态需人工在列表操作） */
function DecisionTimeline({ list }: { list: AgentSuggestion[] }) {
  const items = [...list].sort((a, b) => String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')))
  if (!items.length) return null
  return (
    <Card size="small" title="AI 决策采纳流水（近 50 条，按时间倒序）" style={{ marginTop: 10, background: 'var(--bg-input)' }}>
      <List size="small" dataSource={items.slice(0, 50)} renderItem={(s) => {
        const st = String(s.status ?? '')
        const tone = st === 'adopted' ? 'green' : st === 'approved' ? 'blue'
          : st === 'rejected' ? 'default' : 'orange'
        return (
          <List.Item>
            <div style={{ width: '100%' }}>
              <Space wrap>
                <Tag color={tone}>{SUG_STATUS[st]?.label ?? st}</Tag>
                <Tag>{MODULE_LABEL[String(s.target_agent ?? '')] ?? s.target_agent}</Tag>
                <Text type="secondary" style={{ fontSize: 12 }}>{String(s.created_at ?? '').slice(0, 16)}</Text>
              </Space>
              <div style={{ fontSize: 13, marginTop: 2 }}>{String(s.rule_name ?? '')}</div>
              <Text type="secondary" style={{ fontSize: 12 }}>{String(s.current_value ?? '—')} → {String(s.suggested_value ?? '—')}</Text>
            </div>
          </List.Item>
        )
      }} />
    </Card>
  )
}

/** 选股胜率趋势：按选中日分组的 T+5 胜率折线（纯展示，需 ≥2 个选中日） */
function WinRateTrend({ list }: { list: TrackVerifyRow[] }) {
  const data = (() => {
    const g = new Map<string, { win: number; n: number }>()
    for (const r of list) {
      if (r.t5_pct == null) continue
      const d = String(r.select_date ?? '')
      if (!d) continue
      const cur = g.get(d) ?? { win: 0, n: 0 }
      cur.n += 1
      if (Number(r.t5_pct) >= 0) cur.win += 1
      g.set(d, cur)
    }
    return Array.from(g).sort((a, b) => a[0].localeCompare(b[0]))
      .map(([d, v]) => ({ date: d, rate: v.n ? Math.round((v.win / v.n) * 1000) / 10 : 0, n: v.n }))
  })()
  if (data.length < 2) return null
  const option: EChartsOption = {
    tooltip: { trigger: 'axis', formatter: (p: unknown) => {
      const it = (p as Array<{ axisValue: string; data: number }>)[0]
      return `${it.axisValue}：胜率 ${it.data.toFixed(1)}%`
    } },
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: data.map((d) => d.date), axisLabel: { color: '#9ca3af', rotate: 30 } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%', color: '#9ca3af' }, splitLine: { lineStyle: { color: 'rgba(60,80,120,0.2)' } } },
    series: [{ type: 'line', data: data.map((d) => d.rate), smooth: true, symbol: 'circle', symbolSize: 5,
      itemStyle: { color: '#10b981' }, areaStyle: { color: 'rgba(16,185,129,0.12)' } }],
  }
  return <ChartCard title="选股胜率趋势（按选中日 T+5 胜率）" option={option} height={220} />
}

/** 选股准确率验证（track verify，直调） */
function TrackVerify() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [date, setDate] = useState<string>()
  const [period, setPeriod] = useState<string>('all')
  const [sortKey, setSortKey] = useState<string>('rating-date')
  const range = useMemo(() => periodToRange(period), [period])

  const { data: dates } = useQuery({ queryKey: ['tv-dates'], queryFn: () => trackVerifyDates() })
  const { data: rows } = useQuery({
    queryKey: ['tv-list', period, date],
    queryFn: async () => {
      if (date) return trackVerifyList(date)
      const params: Record<string, unknown> = { limit: 200 }
      if (range.start) params.start_date = range.start
      if (range.end) params.end_date = range.end
      return get<TrackVerifyRow[]>('/track/verify/list', params)
    },
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
  const runBackfill = async () => { try { await runTrackVerify(true); message.success('历史回填已提交后台，将逐日补算候选 T+N'); qc.invalidateQueries({ queryKey: ['tv-list'] }) } catch (e) { message.error(e instanceof Error ? e.message : '失败') } }
  const runSuggest = async () => { try { await runTrackSuggest(); message.success('建议生成已提交后台') } catch (e) { message.error(e instanceof Error ? e.message : '失败') } }

  const ratingDist = useMemo(() => {
    const m = new Map<string, number>()
    for (const r of sortedRows) { const k = String(r.select_rating ?? '').trim() || '未评级'; m.set(k, (m.get(k) ?? 0) + 1) }
    return Array.from(m)
  }, [sortedRows])
  const rankedByT5 = useMemo(() => [...sortedRows].filter((r) => r.t5_pct != null)
    .sort((a, b) => Number(b.t5_pct) - Number(a.t5_pct)), [sortedRows])
  const bestT5 = rankedByT5.slice(0, 3)
  const worstT5 = [...rankedByT5].reverse().slice(0, 3)
  const dateRange = useMemo(() => {
    const ds = (rows ?? []).map((r) => String(r.select_date ?? '')).filter(Boolean).sort()
    return { min: ds[0] ?? '—', max: ds[ds.length - 1] ?? '—', n: ds.length }
  }, [rows])
  const periodAvg = useMemo(() => {
    const avg = (k: 't3_pct' | 't5_pct' | 't10_pct') => {
      const real = (rows ?? []).map((r) => Number(r[k])).filter((v) => Number.isFinite(v))
      return real.length ? real.reduce((s, v) => s + v, 0) / real.length : null
    }
    return { t3: avg('t3_pct'), t5: avg('t5_pct'), t10: avg('t10_pct') }
  }, [rows])

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
        <Select placeholder="时间范围" style={{ width: 110 }} value={period} onChange={setPeriod} options={PERIOD_OPTIONS} />
        <Select placeholder="选择日期（精确）" style={{ width: 150 }} value={date} onChange={setDate} allowClear
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
        <Button onClick={runBackfill}>历史回填</Button>
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
      <StatCardGrid>
        <StatCard label="T+3 平均" value={periodAvg.t3 != null ? `${periodAvg.t3 >= 0 ? '+' : ''}${periodAvg.t3.toFixed(2)}%` : '—'} tone="mute" sub="选中日 3 日后" />
        <StatCard label="T+5 平均" value={periodAvg.t5 != null ? `${periodAvg.t5 >= 0 ? '+' : ''}${periodAvg.t5.toFixed(2)}%` : '—'} tone="mute" sub="选中日 5 日后" />
        <StatCard label="T+10 平均" value={periodAvg.t10 != null ? `${periodAvg.t10 >= 0 ? '+' : ''}${periodAvg.t10.toFixed(2)}%` : '—'} tone="mute" sub="选中日 10 日后" />
        <StatCard label="已验证日期" value={dateRange.n} tone="mute" sub={`${dateRange.min} ~ ${dateRange.max}`} />
      </StatCardGrid>
      <Alert type="info" showIcon style={{ marginBottom: 10 }}
        message={`验证口径：候选选中日 T+N 涨跌幅（相对选中日收盘 base_close_price），T+N 收益跑赢沪深300 = 胜。列表支持按时间范围（近 1/3/6/12 月）与精确日期过滤；「历史回填」逐日补算未追踪的历史候选。`} />
      <WinRateTrend list={rows ?? []} />
      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
        排序规则：默认「评级 A→C + 选中日」；T+3/T+5/T+10 仅显示已到期样本，未到期显示「—」；「建仓级别」徽章来自当日可建仓判定（只读展示）。
      </Text>
      <Card size="small" title="统计口径说明" style={{ background: 'var(--bg-input)', marginBottom: 10 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          「生成建议」基于已到期样本的胜率/回撤做提示性建议（落 agent_suggestion 待审核），不会自动改动任何策略。
        </Text>
        <Space direction="vertical" style={{ width: '100%' }} size={4}>
          <Text type="secondary">• 胜率 = 跑赢沪深300 的信号占比（T+N 收益 &gt; 大盘收益 = 胜）</Text>
          <Text type="secondary">• 平均涨幅 = 全部到期样本 T+5 涨跌幅均值（% 相对选中日收盘）</Text>
          <Text type="secondary">• 最大回撤 = 到期样本窗口内最低价到选中日的回撤幅度</Text>
          <Text type="secondary">• 样本量 = T+5 已到期的追踪行数（未到期不计入胜率）</Text>
          <Text type="secondary">• 数据来源：候选池选中日 base_close_price + 日 K 收盘（纯代码计算，零 LLM）</Text>
        </Space>
      </Card>
      <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
        数据截止：最近一次 T+N 验证运行结果；「历史回填」可逐日补算未追踪的历史候选，补算为后台任务不阻塞页面。
      </Text>
      <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
        最近验证日期：{dates?.[0] ?? '—'}；「手动验证（T+N）」对最新候选补算已到期样本，「生成建议」产出提示性建议（待审核）。
      </Text>
      <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
        追踪状态：追踪中 = 选中日 T+5 未到期；已到期 = 已补算 T+5 收益并可计胜率。
      </Text>
      <Space wrap style={{ marginBottom: 10 }}>
        <Text type="secondary">评级分布：</Text>
        {ratingDist.map(([k, n]) => (
          <Tag key={k} color={k === 'A' ? 'red' : k === 'B' ? 'orange' : k === 'C' ? 'blue' : 'default'}>{k} {n}</Tag>
        ))}
        {!ratingDist.length ? <Text type="secondary">无</Text> : null}
        <Text type="secondary" style={{ marginLeft: 8 }}>A=强烈推荐 · B=建议关注 · C=谨慎观察（LLM 信心度档位映射，纯展示）</Text>
      </Space>
      <Row gutter={16} style={{ marginBottom: 10 }}>
        <Col span={12}>
          <Card size="small" title="T+5 表现最佳（top 3）" style={{ background: 'var(--bg-input)' }}>
            {bestT5.length ? <List size="small" dataSource={bestT5} renderItem={(r) => (
              <List.Item>
                <StockLabel code={String(r.stock_code ?? '')} name={String(r.stock_name ?? '')} />
                <Text style={{ color: (r.t5_pct ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }}>{r.t5_pct}%</Text>
              </List.Item>
            )} /> : <EmptyState text="暂无 T+5 到期数据。" icon="📭" />}
          </Card>
        </Col>
        <Col span={12}>
          <Card size="small" title="T+5 表现最差（top 3）" style={{ background: 'var(--bg-input)' }}>
            {worstT5.length ? <List size="small" dataSource={worstT5} renderItem={(r) => (
              <List.Item>
                <StockLabel code={String(r.stock_code ?? '')} name={String(r.stock_name ?? '')} />
                <Text style={{ color: (r.t5_pct ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }}>{r.t5_pct}%</Text>
              </List.Item>
            )} /> : <EmptyState text="暂无 T+5 到期数据。" icon="📭" />}
          </Card>
        </Col>
      </Row>
      <Table size="small" rowKey="id" dataSource={sortedRows} pagination={{ pageSize: 10 }}
        columns={[
          { title: '股票', key: 'stock', render: (_: unknown, r: TrackVerifyRow) => <StockLabel code={String(r.stock_code ?? '')} name={String(r.stock_name ?? '')} /> },
          { title: '评级', dataIndex: 'select_rating', width: 70, render: (v: unknown) => String(v ?? '').trim() || '—' },
          {
            title: '建仓级别',
            key: 'tradeable_label',
            width: 110,
            render: (_: unknown, r: TrackVerifyRow) =>
              <Tooltip title="当日可建仓判定（严格度门槛 + 买点/利空硬条件）；只读展示"> {renderBadge(String(r.select_date ?? ''), String(r.stock_code ?? ''))} </Tooltip>,
          },
          { title: '选中日', dataIndex: 'select_date', width: 100 },
          { title: 'T+3', dataIndex: 't3_pct', width: 70, render: (v: unknown) => v != null ? `${v}%` : '—' },
          { title: 'T+5', dataIndex: 't5_pct', width: 70, render: (v: unknown) => v != null ? `${v}%` : '—' },
          {
            title: 'T+5 结果', key: 't5res', width: 80,
            render: (_: unknown, r: TrackVerifyRow) => r.t5_pct != null
              ? <Tag color={Number(r.t5_pct) >= 0 ? 'green' : 'red'}>{Number(r.t5_pct) >= 0 ? '胜' : '负'}</Tag>
              : <Tag color="default">未到期</Tag>,
          },
          {
            title: '追踪', dataIndex: 'is_finished', width: 70,
            render: (v: unknown) => v ? <Tag color="green">已到期</Tag> : <Tag color="blue">追踪中</Tag>,
          },
          { title: 'T+10', dataIndex: 't10_pct', width: 80, render: (v: unknown) => v != null ? `${v}%` : '—' },
          { title: '最大回撤%', dataIndex: 'max_drawdown', width: 90, render: (v: unknown) => v ?? '—' },
        ]} locale={{ emptyText: '当前筛选无追踪数据：切换时间范围、选择精确日期，或点「历史回填」逐日补算未追踪候选。' }} />
    </div>
  )
}

/** 复盘建议列表（agent_suggestions） */
function Suggestions() {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const { data: rows } = useQuery({ queryKey: ['agent-sug'], queryFn: () => agentSuggestions() })
  const list = rows ?? []
  const byAgent = (() => {
    const m = new Map<string, number>()
    for (const s of list) { const a = s.target_agent ?? '其他'; m.set(a, (m.get(a) ?? 0) + 1) }
    return Array.from(m)
  })()
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

  const byStatus = (st: string) => list.filter((s) => s.status === st).length
  const hardCount = list.filter((s) => s.rule_type === 'hard').length

  return (
    <>
      <Alert type="info" showIcon style={{ marginBottom: 10 }}
        message="策略闭环：ReviewAgent 每次平仓后产出优化建议（偏好/规则），全部经人工审核确认后才生效；硬规则（HARD_RULES）采纳需二次确认。驳回会以「驳回 + 理由」留痕。" />
      <StatCardGrid>
        <StatCard label="待审建议" value={byStatus('pending')} tone={byStatus('pending') ? 'warn' : 'mute'} sub="需人工审核后生效" />
        <StatCard label="已通过" value={byStatus('approved')} tone="ok" sub="待应用生效" />
        <StatCard label="已采纳生效" value={byStatus('adopted')} tone="ok" sub="已写入偏好/规则" />
        <StatCard label="已驳回" value={byStatus('rejected')} tone="mute" sub="含人工驳回" />
      </StatCardGrid>
      <Space wrap style={{ margin: '10px 0' }}>
        <Text type="secondary">规则类型：</Text>
        <Tag color={hardCount ? 'volcano' : 'default'}>硬规则 {hardCount}</Tag>
        <Tag>偏好/参数 {list.length - hardCount}</Tag>
        <Text type="secondary" style={{ marginLeft: 8 }}>Agent 分布：</Text>
        {byAgent.map(([a, n]) => <Tag key={a}>{MODULE_LABEL[a] ?? a} {n}</Tag>)}
      </Space>
      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
        建议按目标 Agent 分布如上；全部需人工审核，「硬规则」采纳需二次确认。展开行可查看规则全文。
      </Text>
      <Table size="small" rowKey="id" dataSource={list} pagination={{ pageSize: 10 }}
        expandable={{ expandedRowRender: (r) => <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0 }}>{String(r.rule_text ?? '无规则全文')}</pre> }}
        columns={[
          { title: 'Agent', dataIndex: 'target_agent', width: 100, render: (v: string) => MODULE_LABEL[v] ?? v },
          { title: '类型', dataIndex: 'target_kind', width: 90, render: (v: string) =>
            <Tag color={v === 'hard' ? 'volcano' : v === 'profile' ? 'blue' : 'default'}>{v === 'hard' ? '硬规则' : v === 'profile' ? '偏好' : '提示词'}</Tag> },
          { title: '规则', dataIndex: 'rule_name', ellipsis: true },
          { title: '当前→建议', key: 'val', width: 160, render: (_: unknown, r: (typeof list)[number]) => <Text>{(r.current_value ?? '—')} → {r.suggested_value ?? '—'}</Text> },
          { title: '时间', dataIndex: 'created_at', width: 130, render: (v: string) => String(v ?? '').slice(0, 16) },
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
      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>
        操作指引：采纳 = 通过审核（偏好类写入档案；规则类进入待应用）；应用生效 = 硬规则需二次确认后落地；驳回 = 以「驳回 + 理由」留痕。全部需人工操作，系统绝不自动生效。
      </Text>
    </>
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
  const totalCost = (attr as Record<string, unknown> | undefined)?.total_cost as number | undefined
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
      <Alert type="info" showIcon style={{ marginBottom: 10 }}
        message="组合归因口径：组合曲线 = 当前持仓视角逐日 Σ 单票浮盈亏 / 总成本 × 100（建仓前不计入、缺行情日不计入、不伪造 0）；贡献度 = 单票浮盈亏 / 总成本。选择单股可查看其历史多次操作的周期复利。仅做展示，不触发任何自动调仓。" />
      <StatCardGrid>
        <StatCard label="当前总成本" value={totalCost != null ? `¥${(totalCost / 10000).toFixed(1)}万` : '—'} tone="mute" />
        <StatCard label="持仓数量" value={contributors.length} tone="mute" sub="贡献度已核算" />
        <StatCard label="盈利持仓" value={contributors.filter((c) => (c.contribution_pct ?? 0) > 0).length} tone="ok" sub="贡献度>0" />
        <StatCard label="亏损持仓" value={contributors.filter((c) => (c.contribution_pct ?? 0) < 0).length} tone="err" sub="贡献度<0" />
      </StatCardGrid>
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
        <Text type="secondary" style={{ fontSize: 12 }}>
          周期 = 单股一次建仓→离场为一个完整周期；多笔操作按时间顺序串联为复利链。样本不足时相关指标显示「—」。
        </Text>
      </Card>
      <Card size="small" title="持仓贡献明细（当前持仓逐只）" style={{ background: 'var(--bg-input)' }}>
        <Table size="small" rowKey="stock_code" dataSource={contributors} pagination={false}
          columns={[
            { title: '标的', key: 'stock', render: (_: unknown, c: Record<string, unknown>) =>
              <StockLabel code={String(c.stock_code ?? '')} name={String(c.stock_name ?? '')} /> },
            { title: '贡献度%', dataIndex: 'contribution_pct', width: 100,
              render: (v: unknown) => v != null ? <Text style={{ color: Number(v) >= 0 ? 'var(--up)' : 'var(--down)' }}>{Number(v) >= 0 ? '+' : ''}{String(v)}%</Text> : '—' },
            { title: '浮盈亏', dataIndex: 'pnl_amount', width: 110,
              render: (v: unknown) => v != null ? `¥${Number(v).toFixed(0)}` : '—' },
            { title: '持仓天数', dataIndex: 'holding_days', width: 90, render: (v: unknown) => v ?? '—' },
          ]} />
      </Card>
      <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
        贡献度 = 单票浮盈亏 / 当前持仓总成本 × 100（正绿/负红）；持仓天数按建仓日至今计算。本页均为展示层只读，不参与任何自动调仓。
      </Text>
      <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
        周期复利口径：按该股历史每次建仓→离场为一个周期，汇总总盈亏 / 平均持仓 / 胜率 / 拖累率；样本不足时相关字段显示「—」。
      </Text>
    </Space>
  )
}

/** 每日组合总结（daily-summary：当前盈亏 + N 日曲线 + top gainers/losers + 总结文案） */
function DailySummary() {
  const [period, setPeriod] = useState<string>('1m')
  const days = PERIOD_DAYS[period] ?? 30
  const { data, isError, error, refetch } = useQuery({
    queryKey: ['daily-summary', days],
    queryFn: () => get<DailySummaryPayload>('/portfolio/daily-summary', { days }),
  })
  if (isError) return <ErrorCard title="组合总结加载失败" message={error?.message} onRetry={() => refetch()} />
  const cur = data?.current
  const series = data?.series ?? []
  const seriesSum = series.reduce((s, p) => s + (p.pnl_pct ?? 0), 0)
  const seriesMax = series.length ? Math.max(...series.map((p) => p.pnl_pct ?? 0)) : 0
  const seriesMin = series.length ? Math.min(...series.map((p) => p.pnl_pct ?? 0)) : 0
  const option: EChartsOption | null = series.length ? {
    tooltip: { trigger: 'axis', formatter: (p: unknown) => {
      const it = (p as Array<{ axisValue: string; data: number }>)[0]
      return `${it.axisValue}：组合盈亏 ${it.data >= 0 ? '+' : ''}${it.data.toFixed(2)}%`
    } },
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
    xAxis: { type: 'category', data: series.map((s) => s.date), axisLabel: { color: '#9ca3af' } },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%', color: '#9ca3af' }, splitLine: { lineStyle: { color: 'rgba(60,80,120,0.2)' } } },
    series: [{ type: 'line', data: series.map((s) => s.pnl_pct), smooth: true, symbol: 'circle', symbolSize: 4,
      itemStyle: { color: '#3b82f6' }, areaStyle: { color: 'rgba(59,130,246,0.15)' } }],
  } : null
  const renderTop = (title: string, items: Array<{ code: string; name: string; pnl_pct: number }>) => (
    <div>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{title}</div>
      {items.length ? (
        <List size="small" dataSource={items} renderItem={(it) => (
          <List.Item>
            <StockLabel code={it.code} name={it.name} />
            <Text style={{ color: it.pnl_pct >= 0 ? 'var(--up)' : 'var(--down)' }}>{it.pnl_pct >= 0 ? '+' : ''}{it.pnl_pct}%</Text>
          </List.Item>
        )} />
      ) : <EmptyState text="暂无数据。" icon="📭" />}
    </div>
  )
  return (
    <Card size="small" title={`📈 每日组合总结（${PERIOD_OPTIONS.find((p) => p.value === period)?.label ?? ''}）`}
      extra={<Select size="small" style={{ width: 100 }} value={period} onChange={setPeriod}
        options={PERIOD_OPTIONS.filter((o) => o.value !== 'all')} />}
      style={{ marginTop: 16 }}>
      {!data ? (
        <>
          <EmptyState text="暂无组合总结数据（录入建仓并刷新行情后生成）。" icon="📈" />
          <Text type="secondary" style={{ fontSize: 12 }}>
            录入持仓并触发行情刷新后，此处将展示组合当日盈亏 / N 日曲线 / 贡献领先与拖累。
          </Text>
        </>
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          {data.summary_text ? <Alert type="info" showIcon message={data.summary_text} /> : null}
          <Space wrap>
            <Tag color={(cur?.pnl_pct ?? 0) >= 0 ? 'green' : 'red'}>今日{(cur?.pnl_pct ?? 0) >= 0 ? '盈利' : '亏损'}</Tag>
            <Tag color={series.length ? 'blue' : 'default'}>曲线样本 {series.length} 日</Tag>
            {!series.length ? <Tag color="default">历史曲线数据不足</Tag> : null}
          </Space>
          {series.length ? (
            <Alert type={seriesMin <= -8 ? 'warning' : 'info'} showIcon
              message={`区间最低点 ${seriesMin.toFixed(2)}%${seriesMin <= -8 ? '，超过单笔止损参考 -8%，需关注回撤控制' : '，处于可接受范围'}。`} />
          ) : null}
          <Row gutter={16}>
            <Col span={6}>
              <Statistic title="当日组合盈亏" value={cur?.pnl_pct ?? '—'} suffix="%"
                valueStyle={{ color: (cur?.pnl_pct ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }} />
            </Col>
            <Col span={6}><Statistic title="浮盈亏金额" value={cur?.pnl_amount ?? 0} precision={0} /></Col>
            <Col span={6}><Statistic title="当前市值" value={cur?.market_value ?? 0} precision={0} /></Col>
            <Col span={6}>
              <Statistic title="区间累计" value={`${seriesSum >= 0 ? '+' : ''}${seriesSum.toFixed(2)}%`}
                valueStyle={{ color: seriesSum >= 0 ? 'var(--up)' : 'var(--down)' }} />
              <Text type="secondary" style={{ fontSize: 12 }}>峰值 {seriesMax.toFixed(2)}% / 谷底 {seriesMin.toFixed(2)}%</Text>
            </Col>
          </Row>
          {option ? <ChartCard title={`组合盈亏曲线（近 ${days} 日）`} option={option} height={240} /> : null}
          <Row gutter={16}>
            <Col span={12}>{renderTop('贡献领先（top 3）', data.top_gainers ?? [])}</Col>
            <Col span={12}>{renderTop('贡献拖累（top 3）', data.top_losers ?? [])}</Col>
          </Row>
          <Text type="secondary" style={{ fontSize: 12 }}>
            口径：组合盈亏 = Σ(最新收盘 − 每股成本) × 股数 / 总成本 × 100；缺行情日当日不计入（不伪造 0）。
            当前数据来自当前持仓视角，切换右上角时间范围查看历史区间表现，曲线与 top 榜随范围联动。
          </Text>
          <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
            无持仓或行情未刷新时不生成总结（诚实降级，不伪造 0）；数据不足的字段统一显示「—」。
          </Text>
          <Alert type="info" showIcon
            message="组合总结仅为展示参考，不构成买卖建议；仓位与风控规则由全局基线与个人偏好档案约束，调整需人工在「个人交易偏好」页完成。" />
        </Space>
      )}
    </Card>
  )
}

/** 交易复盘页（Phase 4 黑盒规范） */
export function ReviewsPage() {
  return (
    <div>
      <Alert type="info" showIcon style={{ marginBottom: 12 }}
        message="交易复盘页汇聚 4 类看板：组合复盘（归因曲线/贡献瀑布/周期复利）· 每日复盘报告（人工卖出自动触发）· 选股效果验证（T+N 追踪胜率）· 策略闭环建议（人工审核后生效）。底部为每日组合总结。所有 Agent 优化建议必须经人工审核确认后生效。" />
      <Tabs items={[
        { key: 'attr', label: '组合复盘', children: <PortfolioAttributionView /> },
        { key: 'reviews', label: '每日复盘报告', children: <ReviewsList /> },
        { key: 'track', label: '选股效果验证', children: <TrackVerify /> },
        { key: 'sug', label: '策略闭环建议', children: <Suggestions /> },
      ]} />
      <DailySummary />
    </div>
  )
}

export default ReviewsPage
