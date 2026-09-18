import { useEffect, useRef, useState } from 'react'
import {
  Alert, App, Button, Card, Col, DatePicker, Descriptions, Drawer, Empty, Form, Input,
  InputNumber, Modal, Row, Segmented, Select, Space, Statistic, Table, Tag, Tabs, Tooltip, Typography,
} from 'antd'
import { InboxOutlined, PauseOutlined, PlayCircleOutlined, PlusOutlined, RadarChartOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import dayjs, { type Dayjs } from 'dayjs'
import {
  archivePaperAccount, collectPaperContext, createPaperAccount, monitorPaper, paperAccounts, paperAlerts,
  paperContexts, paperExecutions, paperSummary, paperWebEvidence, refreshPaperQuotes,
  runPaper, setPaperAccountStatus, type PaperAlert, type PaperContext, type PaperContextRequest,
  type PaperAccount, type PaperExecution, type PaperMode, type PaperPosition, type PaperQuoteState, type PaperToolTrace, type PaperWebEvidence,
} from '@/api/paper'
import { KlineChart } from '@/components/charts/KlineChart'

const { Text, Paragraph, Link } = Typography
const numeric = (value: unknown) => value == null || value === '' ? NaN : Number(value)
const money = (value: unknown) => Number.isFinite(numeric(value))
  ? `¥${numeric(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'
const number = (value: unknown) => Number.isFinite(numeric(value)) ? numeric(value).toLocaleString('zh-CN') : '—'
const pct = (value: unknown) => Number.isFinite(numeric(value))
  ? `${numeric(value) >= 0 ? '+' : ''}${numeric(value).toFixed(2)}%` : '—'
const labels: Record<string, string> = {
  buy: '买入', sell: '卖出', hold: '继续持有', reduce: '减仓', exit: '清仓', add: '加仓',
  filled: '已成交', rejected: '已拒绝', pending: '处理中', ok: '已获取', error: '获取失败',
  unavailable: '行情缺失', partial: '部分缺失', partial_or_unavailable: '行情不完整',
  stale: '行情已过期', no_data: '暂无数据', empty: '暂无数据', missing: '资料缺失',
  frozen: '已冻结', ready: '已就绪', active: '运行中', paused: '已暂停', archived: '已归档',
  live_paper: '实时模拟', historical_replay: '历史回放', research: '研究取证',
  info: '常规关注', warning: '风险提醒', critical: '紧急风险',
  tencent: '腾讯行情', eastmoney_batch: '东财批量行情', eastmoney: '东方财富',
  spot_quote: '单股行情', snapshot: '行情快照', universe: '全市场行情', none: '暂无来源',
  paper: 'AI模拟', paper_monitor: '模拟持仓监控', paper_sell: '模拟卖出决策',
  paper_execution: '模拟执行', paper_quote: '模拟行情', paper_risk: '模拟风控',
  get_quote: '实时行情', get_daily_kline: '日K线', get_news: '新闻公告', get_financial: '财务指标',
  get_fund_flow: '资金流向', search_knowledge: '知识库检索', get_sector_regime: '板块环境',
  get_factor_calibration: '因子校准', get_distribution_phase: '派发阶段', get_capital_view: '资本视图',
  get_position_risk: '持仓风险', get_hot_money_context: '游资背景', historical_snapshot: '历史冻结快照',
  'paper_web.search': '联网检索', skipped: '暂缓处理',
  not_tradeable: '未通过可建仓验证', already_holding: '已有模拟持仓',
  plan_or_price_missing: '建仓计划或价格缺失', future_data: '资料晚于决策时点',
  cash_or_plan_position_too_small: '资金或计划仓位不足一手', no_position: '没有对应模拟持仓',
  t_plus_one_or_no_lot: '当日买入不可卖出，或可卖数量不足一手',
  suspended: '标的停牌', price_missing: '价格缺失', limit_up: '涨停无法买入', limit_down: '跌停无法卖出',
  llm_unavailable: 'AI研判暂不可用',
}
const label = (value: unknown, fallback = '暂未记录') => {
  if (value == null || value === '') return fallback
  const text = String(value)
  return labels[text] ?? (/[\u3400-\u9fff]/.test(text) ? text : fallback)
}
const isReferenceQuote = (quote?: PaperQuoteState) => quote?.quote_reference_only === true || quote?.quote_status === 'stale'
const quoteSource = (source?: string) => source ? labels[source] ?? source : '暂无来源'
const valuationMoney = (value: unknown) => Number.isFinite(numeric(value)) ? money(value) : '暂无数据'
const fieldLabels: Record<string, string> = {
  stock_code: '股票代码', code: '股票代码', stock_name: '股票名称', name: '名称',
  trade_date: '交易日期', mode: '研究模式', fact_as_of: '事实时点', created_at: '记录时间',
  price: '价格', close: '收盘价', open: '开盘价', high: '最高价', low: '最低价',
  change_pct: '涨跌幅（%）', volume: '成交量', amount: '成交额', date: '日期', time: '行情时间',
  source: '来源', status: '状态', note: '数据说明', error: '缺失原因', rows: '数据记录',
  news: '新闻公告', title: '标题', content: '内容', published_at: '发布时间', url: '来源链接',
  report_date: '报告期', roe: '净资产收益率', revenue_yoy: '营收同比', profit_yoy: '利润同比',
  debt_ratio: '资产负债率', main_net_inflow: '主力净流入', main_net_pct: '主力净流入占比',
  super_large_net: '超大单净流入', large_net: '大单净流入', medium_net: '中单净流入', small_net: '小单净流入',
  hits: '知识参考', regime: '板块环境', period: '观察周期', text: '分析摘要',
  distribution_phase: '派发阶段', phase_label: '阶段', confidence: '信心度', six_dim: '维度证据',
  capital_view: '资本视图', aggregate: '聚合事实', context: '背景分析', missing_data: '缺失资料',
  web_evidence: '联网证据', historical_policy: '回放口径', action: '建议动作', reason: '依据',
  message: '研判内容', severity: '风险程度', alert_type: '提醒类型', decision: '卖出决策', signal: '监控信号',
}
const safeUrl = (value: unknown) => {
  try { const url = new URL(String(value)); return ['http:', 'https:'].includes(url.protocol) ? url.href : undefined } catch { return undefined }
}
const modeTag = (mode: unknown) => <Tag color={mode === 'historical_replay' ? 'gold' : 'blue'}>{label(mode, '模式未记录')}</Tag>
const statusTag = (status: unknown) => <Tag color={['ok', 'ready', 'filled'].includes(String(status)) ? 'green' : 'default'}>{label(status)}</Tag>
const timeText = (value: unknown) => {
  if (!value) return '—'
  const raw = String(value)
  if (/^\d{10}$/.test(raw)) return dayjs(Number(raw) * 1000).format('YYYY-MM-DD HH:mm:ss')
  return raw
}

const record = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value)
  ? value as Record<string, unknown> : {}
const planOf = (row: PaperPosition) => record(record(row.metadata).control_plan)
const lifecycleOf = (row: PaperPosition) => record(record(row.metadata).lifecycle)
const lastControlOf = (row: PaperPosition) => record(record(row.metadata).last_control)
const planPct = (value: unknown) => Number.isFinite(numeric(value) * 100) ? (numeric(value) * 100 >= 0 ? '+' : '') + (numeric(value) * 100).toFixed(0) + '%' : '—'
const phaseLabel = (value: unknown) => ({
  opened: '建仓后持有', added: '已加仓', trailing_protection: '止盈保护',
  hard_stop_loss: '硬止损触发', main_take_profit: '主止盈触发', trailing_stop: '移动止损触发',
}[String(value)] ?? (value ? String(value) : '未记录'))
const controlMetrics = (row: PaperPosition) => {
  const plan = planOf(row)
  const lifecycle = lifecycleOf(row)
  const lastControl = lastControlOf(row)
  const hardStop = numeric(plan.stop_loss) || numeric(row.stop_loss)
  const protectedStop = numeric(lifecycle.protected_stop_loss)
  const activeStop = protectedStop > 0 ? Math.max(hardStop, protectedStop) : hardStop
  const price = numeric(row.current_price)
  const distancePct = Number.isFinite(price) && activeStop > 0 ? (price / activeStop - 1) * 100 : NaN
  return { plan, lifecycle, lastControl, hardStop, protectedStop, activeStop, price, distancePct }
}
const controlDetails = (row: PaperPosition) => {
  const { plan, lifecycle, lastControl, hardStop, protectedStop, activeStop, price, distancePct } = controlMetrics(row)
  if (!Object.keys(plan).length && !hardStop) return { '盈亏控制计划': '暂无计划' }
  return {
    '建仓配置': planPct(plan.initial_allocation_pct) + '（首仓）',
    '加仓条件': '盈利达到 ' + planPct(plan.add_trigger_pct) + '，加仓 ' + planPct(plan.add_allocation_pct) + '，最高总配置 ' + planPct(plan.max_allocation_pct),
    '生命周期阶段': phaseLabel(lifecycle.phase),
    '硬止损': money(hardStop) + '（' + planPct(plan.stop_loss_pct) + '）',
    '当前保护价': money(activeStop) + (protectedStop > 0 ? '（止盈后上移）' : ''),
    '第一止盈': money(plan.first_take_profit) + '（' + planPct(plan.first_take_profit_pct) + '）',
    '主止盈': money(plan.main_take_profit) + '（' + planPct(plan.main_take_profit_pct) + '）',
    '移动止损': planPct(plan.trailing_stop_pct),
    '当前距离保护价': Number.isFinite(distancePct) ? (distancePct >= 0 ? '+' : '') + distancePct.toFixed(2) + '%' : '暂无价格',
    '当前控制动作': label(lastControl.action, '继续持有') + ' · ' + label(lastControl.reason, '按计划观察'),
    '控制事实价格': Number.isFinite(price) ? money(price) : '暂无数据',
  }
}

const trendColor = (value: number) => value >= 0 ? '#ef4444' : '#10b981'
const trendTag = (value: number) => !Number.isFinite(value) ? 'default' : value >= 0 ? 'red' : 'green'

function PositionCard({ pos, onKline, onDetail }: { pos: PaperPosition; onKline: (row: PaperPosition) => void; onDetail: (row: PaperPosition) => void }) {
  const { lifecycle, activeStop, distancePct } = controlMetrics(pos)
  const price = numeric(pos.current_price)
  const avg = numeric(pos.avg_price)
  const rawChange = numeric((pos as PaperPosition & { change_pct?: number }).change_pct)
  const changePct = Number.isFinite(rawChange) ? rawChange : Number.isFinite(price) && avg > 0 ? (price / avg - 1) * 100 : NaN
  const reference = isReferenceQuote(pos)
  const tone = Number.isFinite(changePct) ? trendColor(changePct) : Number.isFinite(numeric(pos.pnl_pct)) ? trendColor(numeric(pos.pnl_pct)) : undefined
  const changeTag = trendTag(changePct)
  const pnlTag = trendTag(numeric(pos.pnl_pct))
  return <Card size="small" style={{ height: '100%' }} styles={{ body: { minHeight: 208 } }}>
    <Space orientation="vertical" size={12} style={{ width: '100%' }}>
      <div><Space size={6} wrap><Text strong style={{ fontSize: 16 }}>{pos.stock_code}</Text><Text strong style={{ fontSize: 16 }}>{pos.stock_name ?? pos.name ?? '—'}</Text>{reference ? <Tag color="orange">参考行情</Tag> : null}</Space><div><Text type="secondary" style={{ fontSize: 12 }}>{quoteSource(pos.quote_source)} · {label(pos.quote_status)} · 建仓 {timeText(pos.opened_trade_date)}</Text></div></div>
      <div><Text type="secondary" style={{ fontSize: 12 }}>{reference ? '最后价格' : '现价'}</Text><div style={{ fontSize: 26, fontWeight: 600, lineHeight: 1.25, color: tone }}>{valuationMoney(pos.current_price)}</div><Space size={4} wrap style={{ marginTop: 4 }}><Tag color={changeTag}>涨跌 {pct(changePct)}</Tag><Tag color={pnlTag}>浮动盈亏 {valuationMoney(pos.pnl_amount)}（{pct(pos.pnl_pct)}）</Tag></Space></div>
      <Space size={[12, 4]} wrap>
        <Text type="secondary">持仓 / 可卖：{number(pos.shares)} / {number(pos.available_shares)}</Text>
        <Text type="secondary">成本价：{money(pos.avg_price)}</Text>
        <Text type="secondary">{reference ? '估算市值' : '市值'}：{valuationMoney(pos.market_value)}</Text>
        <Text type="secondary">阶段：{phaseLabel(lifecycle.phase)}</Text>
        <Text type="secondary">保护价：{money(activeStop)}（{Number.isFinite(distancePct) ? `${distancePct >= 0 ? '+' : ''}${distancePct.toFixed(2)}%` : '暂无价格'}）</Text>
      </Space>
      <Space size={8} wrap><Button size="small" type="link" onClick={() => onKline(pos)}>K线</Button><Button size="small" onClick={() => onDetail(pos)}>详情</Button></Space>
    </Space>
  </Card>
}

function FactDetails({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value == null || value === '') return <Text type="secondary">—</Text>
  if (typeof value === 'boolean') return <span>{value ? '是' : '否'}</span>
  if (typeof value !== 'object') {
    const text = String(value)
    return <Text style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{labels[text] ?? text}</Text>
  }
  if (depth > 3) return <Text type="secondary">已保存详细证据</Text>
  if (Array.isArray(value)) return value.length ? <Space orientation="vertical" style={{ width: '100%' }} size={6}>
    {value.slice(0, 8).map((item, index) => <div key={index}><FactDetails value={item} depth={depth + 1} /></div>)}
    {value.length > 8 ? <Text type="secondary">共 {value.length} 条，展示最近取出的前 8 条</Text> : null}
  </Space> : <Text type="secondary">暂无记录</Text>
  return <Descriptions size="small" column={{ xs: 1, sm: 2, md: 3 }} styles={{ label: { width: 120 } }} items={Object.entries(value).map(([key, item], index) => ({
    key: `${key}-${index}`, label: fieldLabels[key] ?? labels[key] ?? (/[\u3400-\u9fff]/.test(key) ? key : '其他字段'),
    children: key === 'url' && safeUrl(item) ? <Link href={safeUrl(item)} target="_blank" rel="noopener noreferrer">查看原文</Link> : <FactDetails value={item} depth={depth + 1} />,
  }))} />
}

function ContextDetails({ context }: { context: PaperContext }) {
  const tools = context.tool_trace ?? []
  return <div style={{ padding: '8px 12px', overflowWrap: 'anywhere', background: 'var(--bg-input)' }}>
    <Descriptions size="small" column={{ xs: 1, sm: 2, md: 3 }} styles={{ label: { width: 120 } }} items={[
      { label: '事实时点', children: timeText(context.facts?.fact_as_of) },
      { label: '来源证据', children: `${context.source_refs?.length ?? 0} 条` },
    ]} />
    <Table size="small" rowKey={(_, index) => String(index)} pagination={false} dataSource={tools} scroll={{ x: 760 }} columns={[
      { title: '工具', dataIndex: 'tool', width: 110, render: (v: unknown) => label(v, '补充数据工具') },
      { title: '结果', dataIndex: 'status', width: 90, render: statusTag },
      { title: '资料摘要', width: 320, render: (_: unknown, row: PaperToolTrace) => {
        const fact = (context.facts?.[row.tool ?? ''] ?? row.result) as Record<string, unknown> | undefined
        const values = fact && Object.values(fact).find(Array.isArray)
        return row.error || fact?.error ? label(row.error || fact?.error, '数据请求失败')
          : Array.isArray(values) ? <Tooltip title={String(fact?.note || '证据已记录')}>{`${values.length} 条`}</Tooltip> : label(fact?.note, '证据已记录')
      } },
    ]} expandable={{ expandedRowRender: (row) => <FactDetails value={context.facts?.[row.tool ?? ''] ?? row.result ?? row.error} /> }} locale={{ emptyText: '没有工具调用记录' }} />
    {context.stage === 'monitor' ? <Card size="small" title="监控结论 / 卖出研判"><FactDetails value={{ '监控结论': context.facts?.monitor, '卖出研判': context.facts?.sell }} /></Card> : null}
  </div>
}

interface ResearchForm {
  stock_code: string
  trade_date: Dayjs
  mode: PaperMode
  web_query?: string
  web_urls?: string
  historical_context_id?: number
}

export function PaperTradingPanel() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [selectedId, setSelectedId] = useState<number>()
  const [accountView, setAccountView] = useState<'current' | 'archived'>('current')
  const [archiveTarget, setArchiveTarget] = useState<PaperAccount>()
  const [createOpen, setCreateOpen] = useState(false)
  const [researchOpen, setResearchOpen] = useState(false)
  const [tab, setTab] = useState('positions')
  const [detailPosition, setDetailPosition] = useState<PaperPosition | null>(null)
  const [klineFocus, setKlineFocus] = useState(false)
  const klineRef = useRef<HTMLDivElement>(null)
  const [focusedContextId, setFocusedContextId] = useState<number>()
  const [form] = Form.useForm<{ name: string; initial_cash: number }>()
  const [researchForm] = Form.useForm<ResearchForm>()
  const researchMode = Form.useWatch('mode', researchForm) ?? 'live_paper'
  useEffect(() => {
    if (!klineFocus || !detailPosition) return
    const timer = setTimeout(() => klineRef.current?.scrollIntoView({ block: 'start' }), 120)
    return () => clearTimeout(timer)
  }, [klineFocus, detailPosition])
  const accountsQuery = useQuery({ queryKey: ['paper-accounts', accountView], queryFn: () => paperAccounts(accountView === 'archived' ? { status: 'archived' } : undefined), refetchInterval: 30_000 })
  const accounts = accountsQuery.data ?? []
  const accountId = accounts.some((row) => row.id === selectedId) ? selectedId : accounts[0]?.id
  const account = accounts.find((row) => row.id === accountId)
  const archived = account?.status === 'archived'
  const summaryQuery = useQuery({ queryKey: ['paper-summary', accountId], queryFn: () => paperSummary(accountId!), enabled: accountId != null, refetchInterval: 30_000 })
  const executionsQuery = useQuery({ queryKey: ['paper-executions', accountId], queryFn: () => paperExecutions(accountId!), enabled: accountId != null && tab === 'executions', refetchInterval: 30_000 })
  const contextsQuery = useQuery({ queryKey: ['paper-contexts', accountId], queryFn: () => paperContexts(accountId!), enabled: accountId != null && (tab === 'contexts' || researchOpen), refetchInterval: 30_000 })
  const evidenceQuery = useQuery({ queryKey: ['paper-web-evidence', accountId], queryFn: () => paperWebEvidence(accountId!), enabled: accountId != null && tab === 'evidence', refetchInterval: 30_000 })
  const alertsQuery = useQuery({ queryKey: ['paper-alerts', accountId], queryFn: () => paperAlerts(accountId!), enabled: accountId != null && tab === 'alerts', refetchInterval: 30_000 })
  const refresh = () => {
    for (const key of ['paper-accounts', 'paper-summary', 'paper-positions', 'paper-executions', 'paper-contexts', 'paper-web-evidence', 'paper-alerts']) qc.invalidateQueries({ queryKey: [key] })
  }
  const onError = (error: Error) => message.error(error.message || '操作失败，请稍后重试')
  const create = useMutation({ mutationFn: createPaperAccount, onError, onSuccess: (created) => {
    setCreateOpen(false); form.resetFields(); setAccountView('current'); setSelectedId(created.id); refresh(); message.success('模拟账户已创建')
  } })
  const status = useMutation({ mutationFn: ({ id, next }: { id: number; next: 'active' | 'paused' }) => setPaperAccountStatus(id, next), onSuccess: refresh, onError })
  const archive = useMutation({ mutationFn: (id: number) => archivePaperAccount(id), onError, onSuccess: (result) => {
    qc.setQueryData<PaperAccount[]>(['paper-accounts', 'current'], (rows) => rows?.filter((row) => row.id !== result.id))
    setArchiveTarget(undefined); setSelectedId(undefined); setFocusedContextId(undefined); setResearchOpen(false); refresh()
    message.success('模拟账户已暂停并归档，历史记录已保留')
  } })
  const run = useMutation({ mutationFn: (id: number) => runPaper(id), onError, onSuccess: (result) => {
    refresh()
    message.success(Number.isFinite(numeric(result.filled)) ? `模拟运行完成：成交 ${number(result.filled)} 笔，拒绝 ${number(result.rejected)} 笔` : '模拟运行任务已提交')
  } })
  const quotes = useMutation({ mutationFn: refreshPaperQuotes, onError, onSuccess: (result) => {
    refresh()
    if (result.quote_errors?.length || (result.quote_status && result.quote_status !== 'ok')) message.warning('行情刷新部分失败，请查看行情状态')
    else message.success(`行情刷新完成：${result.positions?.length ?? 0} 条持仓`)
  } })
  const monitor = useMutation({ mutationFn: (id: number) => monitorPaper(id), onError, onSuccess: (result) => {
    refresh(); setTab('alerts')
    const rows = Array.isArray(result.results) ? result.results as Record<string, unknown>[] : []
    const failed = rows.filter((row) => row.status === 'error' || row.status === 'skipped').length
    if (failed) message.warning(`模拟巡检完成，${failed} 只持仓有未完成项目，请查看告警`)
    else message.success(`模拟巡检完成：${number(result.monitored)} 只持仓`)
  } })
  const research = useMutation({ mutationFn: ({ id, body }: { id: number; body: PaperContextRequest }) => collectPaperContext(id, body), onError, onSuccess: () => {
    setResearchOpen(false); refresh(); setTab('contexts'); message.success('研究上下文已保存')
  } })
  const summary = summaryQuery.data
  const positions = summary?.positions ?? []
  const referenceOnly = isReferenceQuote(summary)
  const queryError = [accountsQuery, summaryQuery, executionsQuery, contextsQuery, evidenceQuery, alertsQuery].find((query) => query.isError)?.error
  const openDetail = (row: PaperPosition, focusKline = false) => { setKlineFocus(focusKline); setDetailPosition(row) }
  const closeDetail = () => { setDetailPosition(null); setKlineFocus(false) }
  const executionColumns = [
    { title: '日期 / 事实时点', dataIndex: 'trade_date', width: 150, render: (v: unknown, row: PaperExecution) => <Space orientation="vertical" size={0}><span>{timeText(v)}</span><Text type="secondary">{timeText(row.fact_as_of)}</Text>{modeTag(row.mode ?? row.metadata?.mode ?? row.metadata_json?.mode)}</Space> },
    { title: '标的', key: 'stock', width: 110, render: (_: unknown, row: PaperExecution) => `${row.stock_code ?? '—'} ${row.stock_name ?? ''}` },
    { title: '方向', dataIndex: 'side', width: 80, render: (v: unknown) => label(v) },
    { title: '状态', dataIndex: 'status', width: 110, render: (v: unknown, row: PaperExecution) => <Space orientation="vertical" size={0}>{statusTag(v)}{v !== 'filled' && row.reject_reason ? <Text type="secondary">{label(row.reject_reason, '成交约束未通过')}</Text> : null}</Space> },
    { title: '数量 / 成交价', key: 'fill', width: 140, render: (_: unknown, row: PaperExecution) => `${number(row.shares)} / ${money(row.executed_price)}` },
    { title: '费用', key: 'fees', width: 100, render: (_: unknown, row: PaperExecution) => money(Number(row.commission ?? 0) + Number(row.stamp_tax ?? 0) + Number(row.transfer_fee ?? 0)) },
  ]
  const contextColumns = [
    { title: '记录', dataIndex: 'id', width: 80, render: (value: number) => `#${value}` },
    { title: '交易日期', dataIndex: 'trade_date', width: 110 }, { title: '标的', dataIndex: 'stock_code', width: 100 },
    { title: '研究模式', dataIndex: 'mode', width: 110, render: modeTag },
    { title: '工具结果', width: 140, render: (_: unknown, row: PaperContext) => { const trace = row.tool_trace ?? []; return `已完成 ${trace.filter((item) => item.status === 'ok').length} / ${trace.length} 项` } },
    { title: '联网来源', width: 90, render: (_: unknown, row: PaperContext) => `${row.source_refs?.filter((ref) => ref.type === 'web').length ?? 0} 条` },
    { title: '记录时间', dataIndex: 'created_at', width: 150, render: timeText },
  ]
  const evidenceColumns = [
    { title: '标的 / 日期', render: (_: unknown, row: PaperWebEvidence) => <Space orientation="vertical" size={0}><span>{row.stock_code || '账户研究'}</span><Text type="secondary">{row.trade_date}</Text></Space> },
    { title: '联网证据', width: 320, render: (_: unknown, row: PaperWebEvidence) => <Space orientation="vertical" size={0} style={{ width: '100%' }}>{safeUrl(row.url) ? <Link href={safeUrl(row.url)} target="_blank" rel="noopener noreferrer">{row.title || row.domain || '查看来源'}</Link> : <Text>{row.title || '来源未记录'}</Text>}<Text type="secondary">{row.domain}</Text></Space> },
    { title: '采集状态', dataIndex: 'status', render: statusTag },
    { title: '发布时间 / 获取时间', render: (_: unknown, row: PaperWebEvidence) => <Space orientation="vertical" size={0}><span>{timeText(row.published_at)}</span><Text type="secondary">{timeText(row.fetched_at)}</Text></Space> },
  ]
  const alertColumns = [
    { title: '日期 / 标的', render: (_: unknown, row: PaperAlert) => <Space orientation="vertical" size={0}><span>{row.trade_date}</span><Text strong>{row.stock_code}</Text></Space> },
    { title: '风险级别', dataIndex: 'severity', render: (v: unknown) => <Tag color={v === 'critical' ? 'red' : v === 'warning' ? 'orange' : 'default'}>{label(v)}</Tag> },
    { title: '提醒', width: 360, render: (_: unknown, row: PaperAlert) => <Space orientation="vertical" size={0}><Text strong>{label(row.alert_type, '模拟监控提醒')}</Text><Text>{label(row.message, '暂无详细说明')}</Text></Space> },
    { title: '来源', dataIndex: 'source', render: (v: unknown) => label(v, '模拟巡检') },
    { title: '研究记录', render: (_: unknown, row: PaperAlert) => row.context_id ? <Button type="link" size="small" onClick={() => { setFocusedContextId(row.context_id); setTab('contexts') }}>记录 #{row.context_id}</Button> : '—' },
  ]
  const openResearch = () => {
    researchForm.resetFields()
    researchForm.setFieldsValue({ stock_code: positions[0]?.stock_code ?? '', mode: 'live_paper', trade_date: dayjs(), web_query: '', web_urls: '' })
    setResearchOpen(true)
  }

  return <Card size="small" title={<Space wrap><span>AI模拟账户</span><Tag color="blue">AI模拟</Tag><Tag>真实资产独立统计</Tag></Space>} style={{ marginBottom: 12 }}>
    <Space wrap style={{ marginBottom: 12, width: '100%' }}>
      <Segmented value={accountView} options={[{ value: 'current', label: '当前账户' }, { value: 'archived', label: '已归档', icon: <InboxOutlined /> }]} onChange={(value) => { setAccountView(value as 'current' | 'archived'); setSelectedId(undefined); setFocusedContextId(undefined); setResearchOpen(false) }} />
      <Select style={{ width: 220, maxWidth: '100%' }} placeholder="选择模拟账户" value={accountId} onChange={(id) => { setSelectedId(id); setFocusedContextId(undefined) }} loading={accountsQuery.isLoading} options={accounts.map((row) => ({ value: row.id, label: `${row.name ?? `模拟账户 #${row.id}`} · ${label(row.status)}` }))} />
      <Button icon={<PlusOutlined />} onClick={() => { form.setFieldsValue({ name: 'AI模拟账户', initial_cash: 100_000 }); setCreateOpen(true) }}>新建账户</Button>
      {account ? <>
        <Button icon={account.status === 'paused' ? <PlayCircleOutlined /> : <PauseOutlined />} loading={status.isPending} disabled={archived || archive.isPending} onClick={() => status.mutate({ id: account.id, next: account.status === 'paused' ? 'active' : 'paused' })}>{archived ? '已停止运行' : account.status === 'paused' ? '继续运行' : '暂停运行'}</Button>
        <Button icon={<ReloadOutlined />} loading={quotes.isPending} disabled={archived || archive.isPending} onClick={() => quotes.mutate(account.id)}>刷新行情</Button>
        <Button icon={<SearchOutlined />} loading={research.isPending} disabled={archived || archive.isPending} onClick={openResearch}>研究取证</Button>
        <Button icon={<RadarChartOutlined />} loading={monitor.isPending} disabled={account.status !== 'active' || archive.isPending} onClick={() => monitor.mutate(account.id)}>模拟巡检</Button>
        <Button type="primary" icon={<PlayCircleOutlined />} loading={run.isPending} disabled={account.status !== 'active' || archive.isPending} onClick={() => run.mutate(account.id)}>立即补跑</Button>
        {!archived ? <Button danger icon={<InboxOutlined />} disabled={status.isPending || run.isPending || monitor.isPending || quotes.isPending || research.isPending} loading={archive.isPending} onClick={() => setArchiveTarget(account)}>归档账户</Button> : null}
      </> : null}
    </Space>
    {queryError ? <Alert type="error" showIcon title="模拟数据加载失败" description={queryError.message} action={<Button size="small" icon={<ReloadOutlined />} onClick={refresh}>重试</Button>} style={{ marginBottom: 10 }} /> : null}
    {account ? <Alert type="info" showIcon message={archived ? '账户已归档，自动监控和模拟执行已停止；历史记录已保留。' : account.status === 'active' ? '自动运行已开启：后端服务在线时，交易日盘中每隔设定周期自动监控、估值和模拟执行；“立即补跑”仅用于现在手动触发一次。' : '自动运行已暂停：点击“继续运行”后恢复交易日盘中自动监控和模拟执行。'} style={{ marginBottom: 10 }} /> : null}
    {!account ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={accountView === 'archived' ? '暂无已归档账户' : '暂无模拟账户'} /> : <>
      <Row gutter={[8, 12]} style={{ marginBottom: 12 }}>
        <Col xs={12} sm={6}><Statistic title="模拟现金" value={money(summary?.cash)} styles={{ content: { fontSize: 20 } }} /></Col>
        <Col xs={12} sm={6}><Statistic title={referenceOnly ? '估算模拟市值' : '模拟市值'} value={valuationMoney(summary?.market_value)} styles={{ content: { fontSize: 20, overflowWrap: 'anywhere' } }} /></Col>
        <Col xs={12} sm={6}><Statistic title={referenceOnly ? '估算模拟总资产' : '模拟总资产'} value={valuationMoney(summary?.equity)} styles={{ content: { fontSize: 20, overflowWrap: 'anywhere' } }} /></Col>
        <Col xs={12} sm={6}><Statistic title={referenceOnly ? '估算累计盈亏' : '累计盈亏'} value={valuationMoney(summary?.pnl_amount)} styles={{ content: { fontSize: 20, overflowWrap: 'anywhere' } }} /><Text type="secondary">{pct(summary?.pnl_pct)}</Text></Col>
      </Row>
      <Descriptions size="small" column={{ xs: 1, sm: 3 }} items={[
        { label: '初始资金', children: money(summary?.initial_cash ?? account.initial_cash) },
        { label: '行情事实时间', children: timeText(summary?.valuation_as_of || summary?.fact_as_of || summary?.quote_time) },
        { label: '行情来源', children: <Space wrap style={{ overflowWrap: 'anywhere' }}><span>{quoteSource(summary?.quote_source)}</span>{statusTag(summary?.quote_status)}</Space> },
      ]} />
      {referenceOnly ? <Alert type="warning" showIcon title={summary?.quote_notice || '行情已过期，仅供参考'} description="市值和盈亏按最后一次有效价格估算。" style={{ marginBottom: 10 }} /> : null}
      {summary?.quote_status && !['ok', 'stale'].includes(summary.quote_status) ? <Alert type="warning" showIcon title="模拟估值暂不完整" description={(summary.quote_errors ?? []).map((item) => label(item, '行情请求失败')).join('；') || '部分持仓没有历史有效行情，合计市值和盈亏暂无数据。'} style={{ marginBottom: 10 }} /> : null}
      <Tabs activeKey={tab} onChange={setTab} items={[
        { key: 'positions', label: `模拟持仓（${positions.length}）`, children: summaryQuery.isLoading && !positions.length ? (
          <Row gutter={[12, 12]}>{[0, 1, 2].map((key) => <Col key={key} xs={24} md={12} xl={8}><Card size="small" loading /></Col>)}</Row>
        ) : positions.length ? (
          <Row gutter={[12, 12]}>{positions.map((pos) => (
            <Col key={pos.id} xs={24} md={12} xl={8}><PositionCard pos={pos} onKline={(row) => openDetail(row, true)} onDetail={(row) => openDetail(row)} /></Col>
          ))}</Row>
        ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无模拟持仓" /> },
        { key: 'executions', label: '模拟流水', children: <Table size="small" rowKey="id" loading={executionsQuery.isLoading} columns={executionColumns} dataSource={executionsQuery.data ?? []} pagination={{ pageSize: 8 }} scroll={{ x: 1000 }} locale={{ emptyText: '暂无模拟成交或拒绝记录' }} /> },
        { key: 'contexts', label: '研究上下文', children: <>
          {focusedContextId != null ? <Space style={{ marginBottom: 8 }}><Text type="secondary">当前查看记录 #{focusedContextId}</Text><Button size="small" onClick={() => setFocusedContextId(undefined)}>查看全部</Button></Space> : null}
          <Table size="small" rowKey="id" loading={contextsQuery.isLoading} columns={contextColumns} dataSource={(contextsQuery.data ?? []).filter((row) => focusedContextId == null || row.id === focusedContextId)} pagination={{ pageSize: 8 }} scroll={{ x: 880 }} expandable={{ expandedRowRender: (row) => <ContextDetails context={row} />, ...(focusedContextId != null ? { expandedRowKeys: [focusedContextId] } : {}) }} locale={{ emptyText: focusedContextId == null ? '暂无模拟研究记录' : '此记录不在最近研究列表中' }} />
        </> },
        { key: 'evidence', label: '联网证据', children: <Table size="small" rowKey="id" loading={evidenceQuery.isLoading} columns={evidenceColumns} dataSource={evidenceQuery.data ?? []} pagination={{ pageSize: 8 }} scroll={{ x: 760 }} expandable={{ expandedRowRender: (row) => <div style={{ overflowWrap: 'anywhere' }}><Paragraph>{row.excerpt || label(row.error, '暂无可读摘要')}</Paragraph><Descriptions size="small" column={1} items={[{ label: '事实时点', children: timeText(row.fact_as_of) }, { label: '内容指纹', children: row.content_hash || '未生成' }]} /></div> }} locale={{ emptyText: '暂无联网证据' }} /> },
        { key: 'alerts', label: '模拟告警', children: <Table size="small" rowKey="id" loading={alertsQuery.isLoading} columns={alertColumns} dataSource={alertsQuery.data ?? []} pagination={{ pageSize: 8 }} scroll={{ x: 800 }} locale={{ emptyText: '暂无模拟告警' }} /> },
      ]} />
    </>}
    <Modal title="归档模拟账户" open={archiveTarget != null} okText="暂停并归档" cancelText="取消" okButtonProps={{ danger: true }} confirmLoading={archive.isPending} closable={!archive.isPending} maskClosable={!archive.isPending} cancelButtonProps={{ disabled: archive.isPending }} onCancel={() => setArchiveTarget(undefined)} onOk={() => { if (archiveTarget) archive.mutate(archiveTarget.id) }}>
      <Paragraph>确定归档“{archiveTarget?.name || `模拟账户 #${archiveTarget?.id}`}”？</Paragraph>
      <Paragraph>归档前会强制暂停账户，随后从普通账户列表隐藏。归档后不能运行、补跑或自动监控。</Paragraph>
      <Paragraph>账户、持仓、模拟流水、复盘和审计记录全部保留，可在“已归档”中查看历史记录。</Paragraph>
    </Modal>
    <Modal title="新建 AI 模拟账户" open={createOpen} okText="创建" cancelText="取消" confirmLoading={create.isPending} onCancel={() => setCreateOpen(false)} onOk={() => form.submit()}>
      <Form form={form} layout="vertical" onFinish={(values) => create.mutate(values)}>
        <Form.Item label="账户名称" name="name" rules={[{ required: true, message: '请输入账户名称' }]}><Input maxLength={64} /></Form.Item>
        <Form.Item label="初始资金（元）" name="initial_cash" rules={[{ required: true, message: '请输入初始资金' }, { type: 'number', min: 1, message: '初始资金必须大于 0' }]}><InputNumber min={1} step={10_000} precision={2} style={{ width: '100%' }} /></Form.Item>
      </Form>
    </Modal>
    <Modal title="模拟研究取证" open={researchOpen} okText="开始取证" cancelText="取消" confirmLoading={research.isPending} onCancel={() => setResearchOpen(false)} onOk={() => researchForm.submit()}>
      <Form form={researchForm} layout="vertical" onFinish={(values) => {
        if (accountId == null || archived) return
        const frozen = (contextsQuery.data ?? []).find((row) => row.id === values.historical_context_id)
        if (values.mode === 'historical_replay' && !frozen) { message.error('请选择已保存的研究快照'); return }
        research.mutate({ id: accountId, body: { stock_code: values.stock_code.trim(), trade_date: values.trade_date.format('YYYY-MM-DD'), mode: values.mode, web_query: values.mode === 'live_paper' ? values.web_query?.trim() : '', web_urls: values.mode === 'live_paper' ? (values.web_urls ?? '').split(/\r?\n/).map((url) => url.trim()).filter(Boolean) : [], ...(values.mode === 'historical_replay' && frozen ? { historical_facts: { facts: frozen.facts, tool_trace: frozen.tool_trace, source_refs: frozen.source_refs } } : {}) } })
      }}>
        <Form.Item label="研究模式" name="mode"><Segmented block options={[{ value: 'live_paper', label: '实时模拟' }, { value: 'historical_replay', label: '历史回放' }]} onChange={(value) => { if (value === 'live_paper') researchForm.setFieldValue('trade_date', dayjs()) }} /></Form.Item>
        {researchMode === 'historical_replay' ? <Form.Item label="已保存的研究快照" name="historical_context_id" rules={[{ required: true, message: '请选择研究快照' }]}><Select loading={contextsQuery.isLoading} options={(contextsQuery.data ?? []).filter((row) => row.facts?.fact_as_of).map((row) => ({ value: row.id, label: `${row.trade_date} · ${row.stock_code} · 记录 #${row.id}` }))} notFoundContent="暂无已保存的研究快照" onChange={(id) => { const frozen = (contextsQuery.data ?? []).find((row) => row.id === id); if (frozen) researchForm.setFieldsValue({ stock_code: frozen.stock_code, trade_date: dayjs(frozen.trade_date) }) }} /></Form.Item> : null}
        <Form.Item label="股票代码" name="stock_code" rules={[{ required: true, message: '请输入股票代码' }, { pattern: /^\d{6}$/, message: '请输入 6 位股票代码' }]}><Input disabled={researchMode === 'historical_replay'} maxLength={6} inputMode="numeric" /></Form.Item>
        <Form.Item label="交易日期" name="trade_date" rules={[{ required: true, message: '请选择交易日期' }]}><DatePicker allowClear={false} disabled style={{ width: '100%' }} /></Form.Item>
        {researchMode === 'live_paper' ? <>
          <Form.Item label="联网检索主题" name="web_query"><Input maxLength={200} /></Form.Item>
          <Form.Item label="来源网址（每行一条，最多 5 条）" name="web_urls" rules={[{ validator: (_, value: string | undefined) => {
            const urls = (value ?? '').split(/\r?\n/).map((url) => url.trim()).filter(Boolean)
            return urls.length > 5 ? Promise.reject(new Error('最多添加 5 个来源网址')) : urls.some((url) => !safeUrl(url)) ? Promise.reject(new Error('请输入有效的网页网址')) : Promise.resolve()
          } }]}><Input.TextArea autoSize={{ minRows: 2, maxRows: 5 }} /></Form.Item>
        </> : null}
      </Form>
    </Modal>
    <Drawer
      title={detailPosition?.stock_code ? `${detailPosition.stock_code} ${detailPosition.stock_name ?? detailPosition.name ?? ''}` : '持仓详情'}
      open={!!detailPosition}
      onClose={closeDetail}
      width={720}
      destroyOnHidden
    >
      {detailPosition ? <Space orientation="vertical" size={16} style={{ width: '100%' }}>
        <Row gutter={[8, 8]}>
          <Col xs={12} sm={6}><Statistic title={isReferenceQuote(detailPosition) ? '最后价格' : '现价'} value={valuationMoney(detailPosition.current_price)} styles={{ content: { fontSize: 18 } }} /></Col>
          <Col xs={12} sm={6}><Statistic title="浮动盈亏" value={valuationMoney(detailPosition.pnl_amount)} styles={{ content: { fontSize: 18 } }} /><Text type="secondary">{pct(detailPosition.pnl_pct)}</Text></Col>
          <Col xs={12} sm={6}><Statistic title="持仓 / 可卖" value={`${number(detailPosition.shares)} / ${number(detailPosition.available_shares)}`} styles={{ content: { fontSize: 18 } }} /></Col>
          <Col xs={12} sm={6}><Statistic title={isReferenceQuote(detailPosition) ? '估算市值' : '市值'} value={valuationMoney(detailPosition.market_value)} styles={{ content: { fontSize: 18 } }} /></Col>
        </Row>
        <div><Text strong>风控计划</Text><FactDetails value={controlDetails(detailPosition)} /></div>
        <div><Space size={6} wrap><Text strong>行情事实</Text>{statusTag(detailPosition.quote_status)}</Space><FactDetails value={{ '行情来源': quoteSource(detailPosition.quote_source), '事实时间': timeText(detailPosition.fact_as_of || detailPosition.quote_time), '行情时间': timeText(detailPosition.quote_time), '行情说明': detailPosition.quote_notice || detailPosition.quote_error || detailPosition.missing_reason }} /></div>
        <div><Text strong>监控研判</Text><FactDetails value={detailPosition.metadata?.monitor} /></div>
        <div><Text strong>卖出决策</Text><FactDetails value={detailPosition.metadata?.sell_decision} /></div>
        <div ref={klineRef}><Text strong>K线图</Text><KlineChart code={detailPosition.stock_code} name={detailPosition.name ?? detailPosition.stock_name} anchorDate={detailPosition.opened_trade_date ?? ''} anchorKind="entry" days={60} height={360} /></div>
      </Space> : null}
    </Drawer>
  </Card>
}

export default PaperTradingPanel
