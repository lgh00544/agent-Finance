import { useState } from 'react'
import {
  Alert,
  App,
  Button,
  Card,
  Collapse,
  Descriptions,
  Drawer,
  Form,
  Input,
  InputNumber,
  Modal,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
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
  redLineCheck,
  sellDecisions,
  takeProfitPlan,
} from '@/api/holdings'
import { alerts } from '@/api/alerts'
import { marketIndices } from '@/api/market'
import { ocrHolding, ocrStatus } from '@/api/ocr'
import { saveAccountBaseline } from '@/api/account'
import { useTaskSubmit } from '@/hooks/useTaskSubmit'
import { EmptyState, ErrorCard, StockLabel } from '@/components/common'
import { moneySigned } from '@/utils/format'
import type { Holding } from '@/types'

const { Text } = Typography

// ===== 知识库风控红线（仅前端黄色提示，不阻断；最终以后端为准） =====
const C3_LOSS_PCT = 0.92   // C3 止损 = 成本 × 0.92（永久红线）
const C1_CAP_PCT = 60.0    // C1：总仓位上限
const C2_CAP_PCT = 30.0    // C2：单票仓位上限
const E2_INDEX_BAR = 4000.0 // E2：沪指 < 4000 = 防御期，仓位软上限 20%
const E2_SOFT_CAP = 20.0

const ACTION_MAP: Record<string, string> = {
  hold: '持有', reduce: '减仓', exit: '清仓', partial: '部分减仓', sell: '卖出清仓',
}
const CONF_MAP: Record<string, string> = { high: '高', medium: '中', low: '低' }

/** 涨跌色（中国股市惯例：正红负绿） */
function pnlColor(v: number | null | undefined): string {
  if (v == null) return 'var(--text)'
  return v > 0 ? 'var(--up)' : v < 0 ? 'var(--down)' : 'var(--text)'
}

/** ===== 需求 A：同代码去重合并（纯展示层，数据库原始记录保留） ===== */
export interface MergedRow {
  code: string
  records: Holding[]
  keep: Holding[]
  current: Holding
  total_shares: number
  weighted_price: number | null
}

function dedupeAndMerge(rows: Holding[]): MergedRow[] {
  const groups: Record<string, Holding[]> = {}
  for (const r of rows) {
    groups[r.stock_code] ??= []
    groups[r.stock_code].push(r)
  }
  const merged: MergedRow[] = []
  for (const code of Object.keys(groups)) {
    const items = [...groups[code]].sort((a, b) =>
      String(a.entry_date ?? '').localeCompare(String(b.entry_date ?? '')) ||
      String(a.created_at ?? '').localeCompare(String(b.created_at ?? '')))
    const byDate: Record<string, Holding[]> = {}
    for (const it of items) {
      byDate[it.entry_date ?? ''] ??= []
      byDate[it.entry_date ?? ''].push(it)
    }
    // 同建仓日期重复录入 → 仅保留录入时间最晚一条
    const keep = Object.values(byDate).map((g) =>
      g.reduce((max, x) => (String(x.created_at ?? '') >= String(max.created_at ?? '') ? x : max)))
      .sort((a, b) => String(a.entry_date ?? '').localeCompare(String(b.entry_date ?? '')) ||
        String(a.created_at ?? '').localeCompare(String(b.created_at ?? '')))
    // 当前有效 = 建仓日期最新且录入时间最晚的那笔
    const current = keep[keep.length - 1]
    const total_shares = keep.reduce((s, k) => s + Number(k.shares || 0), 0)
    const weighted_price = total_shares
      ? keep.reduce((s, k) => s + Number(k.entry_price || 0) * Number(k.shares || 0), 0) / total_shares
      : null
    const dupDates = new Set(Object.entries(byDate).filter(([, g]) => g.length > 1).map(([d]) => d))
    const tagged = items.map((it) => ({
      ...it,
      _dedupe_status: it.id === current.id
        ? '当前有效'
        : (it.entry_date ?? '') in dupDates
          ? '重复录入（已自动忽略）'
          : '历史买入',
    }))
    merged.push({ code, records: tagged, keep, current, total_shares, weighted_price })
  }
  merged.sort((a, b) =>
    String(a.current.entry_date ?? '').localeCompare(String(b.current.entry_date ?? '')) ||
    String(a.current.created_at ?? '').localeCompare(String(b.current.created_at ?? '')))
  return merged
}

