import { useEffect, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { plans } from '@/api/positions'
import { candidates } from '@/api/candidates'
import { scores } from '@/api/scores'
import { useTaskSubmit } from '@/hooks/useTaskSubmit'
import { EmptyState, ErrorCard, StockLabel } from '@/components/common'
import type { PositionPlan, StockScoreInfo } from '@/types'

const { Text } = Typography

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  proposed: { label: '待评估', color: 'orange' },
  accepted: { label: '已采纳', color: 'green' },
  abandoned: { label: '已放弃', color: 'default' },
}
const GRADE_TONE: Record<string, string> = { A: 'red', B: 'orange', C: 'blue' }
const SOURCE_LABEL: Record<string, string> = { candidate: '每日候选池', manual: '手动生成' }
const FRESHNESS_LABEL: Record<string, { label: string; color: string }> = {
  realtime: { label: '实时数据', color: 'green' },
  cache30m: { label: '30分钟缓存', color: 'orange' },
}

/** 触发信号：止盈已触发=涨=红(var--up) / 止损已触发=跌=绿(var--down) / 正常待评估=橙(var--warn) */
function signalOf(p: PositionPlan): { label: string; color: string; bar: string } {
  const q = (p.detail?.quant ?? {}) as Record<string, unknown>
  const cur = Number(q.current_price)
  const tp = parseFloat(String(q.take_profit ?? ''))
  const sl = parseFloat(String(q.initial_stop ?? ''))
  if (Number.isFinite(cur) && Number.isFinite(tp) && cur >= tp) return { label: '止盈已触发', color: 'red', bar: 'var(--up)' }
  if (Number.isFinite(cur) && Number.isFinite(sl) && cur <= sl) return { label: '止损已触发', color: 'green', bar: 'var(--down)' }
  return { label: '正常待评估', color: 'orange', bar: 'var(--warn)' }
}

/** 维度归因条（与候选池页同款渲染：名称 + 分数条 + 结论 + 建议） */
function DimensionBars({ dims, finalAdvice }: { dims: Array<Record<string, unknown>>; finalAdvice?: unknown }) {
  return (
    <div>
      {dims.length ? (
        dims.map((d) => {
          const score = Number(d.score ?? 0)
          const verdict = String(d.verdict ?? '中性')
          const color = verdict === '支持' ? 'var(--up)' : verdict === '风险' ? 'var(--warn)' : 'var(--text-mute)'
          return (
            <div key={String(d.dim)} style={{ marginBottom: 6 }}>
              <Space>
                <Text style={{ width: 90, fontWeight: 600 }}>{String(d.dim)}</Text>
                <div className="conf-bar" style={{ width: 180 }}>
                  <div className="conf-bar-fill high" style={{ width: `${Math.max(0, Math.min(100, score))}%`, background: color }} />
                </div>
                <Text type="secondary">{score.toFixed(0)}</Text>
                <Tag color={verdict === '支持' ? 'red' : verdict === '风险' ? 'orange' : 'default'}>{verdict}</Tag>
              </Space>
              {d.advice ? <div style={{ marginLeft: 96 }}><Text type="secondary">{String(d.advice)}</Text></div> : null}
            </div>
          )
        })
      ) : (
        <EmptyState text="暂无维度归因。" icon="📊" />
      )}
      {finalAdvice ? <Alert type="info" showIcon style={{ marginTop: 8 }} message={String(finalAdvice)} /> : null}
    </div>
  )
}

