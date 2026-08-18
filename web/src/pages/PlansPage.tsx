import { useState } from 'react'
import {
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
import type { PositionPlan } from '@/types'

const { Text } = Typography

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  proposed: { label: '待评估', color: 'orange' },
  accepted: { label: '已采纳', color: 'green' },
  abandoned: { label: '已放弃', color: 'default' },
}
const GRADE_TONE: Record<string, string> = { A: 'red', B: 'orange', C: 'blue' }
const SOURCE_LABEL: Record<string, string> = { candidate: '每日候选池', manual: '手动生成' }

/** 计划详情展开：仓位分配 + 分档买入 + 止盈止损 + 建仓逻辑 + 生成依据 */
function PlanExpand({ p }: { p: PositionPlan }) {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const detail = (p.detail ?? {}) as Record<string, unknown>
  const quant = (detail.quant ?? {}) as Record<string, unknown>
  const batches = (quant.batches as Array<Record<string, unknown>>) ?? []
  const grade = (detail.grade as string) ?? '—'

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

      {grade !== '—' ? (
        <Card size="small" title="生成依据（评级依据）" style={{ background: 'var(--bg-input)' }}>
          <div>综合评级：<Tag color={GRADE_TONE[grade] ?? 'default'}>{grade} 级</Tag>
            {quant.confidence != null ? ` 置信 ${String(quant.confidence)}` : ''}
          </div>
        </Card>
      ) : null}
    </div>
  )
}

/** 新建建仓方案弹窗（候选池选择 / 手动输入） */
function NewPlanModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const { data: candRows } = useQuery({ queryKey: ['candidates'], queryFn: () => candidates(undefined, 50) })
  const { data: scoreMap } = useQuery({ queryKey: ['scores-all'], queryFn: () => scores(undefined, undefined, 500) })
  const gen = useTaskSubmit('position', () => {
    message.success('建仓方案生成任务已提交后台')
    form.resetFields()
    onClose()
  })
  const gradeOf = (code: string) => (scoreMap ?? []).find((s) => s.stock_code === code)?.grade

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
  const [newOpen, setNewOpen] = useState(false)

  const { data: rows, isError, error, refetch } = useQuery({ queryKey: ['plans'], queryFn: () => plans(undefined, 200) })

  if (isError) return <ErrorCard title="建仓计划加载失败" message={error?.message} onRetry={() => refetch()} />
  const shown = (rows ?? []).filter((p) => status === '全部' || STATUS_MAP[p.status ?? '']?.label === status)
  if (!shown.length) return <EmptyState text="暂无建仓方案。可点击「新建建仓方案」生成。" icon="🧭" />

  const cols = [
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

  return (
    <div>
      <Space style={{ marginBottom: 10 }} wrap>
        <Select value={status} onChange={(v) => setStatus(v)} style={{ width: 120 }}
          options={['全部', '待评估', '已采纳', '已放弃'].map((s) => ({ label: s, value: s }))} />
        <Button type="primary" onClick={() => setNewOpen(true)}>新建建仓方案</Button>
        <Button onClick={() => refetch()}>刷新</Button>
        <Text type="secondary">共 {shown.length} 条计划 · 仅 B 级及以上标的可生成（后端强校验）</Text>
      </Space>
      <Table<PositionPlan>
        rowKey="id" size="small" dataSource={shown} columns={cols}
        pagination={{ pageSize: 20 }}
        expandable={{ expandedRowRender: (p) => <PlanExpand p={p} /> }}
      />
      <NewPlanModal open={newOpen} onClose={() => setNewOpen(false)} />
    </div>
  )
}

export default PlansPage