/** 上证指数（E2 防御期判断；拉取失败返回 null 不阻塞） */
function useShanghaiIndex() {
  const { data } = useQuery({ queryKey: ['market-indices'], queryFn: marketIndices, staleTime: 60_000 })
  const idx = (data?.indices ?? []).find((i) => String(i.name ?? '').includes('上证'))
  return typeof idx?.price === 'number' ? idx.price : null
}

/** 加仓/减仓风控黄色警告（C2/C1/E2；C3 单独处理） */
function positionWarnings(opts: {
  newShares: number
  currentPrice: number | null
  totalCapital: number
  otherMv: number
  shanghai: number | null
}): string[] {
  const { newShares, currentPrice, totalCapital, otherMv, shanghai } = opts
  if (!totalCapital || totalCapital <= 0 || currentPrice == null) return []
  const mv_new = newShares * currentPrice
  const mv_total_new = otherMv + mv_new
  const c2 = mv_new / totalCapital * 100
  const c1 = mv_total_new / totalCapital * 100
  const warns: string[] = []
  if (c2 > C2_CAP_PCT) warns.push(`单票仓位将达 ${c2.toFixed(1)}%，超过 C2 上限 ${C2_CAP_PCT.toFixed(0)}%（C2）`)
  if (c1 > C1_CAP_PCT) warns.push(`总仓位将达 ${c1.toFixed(1)}%，超过 C1 上限 ${C1_CAP_PCT.toFixed(0)}%（C1）`)
  if (shanghai != null && shanghai < E2_INDEX_BAR && c1 > E2_SOFT_CAP) {
    warns.push(`防御期（沪指 ${shanghai.toFixed(0)} < ${E2_INDEX_BAR.toFixed(0)}）仓位软上限 ${E2_SOFT_CAP.toFixed(0)}%，当前预计 ${c1.toFixed(1)}%`)
  }
  return warns
}

/** 操作提交前的 Modal.confirm 二次确认（人工 fail-closed，必含「仅记录，不触发实盘交易」） */
function confirmOp(modal: ReturnType<typeof App.useApp>['modal'], opts: {
  title: string
  warns: string[]
  fieldsText: string
  onOk: () => void
}): void {
  const blocks = [
    ...opts.warns.map((w) => `⚠️ ${w}`),
    `**请核对以下录入信息：**\n${opts.fieldsText}`,
    '⚠️ 仅记录，不触发实盘交易；确认后按知识库规则自动重算风控档位并留痕（K223 可追溯）。',
  ]
  modal.confirm({
    title: opts.title,
    width: 460,
    okText: '确认记录',
    cancelText: '取消',
    onOk: opts.onOk,
    content: <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{blocks.join('\n\n')}</pre>,
  })
}