/** 计划详情展开：仓位分配 + 分档买入 + 止盈止损 + 建仓逻辑 + 生成依据 */
function PlanExpand({ p, scoreMap }: { p: PositionPlan; scoreMap: Record<string, StockScoreInfo> }) {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const detail = (p.detail ?? {}) as Record<string, unknown>
  const quant = (detail.quant ?? {}) as Record<string, unknown>
  const batches = (quant.batches as Array<Record<string, unknown>>) ?? []
  const dims = (detail.dimensions as Array<Record<string, unknown>>) ?? []
  const grade = scoreMap[p.stock_code]?.grade ?? (detail.grade as string) ?? '—'
  const freshness = detail.freshness as string | undefined

  const refresh = useTaskSubmit('position', () => {
    message.success('建仓方案重算任务已提交后台')
    qc.invalidateQueries({ queryKey: ['plans'] })
  })

  return (
    <div>
      <Space style={{ marginBottom: 8 }}>
        <Button size="small" type="primary" loading={refresh.submit.isPending}
          onClick={() => refresh.submit.mutate({ stock_code: p.stock_code, stock_name: p.stock_name ?? '' })}>
          手动刷新本计划（击穿缓存重算）
        </Button>
        {freshness ? (
          <Tag color={FRESHNESS_LABEL[freshness]?.color ?? 'default'}>{FRESHNESS_LABEL[freshness]?.label ?? freshness}</Tag>
        ) : null}
      </Space>

      {quant.current_price != null ? (
        <Card size="small" title="仓位分配（核心信息总览）" style={{ background: 'var(--bg-input)', marginBottom: 8 }}>
          <Descriptions size="small" column={2} items={[
            { key: 'p', label: '当前股价', children: String(quant.current_price ?? '—') },
            { key: 'cap', label: '单票总仓位上限', children: String(quant.position_cap_pct ?? '—') + '%' },
            { key: 'amount', label: '仓位金额', children: String(quant.position_amount ?? '—') },
            { key: 'shares', label: '可买股数', children: String(quant.position_shares ?? '—') },
            { key: 'sl', label: '初始止损', children: <Text type="danger">{(quant.initial_stop as string) ?? '—'}</Text> },
            { key: 'tp', label: '第一止盈', children: <Text type="success">{(quant.take_profit as string) ?? '—'}</Text> },
            { key: 'be', label: '盈亏比', children: `${String(quant.breakeven_ratio ?? '—')}:1` },
            { key: 'exp', label: '建仓后总仓位', children: quant.expected_total_pct != null ? `${quant.expected_total_pct}%` : '—' },
          ]} />
        </Card>
      ) : null}

      {batches.length ? (
        <Card size="small" title="分档买入明细" style={{ background: 'var(--bg-input)', marginBottom: 8 }}>
          <Table size="small" rowKey={(r) => String(r.tranche ?? Math.random())} pagination={false}
            dataSource={batches}
            columns={[
              { title: '批次', dataIndex: 'tranche', width: 80 },
              { title: '价格区间', dataIndex: 'price_zone', width: 120 },
              { title: '触发条件', dataIndex: 'trigger_note' },
              { title: '金额', dataIndex: 'amount', width: 90, render: (v) => v ?? '—' },
              { title: '股数', dataIndex: 'shares', width: 80, render: (v) => v ?? '—' },
              { title: '累计占比%', dataIndex: 'cum_pct', width: 90, render: (v) => v ?? '—' },
            ]} />
          <div style={{ marginTop: 8, fontSize: 13 }}>
            合计：总投入 <Text strong>{String(quant.total_amount ?? '—')} 元</Text>，
            总持股 <Text strong>{String(quant.total_shares ?? '—')} 股</Text>，
            不突破 C1 单票上限 <Text strong>{String(quant.position_cap_pct ?? '—')}%</Text>
          </div>
        </Card>
      ) : p.batches?.length ? (
        <Card size="small" title="分档买入明细（旧数据，LLM 比例明细）" style={{ background: 'var(--bg-input)', marginBottom: 8 }}>
          <Text type="secondary">（旧数据，量化字段不可用——仅展示 LLM 比例明细）</Text>
          <Table size="small" rowKey={(r) => String((r as Record<string, unknown>).tranche ?? Math.random())} pagination={false}
            dataSource={p.batches as Array<Record<string, unknown>>}
            columns={[
              { title: '批次', dataIndex: 'tranche', width: 80 },
              { title: '价格区间', dataIndex: 'price_zone', width: 120 },
              { title: '资金占比%', dataIndex: 'ratio_pct', width: 100 },
              { title: '触发条件', dataIndex: 'trigger_note' },
            ]} />
        </Card>
      ) : null}

      <Card size="small" title="止盈止损与风控规则" style={{ background: 'var(--bg-input)', marginBottom: 8 }}>
        <div>- 止损规则：初始止损 <Text strong>{(quant.initial_stop as string) ?? p.stop_loss ?? '—'}</Text>（C3 硬止损）</div>
        <div>- 止盈规则：第一目标 <Text strong>{(quant.take_profit as string) ?? p.take_profit ?? '—'}</Text> 减仓 1/3 → 第二目标再减 1/3 → 移动止盈</div>
        <div>- 仓位红线：单票 ≤ C1（{String(quant.position_cap_pct ?? '—')}%），总仓 ≤ C2 60%</div>
      </Card>

      {detail.market_regime || p.rationale ? (
        <Card size="small" title="市场强弱判断与建仓逻辑" style={{ background: 'var(--bg-input)', marginBottom: 8 }}>
          <div>{String(detail.market_regime ?? '（无）')}</div>
          <div>{String(p.rationale ?? '（无）')}</div>
        </Card>
      ) : null}

      {(grade !== '—') ? (
        <Card size="small" title="生成依据（评级依据）" style={{ background: 'var(--bg-input)' }}>
          <div style={{ marginBottom: 6 }}>综合评级：<Tag color={GRADE_TONE[grade] ?? 'default'}>{grade} 级</Tag>
            {scoreMap[p.stock_code]?.score != null ? ` ${scoreMap[p.stock_code].score} 分` : ''}
            {scoreMap[p.stock_code] ? '（评分报告同源数据）' : ''}
            {quant.confidence != null ? ` 置信 ${String(quant.confidence)}` : ''}
          </div>
          <div style={{ marginBottom: 10 }}>
            <Text strong>风险提示：</Text>
            <div>
              {((scoreMap[p.stock_code]?.risk_list as string[]) ?? []).length > 0 ? (
                ((scoreMap[p.stock_code]?.risk_list as string[]) ?? []).map((risk, i) => (
                  <div key={i} style={{ marginLeft: 12 }}>- ⚠️ {risk}</div>
                ))
              ) : (
                <Text type="secondary">（该轮未输出）</Text>
              )}
            </div>
          </div>
          <div>
            <Text strong>维度归因（白盒，主结论）：</Text>
            <DimensionBars dims={dims} finalAdvice={detail.final_advice} />
          </div>
        </Card>
      ) : null}
    </div>
  )
}

