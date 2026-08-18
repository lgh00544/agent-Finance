import { useMemo, useState } from 'react'
import {
  App,
  Alert,
  Button,
  Card,
  Modal,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { candidateConcentration, candidateDates, candidateTradeable, candidates, stockNames } from '@/api/candidates'
import { trackVerifyStats } from '@/api/track'
import { traces, traceDetail } from '@/api/traces'
import { useTaskSubmit } from '@/hooks/useTaskSubmit'
import { EmptyState, StatCard, StatCardGrid, StockLabel } from '@/components/common'
import type { Candidate } from '@/types'

const { Text } = Typography

const TIER_MAP: Record<string, string> = { 强烈推荐: 'A', 建议关注: 'B', 谨慎观察: 'C' }
const TIER_DOT: Record<string, string> = { A: 'red', B: 'orange', C: 'blue' }

/** 候选行展开详情：维度归因 + 候选理由 + 风险 + 生成建仓方案 */
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

      {(dims as Array<Record<string, unknown>>).length ? (
        <Card size="small" title="维度归因（五维白盒，主结论）" style={{ background: 'var(--bg-input)', marginBottom: 8 }}>
          {dims.map((d) => {
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
          })}
          {detail.final_advice ? (
            <Alert type="info" showIcon style={{ marginTop: 6 }} message={String(detail.final_advice)} />
          ) : null}
        </Card>
      ) : null}

      {reasons.length ? (
        <Card size="small" title="候选理由" style={{ background: 'var(--bg-input)', marginBottom: 8 }}>
          {reasons.map((r, i) => <div key={i}>{i + 1}. {r}</div>)}
        </Card>
      ) : null}

      {(risks.length || riskNotice.length) ? (
        <Card size="small" title="风险点" style={{ background: 'var(--bg-input)', marginBottom: 8 }}>
          {risks.map((r, i) => <div key={`r${i}`}>⚠️ {r}</div>)}
          {riskNotice.map((r, i) => <div key={`n${i}`}>⚠️ {r}</div>)}
        </Card>
      ) : null}
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

/** 候选池页（Phase 2） */
export function CandidatesPage() {
  const { message } = App.useApp()
  const [date, setDate] = useState<string>()
  const [filter, setFilter] = useState('全部候选')
  const [traceStock, setTraceStock] = useState<{ code: string; date: string } | null>(null)

  const { data: dates } = useQuery({ queryKey: ['candidate-dates'], queryFn: () => candidateDates(30) })
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

  const dig = useTaskSubmit('daily_pipeline', () => {
    message.success('每日挖掘任务已提交后台')
    window.setTimeout(() => location.reload(), 1500)
  })

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
          value={wr != null ? `${(wr * 100).toFixed(1)}%` : '无数据'}
          tone={wr != null ? (wr >= 0.5 ? 'ok' : wr < 0.4 ? 'err' : 'warn') : 'mute'}
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
              title: '排名/股票', key: 'stock', width: 200,
              render: (_: unknown, r: Candidate) => (
                <Space>
                  <Text type="secondary">#{r.rank ?? '—'}</Text>
                  <StockLabel code={r.stock_code} name={nameOf(r)} />
                </Space>
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
      <TraceModal code={traceStock?.code ?? ''} date={traceStock?.date ?? ''}
        open={!!traceStock} onClose={() => setTraceStock(null)} />
    </div>
  )
}

export default CandidatesPage