/** ============ 需求 B：4 种手动持仓操作（按钮组 + 各自 Modal） ============ */
function HoldingOps({ h, currentPrice, totalCapital, otherMv, shanghai }: {
  h: Holding
  currentPrice: number | null
  totalCapital: number
  otherMv: number
  shanghai: number | null
}) {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const [opening, setOpening] = useState<null | 'add' | 'reduce' | 'exit' | 'cost'>(null)
  const [form] = Form.useForm()
  const invalidate = () => qc.invalidateQueries({ queryKey: ['holding-quotes'] })

  const runOp = useMutation({
    mutationFn: (values: Record<string, unknown>) => {
      if (opening === 'add') return holdingAdd(h.id, values)
      if (opening === 'reduce' || opening === 'exit') {
        const close = opening === 'exit'
        return exitHolding(h.id, {
          price: values.price,
          shares: close ? h.shares ?? 0 : values.shares,
          trade_date: values.trade_date,
          note: values.note ?? '',
        })
      }
      return holdingCost(h.id, { cost_price: values.cost_price, reason: values.reason })
    },
    onSuccess: () => {
      message.success('操作已记录，风控档位已自动重算')
      form.resetFields()
      setOpening(null)
      invalidate()
    },
    onError: (e: Error) => message.error(e.message),
  })

  const openOp = (type: 'add' | 'reduce' | 'exit' | 'cost') => {
    form.resetFields()
    form.setFieldsValue({ trade_date: new Date().toISOString().slice(0, 10) })
    setOpening(type)
  }

  const onFinish = (v: Record<string, unknown>) => {
    if (opening === 'add') {
      const cur = currentPrice ?? (typeof h.current_price === 'number' ? h.current_price : null)
      const oldShares = h.shares ?? 0
      const newShares = oldShares + Number(v.shares)
      const newCost = newShares
        ? (Number(h.entry_price || 0) * oldShares + Number(v.price) * Number(v.shares)) / newShares
        : 0
      const warns = [...positionWarnings({
        newShares,
        currentPrice: cur, totalCapital, otherMv, shanghai,
      })]
      // C3 止损红线：成交价低于成本×0.92 时警告
      if (newCost > 0 && Number(v.price) < newCost * C3_LOSS_PCT) {
        warns.push(`成交价 ${Number(v.price)} 低于 C3 止损位（成本 ${newCost.toFixed(2)} × 0.92 = ${(newCost * C3_LOSS_PCT).toFixed(2)}），跌破止损红线加仓（C3）`)
      }
      if ((v.shares as number) % 100 !== 0) { message.warning('加仓股数必须为 100 的整数倍'); return }
      confirmOp(modal, {
        title: `确认加仓（仅记录，不触发实盘交易）`,
        warns,
        fieldsText: `成交价 ${Number(v.price)} × ${Number(v.shares)} 股\n日期 ${String(v.trade_date ?? '')}\n备注 ${String(v.note ?? '') || '（无）'}`,
        onOk: () => runOp.mutate({ price: v.price, shares: v.shares, trade_date: v.trade_date, note: v.note ?? '' }),
      })
    } else if (opening === 'reduce' || opening === 'exit') {
      const close = opening === 'exit'
      const cur = currentPrice ?? (typeof h.current_price === 'number' ? h.current_price : null)
      const sellShares = close ? (h.shares ?? 0) : Number(v.shares)
      const remainShares = (h.shares ?? 0) - sellShares
      const newShares = remainShares
      const warns = [...positionWarnings({
        newShares,
        currentPrice: cur, totalCapital, otherMv, shanghai,
      })]
      if (!close && (v.shares as number) % 100 !== 0) { message.warning('卖出股数必须为 100 的整数倍'); return }
      if (sellShares > (h.shares ?? 0)) { message.warning('卖出股数超过持仓'); return }
      if (close && sellShares !== (h.shares ?? 0)) { message.warning('清仓应卖出全部持仓股数'); return }
      confirmOp(modal, {
        title: close ? '确认清仓（仅记录，不触发实盘交易）' : '确认减仓（仅记录，不触发实盘交易）',
        warns,
        fieldsText: `成交价 ${Number(v.price)} × ${sellShares} 股\n卖出后剩余 ${remainShares} 股\n日期 ${String(v.trade_date ?? '')}\n备注 ${String(v.note ?? '') || '（无）'}`,
        onOk: () => runOp.mutate({ price: v.price, shares: sellShares, trade_date: v.trade_date, note: v.note ?? '' }),
      })
    } else if (opening === 'cost') {
      const warns: string[] = []
      if (Number(v.cost_price) <= 0) { message.warning('请输入正数成本价'); return }
      if (!String(v.reason ?? '').trim()) { message.warning('必须填写修正原因（留痕追溯）'); return }
      confirmOp(modal, {
        title: '确认修正成本（仅记录，不触发实盘交易）',
        warns,
        fieldsText: `修正后成本价 ${Number(v.cost_price)}\n修正原因 ${String(v.reason)}`,
        onOk: () => runOp.mutate({ cost_price: v.cost_price, reason: v.reason }),
      })
    }
  }

  return (
    <>
      <Space wrap style={{ marginBottom: 8 }}>
        <Tag color="blue">持仓 {h.shares ?? 0} 股</Tag>
        <Tag color="cyan">成本 {h.entry_price ?? '—'}</Tag>
        <Tag color="geekblue">现价 {h.current_price ?? '—'}</Tag>
      </Space>
      <Space wrap style={{ marginBottom: 10 }}>
        <Button size="small" type="primary" onClick={() => openOp('add')}>加仓</Button>
        <Button size="small" onClick={() => openOp('reduce')}>减仓</Button>
        <Button size="small" danger onClick={() => openOp('exit')}>清仓</Button>
        <Button size="small" onClick={() => openOp('cost')}>修正成本</Button>
      </Space>
      <Alert type="warning" showIcon style={{ fontSize: 12 }}
        message="以上操作仅记录人工成交结果，系统不自动下单；操作后 C3 止损 / 移动止盈 / +5% / +10% 减仓档位按知识库规则自动重算并留痕（K223 可追溯）。" />

      <Modal title={{
        add: '记录加仓', reduce: '记录减仓', exit: '记录清仓', cost: '修正成本',
      }[opening ?? 'add']} open={!!opening} onCancel={() => setOpening(null)} footer={null} width={460}>
        <Form form={form} layout="vertical" onFinish={onFinish}>
          {opening === 'add' || opening === 'reduce' || opening === 'exit' ? (
            <>
              <Form.Item name="price" label="成交价格 *" rules={[{ required: true, message: '必填' }]}>
                <InputNumber min={0} step={0.01} style={{ width: '100%' }} />
              </Form.Item>
              {opening !== 'exit' ? (
                <Form.Item name="shares" label={opening === 'add' ? '操作股数 *（100 整数倍）' : '减仓股数 *（100 整数倍，≤ 持仓）'}
                  rules={[{ required: true, message: '必填' }]}>
                  <InputNumber min={100} step={100} style={{ width: '100%' }} max={opening === 'reduce' ? (h.shares ?? 0) : undefined} />
                </Form.Item>
              ) : (
                <Form.Item label="清仓股数"><InputNumber value={h.shares ?? 0} disabled style={{ width: '100%' }} /></Form.Item>
              )}
              {opening === 'exit' ? (
                <Form.Item name="note" label="清仓原因"><Input placeholder="可选" /></Form.Item>
              ) : (
                <Form.Item name="note" label="操作备注"><Input placeholder="可选" /></Form.Item>
              )}
            </>
          ) : (
            <>
              <Form.Item name="cost_price" label="修正后成本价 *" rules={[{ required: true, message: '必填' }]}>
                <InputNumber min={0} step={0.01} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item name="reason" label="修正原因 *（必填留痕）" rules={[{ required: true, message: '必填' }]}>
                <Input />
              </Form.Item>
            </>
          )}
          <Form.Item name="trade_date" label="日期" initialValue={new Date().toISOString().slice(0, 10)}>
            <Input type="date" style={{ width: '100%' }} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={runOp.isPending} block>
            提交（仅记录，不触发实盘交易）
          </Button>
        </Form>
      </Modal>
    </>
  )
}