/** 新建建仓方案弹窗（候选池选择 / 手动输入） */
function NewPlanModal({ open, onClose, scoreMap }: { open: boolean; onClose: () => void; scoreMap: Record<string, StockScoreInfo> }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const { data: candRows } = useQuery({ queryKey: ['candidates'], queryFn: () => candidates(undefined, 50) })
  const gen = useTaskSubmit('position', () => {
    message.success('建仓方案生成任务已提交后台')
    form.resetFields()
    onClose()
  })
  const gradeOf = (code: string) => scoreMap[code]?.grade

  const opts = (candRows ?? []).map((c) => ({
    label: `${c.stock_code} ${c.stock_name ?? ''}（${gradeOf(c.stock_code) ?? '—'} 级）`,
    value: c.stock_code,
  }))

  return (
    <Modal title="新建建仓方案（仅综合评级 ≥B 可生成，C 级提示评级不足）" open={open} onCancel={onClose} footer={null}>
      <Form form={form} layout="vertical" onFinish={(v) => {
        const manual = String(v.manual_code ?? '').trim()
        if (manual) {
          gen.submit.mutate({ stock_code: manual, stock_name: '', source: 'manual' })
        } else if (v.stock_code) {
          const c = (candRows ?? []).find((x) => x.stock_code === v.stock_code)
          gen.submit.mutate({ stock_code: v.stock_code, stock_name: c?.stock_name ?? '', source: 'manual' })
        } else {
          message.warning('请选择候选池标的或输入 6 位股票代码')
        }
      }}>
        <Form.Item name="stock_code" label="候选池标的（最新一轮）">
          <Select allowClear showSearch options={opts} placeholder="从候选池选择" filterOption={(input, o) => String(o?.label ?? '').includes(input)} />
        </Form.Item>
        <Form.Item name="manual_code" label="或手动输入代码（6 位）">
          <Input placeholder="或手动输入 6 位股票代码" maxLength={6} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={gen.submit.isPending} block>
          生成建仓计划（后台）
        </Button>
      </Form>
    </Modal>
  )
}

