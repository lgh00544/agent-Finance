import { useState } from 'react'
import {
  App,
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Radio,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  addHolding,
  exitHolding,
  holdingAdd,
  holdingCost,
  holdingQuotes,
  holdingTrades,
  holdings,
  monitorHolding,
  sellDecisions,
  takeProfitPlan,
} from '@/api/holdings'
import { alerts } from '@/api/alerts'
import { ocrHolding, ocrStatus } from '@/api/ocr'
import { saveAccountBaseline } from '@/api/account'
import { useTaskSubmit } from '@/hooks/useTaskSubmit'
import { EmptyState, ErrorCard, StockLabel } from '@/components/common'
import { moneySigned } from '@/utils/format'
import type { Holding } from '@/types'

const { Text } = Typography

/** 涨跌色（中国股市惯例：正红负绿） */
function pnlColor(v: number | null | undefined): string {
  if (v == null) return 'var(--text)'
  return v > 0 ? 'var(--up)' : v < 0 ? 'var(--down)' : 'var(--text)'
}

/** ============ 操作区：加仓/减仓/清仓/成本修正 ============ */
function HoldingOpsForm({ h }: { h: Holding }) {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [opType, setOpType] = useState('add')
  const [form] = Form.useForm()
  const invalidate = () => qc.invalidateQueries({ queryKey: ['holding-quotes'] })

  const runOp = useMutation({
    mutationFn: (values: Record<string, unknown>) => {
      if (opType === 'add') return holdingAdd(h.id, values)
      if (opType === 'exit') return exitHolding(h.id, values)
      return holdingCost(h.id, values)
    },
    onSuccess: () => {
      message.success('操作已记录，风控档位已自动重算')
      form.resetFields()
      invalidate()
    },
    onError: (e: Error) => message.error(e.message),
  })

  const mon = useMutation({
    mutationFn: () => monitorHolding(h.id),
    onSuccess: () => {
      message.success('监控信号已生成')
      invalidate()
    },
    onError: (e: Error) => message.error(e.message),
  })

  return (
    <Card size="small" style={{ background: 'var(--bg-input)' }}>
      <Space wrap style={{ marginBottom: 10 }}>
        <Button size="small" type="primary" loading={mon.isPending} onClick={() => mon.mutate()}>
          立即执行监控
        </Button>
        <Tag color="blue">持仓 {h.shares ?? 0} 股</Tag>
        <Tag color="cyan">成本 {h.entry_price ?? '—'}</Tag>
        <Tag color="geekblue">现价 {h.current_price ?? '—'}</Tag>
      </Space>
      <Radio.Group
        value={opType}
        onChange={(e) => setOpType(e.target.value)}
        optionType="button"
        size="small"
        options={[
          { label: '记录加仓', value: 'add' },
          { label: '记录减仓/清仓', value: 'exit' },
          { label: '成本修正', value: 'cost' },
        ]}
      />
      <Form
        form={form}
        layout="inline"
        style={{ marginTop: 10, rowGap: 8 }}
        onFinish={(v) => runOp.mutate(v)}
        initialValues={{ trade_date: new Date().toISOString().slice(0, 10) }}
      >
        <Form.Item name="price" label="成交价格" rules={[{ required: true, message: '必填' }]}>
          <InputNumber min={0} step={0.01} placeholder="如 12.50" style={{ width: 110 }} />
        </Form.Item>
        {opType !== 'cost' && (
          <Form.Item name="shares" label={opType === 'add' ? '股数(100倍)' : '卖出股数'} rules={[{ required: true, message: '必填' }]}>
            <InputNumber min={100} step={100} style={{ width: 110 }} />
          </Form.Item>
        )}
        {opType === 'cost' && (
          <Form.Item name="reason" label="修正原因" rules={[{ required: true, message: '必填留痕' }]}>
            <Input placeholder="如 实盘核对修正" style={{ width: 150 }} />
          </Form.Item>
        )}
        {opType !== 'cost' && (
          <Form.Item name="note" label="备注">
            <Input placeholder="可选" style={{ width: 120 }} />
          </Form.Item>
        )}
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={runOp.isPending} size="small">
            确认{opType === 'add' ? '加仓' : opType === 'exit' ? '减仓/清仓' : '修正'}
          </Button>
        </Form.Item>
      </Form>
      {opType === 'exit' && (
        <Alert type="warning" showIcon style={{ marginTop: 8, fontSize: 12 }}
          message="卖出/清仓仅记录人工成交结果，系统不自动下单；清仓将移入历史持仓并触发复盘。" />
      )}
    </Card>
  )
}