/** 卖出前检查红黄状态（检查清单项目色） */
function checkColor(it: string | { label?: string; ok?: boolean }): string {
  if (typeof it !== 'object' || it == null || (it as { ok?: boolean }).ok === undefined) return 'var(--text)'
  return (it as { ok: boolean }).ok ? 'var(--ok)' : 'var(--err)'
}

/** 卖出决策完整渲染（需求 C：render_sell_decision 结构） */
function SellDecisionDetail({ d, shares }: { d: Record<string, unknown>; shares: number }) {
  const action = ACTION_MAP[String(d.action ?? '')] ?? String(d.action ?? '—')
  const conf = CONF_MAP[String(d.confidence ?? '')] ?? String(d.confidence ?? '—')
  const reduceRatio = Number(d.reduce_ratio)
  const dims = (d.dimensions as Array<Record<string, unknown>>) ?? []
  const reasons = (d.reasons as string[]) ?? []
  const checkList = (d.check_list as Array<string | { label?: string; ok?: boolean }>) ?? []
  const isPartial = d.action === 'partial' && !Number.isNaN(reduceRatio) && reduceRatio > 0 && reduceRatio <= 1 && shares > 0
  // 100 股向上取整，不超持仓
  let sellShares = 0
  let remainShares = 0
  if (isPartial) {
    sellShares = Math.ceil((shares * reduceRatio) / 100) * 100
    if (sellShares < 100) sellShares = 100
    if (sellShares > shares) sellShares = shares
    remainShares = shares - sellShares
  }

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Text strong>卖出决策：{action}</Text>
        <Tag style={{ marginLeft: 8 }} color="blue">置信度 {conf}</Tag>
      </div>

      {isPartial ? (
        <Card size="small" style={{ marginBottom: 8, background: 'var(--bg-input)' }}>
          <div><Text strong>建议减仓：{Math.round(reduceRatio * 100)}%</Text>
            <Text type="secondary">（约 {sellShares.toLocaleString()} 股 / {Math.floor(sellShares / 100)} 手）</Text>
          </div>
          <div style={{ marginTop: 4 }}>
            当前持仓 {shares.toLocaleString()} 股 → 建议卖出 {sellShares.toLocaleString()} 股 →
            减仓后剩余 {remainShares.toLocaleString()} 股（{Math.floor(remainShares / 100)} 手）
          </div>
        </Card>
      ) : null}

      {dims.length ? (
        <Card size="small" title="维度归因" style={{ marginBottom: 8, background: 'var(--bg-input)' }}>
          {dims.map((dm) => {
            const score = Number(dm.score ?? 0)
            const verdict = String(dm.verdict ?? '')
            const color = verdict === '支持' ? 'var(--up)' : verdict === '风险' ? 'var(--warn)' : 'var(--text-mute)'
            return (
              <div key={String(dm.dim)} style={{ marginBottom: 6 }}>
                <Space>
                  <Text style={{ width: 100, fontWeight: 600 }}>{String(dm.dim ?? '维度')}</Text>
                  <div className="conf-bar" style={{ width: 180 }}>
                    <div className="conf-bar-fill high" style={{ width: `${Math.max(0, Math.min(100, score))}%`, background: color }} />
                  </div>
                  <Text type="secondary">{score.toFixed(0)}</Text>
                  {verdict ? <Tag>{verdict}</Tag> : null}
                </Space>
                {dm.advice ? <div style={{ marginLeft: 108 }}><Text type="secondary">{String(dm.advice)}</Text></div> : null}
              </div>
            )
          })}
          {d.final_advice ? (
            <Alert type="info" showIcon style={{ marginTop: 6 }} message={String(d.final_advice)} />
          ) : null}
        </Card>
      ) : d.final_advice ? (
        <Alert type="info" showIcon style={{ marginBottom: 8 }} message={String(d.final_advice)} />
      ) : null}

      {reasons.length ? (
        <div style={{ marginBottom: 8 }}>
          <Text strong>研判依据：</Text>
          {reasons.map((r, i) => <div key={i} style={{ marginLeft: 12 }}>{i + 1}. {r}</div>)}
        </div>
      ) : null}

      {d.exit_price_zone ? (
        <div style={{ marginBottom: 8 }}><Text strong>卖出价位区间：</Text>{String(d.exit_price_zone)}</div>
      ) : null}
      {d.risk_warning ? (
        <div style={{ marginBottom: 8 }}><Text strong>风险提示：</Text><Text type="danger">{String(d.risk_warning)}</Text></div>
      ) : null}

      {checkList.length ? (
        <div>
          <Text strong>卖出前检查清单：</Text>
          {checkList.map((it, i) => {
            const label = typeof it === 'string' ? it : String(it.label ?? '')
            const ok = typeof it === 'object' && it != null ? (it as { ok?: boolean }).ok : undefined
            return <div key={i} style={{ marginLeft: 12, color: checkColor(it) }}>{ok != null ? (ok ? '✅' : '⚠️') : '-'} {label}</div>
          })}
        </div>
      ) : null}
    </div>
  )
}

