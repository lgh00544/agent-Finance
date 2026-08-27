import { App, Button, Card, Col, Row, Space, Tag, Typography } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { dashboard, jobStatus, llmStats as fetchLlm, datasourceStats as fetchDs } from '@/api/system'
import { recentTasks, retryTask } from '@/api/tasks'
import { hotSectors, marketCondition, marketIndices } from '@/api/market'
import { holdingQuotes, redLineCheck, takeProfitPlan } from '@/api/holdings'
import { accountPnl } from '@/api/account'
import { useTaskSubmit } from '@/hooks/useTaskSubmit'
import { ChartCard, hotSectorBarOption } from '@/components/charts/ChartCard'
import { EmptyState, ErrorCard, StatCard, StatCardGrid, StockLabel } from '@/components/common'
import type { AccountPnl, HotSector } from '@/types'

const { Text } = Typography

type DashboardData = {
  checked_at?: string
  modules?: Record<string, unknown>
}

/** 市况 band → Tag 色（A股：强=红涨 / 弱=绿跌） */
function bandColor(b: string): string {
  return b.includes('强') ? 'red' : b.includes('弱') ? 'green' : 'orange'
}

/** 严格度档位 → Tag 色（宽松绿/标准蓝/严格橙/极严红） */
function strictColor(s: string): string {
  return s.includes('宽松') ? 'green' : s.includes('标准') ? 'blue' : s.includes('严格') ? 'orange' : s.includes('极严') ? 'red' : 'default'
}