/** ============ 详情抽屉：操作 + 流水 + 止盈计划 + 卖出决策历史 ============ */
function HoldingDrawer({ h, open, onClose }: { h: Holding | null; open: boolean; onClose: () => void }) {
  const { data: trades } = useQuery({
    queryKey: ['holding-trades', h?.id],
    queryFn: () => holdingTrades(h!.id),
    enabled: !!h,
  })
  const { data: tpPlans } = useQuery({ queryKey: ['take-profit-plan'], queryFn: () => takeProfitPlan() })
  const { data: sellHist } = useQuery({
    queryKey: ['sell-decisions', h?.id],
    queryFn: () => sellDecisions(h!.id),
    enabled: !!h,
  })
  const tp = (tpPlans?.rows ?? []).find((p) => p.holding_id === h?.id)

  if (!h) return null
  return (
    <Drawer title={<StockLabel code={h.stock_code} name={h.stock_name} />} open={open} onClose={onClose} width={560}>
      <HoldingOpsForm h={h} />
      {tp ? (
        <Card size="small" title="止盈与仓位计划" style={{ marginTop: 12, background: 'var(--bg-input)' }}>
          <Descriptions size="small" column={2} items={[
            { key: 'sl', label: '止损', children: String(tp.stop_loss ?? '—') },
            { key: 'tp', label: '止盈', children: String(tp.take_profit ?? '—') },
            { key: 'pct', label: '目标仓位', children: tp.target_pct ? `${tp.target_pct}%` : '—' },
            { key: 'cap', label: '建议仓位', children: tp.suggest_pct ? `${tp.suggest_pct}%` : '—' },
          ]} />
        </Card>
      ) : null}
      <Card size="small" title={`操作流水（${trades?.length ?? 0}）`} style={{ marginTop: 12, background: 'var(--bg-input)' }}>
        {trades?.length ? (
          trades.slice(0, 20).map((t: Record<string, unknown>) => (
            <div key={String(t.id)} style={{ fontSize: 13, marginBottom: 4 }}>
              <Tag color={t.side === 'buy' ? 'green' : 'red'}>{String(t.side)}</Tag>
              {String(t.shares)} 股 @ {String(t.price)} · {String(t.trade_date ?? '')}
              {t.note ? <Text type="secondary">（{String(t.note)}）</Text> : null}
            </div>
          ))
        ) : (
          <Text type="secondary">（暂无操作流水）</Text>
        )}
      </Card>
      <Card size="small" title={`卖出决策历史（${sellHist?.length ?? 0}，仅供参考）`} style={{ marginTop: 12, background: 'var(--bg-input)' }}>
        {sellHist?.length ? (
          sellHist.slice(0, 10).map((s: Record<string, unknown>) => {
            const d = (s.decision as Record<string, unknown>) ?? {}
            return (
              <div key={String(s.id)} style={{ fontSize: 13, marginBottom: 6 }}>
                <Text>【{String(d.action ?? '—')}】置信 {String(d.confidence ?? '—')}</Text>
                <div><Text type="secondary">{String(d.exit_price_zone ?? d.risk_warning ?? '')}</Text></div>
                {d.final_advice ? <div><Text type="secondary">{String(d.final_advice)}</Text></div> : null}
              </div>
            )
          })
        ) : (
          <Text type="secondary">（暂无卖出决策）</Text>
        )}
      </Card>
    </Drawer>
  )
}