/** ============ 卖出决策历史（折叠区，每条可展开完整渲染） ============ */
function SellDecisionHistory({ hid, shares }: { hid: number; shares: number }) {
  const { data: hist } = useQuery({
    queryKey: ['sell-decisions', hid],
    queryFn: () => sellDecisions(hid),
  })
  const items = ((hist ?? []) as Array<Record<string, unknown>>).slice(0, 10).map((s, i) => {
    const d = (s.decision as Record<string, unknown>) ?? {}
    const action = ACTION_MAP[String(d.action ?? '')] ?? String(d.action ?? '—')
    const conf = CONF_MAP[String(d.confidence ?? '')] ?? String(d.confidence ?? '—')
    return {
      key: String(s.id ?? i),
      label: (
        <Space>
          <Text strong>【{action}】</Text>
          <Text type="secondary">置信 {conf}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{String(s.created_at ?? '').slice(0, 16)}</Text>
        </Space>
      ),
      children: <SellDecisionDetail d={d} shares={shares} />,
    }
  })
  if (!items.length) return <Text type="secondary">（暂无卖出决策）</Text>
  return <Collapse ghost size="small" items={items} />
}

/** ============ 详情抽屉：操作 + 流水 + 止盈计划 + 卖出决策历史 ============ */
function HoldingDrawer({ h, open, onClose, totalCapital, otherMv, shanghai }: {
  h: Holding | null
  open: boolean
  onClose: () => void
  totalCapital: number
  otherMv: number
  shanghai: number | null
}) {
  const { data: trades } = useQuery({
    queryKey: ['holding-trades', h?.id],
    queryFn: () => holdingTrades(h!.id),
    enabled: !!h,
  })
  const { data: tpPlans } = useQuery({ queryKey: ['take-profit-plan'], queryFn: () => takeProfitPlan() })
  const tp = (tpPlans?.rows ?? []).find((p) => p.holding_id === h?.id)
  if (!h) return null
  return (
    <Drawer title={<StockLabel code={h.stock_code} name={h.stock_name} />} open={open} onClose={onClose} width={600}>
      <HoldingOps h={h} currentPrice={h.current_price ?? null} totalCapital={totalCapital}
        otherMv={otherMv} shanghai={shanghai} />
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
              <Tag color={t.side === 'buy' ? 'green' : t.side === 'sell' ? 'red' : 'blue'}>{String(t.side)}</Tag>
              {String(t.shares)} 股 @ {String(t.price)} · {String(t.trade_date ?? '')}
              {t.note ? <Text type="secondary">（{String(t.note)}）</Text> : null}
            </div>
          ))
        ) : (
          <Text type="secondary">（暂无操作流水）</Text>
        )}
      </Card>
      <Card size="small" title="卖出决策历史（仅供参考，卖出由人工执行）" style={{ marginTop: 12, background: 'var(--bg-input)' }}>
        <SellDecisionHistory hid={h.id} shares={h.shares ?? 0} />
      </Card>
    </Drawer>
  )
}