/** 建仓计划页（Phase 2） */
export function PlansPage() {
  const [status, setStatus] = useState('全部')
  const [date, setDate] = useState('')
  const [grade, setGrade] = useState('全部评级')
  const [source, setSource] = useState('全部来源')
  const [newOpen, setNewOpen] = useState(false)
  const [page, setPage] = useState(1)

  const { data: rows, isError, error, refetch } = useQuery({ queryKey: ['plans'], queryFn: () => plans(undefined, 200) })
  const { data: scoreRows } = useQuery({ queryKey: ['scores-all'], queryFn: () => scores(undefined, undefined, 500) })

  const scoreMap = (scoreRows ?? []).reduce<Record<string, StockScoreInfo>>((m, s) => {
    if (s.stock_code) m[s.stock_code] = s
    return m
  }, {})

  // 日期下拉选项：plan_date 倒序（最新优先），dates[0] 即最近一天
  const dates = Array.from(new Set((rows ?? []).map((p) => p.plan_date || (p.created_at ?? '').slice(0, 10)).filter(Boolean))).sort((a, b) => b.localeCompare(a))

  // 首次进入且日期已加载 → 默认只查最近一天（prev 仍为 '' 表示尚未手动选择，仅在首次生效）
  useEffect(() => { if (dates.length) setDate((prev) => (prev === '' ? dates[0] : prev)) }, [dates])

  // 筛选条件变化 → 分页重置到第一页
  useEffect(() => { setPage(1) }, [status, date, grade, source])

  if (isError) return <ErrorCard title="建仓计划加载失败" message={error?.message} onRetry={() => refetch()} />

  let shown = (rows ?? []).filter((p) => status === '全部' || STATUS_MAP[p.status ?? '']?.label === status)
  // date=''（数据刚加载、默认日期落定前）以最近一天兜底，避免全量闪烁
  const curDate = date || (dates.length ? dates[0] : '全部日期')
  if (curDate !== '全部日期') shown = shown.filter((p) => (p.plan_date || '') === curDate)
  if (grade !== '全部评级') {
    shown = shown.filter((p) => {
      const g = scoreMap[p.stock_code]?.grade ?? ''
      if (grade === '未评级') return !g
      return g === grade
    })
  }
  if (source !== '全部来源') {
    shown = shown.filter((p) => (p.source || 'manual') === source)
  }

  if (!shown.length) return <EmptyState text="暂无匹配的建仓方案。可点击「新建建仓方案」生成。" icon="🧭" />

  const cols = [
    {
      title: '信号', key: 'signal', width: 130,
      render: (_: unknown, p: PositionPlan) => {
        const s = signalOf(p)
        return (
          <div style={{ borderLeft: `4px solid ${s.bar}`, paddingLeft: 8 }}>
            <Tag color={s.color}>{s.label}</Tag>
          </div>
        )
      },
    },
    {
      title: '股票', key: 'stock', width: 160,
      render: (_: unknown, p: PositionPlan) => <StockLabel code={p.stock_code} name={p.stock_name} />,
    },
    {
      title: '状态', dataIndex: 'status', width: 90,
      render: (v: string) => <Tag color={STATUS_MAP[v]?.color ?? 'default'}>{STATUS_MAP[v]?.label ?? v}</Tag>,
    },
    { title: '总仓位', dataIndex: 'total_pct', width: 80, render: (v: number) => `${v}%` },
    {
      title: '来源', dataIndex: 'source', width: 100,
      render: (v: string) => <Tag color={v === 'candidate' ? 'blue' : 'default'}>{SOURCE_LABEL[v] ?? v}</Tag>,
    },
    { title: '止损', dataIndex: 'stop_loss', width: 80, render: (v: number) => v ?? '—' },
    { title: '止盈', dataIndex: 'take_profit', width: 80, render: (v: number) => v ?? '—' },
    { title: '生成时间', dataIndex: 'created_at', width: 150, render: (v: string) => String(v ?? '').slice(0, 16) },
  ]

  const sourceOpts = ['全部来源', '每日候选池', '手动生成'].map((s) => ({ label: s, value: s === '每日候选池' ? 'candidate' : s === '手动生成' ? 'manual' : s }))

  return (
    <div>
      <Space style={{ marginBottom: 10 }} wrap>
        <Select value={status} onChange={(v) => setStatus(v)} style={{ width: 120 }}
          options={['全部', '待评估', '已采纳', '已放弃'].map((s) => ({ label: s, value: s }))} />
        <Select value={date} onChange={(v) => setDate(v)} style={{ width: 130 }}
          options={[{ label: '全部日期', value: '全部日期' }, ...dates.map((d) => ({ label: d, value: d }))]} />
        <Select value={grade} onChange={(v) => setGrade(v)} style={{ width: 120 }}
          options={[
            { label: '全部评级', value: '全部评级' },
            { label: 'A 级', value: 'A' },
            { label: 'B 级', value: 'B' },
            { label: 'C 级', value: 'C' },
            { label: '未评级', value: '未评级' },
          ]} />
        <Select value={source} onChange={(v) => setSource(v)} style={{ width: 130 }} options={sourceOpts} />
        <Button type="primary" onClick={() => setNewOpen(true)}>新建建仓方案</Button>
        <Button onClick={() => refetch()}>刷新</Button>
        <Text type="secondary">共 {shown.length} 条计划 · 仅 B 级及以上标的可生成（后端强校验）</Text>
      </Space>
      <Table<PositionPlan>
        key={`${status}|${date}|${grade}|${source}`}
        rowKey="id" size="small" dataSource={shown} columns={cols}
        pagination={{ pageSize: 20, current: page, onChange: setPage }}
        onRow={(p) => ({ style: p.status === 'accepted'
          ? { borderTop: '1px solid var(--down)', borderBottom: '1px solid var(--down)', borderRight: '1px solid var(--down)' }
          : undefined })}
        expandable={{ expandedRowRender: (p) => <PlanExpand p={p} scoreMap={scoreMap} /> }}
      />
      <NewPlanModal open={newOpen} onClose={() => setNewOpen(false)} scoreMap={scoreMap} />
    </div>
  )
}

export default PlansPage
