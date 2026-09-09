import { useState } from 'react'
import {
  Alert, App, Button, Card, Col, DatePicker, Descriptions, Empty, Form, Input,
  InputNumber, Modal, Row, Segmented, Select, Space, Statistic, Table, Tag, Tabs, Typography,
} from 'antd'
import { PauseOutlined, PlayCircleOutlined, PlusOutlined, RadarChartOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import dayjs, { type Dayjs } from 'dayjs'
import {
  collectPaperContext, createPaperAccount, monitorPaper, paperAccounts, paperAlerts,
  paperContexts, paperExecutions, paperSummary, paperWebEvidence, refreshPaperQuotes,
  runPaper, setPaperAccountStatus, type PaperAlert, type PaperContext, type PaperContextRequest,
  type PaperExecution, type PaperMode, type PaperPosition, type PaperToolTrace, type PaperWebEvidence,
} from '@/api/paper'

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
  frozen: '已冻结', ready: '已就绪', active: '运行中', paused: '已暂停',
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

function FactDetails({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value == null || value === '') return <Text type="secondary">—</Text>
  if (typeof value === 'boolean') return <span>{value ? '是' : '否'}</span>
  if (typeof value !== 'object') {
    const text = String(value)
    return <span style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{labels[text] ?? text}</span>
  }
  if (depth > 3) return <Text type="secondary">已保存详细证据</Text>
  if (Array.isArray(value)) return value.length ? <Space orientation="vertical" style={{ width: '100%' }} size={8}>
    {value.slice(0, 8).map((item, index) => <div key={index}><FactDetails value={item} depth={depth + 1} /></div>)}
    {value.length > 8 ? <Text type="secondary">共 {value.length} 条，展示最近取出的前 8 条</Text> : null}
  </Space> : <Text type="secondary">暂无记录</Text>
  return <Descriptions size="small" column={1} items={Object.entries(value).map(([key, item], index) => ({
    key: `${key}-${index}`, label: fieldLabels[key] ?? labels[key] ?? (/[\u3400-\u9fff]/.test(key) ? key : '补充资料'),
    children: key === 'url' && safeUrl(item) ? <Link href={safeUrl(item)} target="_blank" rel="noopener noreferrer">查看原文</Link> : <FactDetails value={item} depth={depth + 1} />,
  }))} />
}

function ContextDetails({ context }: { context: PaperContext }) {
  const tools = context.tool_trace ?? []
  return <div style={{ padding: '8px 12px', overflowWrap: 'anywhere' }}>
    <Descriptions size="small" column={{ xs: 1, sm: 2 }} items={[
      { label: '事实时点', children: timeText(context.facts?.fact_as_of) },
      { label: '来源证据', children: `${context.source_refs?.length ?? 0} 条` },
    ]} />
    <Table size="small" rowKey={(_, index) => String(index)} pagination={false} dataSource={tools} scroll={{ x: 500 }} columns={[
      { title: '工具', dataIndex: 'tool', render: (v: unknown) => label(v, '补充数据工具') },
      { title: '结果', dataIndex: 'status', render: statusTag },
      { title: '资料摘要', render: (_: unknown, row: PaperToolTrace) => {
        const fact = (context.facts?.[row.tool ?? ''] ?? row.result) as Record<string, unknown> | undefined
        const values = fact && Object.values(fact).find(Array.isArray)
        return row.error || fact?.error ? label(row.error || fact?.error, '数据请求失败')
          : Array.isArray(values) ? `${values.length} 条记录` : label(fact?.note, '证据已记录')
      } },
    ]} expandable={{ expandedRowRender: (row) => <FactDetails value={context.facts?.[row.tool ?? ''] ?? row.result ?? row.error} /> }} locale={{ emptyText: '没有工具调用记录' }} />
    {context.stage === 'monitor' ? <FactDetails value={{ '监控结论': context.facts?.monitor, '卖出研判': context.facts?.sell }} /> : null}
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
  const [createOpen, setCreateOpen] = useState(false)
  const [researchOpen, setResearchOpen] = useState(false)
  const [tab, setTab] = useState('positions')
  const [focusedContextId, setFocusedContextId] = useState<number>()
  const [form] = Form.useForm<{ name: string; initial_cash: number }>()
  const [researchForm] = Form.useForm<ResearchForm>()
  const researchMode = Form.useWatch('mode', researchForm) ?? 'live_paper'
  const accountsQuery = useQuery({ queryKey: ['paper-accounts'], queryFn: paperAccounts, refetchInterval: 30_000 })
  const accounts = accountsQuery.data ?? []
  const accountId = selectedId ?? accounts[0]?.id
  const account = accounts.find((row) => row.id === accountId)
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
    setCreateOpen(false); form.resetFields(); setSelectedId(created.id); refresh(); message.success('模拟账户已创建')
  } })
  const status = useMutation({ mutationFn: ({ id, next }: { id: number; next: 'active' | 'paused' }) => setPaperAccountStatus(id, next), onSuccess: refresh, onError })
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
  const queryError = [accountsQuery, summaryQuery, executionsQuery, contextsQuery, evidenceQuery, alertsQuery].find((query) => query.isError)?.error
  const positionColumns = [
    { title: '标的', key: 'stock', render: (_: unknown, row: PaperPosition) => <Space orientation="vertical" size={0}><Text strong>{row.stock_code}</Text><Text type="secondary">{row.stock_name ?? row.name ?? '—'}</Text></Space> },
    { title: '持仓 / 可卖', key: 'shares', render: (_: unknown, row: PaperPosition) => `${number(row.shares)} / ${number(row.available_shares)}` },
    { title: '成本价', dataIndex: 'avg_price', render: money },
    { title: '现价 / 市值', key: 'market', render: (_: unknown, row: PaperPosition) => <Space orientation="vertical" size={0}><span>{money(row.current_price)}</span><Text type="secondary">{money(row.market_value)}</Text></Space> },
    { title: '浮动盈亏', key: 'pnl', render: (_: unknown, row: PaperPosition) => <span>{money(row.pnl_amount)}（{pct(row.pnl_pct)}）</span> },
    { title: '行情来源 / 状态', key: 'quote', render: (_: unknown, row: PaperPosition) => <Space orientation="vertical" size={0}><span>{label(row.quote_source)}</span>{statusTag(row.quote_status)}<Text type="secondary">{timeText(row.quote_time)}</Text>{row.quote_error || row.missing_reason || row.current_price == null ? <Text type="warning">{label(row.quote_error || row.missing_reason, '没有可用价格')}</Text> : null}</Space> },
    { title: '建仓日期', dataIndex: 'opened_trade_date', render: timeText },
  ]
  const executionColumns = [
    { title: '日期 / 事实时点', dataIndex: 'trade_date', render: (v: unknown, row: PaperExecution) => <Space orientation="vertical" size={0}><span>{timeText(v)}</span><Text type="secondary">{timeText(row.fact_as_of)}</Text>{modeTag(row.mode ?? row.metadata?.mode ?? row.metadata_json?.mode)}</Space> },
    { title: '标的', key: 'stock', render: (_: unknown, row: PaperExecution) => `${row.stock_code ?? '—'} ${row.stock_name ?? ''}` },
    { title: '方向', dataIndex: 'side', render: (v: unknown) => label(v) },
    { title: '状态', dataIndex: 'status', render: (v: unknown, row: PaperExecution) => <Space orientation="vertical" size={0}>{statusTag(v)}{v !== 'filled' && row.reject_reason ? <Text type="secondary">{label(row.reject_reason, '成交约束未通过')}</Text> : null}</Space> },
    { title: '数量 / 成交价', key: 'fill', render: (_: unknown, row: PaperExecution) => `${number(row.shares)} / ${money(row.executed_price)}` },
    { title: '费用', key: 'fees', render: (_: unknown, row: PaperExecution) => money(Number(row.commission ?? 0) + Number(row.stamp_tax ?? 0) + Number(row.transfer_fee ?? 0)) },
  ]
  const contextColumns = [
    { title: '记录', dataIndex: 'id', render: (value: number) => `#${value}` },
    { title: '交易日期', dataIndex: 'trade_date' }, { title: '标的', dataIndex: 'stock_code' },
    { title: '研究模式', dataIndex: 'mode', render: modeTag },
    { title: '工具结果', render: (_: unknown, row: PaperContext) => { const trace = row.tool_trace ?? []; return `已完成 ${trace.filter((item) => item.status === 'ok').length} / ${trace.length} 项` } },
    { title: '联网来源', render: (_: unknown, row: PaperContext) => `${row.source_refs?.filter((ref) => ref.type === 'web').length ?? 0} 条` },
    { title: '记录时间', dataIndex: 'created_at', render: timeText },
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
      <Select style={{ width: 220, maxWidth: '100%' }} placeholder="选择模拟账户" value={accountId} onChange={(id) => { setSelectedId(id); setFocusedContextId(undefined) }} loading={accountsQuery.isLoading} options={accounts.map((row) => ({ value: row.id, label: `${row.name ?? `模拟账户 #${row.id}`} · ${label(row.status)}` }))} />
      <Button icon={<PlusOutlined />} onClick={() => { form.setFieldsValue({ name: 'AI模拟账户', initial_cash: 100_000 }); setCreateOpen(true) }}>新建账户</Button>
      {account ? <>
        <Button icon={account.status === 'paused' ? <PlayCircleOutlined /> : <PauseOutlined />} loading={status.isPending} onClick={() => status.mutate({ id: account.id, next: account.status === 'paused' ? 'active' : 'paused' })}>{account.status === 'paused' ? '继续运行' : '暂停运行'}</Button>
        <Button icon={<ReloadOutlined />} loading={quotes.isPending} onClick={() => quotes.mutate(account.id)}>刷新行情</Button>
        <Button icon={<SearchOutlined />} loading={research.isPending} onClick={openResearch}>研究取证</Button>
        <Button icon={<RadarChartOutlined />} loading={monitor.isPending} disabled={account.status === 'paused'} onClick={() => monitor.mutate(account.id)}>模拟巡检</Button>
        <Button type="primary" icon={<PlayCircleOutlined />} loading={run.isPending} disabled={account.status === 'paused'} onClick={() => run.mutate(account.id)}>立即补跑</Button>
      </> : null}
    </Space>
    {queryError ? <Alert type="error" showIcon title="模拟数据加载失败" description={queryError.message} action={<Button size="small" icon={<ReloadOutlined />} onClick={refresh}>重试</Button>} style={{ marginBottom: 10 }} /> : null}
    {account ? <Alert type="info" showIcon message={account.status === 'active' ? '自动运行已开启：后端服务在线时，交易日盘中每隔设定周期自动监控、估值和模拟执行；“立即补跑”仅用于现在手动触发一次。' : '自动运行已暂停：点击“继续运行”后恢复交易日盘中自动监控和模拟执行。'} style={{ marginBottom: 10 }} /> : null}
    {!account ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无模拟账户" /> : <>
      <Row gutter={[8, 12]} style={{ marginBottom: 12 }}>
        <Col xs={12} sm={6}><Statistic title="模拟现金" value={money(summary?.cash)} styles={{ content: { fontSize: 20 } }} /></Col>
        <Col xs={12} sm={6}><Statistic title="模拟市值" value={money(summary?.market_value)} styles={{ content: { fontSize: 20 } }} /></Col>
        <Col xs={12} sm={6}><Statistic title="模拟总资产" value={money(summary?.equity)} styles={{ content: { fontSize: 20 } }} /></Col>
        <Col xs={12} sm={6}><Statistic title="累计盈亏" value={money(summary?.pnl_amount)} styles={{ content: { fontSize: 20 } }} /><Text type="secondary">{pct(summary?.pnl_pct)}</Text></Col>
      </Row>
      <Descriptions size="small" column={{ xs: 1, sm: 3 }} items={[
        { label: '初始资金', children: money(summary?.initial_cash ?? account.initial_cash) },
        { label: '估值时点', children: timeText(summary?.valuation_as_of) },
        { label: '行情来源', children: <Space wrap><span>{label(summary?.quote_source)}</span>{statusTag(summary?.quote_status)}</Space> },
      ]} />
      {summary?.quote_status && summary.quote_status !== 'ok' ? <Alert type="warning" showIcon title="模拟估值暂不完整" description={(summary.quote_errors ?? []).map((item) => label(item, '行情请求失败')).join('；') || '部分持仓尚无有效行情，市值和盈亏暂不可用。'} style={{ marginBottom: 10 }} /> : null}
      <Tabs activeKey={tab} onChange={setTab} items={[
        { key: 'positions', label: `模拟持仓（${positions.length}）`, children: <Table size="small" rowKey="id" loading={summaryQuery.isLoading} columns={positionColumns} dataSource={positions} pagination={{ pageSize: 8 }} scroll={{ x: 980 }} expandable={{ expandedRowRender: (row) => <FactDetails value={{ '事实时点': row.fact_as_of, '监控研判': row.metadata?.monitor, '卖出决策': row.metadata?.sell_decision }} /> }} locale={{ emptyText: '暂无模拟持仓' }} /> },
        { key: 'executions', label: '模拟流水', children: <Table size="small" rowKey="id" loading={executionsQuery.isLoading} columns={executionColumns} dataSource={executionsQuery.data ?? []} pagination={{ pageSize: 8 }} scroll={{ x: 880 }} locale={{ emptyText: '暂无模拟成交或拒绝记录' }} /> },
        { key: 'contexts', label: '研究上下文', children: <>
          {focusedContextId != null ? <Space style={{ marginBottom: 8 }}><Text type="secondary">当前查看记录 #{focusedContextId}</Text><Button size="small" onClick={() => setFocusedContextId(undefined)}>查看全部</Button></Space> : null}
          <Table size="small" rowKey="id" loading={contextsQuery.isLoading} columns={contextColumns} dataSource={(contextsQuery.data ?? []).filter((row) => focusedContextId == null || row.id === focusedContextId)} pagination={{ pageSize: 8 }} scroll={{ x: 760 }} expandable={{ expandedRowRender: (row) => <ContextDetails context={row} />, ...(focusedContextId != null ? { expandedRowKeys: [focusedContextId] } : {}) }} locale={{ emptyText: focusedContextId == null ? '暂无模拟研究记录' : '此记录不在最近研究列表中' }} />
        </> },
        { key: 'evidence', label: '联网证据', children: <Table size="small" rowKey="id" loading={evidenceQuery.isLoading} columns={evidenceColumns} dataSource={evidenceQuery.data ?? []} pagination={{ pageSize: 8 }} scroll={{ x: 760 }} expandable={{ expandedRowRender: (row) => <div style={{ overflowWrap: 'anywhere' }}><Paragraph>{row.excerpt || label(row.error, '暂无可读摘要')}</Paragraph><Descriptions size="small" column={1} items={[{ label: '事实时点', children: timeText(row.fact_as_of) }, { label: '内容指纹', children: row.content_hash || '未生成' }]} /></div> }} locale={{ emptyText: '暂无联网证据' }} /> },
        { key: 'alerts', label: '模拟告警', children: <Table size="small" rowKey="id" loading={alertsQuery.isLoading} columns={alertColumns} dataSource={alertsQuery.data ?? []} pagination={{ pageSize: 8 }} scroll={{ x: 800 }} locale={{ emptyText: '暂无模拟告警' }} /> },
      ]} />
    </>}
    <Modal title="新建 AI 模拟账户" open={createOpen} okText="创建" cancelText="取消" confirmLoading={create.isPending} onCancel={() => setCreateOpen(false)} onOk={() => form.submit()}>
      <Form form={form} layout="vertical" onFinish={(values) => create.mutate(values)}>
        <Form.Item label="账户名称" name="name" rules={[{ required: true, message: '请输入账户名称' }]}><Input maxLength={64} /></Form.Item>
        <Form.Item label="初始资金（元）" name="initial_cash" rules={[{ required: true, message: '请输入初始资金' }, { type: 'number', min: 1, message: '初始资金必须大于 0' }]}><InputNumber min={1} step={10_000} precision={2} style={{ width: '100%' }} /></Form.Item>
      </Form>
    </Modal>
    <Modal title="模拟研究取证" open={researchOpen} okText="开始取证" cancelText="取消" confirmLoading={research.isPending} onCancel={() => setResearchOpen(false)} onOk={() => researchForm.submit()}>
      <Form form={researchForm} layout="vertical" onFinish={(values) => {
        if (accountId == null) return
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
  </Card>
}

export default PaperTradingPanel