/** ============ 卖出决策两步确认（需求 C 入口） ============ */
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

/** 红线徽章（批次G）：C1/C2/C3/K139 四色——绿(无)/黄(预警)/红(触发)/灰(无数据)；悬停显示触发条件 */
function RedLineBadges({ red, price }: { red?: Record<string, unknown>; price: number | null | undefined }) {
  const badge = (label: string, color: string, tip: string) => (
    <Tooltip title={tip}>
      <Tag color={color} style={{ marginInlineEnd: 2, fontSize: 11 }}>{label}</Tag>
    </Tooltip>
  )
  const c1 = red?.c1_alert as boolean | null | undefined
  const c2 = red?.c2_alert as boolean | null | undefined
  const c3 = red?.c3_alert as boolean | null | undefined
  const k139 = (red?.k139_sop as Record<string, unknown>) ?? null
  const cap = red?.c1_cap_pct as number | null | undefined
  const draw = red?.c2_drawdown_pct as number | null | undefined
  const sl = red?.c3_stop_loss as number | null | undefined
  const stage = String(k139?.stage ?? '')
  const ts = k139?.trailing_stop as number | null | undefined
  const c3dist = (typeof price === 'number' && typeof sl === 'number' && sl > 0)
    ? ((price - sl) / sl * 100).toFixed(1) : null
  const colorOf = (v: boolean | null | undefined) => (v === true ? 'red' : v === false ? 'green' : 'default')
  const k139Color = stage === '跌破C3' ? 'red' : stage.includes('减仓') ? 'orange' : stage ? 'green' : 'default'
  return (
    <Space size={2} wrap>
      {badge('C1', colorOf(c1), cap != null ? `C1 单只占比 ${cap}%，上限 60%（超限触发）` : 'C1 占比无数据')}
      {badge('C2', colorOf(c2), draw != null ? `C2 日内回撤 ${draw}%，触发线 -30%（相对成本）` : 'C2 回撤无数据')}
      {badge('C3', colorOf(c3), sl != null ? `C3 止损 ${sl}，距 ${c3dist ?? '—'}%（成本×0.92）` : 'C3 止损无数据')}
      {badge('K139', k139Color, k139 ? `K139 SOP：${stage}，移动止盈 ${ts ?? '—'}` : 'K139 SOP 无数据')}
    </Space>
  )
}

