import { App, Button, Card, Col, Row, Space, Tag, Typography } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { dashboard, jobStatus, llmStats as fetchLlm, datasourceStats as fetchDs } from '@/api/system'
import { recentTasks, retryTask } from '@/api/tasks'
import { hotSectors } from '@/api/market'
import { holdingQuotes, takeProfitPlan } from '@/api/holdings'
import { useTaskSubmit } from '@/hooks/useTaskSubmit'
import { ChartCard, hotSectorBarOption } from '@/components/charts/ChartCard'
import { ErrorCard, StatCard, StatCardGrid, StockLabel } from '@/components/common'
import type { HotSector } from '@/types'

const { Text } = Typography

type DashboardData = {
  checked_at?: string
  modules?: Record<string, unknown>
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

  const dig = useTaskSubmit('daily_pipeline', () => {
    message.success('每日挖掘任务已提交后台')
    qc.invalidateQueries({ queryKey: ['dashboard'] })
  })

  const mods = dash?.modules ?? {}
  const holdings = (mods.holdings as Array<Record<string, unknown>>) ?? []
  const tradeable = (mods.candidate_tradeable as { date?: string; count?: number; total?: number }) ?? {}
  const alerts = (mods.alerts as Array<Record<string, unknown>>) ?? []
  const marketCond = (mods.market_condition as Record<string, unknown>) ?? {}
  const scores = (mods.scores as Array<Record<string, unknown>>) ?? []

  const ops = (tpPlans?.rows ?? []) as Array<Record<string, unknown>>

  return (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Text type="secondary">页面数据刷新时间：{dash?.checked_at ?? '—'}</Text>
        <Button type="primary" loading={dig.submit.isPending} onClick={() => dig.submit.mutate({})}>
          手动触发每日挖掘（后台）
        </Button>
        <Button onClick={() => qc.invalidateQueries({ queryKey: ['dashboard'] })}>刷新看板</Button>
      </Space>

      <StatCardGrid>
        <StatCard
          label="今日可建仓"
          value={tradeable.count ?? 0}
          tone={(tradeable.count ?? 0) > 0 ? 'ok' : 'warn'}
          sub={`${tradeable.date ?? '今日'} · 候选池 ${tradeable.total ?? 0} 只`} />
        <StatCard label="当前持仓" value={holdings.length} tone="info" sub="有效持仓标的" />
        <StatCard label="告警记录" value={alerts.length} tone="warn" sub="全部信号记录" />
        <StatCard label="市况评分"
          value={marketCond.total_score != null ? `${marketCond.total_score} 分` : '—'}
          tone={String(marketCond.band ?? '').includes('强') ? 'up' : String(marketCond.band ?? '').includes('弱') ? 'down' : 'warn'}
          sub={`${marketCond.band ?? '—'} · 候选池上限 ${marketCond.cap ?? '—'} 只`} />
      </StatCardGrid>

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
          {quotes?.rows?.length ? (
            <Card size="small" title="当前持仓概览（每日定时 / 手动触发后刷新）" style={{ background: 'var(--bg-card)', marginBottom: 12 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 8 }}>
                {quotes.rows.slice(0, 12).map((q) => {
                  const h = q as Record<string, unknown>
                  const code = String(h.stock_code ?? '—')
                  const name = String(h.stock_name ?? '')
                  const shares = Number(h.shares ?? 0)
                  const cost = Number(h.entry_price ?? 0)
                  const price = h.current_price != null ? Number(h.current_price) : null
                  const mv = h.market_value != null ? Number(h.market_value) : (price != null ? price * shares : 0)
                  const pnl = (price != null && cost > 0) ? (price - cost) * shares : null
                  const pnlPct = (price != null && cost > 0) ? (price - cost) / cost * 100 : null
                  const sl = h.stop_loss ?? '—'
                  const tp = h.take_profit ?? '—'
                  const pnlColor = pnl == null ? 'var(--text)' : pnl > 0 ? 'var(--up)' : pnl < 0 ? 'var(--down)' : 'var(--text)'
                  return (
                    <div key={code} style={{ padding: 8, borderRadius: 6, background: 'var(--bg-input)' }}>
                      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                        <Text strong>{code} {name}</Text>
                        <Tag color={pnl != null && pnl >= 0 ? 'red' : 'green'}>{pnl != null ? `${pnl >= 0 ? '+' : ''}${(pnlPct ?? 0).toFixed(2)}%` : '—'}</Tag>
                      </Space>
                      <div style={{ fontSize: 12, marginTop: 4, color: 'var(--text-mute)' }}>
                        持股 <Text strong style={{ color: 'var(--text)' }}>{shares.toLocaleString()}</Text> 股
                        · 成本 <Text strong style={{ color: 'var(--text)' }}>{cost.toFixed(2)}</Text>
                        · 现价 <Text strong style={{ color: 'var(--text)' }}>{price?.toFixed(2) ?? '—'}</Text>
                        · 市值 <Text strong style={{ color: 'var(--text)' }}>{mv.toLocaleString()}</Text>
                      </div>
                      <div style={{ fontSize: 12, marginTop: 2, color: pnlColor }}>
                        浮盈 {pnl != null ? `${pnl >= 0 ? '+' : ''}${pnl.toFixed(0)}` : '—'} 元
                        · 止损 <Text type="danger">{String(sl)}</Text>
                        · 止盈 <Text type="success">{String(tp)}</Text>
                      </div>
                    </div>
                  )
                })}
              </div>
              <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
                行情最后更新：{quotes?.quote_time ?? '—'}（约 60s 缓存）
                · 监控定时 5 分钟轮询 / 手动「立即刷新监控」后自动更新
              </Text>
            </Card>
          ) : null}
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