/** ============ 卖出决策两步确认 ============ */
function SellDecisionBtn({ hid, size = 'small' as const }: { hid: number; size?: 'small' | 'middle' }) {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const sell = useTaskSubmit('sell_decision', () => {
    message.success('卖出决策任务已提交后台，完成后自动展示')
    qc.invalidateQueries({ queryKey: ['sell-decisions', hid] })
  })
  const confirm = () => {
    modal.confirm({
      title: '生成卖出决策',
      content: '决策仅供参考，卖出必须由你人工执行。',
      okText: '确认提交后台',
      cancelText: '取消',
      onOk: () => sell.submit.mutate({ holding_id: hid }),
    })
  }
  return (
    <Button size={size} loading={sell.submit.isPending} onClick={confirm}>
      生成卖出决策
    </Button>
  )
}

/** ============ 当前持仓表 ============ */
function HoldingsTable() {
  const [drawerH, setDrawerH] = useState<Holding | null>(null)
  const { data, isError, error, refetch } = useQuery({
    queryKey: ['holding-quotes'],
    queryFn: holdingQuotes,
    refetchInterval: 60_000,
  })
  const rows = data?.rows ?? []
  if (isError) return <ErrorCard title="持仓数据加载失败" message={error?.message} onRetry={() => refetch()} />
  if (!rows.length) return <EmptyState text="暂无持仓。可通过「录入人工建仓」创建。" icon="📭" />

  const cols = [
    {
      title: '股票', key: 'stock', width: 150,
      render: (_: unknown, r: Holding) => <StockLabel code={r.stock_code} name={r.stock_name} />,
    },
    { title: '建仓日', dataIndex: 'entry_date', width: 96 },
    {
      title: '现价', key: 'price', width: 88,
      render: (_: unknown, r: Holding) => (
        <Text style={{ color: pnlColor(r.current_price) }}>{r.current_price ?? '—'}</Text>
      ),
    },
    {
      title: '盈亏', key: 'pnl', width: 150,
      render: (_: unknown, r: Holding) => {
        const p = r.current_price
        const w = r.entry_price
        if (p == null || !w) return '—'
        const amt = (Number(p) - Number(w)) * (r.shares ?? 0)
        const pctv = (Number(p) - Number(w)) / Number(w) * 100
        return <Text style={{ color: pnlColor(amt) }}>{moneySigned(amt)}（{pctv >= 0 ? '+' : ''}{pctv.toFixed(2)}%）</Text>
      },
    },
    { title: '止损', dataIndex: 'stop_loss', width: 80, render: (v: unknown) => v ?? '—' },
    { title: '止盈', dataIndex: 'take_profit', width: 80, render: (v: unknown) => v ?? '—' },
    { title: '目标仓位', key: 'target', width: 88, render: (_: unknown, r: Holding) => (r.target_pct ? `${r.target_pct}%` : '—') },
    {
      title: '操作', key: 'ops', width: 190,
      render: (_: unknown, r: Holding) => (
        <Space size={4}>
          <Button size="small" type="primary" onClick={() => setDrawerH(r)}>详情/操作</Button>
          <SellDecisionBtn hid={r.id} />
        </Space>
      ),
    },
  ]

  return (
    <>
      <Space style={{ marginBottom: 8 }}>
        <Text type="secondary">行情最后更新：{data?.quote_time ?? '—'}（约 60s 缓存）</Text>
        <Button size="small" onClick={() => refetch()}>刷新行情</Button>
      </Space>
      <Table<Holding> rowKey="id" size="small" columns={cols} dataSource={rows}
        pagination={false} />
      <HoldingDrawer h={drawerH} open={!!drawerH} onClose={() => setDrawerH(null)} />
    </>
  )
}

/** ============ 告警记录 ============ */
function AlertsTab() {
  const { data, isError, error, refetch } = useQuery({ queryKey: ['alerts'], queryFn: () => alerts(50) })
  if (isError) return <ErrorCard title="告警加载失败" message={error?.message} onRetry={() => refetch()} />
  const rows = data ?? []
  if (!rows.length) return <EmptyState text="暂无告警记录。" icon="🛡️" />
  const cols = [
    {
      title: '股票', key: 'stock', width: 150,
      render: (_: unknown, r: (typeof rows)[number]) => <StockLabel code={r.stock_code} name={r.stock_name} />,
    },
    {
      title: '严重度', dataIndex: 'severity', width: 90,
      render: (v: string) => <Tag color={v === 'critical' ? 'red' : v === 'warning' ? 'orange' : 'blue'}>{v}</Tag>,
    },
    { title: '类型', dataIndex: 'alert_type', width: 110 },
    { title: '消息', dataIndex: 'message', ellipsis: true },
    { title: '时间', dataIndex: 'created_at', width: 150, render: (v: string) => String(v).slice(0, 16) },
  ]
  return <Table size="small" rowKey="id" columns={cols} dataSource={rows} pagination={{ pageSize: 20 }} />
}