/** ============ 当前持仓表（需求 A：去重合并） ============ */
function HoldingsTable() {
  const [drawerH, setDrawerH] = useState<Holding | null>(null)
  const { data, isError, error, refetch } = useQuery({
    queryKey: ['holding-quotes'],
    queryFn: holdingQuotes,
    refetchInterval: 60_000,
  })
  const { data: redData } = useQuery({
    queryKey: ['red-line-check'],
    queryFn: redLineCheck,
    refetchInterval: 300_000,
  })
  const redMap = new Map<string, Record<string, unknown>>(
    (redData?.rows ?? []).map((r) => [String(r.stock_code), r]))
  const shanghai = useShanghaiIndex()
  const rows = data?.rows ?? []
  if (isError) return <ErrorCard title="持仓数据加载失败" message={error?.message} onRetry={() => refetch()} />
  if (!rows.length) return <EmptyState text="暂无持仓。可通过「录入人工建仓」创建。" icon="📭" />

  const merged = dedupeAndMerge(rows)
  const totalCapital = data?.total_capital ?? 0
  const totalAllMv = merged.reduce((s, m) => s + (m.current.market_value ?? 0), 0)

  const cols: Record<string, unknown>[] = [
    {
      title: '股票', key: 'stock', width: 150,
      render: (_: unknown, m: MergedRow) => <StockLabel code={m.code} name={m.current.stock_name} />,
    },
    {
      title: '建仓日', key: 'entry', width: 96,
      render: (_: unknown, m: MergedRow) => String(m.current.entry_date ?? '—'),
    },
    {
      title: '总股数', key: 'shares', width: 88,
      render: (_: unknown, m: MergedRow) => <Text strong>{(m.total_shares ?? 0).toLocaleString()}</Text>,
    },
    {
      title: '加权成本', key: 'cost', width: 90,
      render: (_: unknown, m: MergedRow) => m.weighted_price != null ? m.weighted_price.toFixed(2) : '—',
    },
    {
      title: '现价', key: 'price', width: 88,
      render: (_: unknown, m: MergedRow) => (
        <Text style={{ color: pnlColor(m.current.current_price) }}>{m.current.current_price ?? '—'}</Text>
      ),
    },
    {
      title: '盈亏', key: 'pnl', width: 150,
      render: (_: unknown, m: MergedRow) => {
        const p = m.current.current_price
        if (p == null || m.weighted_price == null) return '—'
        const amt = (Number(p) - m.weighted_price) * (m.total_shares ?? 0)
        const pctv = m.weighted_price > 0 ? (Number(p) - m.weighted_price) / m.weighted_price * 100 : 0
        return <Text style={{ color: pnlColor(amt) }}>{moneySigned(amt)}（{pctv >= 0 ? '+' : ''}{pctv.toFixed(2)}%）</Text>
      },
    },
    { title: '止损', key: 'sl', width: 76, render: (_: unknown, m: MergedRow) => m.current.stop_loss ?? '—' },
    { title: '止盈', key: 'tp', width: 76, render: (_: unknown, m: MergedRow) => m.current.take_profit ?? '—' },
    { title: '目标仓位', key: 'target', width: 88, render: (_: unknown, m: MergedRow) => (m.current.target_pct ? `${m.current.target_pct}%` : '—') },
    {
      title: '红线', key: 'redline', width: 160,
      render: (_: unknown, m: MergedRow) => (
        <RedLineBadges red={redMap.get(m.code)} price={m.current.current_price ?? null} />
      ),
    },
    {
      title: '操作', key: 'ops', width: 190,
      render: (_: unknown, m: MergedRow) => (
        <Space size={4}>
          <Button size="small" type="primary" onClick={() => setDrawerH(m.current)}>详情/操作</Button>
          <SellDecisionBtn hid={m.current.id} />
        </Space>
      ),
    },
  ]

  return (
    <>
      <Space style={{ marginBottom: 8 }} wrap>
        <Text type="secondary">行情最后更新：{data?.quote_time ?? '—'}（约 60s 缓存）</Text>
        <Button size="small" onClick={() => refetch()}>刷新行情</Button>
      </Space>
      <Table<MergedRow> rowKey={(m) => m.code} size="small" columns={cols} dataSource={merged}
        pagination={false}
        expandable={{
          expandedRowRender: (m) => (
            <Card size="small" title={`历史笔次（${m.records.length}，可审计）`} style={{ background: 'var(--bg-input)' }}>
              {m.records.map((it) => (
                <div key={it.id} style={{ fontSize: 13, marginBottom: 4 }}>
                  <Tag color={it._dedupe_status === '当前有效' ? 'green' : it._dedupe_status === '重复录入（已自动忽略）' ? 'orange' : 'default'}>
                    {String(it._dedupe_status ?? '')}
                  </Tag>
                  {String(it.entry_date ?? '')} · {it.entry_price ?? '—'} 元 · {Number(it.shares ?? 0).toLocaleString()} 股
                  {it.created_at ? <Text type="secondary">（录入 {String(it.created_at).slice(0, 16)}）</Text> : null}
                </div>
              ))}
            </Card>
          ),
        }} />
      <HoldingDrawer h={drawerH} open={!!drawerH} onClose={() => setDrawerH(null)}
        totalCapital={totalCapital}
        otherMv={totalAllMv - (drawerH?.market_value ?? 0)}
        shanghai={shanghai} />
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
