import { useEffect, useMemo, useState } from 'react'
import {
  App,
  Alert,
  Button,
  Card,
  Collapse,
  Input,
  Modal,
  Segmented,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { candidateConcentration, candidateDates, candidateTradeable, candidates, stockNames } from '@/api/candidates'
import { trackVerifyStats } from '@/api/track'
import { traces, traceDetail } from '@/api/traces'
import { useTaskSubmit } from '@/hooks/useTaskSubmit'
import { EmptyState, StatCard, StatCardGrid, StockLabel } from '@/components/common'
import { applyBatchAdjust, batchMetaByAssistantId, chatHistory } from '@/api/chat'
import type { BatchAskResult, Candidate } from '@/types'

const { Text } = Typography

const TIER_MAP: Record<string, string> = { 强烈推荐: 'A', 建议关注: 'B', 谨慎观察: 'C' }
const TIER_DOT: Record<string, string> = { A: 'red', B: 'orange', C: 'blue' }
const LABEL_COLORS: Record<string, string> = {
  '可建仓': 'green',
  '建议关注': 'blue',
  '观察': 'default',
}

const SCOPE_LABELS: Record<string, string> = {
  all: '全部候选',
  tradeable: '仅可建仓',
  A: '仅 A 级',
  B: '仅 B 级',
  C: '仅 C 级',
  manual: '手动勾选',
}

const QUICK_QUESTIONS = [
  { key: 'abs', label: '吸筹逻辑是否合理', q: '这批候选的吸筹逻辑是否合理？吸筹阶段是否真实，有无明显分歧或证伪点？' },
  { key: 'risk', label: '共性风险', q: '这批候选存在哪些共性风险？请重点提示需要人工复核的高风险项。' },
  { key: 'tier', label: '评级松紧', q: '当前评级（A/B/C）松紧是否合理？是否有评级与质量明显不匹配的标的？' },
  { key: 'miss', label: '遗漏优质标的', q: '这批候选中是否遗漏了值得提升关注度的优质标的？' },
]

/** 文本区块：空值/缺失显示占位提示 */
function TextBlock({ value, placeholder = '（该轮未输出）' }: { value?: unknown; placeholder?: string }) {
  const s = String(value ?? '').trim()
  if (!s) return <Text type="secondary">{placeholder}</Text>
  return <div style={{ whiteSpace: 'pre-wrap' }}>{s}</div>
}

/** 候选行展开详情：8 个 Tab（维度归因默认激活） */
function CandidateExpand({ c }: { c: Candidate }) {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const detail = (c.detail ?? {}) as Record<string, unknown>
  const dims = (detail.dimensions as Array<Record<string, unknown>>) ?? []
  const reasons = c.reasons ?? []
  const risks = (detail.risks as string[]) ?? []
  const riskNotice = c.risk_notice ?? []

  const gen = useTaskSubmit('position', () => {
    message.success('建仓方案生成任务已提交后台')
    qc.invalidateQueries({ queryKey: ['plans'] })
  })

  const tier = TIER_MAP[String(detail.confidence_tier ?? '')] ?? ''

  // 各 Tab 内容块
  const dimsTab = (
    <div>
      {(dims as Array<Record<string, unknown>>).length ? (
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
      {detail.final_advice ? (
        <Alert type="info" showIcon style={{ marginTop: 6 }} message={String(detail.final_advice)} />
      ) : null}
    </div>
  )

  const reasonsTab = reasons.length ? (
    reasons.map((r, i) => <div key={i} style={{ marginBottom: 4 }}>{i + 1}. {r}</div>)
  ) : (
    <EmptyState text="暂无候选理由。" icon="📝" />
  )

  const riskTab = (
    <div>
      {risks.map((r, i) => <div key={`r${i}`} style={{ marginBottom: 4 }}>⚠️ {r}</div>)}
      {riskNotice.map((r, i) => <div key={`n${i}`} style={{ marginBottom: 4 }}>⚠️ {r}</div>)}
      {(!risks.length && !riskNotice.length) ? <EmptyState text="暂无风险提示。" icon="🛡️" /> : null}
    </div>
  )

  const opTab = (
    <div>
      {detail.stock_type || detail.focus_type ? (
        <div style={{ marginBottom: 8 }}>
          <Tag>标的类型：{String(detail.stock_type ?? '未评级')}</Tag>
          <Tag>关注类型：{String(detail.focus_type ?? '—')}</Tag>
        </div>
      ) : null}
      <TextBlock value={detail.position_hint} placeholder="（本轮未输出操作建议）" />
    </div>
  )

  const verifyTab = (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Text strong>宏观：</Text> <TextBlock value={detail.macro_view} />
      </div>
      <div style={{ marginBottom: 8 }}>
        <Text strong>中观：</Text> <TextBlock value={detail.meso_view} />
      </div>
      <div>
        <Text strong>微观：</Text> <TextBlock value={detail.micro_view} />
      </div>
    </div>
  )

  const items = [
    { key: 'dims', label: '维度归因', children: dimsTab },
    { key: 'reasons', label: '候选理由', children: reasonsTab },
    {
      key: 'tech',
      label: '技术面',
      children: <TextBlock value={detail.tech_view || detail.meso_view} placeholder="（该轮未输出技术面研判）" />,
    },
    {
      key: 'volume',
      label: '量价资金',
      children: <TextBlock value={detail.volume_analysis} placeholder="（该轮未输出量价与资金结论）" />,
    },
    {
      key: 'levels',
      label: '关键价位',
      children: <TextBlock value={detail.price_levels} placeholder="（该轮未输出关键价位）" />,
    },
    { key: 'risks', label: '风险点', children: riskTab },
    { key: 'ops', label: '操作建议', children: opTab },
    { key: 'verify', label: '三维验证', children: verifyTab },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 10 }}>
        {tier ? <Tag color={TIER_DOT[tier]}>{tier} 级</Tag> : null}
        <Tag>{String(detail.stock_type ?? '未评级')}</Tag>
        <Button
          size="small"
          type="primary"
          loading={gen.submit.isPending}
          onClick={() => gen.submit.mutate({ stock_code: c.stock_code, stock_name: c.stock_name ?? '' })}
        >
          生成建仓方案
        </Button>
      </Space>
      <Tabs defaultActiveKey="dims" size="small" items={items} />
    </div>
  )
}

/** AI 研判留痕弹窗 */
function TraceModal({ code, date, open, onClose }: { code: string; date: string; open: boolean; onClose: () => void }) {
  const { data: rows } = useQuery({
    queryKey: ['traces', code, date],
    queryFn: () => traces(code, date),
    enabled: open,
  })
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)
  const openDetail = (id: number) => traceDetail(id).then(setDetail)
  return (
    <Modal title={`AI 研判留痕：${code}`} open={open} onCancel={() => { setDetail(null); onClose() }} footer={null} width={640}>
      {detail ? (
        <div>
          <Button size="small" onClick={() => setDetail(null)}>← 返回列表</Button>
          <pre style={{ background: 'var(--bg-input)', padding: 12, borderRadius: 6, whiteSpace: 'pre-wrap', fontSize: 12, marginTop: 8 }}>
            {JSON.stringify(detail, null, 2)}
          </pre>
        </div>
      ) : rows?.length ? (
        rows.map((t) => (
          <Card key={t.trace_id} size="small" style={{ marginBottom: 8, background: 'var(--bg-input)' }}>
            <Space wrap>
              <Tag color="blue">{String(t.source_module ?? '—')}</Tag>
              <Text type="secondary">{String(t.create_time ?? '').slice(0, 16)}</Text>
              <Button size="small" onClick={() => openDetail(t.trace_id)}>查看详情</Button>
            </Space>
            <div style={{ fontSize: 13, marginTop: 4 }}>{String(t.final_conclusion ?? '').slice(0, 120)}</div>
          </Card>
        ))
      ) : (
        <EmptyState text="该标的本交易日暂无留痕记录。" icon="🔍" />
      )}
    </Modal>
  )
}