/** 今日真实盈亏（同花顺）cell：三态诚实展示（未接入/有值/过期错误），绝不出假正数 */
function PnlCell({ pnl }: { pnl?: AccountPnl }) {
  if (!pnl?.configured) {
    return (
      <div>
        <Text type="secondary" style={{ fontSize: 12 }}>今日盈亏（同花顺）</Text>
        <div style={{ marginTop: 2 }}><Text type="secondary">未接入 · 同花顺真实盈亏未启用</Text></div>
      </div>
    )
  }
  const s = pnl.snapshot ?? {}
  const yk = s.pnl_yk as number | null | undefined
  const pct = s.pnl_pct as number | null | undefined
  const sh = s.sh_pct as number | null | undefined
  const up = (v: number | null | undefined) => (v == null ? 'default' : Number(v) >= 0 ? 'red' : 'green')
  const ykText = yk == null ? '—' : `${Number(yk) >= 0 ? '+' : ''}¥${Math.abs(Number(yk)).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  const pctText = pct == null ? '—' : `${Number(pct) >= 0 ? '+' : ''}${Number(pct).toFixed(2)}%`
  const expired = s.token_expired === true
  const err = String(s.error ?? '').trim()
  const updatedAt = String(s.updated_at ?? '')
  const parsed = new Date(updatedAt.replace(' ', 'T')).getTime()
  const stale = !!updatedAt && !Number.isNaN(parsed) && Date.now() - parsed > 10 * 60 * 1000
  return (
    <div>
      <Text type="secondary" style={{ fontSize: 12 }}>今日盈亏（同花顺）</Text>
      <div style={{ marginTop: 2 }}>
        <Text strong style={{ color: up(yk) === 'red' ? '#cf1322' : up(yk) === 'green' ? '#389e0d' : undefined }}>
          {ykText} {pctText}
        </Text>
      </div>
      {sh != null && !Number.isNaN(Number(sh)) ? (
        <div style={{ marginTop: 2 }}><Tag color={up(sh)}>上证 {Number(sh) >= 0 ? '+' : ''}{Number(sh).toFixed(2)}%</Tag></div>
      ) : null}
      {expired ? (
        <div style={{ marginTop: 2 }}><Tag color="orange">同花顺 Cookie 已过期，请到 DSH 插件重新登录</Tag></div>
      ) : null}
      {err ? (
        <div style={{ marginTop: 2, color: '#cf1322', fontSize: 12 }}>{err.length > 40 ? `${err.slice(0, 40)}…` : err}</div>
      ) : null}
      <div style={{ marginTop: 2, fontSize: 12 }}>
        <Text type="secondary">{updatedAt ? updatedAt.slice(5, 19) : '—'}{stale ? '（可能过期）' : ''}</Text>
      </div>
    </div>
  )
}

/** detail.factors 最高分因子 → "因子 分/10"（缺 → —） */
function strongestFactor(detail: unknown): string {
  const factors = ((detail as Record<string, unknown> | undefined)?.factors as Array<Record<string, unknown>> | undefined) ?? []
  if (!factors.length) return '—'
  const best = factors.reduce((a, b) => (Number(b.score) > Number(a.score) ? b : a), factors[0])
  return `${String(best.factor ?? '')} ${Number(best.score ?? 0)}/10`
}

/** 任务状态区（对齐 render.task_status_area）：recentTasks 列表 + 失败重试 */
function TaskStatusArea() {
  const { message } = App.useApp()
  const { data: tasks } = useQuery({ queryKey: ['recent-tasks'], queryFn: () => recentTasks(8) })
  const rows = tasks ?? []
  if (!rows.length) return null
  return (
    <Card size="small" title="任务执行记录" style={{ background: 'var(--bg-card)', marginBottom: 12 }}>
      {rows.map((t) => (
        <Space key={t.task_id} style={{ width: '100%', marginBottom: 4, justifyContent: 'space-between' }}>
          <Space>
            <Tag color={t.status === 'done' ? 'green' : t.status === 'failed' ? 'red' : t.status === 'running' ? 'blue' : 'orange'}>
              {t.status === 'done' ? '完成' : t.status === 'failed' ? '失败' : t.status === 'running' ? '执行中' : '排队中'}
            </Tag>
            <Text>{t.label}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t.kind} · 提交于 {String(t.submitted_at ?? '').slice(5, 16)}
            </Text>
          </Space>
          {t.status === 'failed' ? (
            <Button size="small" onClick={() => {
              retryTask(t.task_id)
              message.success('已提交重试')
            }}>重试</Button>
          ) : null}
        </Space>
      ))}
    </Card>
  )
}

/** LLM / 数据源统计 */
function StatsCards() {
  const { data: ls } = useQuery({ queryKey: ['llm-stats'], queryFn: fetchLlm })
  const { data: ds } = useQuery({ queryKey: ['ds-stats'], queryFn: fetchDs })
  const { data: js } = useQuery({ queryKey: ['job-status'], queryFn: jobStatus })
  const jobs = (js?.jobs as Array<Record<string, unknown>>) ?? []
  return (
    <>
      <StatCardGrid>
        <StatCard label="请求总次数（当日）" value={ls?.requests != null ? `${ls.requests} 次` : '—'} tone="info"
          sub="LLM 调用" />
        <StatCard label="缓存命中率"
          value={ls?.hit_rate_pct != null ? `${ls.hit_rate_pct}%` : '—（暂无调用）'} tone="ok" />
        <StatCard label="缓存命中/未命中 token"
          value={ls?.hit_tokens != null ? `${ls.hit_tokens.toLocaleString()} / ${(ls.miss_tokens ?? 0).toLocaleString()}` : '—'}
          tone="mute" />
        <StatCard label="主源成功率"
          value={ds?.success_rate_pct != null ? `${ds.success_rate_pct}%` : '—'} tone={(ds?.success_rate_pct ?? 0) >= 95 ? 'ok' : 'warn'} />
      </StatCardGrid>
      <Card size="small" title="定时任务调度" style={{ background: 'var(--bg-card)', marginBottom: 12 }}>
        {jobs.length ? jobs.slice(0, 6).map((j) => (
          <div key={String(j.name)} style={{ fontSize: 13, marginBottom: 4 }}>
            <Text>{String(j.name)}</Text>：<Text type="secondary">{String(j.next_run ?? '未运行')}</Text>
          </div>
        )) : <Text type="secondary">无已注册的定时任务。</Text>}
      </Card>
    </>
  )
}

/** 系统概览页（Phase 3 看板聚合） */
export function OverviewPage() {
  const { message } = App.useApp()
  const qc = useQueryClient()

  const { data: dash } = useQuery<DashboardData>({
    queryKey: ['dashboard'],
    queryFn: () => dashboard() as Promise<DashboardData>,
    refetchInterval: 60_000,
  })
  const { data: sectors } = useQuery<{ sectors?: HotSector[] }>({
    queryKey: ['hot-sectors'],
    queryFn: hotSectors,
    refetchInterval: 30 * 60_000,
  })
  const { data: tpPlans } = useQuery({ queryKey: ['take-profit-plan'], queryFn: () => takeProfitPlan() })
  const { data: quotes } = useQuery({
    queryKey: ['holding-quotes-overview'],
    queryFn: () => holdingQuotes(),
    refetchInterval: 60_000,  // 与 HoldingsPage 保持一致
  })
  // 市况速览：三大指数 + 严格度（dashboard 的 market_condition 无 strictness，复用 /market-condition 已有 api）
  const { data: idx } = useQuery({ queryKey: ['market-indices'], queryFn: marketIndices })
  const { data: mcStrict } = useQuery({ queryKey: ['market-cond-strict'], queryFn: marketCondition })
  // 同花顺真实今日盈亏（只读展示；默认关返回 {configured:false} → PnlCell 灰态）
  const { data: pnl } = useQuery({ queryKey: ['account-pnl'], queryFn: accountPnl, refetchInterval: 60_000 })
  // 持仓红线预警（复用已有 /red_line_check，5 分钟轮询平衡开销）
  const { data: redRes } = useQuery({
    queryKey: ['red-line-check'],
    queryFn: redLineCheck,
    refetchInterval: 5 * 60_000,
  })

  const dig = useTaskSubmit('daily_pipeline', () => {
    message.success('每日挖掘任务已提交后台')
    qc.invalidateQueries({ queryKey: ['dashboard'] })
  })

  const mods = dash?.modules ?? {}
  const holdings = (mods.holdings as Array<Record<string, unknown>>) ?? []
  const tradeable = (mods.candidate_tradeable as { date?: string; count?: number; total?: number; items?: Array<Record<string, unknown>> }) ?? {}
  const marketCond = (mods.market_condition as Record<string, unknown>) ?? {}
  const scores = (mods.scores as Array<Record<string, unknown>>) ?? []

  const ops = (tpPlans?.rows ?? []) as Array<Record<string, unknown>>

  // ② 今日可建仓标的（is_tradeable 判定行；grade/score/因子从 dashboard.scores 同名代码取，缺则诚实降级）
  const tradeableList = ((tradeable.items ?? []) as Array<Record<string, unknown>>).filter((i) => i.is_tradeable)
  // ③ 持仓分类：止盈/止损 = quotes 现价 vs 参考位；红线 = red_line_check 命中；质量低 holdings 无该字段，诚实置空
  const quoteRows = (quotes?.rows ?? []) as Array<Record<string, unknown>>
  const strictness = String(marketCond.strictness ?? mcStrict?.strictness ?? '')
  const redByCode = new Map((redRes?.rows ?? []).map((r) => [String((r as Record<string, unknown>).stock_code ?? ''), r as Record<string, unknown>]))
  const takeProfitHits = quoteRows.filter((q) => q.current_price != null && q.take_profit != null && Number(q.current_price) >= Number(q.take_profit))
  const stopLossHits = quoteRows.filter((q) => q.current_price != null && q.stop_loss != null && Number(q.current_price) <= Number(q.stop_loss))
  const redLineHits = quoteRows.filter((q) => {
    const r = redByCode.get(String(q.stock_code))
    return !!r && !!(r.c1_alert || r.c2_alert || r.c3_alert || r.c4_high_break || Number(r.k226_alert_level) >= 2 || r.k189_wash_suspect)
  })
  const triggered = new Set([...takeProfitHits, ...stopLossHits, ...redLineHits].map((q) => String(q.stock_code)))
  const normalHits = quoteRows.filter((q) => !triggered.has(String(q.stock_code)))
  const redReason = (q: Record<string, unknown>): string => {
    const r = redByCode.get(String(q.stock_code))
    if (!r) return '红线'
    if (r.c1_alert) return 'C1 集中度'
    if (r.c2_alert) return 'C2 回撤'
    if (r.c3_alert) return 'C3 止损'
    if (r.c4_high_break) return 'C4 突破'
    if (Number(r.k226_alert_level) >= 2) return 'K226 派发'
    return 'K189 对倒'
  }
  const holdCats: Array<{ key: string; label: string; color: string; rows: Array<Record<string, unknown>>; reason: (q: Record<string, unknown>) => string }> = [
    { key: 'tp', label: '止盈触发', color: 'green', rows: takeProfitHits, reason: () => '现价≥止盈' },
    { key: 'sl', label: '止损触发', color: 'red', rows: stopLossHits, reason: () => '现价≤止损' },
    { key: 'rl', label: '红线预警', color: 'orange', rows: redLineHits, reason: redReason },
    { key: 'ql', label: '正常', color: 'default', rows: normalHits, reason: () => '无触发' },
  ]

  return (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Text type="secondary">页面数据刷新时间：{dash?.checked_at ?? '—'}</Text>
        <Button type="primary" loading={dig.submit.isPending} onClick={() => dig.submit.mutate({})}>
          手动触发每日挖掘（后台）
        </Button>
        <Button onClick={() => qc.invalidateQueries({ queryKey: ['dashboard'] })}>刷新看板</Button>
      </Space>

      {/* ① 市况速览（替换原 4 StatCard 位置；数据缺失全 "—" 降级） */}
      <Card size="small" title="市况速览" style={{ background: 'var(--bg-card)', marginBottom: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 8 }}>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>市况 band</Text>
            <div style={{ marginTop: 2 }}><Tag color={bandColor(String(marketCond.band ?? ''))}>{String(marketCond.band ?? '—')}</Tag></div>
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>市况综合分</Text>
            <div style={{ marginTop: 2 }}><Text strong>{marketCond.total_score != null ? `${marketCond.total_score}/100` : '—'}</Text></div>
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>当日严格度</Text>
            <div style={{ marginTop: 2 }}><Tag color={strictColor(strictness)}>{strictness || '—'}</Tag></div>
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>三大指数</Text>
            <div style={{ marginTop: 2 }}>
              <Space size={4} wrap>
                {(idx?.indices ?? []).map((i) => {
                  const pct = i.change_pct
                  return (
                    <Tag key={String(i.code ?? i.name)} color={pct == null ? 'default' : pct >= 0 ? 'red' : 'green'}>
                      {String(i.name ?? '')} {pct == null ? '—' : `${pct >= 0 ? '+' : ''}${pct}%`}
                    </Tag>
                  )
                })}
              </Space>
            </div>
          </div>
          <div><PnlCell pnl={pnl} /></div>
        </div>
        <div style={{ marginTop: 8, fontSize: 13 }}><Text type="secondary">{String(marketCond.summary ?? '—')}</Text></div>
      </Card>

      {/* ② 今日可建仓（可建仓判定 top3；0 只 EmptyState） */}
      <Card size="small" title="今日可建仓" style={{ background: 'var(--bg-card)', marginBottom: 12 }}>
        <StatCard label="今日可建仓"
          value={tradeable.count != null ? `${tradeable.count} / ${tradeable.total ?? 0} 只` : '—'}
          tone={(tradeable.count ?? 0) > 0 ? 'ok' : 'warn'}
          sub={`${tradeable.date ?? '今日'} · 候选池`} />
        {tradeableList.length ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {tradeableList.slice(0, 3).map((it) => {
              const code = String(it.stock_code ?? '')
              const sc = scores.find((s) => String(s.stock_code ?? '') === code)
              const grade = String(sc?.grade ?? it.label ?? '')
              return (
                <div key={code} style={{ padding: 6, borderRadius: 6, background: 'var(--bg-input)' }}>
                  <Space wrap>
                    <StockLabel code={code} name={String(it.stock_name ?? '')} />
                    <Tag color={grade === 'A' ? 'red' : grade === 'B' ? 'orange' : 'blue'}>{grade || '—'}</Tag>
                    {sc?.score != null ? <Text strong>{String(sc.score)}</Text> : <Text type="secondary">—</Text>}
                    <Text type="secondary" style={{ fontSize: 12 }}>最强因子 {strongestFactor(sc?.detail)}</Text>
                  </Space>
                </div>
              )
            })}
          </div>
        ) : (
          <EmptyState text="今日无可建仓标的" icon="—" />
        )}
      </Card>

      <Row gutter={12}>
        <Col xs={24} lg={14}>
          <ChartCard
            title="今日热门板块（涨幅前 5，涨红跌绿）"
            option={hotSectorBarOption((sectors?.sectors ?? []) as HotSector[])}
            loading={!sectors}
          />
          <Card size="small" title="移动止盈计划摘要" style={{ background: 'var(--bg-card)', marginBottom: 12 }}>
            {ops.length ? ops.slice(0, 5).map((p) => {
              const pp = p as Record<string, unknown>
              return (
                <div key={String(pp.holding_id)} style={{ fontSize: 13, marginBottom: 4 }}>
                  <Text>{String(pp.stock_code ?? '—')} {String(pp.stock_name ?? '')}</Text>
                  ：止损 <Text type="danger">{String(pp.stop_loss ?? '—')}</Text>
                  {' / 止盈 '}<Text type="success">{String(pp.take_profit ?? '—')}</Text>
                  {' / 目标 '}{String(pp.target_pct ?? '—')}%
                </div>
              )
            }) : <Text type="secondary">（暂无在途止盈计划）</Text>}
          </Card>
          {/* ③ 持仓关注（替换原「当前持仓概览」Card：4 分类，每类 0/1-3 只） */}
          <Card size="small" title="持仓关注" style={{ background: 'var(--bg-card)', marginBottom: 12 }}>
            <StatCard label="持仓总数" value={holdings.length} tone="info" sub="有效持仓标的" />
            {holdCats.map((c) => (
              <div key={c.key} style={{ marginBottom: 10 }}>
                <Space style={{ marginBottom: 4 }}>
                  <Text strong style={{ fontSize: 13 }}>{c.label}</Text>
                  <Tag color={c.rows.length ? c.color : 'default'}>{c.rows.length || '无'}</Tag>
                </Space>
                {c.rows.length ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {c.rows.slice(0, 3).map((q) => (
                      <div key={String(q.stock_code)} style={{ padding: '4px 8px', borderRadius: 6, background: 'var(--bg-input)' }}>
                        <StockLabel code={String(q.stock_code)} name={String(q.stock_name ?? '')} />
                        <Tag color={c.color} style={{ marginLeft: 4 }}>{c.reason(q)}</Tag>
                      </div>
                    ))}
                  </div>
                ) : (
                  <Text type="secondary" style={{ fontSize: 12 }}>无</Text>
                )}
              </div>
            ))}
            <Text type="secondary" style={{ fontSize: 12, marginTop: 6, display: 'block' }}>
              行情最后更新：{quotes?.quote_time ?? '—'}（约 60s 缓存）
              · 监控定时 5 分钟轮询 / 手动「立即刷新监控」后自动更新
            </Text>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <StatsCards />
        </Col>
      </Row>

      <TaskStatusArea />

      {scores.length ? (
        <Card size="small" title="最新评分" style={{ background: 'var(--bg-card)', marginBottom: 12 }}>
          {scores.slice(0, 5).map((s) => (
            <div key={String(s.id)} style={{ fontSize: 13, marginBottom: 4 }}>
              <StockLabel code={String(s.stock_code ?? '')} name={String(s.stock_name ?? '')} />
              ：{String(s.score ?? '—')} 分 <Tag color={(s.grade as string) === 'A' ? 'red' : (s.grade as string) === 'B' ? 'orange' : 'blue'}>{String(s.grade ?? '—')}</Tag>
            </div>
          ))}
        </Card>
      ) : null}

      {!dash ? <ErrorCard title="首页数据加载失败" message="请确认后端服务运行正常。" onRetry={() => qc.invalidateQueries({ queryKey: ['dashboard'] })} /> : null}
    </div>
  )
}

export default OverviewPage