/** ============ 历史持仓 ============ */
function HistoryTab() {
  const { data, isError, error, refetch } = useQuery({
    queryKey: ['holdings-exited'],
    queryFn: () => holdings('exited'),
  })
  if (isError) return <ErrorCard title="历史持仓加载失败" message={error?.message} onRetry={() => refetch()} />
  const rows = data ?? []
  if (!rows.length) return <EmptyState text="暂无已离场持仓。" icon="📭" />
  const cols = [
    {
      title: '股票', key: 'stock', width: 160,
      render: (_: unknown, r: Holding) => <StockLabel code={r.stock_code} name={r.stock_name} />,
    },
    { title: '建仓日', dataIndex: 'entry_date', width: 100 },
    { title: '股数', dataIndex: 'shares', width: 80 },
    { title: '成本', dataIndex: 'entry_price', width: 90, render: (v: number) => v ?? '—' },
    { title: '备注', dataIndex: 'note', ellipsis: true },
    { title: '离场时间', dataIndex: 'created_at', width: 150, render: (v: string) => String(v).slice(0, 16) },
  ]
  return <Table size="small" rowKey="id" columns={cols} dataSource={rows} pagination={{ pageSize: 20 }} />
}

/** ============ 手动建仓 / OCR 截图 / 账户基线 ============ */
function AddHoldingModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [form] = Form.useForm()
  const add = useMutation({
    mutationFn: (v: Record<string, unknown>) => addHolding(v),
    onSuccess: (r) => {
      message.success(`持仓已保存 ID=${r.id}`)
      form.resetFields()
      qc.invalidateQueries({ queryKey: ['holding-quotes'] })
      onClose()
    },
    onError: (e: Error) => message.error(e.message),
  })
  return (
    <Modal title="录入人工建仓（系统不自动下单）" open={open} onCancel={onClose} footer={null} width={520}>
      <Form form={form} layout="vertical" onFinish={(v) => add.mutate(v)}
        initialValues={{ entry_date: new Date().toISOString().slice(0, 10) }}>
        <Form.Item name="stock_code" label="股票代码 *" rules={[{ required: true, message: '请输入 6 位代码' }]}>
          <Input placeholder="如 603993" maxLength={6} />
        </Form.Item>
        <Form.Item name="stock_name" label="股票名称 *" rules={[{ required: true, message: '请输入名称' }]}>
          <Input />
        </Form.Item>
        <Form.Item name="entry_date" label="建仓日期"><Input placeholder="YYYY-MM-DD" /></Form.Item>
        <Form.Item name="entry_price" label="平均成本价 *" rules={[{ required: true, message: '必填' }]}>
          <InputNumber min={0} step={0.01} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="shares" label="股数 *（100 整数倍）" rules={[{ required: true, message: '必填' }]}>
          <InputNumber min={100} step={100} style={{ width: '100%' }} />
        </Form.Item>
        <Space wrap>
          <Form.Item name="stop_loss" label="止损参考价"><InputNumber min={0} step={0.01} /></Form.Item>
          <Form.Item name="take_profit" label="止盈参考价"><InputNumber min={0} step={0.01} /></Form.Item>
          <Form.Item name="target_pct" label="目标仓位%"><InputNumber min={0} max={100} step={1} /></Form.Item>
        </Space>
        <Form.Item name="note" label="备注"><Input /></Form.Item>
        <Button type="primary" htmlType="submit" loading={add.isPending} block>保存持仓</Button>
      </Form>
    </Modal>
  )
}

function OcrModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message } = App.useApp()
  const [result, setResult] = useState<Array<Record<string, unknown>> | null>(null)
  const { data: status } = useQuery({ queryKey: ['ocr-status'], queryFn: ocrStatus })
  const run = useMutation({
    mutationFn: (f: File) => ocrHolding(f, f.name),
    onSuccess: (r) => {
      setResult(r.recognized ?? [])
      if (!(r.recognized ?? []).length) message.warning('未识别到有效持仓字段')
    },
    onError: (e: Error) => message.error(e.message),
  })
  if (status && !status.enabled) {
    return (
      <Modal title="OCR 截图建仓" open={open} onCancel={onClose} footer={null}>
        <Alert type="info" showIcon message={`OCR 未启用：${status.reason ?? ''}`} />
      </Modal>
    )
  }
  return (
    <Modal title="OCR 截图建仓（识别结果仅供参考，需人工核对）" open={open} onCancel={onClose} footer={null} width={640}>
      <input
        type="file"
        accept="image/png,image/jpeg,image/webp"
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) run.mutate(f)
        }}
      />
      {run.isPending ? <div style={{ padding: 16, textAlign: 'center' }}>OCR 识别中（约 10-30s）…</div> : null}
      {result?.length ? (
        <Table size="small" rowKey={(r) => String(r.stock_code ?? r['股票代码'])} pagination={false}
          dataSource={result}
          columns={Object.keys(result[0]).map((k) => ({
            title: k, dataIndex: k, width: 110,
            render: (v: unknown) => String(v ?? ''),
          }))} />
      ) : null}
    </Modal>
  )
}

function BaselineModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const save = useMutation({
    mutationFn: (v: Record<string, unknown>) => saveAccountBaseline(v),
    onSuccess: () => {
      message.success('账户基准已保存')
      onClose()
    },
    onError: (e: Error) => message.error(e.message),
  })
  return (
    <Modal title="保存账户基准（券商真实值）" open={open} onCancel={onClose} footer={null}>
      <Form form={form} layout="vertical" onFinish={(v) => save.mutate(v)}>
        <Form.Item name="total_asset" label="总资产（元）*" rules={[{ required: true, message: '必填' }]}>
          <InputNumber min={0} step={1000} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="available_cash" label="可用资金（元）"><InputNumber min={0} step={1000} style={{ width: '100%' }} /></Form.Item>
        <Form.Item name="position_pct" label="整体仓位比例（%）"><InputNumber min={0} max={100} step={1} style={{ width: '100%' }} /></Form.Item>
        <Button type="primary" htmlType="submit" loading={save.isPending} block>保存账户基准</Button>
      </Form>
    </Modal>
  )
}

/** ============ 持仓监控页 ============ */
export function HoldingsPage() {
  const { message } = App.useApp()
  const monitorAll = useTaskSubmit('monitor_all', () => message.success('全量监控完成'))
  const sentinel = useTaskSubmit('portfolio_sentinel', () => message.success('组合哨兵巡检完成'))
  const [addOpen, setAddOpen] = useState(false)
  const [ocrOpen, setOcrOpen] = useState(false)
  const [baselineOpen, setBaselineOpen] = useState(false)

  return (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Button type="primary" loading={monitorAll.submit.isPending} onClick={() => monitorAll.submit.mutate({})}>
          立即刷新监控（后台）
        </Button>
        <Button loading={sentinel.submit.isPending} onClick={() => sentinel.submit.mutate({})}>
          运行组合哨兵（组合级风控）
        </Button>
        <Button onClick={() => setAddOpen(true)}>录入人工建仓</Button>
        <Button onClick={() => setOcrOpen(true)}>OCR 截图建仓</Button>
        <Button onClick={() => setBaselineOpen(true)}>账户基线</Button>
      </Space>
      <Tabs
        items={[
          { key: 'hold', label: '当前持仓', children: <HoldingsTable /> },
          { key: 'alert', label: '告警记录', children: <AlertsTab /> },
          { key: 'hist', label: '历史持仓', children: <HistoryTab /> },
        ]}
      />
      <AddHoldingModal open={addOpen} onClose={() => setAddOpen(false)} />
      <OcrModal open={ocrOpen} onClose={() => setOcrOpen(false)} />
      <BaselineModal open={baselineOpen} onClose={() => setBaselineOpen(false)} />
    </div>
  )
}

export default HoldingsPage