/** 批量验证对话：结果分段展示 + 调整方案确认生效 + 历史记录（页面底部折叠面板） */
function BatchVerifyPanel({ date, dayRows }: { date?: string; dayRows: Candidate[] }) {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const [scope, setScope] = useState('all')
  const [codes, setCodes] = useState<string[]>([])
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<BatchAskResult | null>(null)

  // 结果完整 meta（共性/差异/建议/调整方案）按 assistant_msg_id 回查
  const { data: meta } = useQuery({
    queryKey: ['batch-meta', result?.assistant_msg_id ?? ''],
    queryFn: () => batchMetaByAssistantId(result?.assistant_msg_id),
    enabled: !!result?.assistant_msg_id,
  })

  // 历史记录：最近 10 条批量问答
  const { data: history = [], refetch: refetchHistory } = useQuery({
    queryKey: ['batch-history'],
    queryFn: () => chatHistory('discover', 10, 'batch'),
  })

  const batch = useTaskSubmit('batch_ask', (res) => {
    message.success('批量验证完成')
    setResult((res as BatchAskResult) ?? null)
    qc.invalidateQueries({ queryKey: ['batch-history'] })
  })
  // 提交成功后回显任务 ID（后台处理中，完成后自动展示）
  useEffect(() => {
    if (batch.submit.data?.task_id) {
      message.info(`已提交批量验证任务（${batch.submit.data.task_id}）`)
    }
  }, [batch.submit.data?.task_id, message])

  const apply = async (bid?: number) => {
    if (!bid) return
    try {
      const res = await applyBatchAdjust(bid)
      message.success(`已生效 ${(res as { count?: number }).count ?? 0} 条调整，可回滚`)
      setResult(null)
      refetchHistory()
    } catch (e) {
      message.warning(e instanceof Error ? e.message : '确认生效失败，可稍后重试')
    }
  }
  const confirmApply = (bid?: number) => {
    if (!bid) return
    modal.confirm({
      title: '确认生效（人工确认）',
      content: '确认后调整方案将写入候选覆盖（覆盖展示层判定），覆盖后仍可回滚。此操作会改变候选评级与标签。',
      okText: '确认生效',
      cancelText: '取消',
      onOk: () => apply(bid),
    })
  }

  const validCodes = useMemo(() => {
    if (scope !== 'manual') return []
    const max = 20
    return codes.slice(0, max)
  }, [scope, codes])

  const submit = () => {
    if (!question || !question.trim()) {
      message.warning('问题不能为空，请输入批量验证问题')
      return
    }
    if (scope === 'manual' && !validCodes.length) {
      message.warning('手动范围需至少勾选 1 只候选')
      return
    }
    batch.submit.mutate({ scope, codes: validCodes, question: question.trim(), date: date ?? '' })
  }
  const quickAsk = (q: string) => {
    setQuestion(q)
    if (!q.trim()) return
    if (scope === 'manual' && !validCodes.length) {
      message.warning('手动范围需至少勾选 1 只候选后再提问')
      return
    }
    batch.submit.mutate({ scope, codes: validCodes, question: q.trim(), date: date ?? '' })
  }

  const taskPending = batch.submit.isPending || (batch.poll.data && ['pending', 'running'].includes(batch.poll.data.status))
  const taskFailed = batch.poll.data?.status === 'failed'

  const plan = (meta?.adjust_plan as Array<Record<string, unknown>>) ?? []
  const bid = Number(result?.batch_id ?? 0)
  const hasPlan = bid > 0 && plan.length > 0
  const nameMap = useMemo(() => {
    const m: Record<string, string> = {}
    for (const r of dayRows) {
      if (r.stock_code) m[r.stock_code] = r.stock_name ?? r.stock_code
    }
    return m
  }, [dayRows])

  const historyItems = (history ?? []).slice(0, 10).map((h, i) => ({
    key: String(h.id ?? i),
    label: (
      <Space>
        <Tag color={h.role === 'assistant' ? 'blue' : 'default'}>{h.role === 'assistant' ? '回答' : '提问'}</Tag>
        <Text>{String(h.question ?? h.content ?? '').slice(0, 60) || '批量验证'}</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>{String(h.created_at ?? '').slice(0, 16)}</Text>
      </Space>
    ),
    children: (
      <div>
        {h.role === 'assistant' && (h.meta as Record<string, unknown>)?.common_points ? (
          <>
            <Text type="secondary">整体结论：</Text>
            <div style={{ whiteSpace: 'pre-wrap', marginBottom: 8 }}>{String(h.content ?? '')}</div>
            {['common_points', 'differences', 'suggestions'].map((k) => {
              const items = ((h.meta as Record<string, unknown>)?.[k] as string[]) ?? []
              return items.length ? (
                <div key={k} style={{ marginBottom: 4 }}>
                  <Text strong>{k === 'common_points' ? '共性' : k === 'differences' ? '差异' : '建议'}：</Text>
                  {items.map((it, j) => <div key={j}>- {it}</div>)}
                </div>
              ) : null
            })}
          </>
        ) : (
          <Text type="secondary">{String(h.content ?? '（无内容）')}</Text>
        )}
      </div>
    ),
  }))

  return (
    <Collapse
      style={{ marginTop: 16 }}
      items={[{
        key: 'batch',
        label: '批量验证对话（一次提问，统一研判所选范围候选）',
        children: (
          <div>
            <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
              按所选范围注入候选上下文（最多 20 只）；回答按「整体结论 / 共性 / 差异 / 建议」总分结构，
              调整方案需人工「确认生效」后才写入候选覆盖，可回滚留痕。
            </Typography.Paragraph>

            <Space wrap style={{ marginBottom: 10 }}>
              <Select
                style={{ width: 140 }}
                value={scope}
                onChange={(v) => { setScope(String(v)); setCodes([]) }}
                options={Object.entries(SCOPE_LABELS).map(([v, label]) => ({ value: v, label }))}
              />
              {scope === 'manual' ? (
                <Select
                  mode="multiple"
                  style={{ minWidth: 320, maxWidth: 520 }}
                  placeholder="手动勾选标的（最多 20 只）"
                  value={codes}
                  onChange={(v) => setCodes((v as string[]).slice(0, 20))}
                  optionFilterProp="label"
                  options={dayRows.map((r) => ({ value: r.stock_code, label: `${r.stock_name ?? r.stock_code}（${r.stock_code}）` }))}
                />
              ) : null}
            </Space>

            <Space wrap style={{ marginBottom: 10 }}>
              {QUICK_QUESTIONS.map((qq) => (
                <Button key={qq.key} size="small" loading={taskPending} onClick={() => quickAsk(qq.q)}>
                  {qq.label}
                </Button>
              ))}
            </Space>

            <Space.Compact block style={{ marginBottom: 10 }}>
              <Input.TextArea
                rows={2}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="验证问题（多行；可改用上方快捷提问），如：这批候选当前是否适合分批建仓？优先顺序如何？"
              />
              <Button type="primary" loading={taskPending} onClick={submit} style={{ minWidth: 120 }}>
                提交批量验证
              </Button>
            </Space.Compact>

            {taskPending ? (
              <Alert type="info" showIcon style={{ marginTop: 10 }}
                message={`批量验证处理中（任务 ${batch.poll.data?.task_id ?? ''}），完成后自动展示……`} />
            ) : taskFailed ? (
              <Alert type="error" showIcon style={{ marginTop: 10 }}
                message="批量验证失败" description={String(batch.poll.data?.error ?? '后台处理未完成，可重新提交')} />
            ) : null}

            {result ? (
              <Card size="small" style={{ marginTop: 12, background: 'var(--bg-input)' }}>
                <div style={{ marginBottom: 8 }}>
                  <Text strong>整体结论</Text>
                  <Text type="secondary" style={{ marginLeft: 8 }}>
                    （范围：{SCOPE_LABELS[result.scope ?? ''] ?? result.scope ?? '—'} · 注入 {result.count ?? 0} 只 · 信心 {result.confidence ?? 0}/100）
                  </Text>
                </div>
                <div style={{ whiteSpace: 'pre-wrap', marginBottom: 8 }}>{result.answer || '（无结论输出）'}</div>
                {[
                  { title: '共性分析', key: 'common_points' },
                  { title: '差异说明', key: 'differences' },
                  { title: '调整建议', key: 'suggestions' },
                ].map((sec) => {
                  const items = ((meta as Record<string, unknown>)?.[sec.key] as string[]) ?? []
                  return items.length ? (
                    <div key={sec.key} style={{ marginTop: 6 }}>
                      <Text strong>{sec.title}</Text>
                      {items.map((it, j) => <div key={j} style={{ marginLeft: 12 }}>- {it}</div>)}
                    </div>
                  ) : null
                })}
                {result.sources ? (
                  <div style={{ marginTop: 8, fontSize: 12 }}>
                    <Text type="secondary">依据来源：{String(result.sources)}</Text>
                  </div>
                ) : null}
                {hasPlan ? (
                  <div style={{ marginTop: 10 }}>
                    <Text strong>调整方案（仅建议，确认生效后才写入候选覆盖）</Text>
                    {plan.map((p, j) => (
                      <div key={j} style={{ marginLeft: 12 }}>
                        - {nameMap[String(p.stock_code ?? '')] ?? String(p.stock_code ?? '')}（{String(p.stock_code ?? '')}）：
                        {String(p.new_tier ?? '')} / {String(p.new_label ?? '')} —— {String(p.reason ?? '')}
                        {p.evidence ? `（${String(p.evidence)}）` : null}
                      </div>
                    ))}
                    <Button type="primary" size="small" style={{ marginTop: 8 }}
                      onClick={() => confirmApply(bid)}>
                      确认生效（写入候选覆盖，可回滚）
                    </Button>
                  </div>
                ) : bid > 0 ? (
                  <Alert type="info" showIcon style={{ marginTop: 10 }}
                    message="本次回答未生成调整方案" description="未提出需要确认的调整建议，仅展示分析结果。" />
                ) : null}
                <Space style={{ marginTop: 12 }}>
                  <Button size="small" onClick={() => setResult(null)}>清空本次回答</Button>
                </Space>
              </Card>
            ) : null}

            {historyItems.length ? (
              <div style={{ marginTop: 16 }}>
                <Text strong>批量验证历史（可回溯，最近 {historyItems.length} 条）</Text>
                <Collapse ghost size="small" items={historyItems} style={{ marginTop: 6 }} />
              </div>
            ) : null}
          </div>
        ),
      }]}
    />
  )
}

/** 候选池页（Phase 2） */
export function CandidatesPage() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [date, setDate] = useState<string>()
  const [filter, setFilter] = useState('全部候选')
  const [traceStock, setTraceStock] = useState<{ code: string; date: string } | null>(null)

  const { data: dates } = useQuery({ queryKey: ['candidate-dates'], queryFn: () => candidateDates(30) })
  // 默认查询当天的候选池（dates[0] 是最新一天；异步回填避免首帧空态/未选中）
  useEffect(() => {
    if (!date && dates && dates.length > 0) {
      setDate(dates[0])
    }
  }, [date, dates])
  const { data: rows } = useQuery({
    queryKey: ['candidates', date],
    queryFn: () => candidates(date),
    enabled: !!date || !!dates?.length,
  })
  const { data: tradeable } = useQuery({
    queryKey: ['candidate-tradeable', date],
    queryFn: () => candidateTradeable(date),
    enabled: !!date || !!dates?.length,
  })
  const { data: tvStats } = useQuery({ queryKey: ['track-stats-t5'], queryFn: () => trackVerifyStats('t5') })
  const { data: conc } = useQuery({
    queryKey: ['candidate-conc', date],
    queryFn: () => candidateConcentration(date),
    enabled: !!date || !!dates?.length,
  })

  const dig = useTaskSubmit('daily_pipeline', (result) => {
    const count = (result as { count?: number } | null)?.count ?? 0
    message.success(`每日挖掘完成：${count} 只候选`)
    qc.invalidateQueries({ queryKey: ['candidates'] })
    qc.invalidateQueries({ queryKey: ['candidate-dates'] })
  })
  // 提交成功 → 提示查看右下角任务面板，带 task_id 后 6 位
  useEffect(() => {
    const tid = dig.submit.data?.task_id
    if (tid) {
      message.success(`已提交后台，请看右下角任务面板 #${tid.slice(-6)}`)
    }
  }, [dig.submit.data?.task_id, message])

  // 名称补全
  const codes = rows?.filter((r) => !r.stock_name || r.stock_name === r.stock_code).map((r) => r.stock_code) ?? []
  const { data: names } = useQuery({
    queryKey: ['stock-names', codes.join(',')],
    queryFn: () => stockNames(codes),
    enabled: codes.length > 0,
  })
  const nameOf = (c: Candidate) => names?.[c.stock_code] ?? c.stock_name

  // 筛选
  const tradeableMap = useMemo(() => {
    const m: Record<string, Record<string, unknown>> = {}
    for (const it of tradeable?.items ?? []) m[String(it.stock_code)] = it
    return m
  }, [tradeable])
  const shown = (rows ?? []).filter((r) => {
    const tier = TIER_MAP[String((r.detail ?? {}).confidence_tier ?? '')] ?? ''
    if (filter === '可建仓 A+B') return (tradeableMap[r.stock_code] ?? {}).is_tradeable === 1
    if (filter === '观察 C') return tier === 'C'
    return true
  })

  // 选股表现卡（n>0 才展示）
  const tvN = Number(tvStats?.n ?? 0)
  const wr = tvStats?.win_rate
  const avg = tvStats?.avg_pct

  // 行业集中度
  const concTotal = Number(conc?.total ?? 0)
  const concCov = Number(conc?.coverage ?? 0)
  const concGroups = (conc?.groups as Array<Record<string, unknown>>) ?? []

  return (
    <div>
      <Space style={{ marginBottom: 10 }} wrap>
        <Select
          placeholder="选择日期"
          style={{ width: 140 }}
          value={date ?? dates?.[0]}
          onChange={setDate}
          options={(dates ?? []).map((d) => ({ label: d, value: d }))}
        />
        <Segmented value={filter} onChange={(v) => setFilter(String(v))}
          options={['全部候选', '可建仓 A+B', '观察 C']} />
        <Button type="primary" loading={dig.submit.isPending} onClick={() => dig.submit.mutate({})}>
          手动触发每日挖掘（后台）
        </Button>
      </Space>

      <StatCardGrid>
        <StatCard label="今日可建仓标的" value={Number(tradeable?.count ?? 0)}
          tone={Number(tradeable?.count ?? 0) > 0 ? 'ok' : 'mute'}
          sub="评级≥B 且现价在首仓区间" />
        <StatCard label="可自动生成建仓计划" value={Number(tradeable?.plan_candidate_count ?? 0)}
          tone="info" sub="评级 A/B 且暂无方案" />
        <StatCard label="近期选股胜率"
          value={wr != null ? `${wr.toFixed(1)}%` : '无数据'}
          tone={wr != null ? (wr >= 50 ? 'ok' : wr < 40 ? 'err' : 'warn') : 'mute'}
          sub={`盈利 ${tvStats?.wins ?? 0} 笔 / 共 ${tvN} 笔（T+5 已到期）`} />
        <StatCard label="平均涨幅" value={avg != null ? `${avg >= 0 ? '+' : ''}${avg.toFixed(2)}%` : '无数据'}
          tone={avg != null ? (avg > 0 ? 'up' : avg < 0 ? 'down' : 'mute') : 'mute'} sub="T+5 周期" />
      </StatCardGrid>

      {concTotal >= 3 ? (
        concCov < 50 ? (
          <Alert type="info" showIcon style={{ marginBottom: 10 }}
            message={`行业数据覆盖不足（${concCov.toFixed(0)}%），集中度统计暂不展示。`} />
        ) : (
          concGroups.length ? (
            <Alert
              style={{ marginBottom: 10 }}
              type={Number(conc?.max_concentration ?? 0) >= 50 ? 'warning' : 'info'}
              showIcon
              message={
                concGroups.map((g) => `${String(g.industry)} ${Number(g.count)}只(${String(g.pct)}%)`).join('｜')
              }
              description={Number(conc?.max_concentration ?? 0) >= 50
                ? `行业集中度 ${conc?.max_concentration}%（${conc?.max_industry}），建议分散，避免单一行业过度暴露。`
                : undefined}
            />
          ) : null
        )
      ) : null}

      {!shown.length ? (
        <EmptyState text="当日无候选。可点击上方「手动触发每日挖掘」重新生成。" icon="🔍" />
      ) : (
        <Table<Candidate>
          rowKey={(r) => `${r.stock_code}_${r.trade_date}_${r.rank ?? ''}`}
          size="small"
          pagination={{ pageSize: 20 }}
          dataSource={shown}
          expandable={{ expandedRowRender: (r) => <CandidateExpand c={r} /> }}
          columns={[
            {
              title: '排名/股票', key: 'stock', width: 280,
              render: (_: unknown, r: Candidate) => {
                const tv = (tradeableMap[r.stock_code] ?? {}) as Record<string, unknown>
                const label = String(tv.label ?? '')
                const block = String(tv.block_reason ?? '')
                return (
                  <Space size={6} wrap>
                    <Text type="secondary">#{r.rank ?? '—'}</Text>
                    <StockLabel code={r.stock_code} name={nameOf(r)} />
                    {label ? (
                      <Tooltip
                        title={block || '评级 / 现价 / 风险三条件均满足，建议进入建仓阶段'}
                        placement="top"
                      >
                        <Tag color={LABEL_COLORS[label] ?? 'default'} style={{ marginInlineEnd: 0 }}>
                          {label}
                        </Tag>
                      </Tooltip>
                    ) : null}
                  </Space>
                )
              },
            },
            {
              title: '创建时间', key: 'trade_date', width: 110,
              render: (_: unknown, r: Candidate) => (
                <Text type="secondary" style={{ fontSize: 12 }}>{r.trade_date || '—'}</Text>
              ),
            },
            {
              title: '评级', key: 'tier', width: 80,
              render: (_: unknown, r: Candidate) => {
                const t = TIER_MAP[String((r.detail ?? {}).confidence_tier ?? '')] ?? ''
                return t ? <Tag color={TIER_DOT[t]}>{t}</Tag> : '—'
              },
            },
            {
              title: '理由', key: 'reasons', ellipsis: true,
              render: (_: unknown, r: Candidate) => r.reasons?.[0] ?? '—',
            },
            {
              title: '留痕', key: 'trace', width: 80,
              render: (_: unknown, r: Candidate) => (
                <Button size="small" onClick={() => setTraceStock({ code: r.stock_code, date: r.trade_date })}>
                  AI 留痕
                </Button>
              ),
            },
          ]}
        />
      )}
      <BatchVerifyPanel date={date ?? (dates?.[0] ?? '')} dayRows={rows ?? []} />
      <TraceModal code={traceStock?.code ?? ''} date={traceStock?.date ?? ''}
        open={!!traceStock} onClose={() => setTraceStock(null)} />
    </div>
  )
}

export default CandidatesPage
