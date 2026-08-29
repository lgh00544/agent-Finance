import { type CSSProperties, useState } from 'react'
import { App, Alert, Button, Card, Collapse, Descriptions, List, Progress, Select, Space, Tabs, Tag, Tooltip, Typography } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { marketIntel, marketIntelDates, sectorPatterns, sectorRegimeView, sectorRotation } from '@/api/market'
import { useTaskSubmit } from '@/hooks/useTaskSubmit'
import { EmptyState, ErrorCard } from '@/components/common'
import type { MarketIntelInfo, RegimeViewInfo, SectorForwardForecast } from '@/types'

const { Text } = Typography

/** 嵌套 dict → 可读文本（对齐 Streamlit _tab_operative 展平逻辑） */
function flatten(v: unknown, indent = 0): string {
  if (v == null) return ''
  if (typeof v === 'object') {
    if (Array.isArray(v)) return v.map((x) => flatten(x, indent)).filter(Boolean).join('；')
    return Object.entries(v as Record<string, unknown>)
      .map(([k, val]) => {
        const pad = '  '.repeat(indent)
        if (val && typeof val === 'object') return `${pad}${k}(${flatten(val, indent + 1)})`
        return `${pad}${k}: ${String(val)}`
      })
      .join('\n')
  }
  return String(v)
}

/** 未知值 → 可读文本：缺失显（无）；数组用；连接；嵌套对象走 flatten */
function fmt(v: unknown): string {
  if (v == null) return '（无）'
  if (Array.isArray(v)) return v.map(fmt).filter(Boolean).join('；')
  if (typeof v === 'object') return flatten(v)
  const s = String(v)
  return s === '' ? '（无）' : s
}

/** 自由 dict → Descriptions（字段名中文化展示，缺失显（无）） */
function DictTab({ dict, empty }: { dict?: Record<string, unknown>; empty: string }) {
  const entries = Object.entries(dict ?? {})
  if (!entries.length) return <Text type="secondary">{empty}</Text>
  return (
    <Descriptions size="small" column={1} items={entries.map(([k, v], i) => ({
      key: `f-${i}`, label: k, children: <div style={{ whiteSpace: 'pre-wrap' }}>{fmt(v)}</div>,
    }))} />
  )
}

/** 深度化模块：量能成色 / 主线结构 / 箱位理解 / 个股三维验证 */
function DeepModules({ mi }: { mi: MarketIntelInfo }) {
  const vs = (mi.volume_signal ?? {}) as Record<string, unknown>
  const om = (mi.operative_meaning ?? {}) as Record<string, unknown>

  const vc = vs['量能成色']
  const ms = vs['主线结构'] as Record<string, unknown> | undefined
  const bv = om['箱位理解'] as Record<string, unknown> | undefined
  const sv = om['个股验证'] as Array<Record<string, unknown>> | undefined

  return (
    <Space orientation="vertical" style={{ width: '100%' }} size={12}>
      {vc ? <Alert type="info" showIcon title={`量能成色：${String(vc)}`} /> : null}

      {ms ? (
        <Card size="small" title="主线结构" style={{ background: 'var(--bg-input)' }}>
          {ms['进攻主线'] ? <div style={{ color: 'var(--up)' }}>进攻主线：{String(ms['进攻主线'])}</div> : null}
          {ms['接力方向'] ? <div style={{ color: 'var(--info)' }}>接力方向：{String(ms['接力方向'])}</div> : null}
          {ms['退潮方向'] ? <div style={{ color: 'var(--err)' }}>退潮方向：{String(ms['退潮方向'])}</div> : null}
        </Card>
      ) : null}

      {bv ? (
        <Card size="small" title="箱位理解（主升初期绿 / 真出货红，参考权重）" style={{ background: 'var(--bg-input)' }}>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0 }}>{flatten(bv)}</pre>
        </Card>
      ) : null}

      {sv?.length ? (
        <Card size="small" title="个股强度三维验证（主线板块内抽样，涨幅前5）" style={{ background: 'var(--bg-input)' }}>
          {sv.map((s, i) => {
            const verdict = String(s.verdict ?? '')
            const color = verdict === '真强' ? 'var(--up)' : verdict === '加速后段' ? 'var(--warn)' : verdict === '放量滞涨' ? 'var(--warn)' : 'var(--down)'
            return (
              <div key={i} style={{ fontSize: 13, marginBottom: 4 }}>
                <Text style={{ color }}>{String(s.name ?? '')}</Text>
                {' '}{String(s.change_pct ?? '')}% / 量比 {String(s.volume_ratio ?? '—')} / 60日箱位 {String(s.box60 ?? '—')}% /
                <Text type="secondary">{verdict}</Text>
              </div>
            )
          })}
        </Card>
      ) : null}
    </Space>
  )
}

const thStyle: CSSProperties = { textAlign: 'left', padding: '4px 8px', borderBottom: '1px solid var(--border)', fontWeight: 600 }
const tdStyle: CSSProperties = { padding: '4px 8px', borderBottom: '1px solid var(--border)' }
const panelStyle: CSSProperties = { border: '1px solid var(--border)', borderRadius: 8, padding: 12, background: 'var(--bg-input)' }
const metricStyle: CSSProperties = { ...panelStyle, minWidth: 180, flex: '1 1 180px' }

function pct(v?: number | null, digits = 0): string {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return `${(Number(v) * 100).toFixed(digits)}%`
}

function regimeLabel(v?: string | null): string {
  return ({ mainline: '主线行情', rotation: '轮动行情', chaos: '混沌行情' } as Record<string, string>)[v ?? ''] ?? '数据缺失'
}

function biasLabel(v?: string | null): string {
  return ({
    continue: '延续',
    switch: '切换',
    fade: '退潮',
    diverge: '分歧',
    uncertain: '不确定',
    mainline_confirm: '主线确认',
    new_mainline_switch: '新主线切换',
    invalid_rotation: '无效轮动',
  } as Record<string, string>)[v ?? ''] ?? (v || '—')
}

function riskColor(v?: number | null): string {
  if (v == null) return 'default'
  if (v >= 0.7) return 'red'
  if (v >= 0.5) return 'orange'
  return 'green'
}

function byHorizon(rows: SectorForwardForecast[] | undefined, h: string): SectorForwardForecast[] {
  return (rows ?? []).filter((r) => r.forecast_horizon === h)
}

function RegimeStructureTab({ date }: { date?: string }) {
  const { data, isError, error, refetch } = useQuery({
    queryKey: ['sector-regime-view', date],
    queryFn: () => sectorRegimeView(date),
  })
  if (isError) return <ErrorCard title="行情结构加载失败" message={error?.message} onRetry={() => refetch()} />
  const view = data ?? ({} as RegimeViewInfo)
  const regime = view.regime
  const t1 = byHorizon(view.forecasts, 't1')
  const t3 = byHorizon(view.forecasts, 't3')
  const t5 = byHorizon(view.forecasts, 't5')
  const watch = t1.slice(0, 5)
  const highChase = t1.filter((r) => (r.chase_risk ?? 0) >= 0.6).slice(0, 5)
  const switches = t3.concat(t5).filter((r, i, arr) =>
    r.switch_candidate && arr.findIndex((x) => x.sector_name === r.sector_name) === i).slice(0, 5)
  const acc30 = (view.accuracy?.windows ?? []).find((w) => w.window_days === 30)

  return (
    <Space orientation="vertical" style={{ width: '100%' }} size={12}>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ ...panelStyle, flex: '2 1 360px' }}>
          <Text type="secondary">当前行情结构 · {view.trade_date ?? '—'}</Text>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginTop: 4 }}>
            <span style={{ fontSize: 28, fontWeight: 700 }}>{regimeLabel(regime?.current_regime)}</span>
            <Tag color={regime?.current_regime === 'mainline' ? 'red' : regime?.current_regime === 'rotation' ? 'orange' : 'default'}>
              {regime?.regime_stage ?? 'unknown'}
            </Tag>
          </div>
          <Text type="secondary">不是判断“今天风口”，而是用 3/10/20/60 日窗口给当前结构和后续倾向定档。</Text>
        </div>
        <div style={metricStyle}>
          <Text type="secondary">结构置信度</Text>
          <Progress percent={Math.round((regime?.regime_confidence ?? 0) * 100)} size="small" />
        </div>
        <div style={metricStyle}>
          <Text type="secondary">近30日样本</Text>
          <div style={{ fontSize: 24, fontWeight: 700 }}>{acc30?.sample_count ?? 0}</div>
          <Text type="secondary">用于校准这套前瞻准不准</Text>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
        {[
          ['T+1', regime?.forward_bias_t1],
          ['T+3', regime?.forward_bias_t3],
          ['T+5', regime?.forward_bias_t5],
        ].map(([k, v]) => (
          <div key={k} style={panelStyle}>
            <Text type="secondary">{k} 倾向</Text>
            <div style={{ fontSize: 20, fontWeight: 650 }}>{biasLabel(v)}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 10 }}>
        <div style={panelStyle}>
          <Text strong>最值得观察</Text>
          <List size="small" dataSource={watch} locale={{ emptyText: '暂无板块前瞻' }} renderItem={(r) => (
            <List.Item style={{ paddingInline: 0 }}>
              <Space wrap>
                <Tag>{r.rank_no}</Tag><Text strong>{r.sector_name}</Text><Tag color="blue">{biasLabel(r.forward_bias)}</Tag>
                <Text type="secondary">延续 {pct(r.continuation_prob)}</Text>
              </Space>
            </List.Item>
          )} />
        </div>
        <div style={panelStyle}>
          <Text strong>高追风险</Text>
          <List size="small" dataSource={highChase} locale={{ emptyText: '暂无显著高追风险' }} renderItem={(r) => (
            <List.Item style={{ paddingInline: 0 }}>
              <Space wrap>
                <Text strong>{r.sector_name}</Text><Tag color={riskColor(r.chase_risk)}>追高 {pct(r.chase_risk)}</Tag>
                <Text type="secondary">退潮 {pct(r.exhaustion_risk)}</Text>
              </Space>
            </List.Item>
          )} />
        </div>
        <div style={panelStyle}>
          <Text strong>潜在切换</Text>
          <List size="small" dataSource={switches} locale={{ emptyText: '暂无切换候选' }} renderItem={(r) => (
            <List.Item style={{ paddingInline: 0 }}>
              <Space wrap>
                <Text strong>{r.sector_name}</Text><Tag color="purple">{String(r.forecast_horizon).toUpperCase()}</Tag>
                <Text type="secondary">{biasLabel(r.forward_bias)}</Text>
              </Space>
            </List.Item>
          )} />
        </div>
      </div>

      <Card size="small" title="三窗口板块前瞻" style={{ background: 'var(--bg-input)' }}>
        <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
          <thead>
            <tr><th style={thStyle}>窗口</th><th style={thStyle}>板块</th><th style={thStyle}>倾向</th><th style={thStyle}>延续</th><th style={thStyle}>退潮</th><th style={thStyle}>追高</th><th style={thStyle}>切换</th></tr>
          </thead>
          <tbody>
            {[...t1.slice(0, 5), ...t3.slice(0, 5), ...t5.slice(0, 5)].map((r, i) => (
              <tr key={`${r.forecast_horizon}-${r.sector_name}-${i}`}>
                <td style={tdStyle}>{String(r.forecast_horizon).toUpperCase()}</td>
                <td style={tdStyle}>{r.sector_name}</td>
                <td style={tdStyle}>{biasLabel(r.forward_bias)}</td>
                <td style={tdStyle}>{pct(r.continuation_prob)}</td>
                <td style={tdStyle}>{pct(r.exhaustion_risk)}</td>
                <td style={tdStyle}>{pct(r.chase_risk)}</td>
                <td style={tdStyle}>{r.switch_candidate ? '是' : '否'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card size="small" title="历史准确率" style={{ background: 'var(--bg-input)' }}>
        <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
          <thead>
            <tr><th style={thStyle}>窗口</th><th style={thStyle}>结构</th><th style={thStyle}>样本</th><th style={thStyle}>结构命中</th><th style={thStyle}>Top5延续</th><th style={thStyle}>主线命中</th></tr>
          </thead>
          <tbody>
            {(view.accuracy?.windows ?? []).flatMap((w) => (w.groups ?? []).map((g) => ({ w, g }))).map(({ w, g }, i) => (
              <tr key={i}>
                <td style={tdStyle}>{w.window_days}日</td>
                <td style={tdStyle}>{regimeLabel(g.regime)}</td>
                <td style={tdStyle}>{g.sample_count ?? 0}</td>
                <td style={tdStyle}>{pct(g.regime_hit_rate)}</td>
                <td style={tdStyle}>{pct(g.top5_continue_rate)}</td>
                <td style={tdStyle}>{pct(g.mainline_hit_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Collapse size="small" items={[{
        key: 'evidence',
        label: '证据与后验明细',
        children: <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{JSON.stringify({ evidence: regime?.evidence, verify: view.verify }, null, 2)}</pre>,
      }]} />
    </Space>
  )
}

/** 板块轮动决策 Tab：看板切换（日期+手动分析）→ AI 评估（启动归因高亮）→ 多窗口规律解读 */
function SectorRotationTab() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const { data: rDates } = useQuery({ queryKey: ['sector-rotation-dates'], queryFn: () => marketIntelDates(30) })
  const [rDate, setRDate] = useState<string>()
  const curRDate = rDate ?? rDates?.[0]

  const { data: rot } = useQuery({
    queryKey: ['sector-rotation', curRDate],
    queryFn: () => sectorRotation(curRDate),
  })
  const { data: pats } = useQuery({ queryKey: ['sector-patterns'], queryFn: () => sectorPatterns() })
  const runRot = useTaskSubmit('sector_rotation', () => {
    message.success('板块轮动分析任务已提交后台')
    qc.invalidateQueries({ queryKey: ['sector-rotation'] })
  })
  // 每条启动归因的"理由全文展开"状态（index → 是否展开），无条件在顶部声明（Hooks 纪律）
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})
  const toggleExpand = (i: number) => setExpanded((prev) => ({ ...prev, [i]: !prev[i] }))

  const stateColor: Record<string, string> = {
    mainline: 'var(--up)', rotation: 'var(--warn)', chaos: 'var(--err)',
  }
  const stateLabel: Record<string, string> = { mainline: '主线行情', rotation: '轮动行情', chaos: '混沌行情' }
  const launchList = rot?.launch?.length ? rot.launch : (rot?.launch_reasons ?? [])
  const st = rot?.rotation_state ?? ''
  const churn = rot?.churn_rate

  return (
    <Space orientation="vertical" style={{ width: '100%' }} size={12}>
      {/* 看板切换条 */}
      <Space wrap>
        <Select placeholder="选择轮动日期" style={{ width: 160 }} value={curRDate} onChange={setRDate}
          options={(rDates ?? []).map((d) => ({ label: d, value: d }))} />
        <Button type="primary" loading={runRot.submit.isPending} onClick={() => runRot.submit.mutate({})}>
          立即分析（后台）
        </Button>
      </Space>

      {/* 看板指标卡 */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 240px', border: '1px solid var(--border)', borderRadius: 8, padding: 12, background: 'var(--bg-input)' }}>
          <Text type="secondary">轮动状态</Text>
          <div style={{ fontSize: 24, fontWeight: 700, color: stateColor[st] }}>{stateLabel[st] ?? rot?.rotation_state ?? '（数据缺失）'}</div>
          <Text type="secondary" style={{ display: 'block', fontSize: 11 }}>三态判定：主线行情=资金集中单主线；轮动=高低切换快；混沌=无明确主线。</Text>
        </div>
        <div style={{ flex: '1 1 240px', border: '1px solid var(--border)', borderRadius: 8, padding: 12, background: 'var(--bg-input)' }}>
          <Text type="secondary">主切频次 · 主线板块</Text>
          <div style={{ fontSize: 24, fontWeight: 700 }}>
            {churn != null ? `${churn} 次` : '—'}
            <span style={{ fontSize: 14, fontWeight: 500, marginLeft: 8 }}>{rot?.mainline_sector ?? '—'}</span>
          </div>
          <Text type="secondary" style={{ display: 'block', fontSize: 11 }}>churn 越高说明板块切换越频繁；主线板块是资金持续抱团的方向。</Text>
        </div>
      </div>

      {/* AI 评估区 */}
      <Card size="small" style={{ background: 'var(--bg-input)' }}
        title={<span>AI 评估 · 本轮判定 {rot?.count ?? launchList.length} 个板块启动，理由摘要如下</span>}>
        {launchList.length ? launchList.map((lr, i) => (
          <Card key={i} size="small" style={{ marginBottom: 6, background: 'var(--bg-input)' }}>
            <Space wrap><Text strong style={{ fontSize: 15 }}>{lr.sector_name ?? '—'}</Text><Tag color="blue">{lr.reason_tags ?? '（数据缺失）'}</Tag></Space>
            {(() => {
              const full = lr.reason_text || '（数据缺失）'
              const cut = full.split(/[。；\n]/).reduce((acc, s) => (acc.length + s.length + 1 <= 80 ? (acc ? acc + '。' + s : s) : acc), '')
              const isOpen = expanded[i]
              return (
                <div style={{ fontSize: 13, marginTop: 4 }}>
                  <div>{isOpen ? full : (cut || full.slice(0, 80))}</div>
                  {full.length > 80 ? (
                    <Button type="link" size="small" style={{ padding: 0, height: 'auto' }} onClick={() => toggleExpand(i)}>
                      {isOpen ? '折叠' : '展开查看全文'}
                    </Button>
                  ) : null}
                </div>
              )
            })()}
            {lr.reason_chain ? (
              <Collapse size="small" style={{ marginTop: 6 }} items={[{
                key: 'chain',
                label: 'reason_chain 证据链',
                children: (
                  <div>
                    <Text type="secondary" style={{ display: 'block', fontSize: 12, marginBottom: 6 }}>
                      证据链 = 本次判定背后的关键数据点与逻辑步骤，非原始 JSON
                    </Text>
                    {(() => {
                      const rc = lr.reason_chain
                      if (Array.isArray(rc)) return (
                        <Descriptions size="small" column={1} items={rc.map((it, j) => {
                          const o = (it ?? {}) as Record<string, unknown>
                          const reason = Object.entries(o).map(([k, v]) => `${k}: ${fmt(v)}`).join('；')
                          return { key: `rc-${j}`, label: `步骤 ${j + 1}`, children: <div style={{ whiteSpace: 'pre-wrap' }}>{reason}</div> }
                        })} />
                      )
                      if (typeof rc === 'object') return <DictTab dict={rc as Record<string, unknown>} empty="（证据链为空）" />
                      return <Text>{String(rc)}</Text>
                    })()}
                  </div>
                ),
              }]} />
            ) : null}
          </Card>
        )) : <Text type="secondary">（当日无启动归因）</Text>}
      </Card>

      {/* 多窗口规律 */}
      <Card size="small" title="多窗口规律（3/10/20/60 日）" style={{ background: 'var(--bg-input)' }}>
        <Text type="secondary" style={{ display: 'block', fontSize: 12, marginBottom: 8 }}>
          多窗口规律 = 不同时间尺度下板块轮动的统计特征，用于判断「短期换手 vs 中期主线 vs 长期生命周期」。重点关注：轮动周期天（越小越活跃）、生命周期天（越大主线越长）、放量延续率（越大趋势越稳）。
        </Text>
        <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={thStyle}>窗口</th>
              {[['轮动周期(天)', '越小说明板块切换越快、短线越活跃'], ['生命周期(天)', '越大说明主线行情持续时间越长'], ['高切频次', '越大说明资金在板块间切换越频繁'], ['放量延续率', '量比≥1.5 且居前板块次日收涨占比，越大趋势越稳']].map(([t, tip]) => (
                <Tooltip key={t} title={tip}><th style={thStyle}>{t}</th></Tooltip>
              ))}
            </tr>
          </thead>
          <tbody>
            {['3d', '10d', '20d', '60d'].map((w) => {
              const p = pats?.patterns?.[w]
              return (
                <tr key={w}>
                  <td style={tdStyle}>{w}</td>
                  <td style={tdStyle}>{p?.rotation_cycle_days ?? '—'}</td>
                  <td style={tdStyle}>{p?.lifecycle_avg_streak ?? '—'}</td>
                  <td style={tdStyle}>{p?.switch_frequency ?? '—'}</td>
                  <td style={tdStyle}>{p?.volume_breakout_continuation ?? '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <Text type="secondary" style={{ fontSize: 12 }}>放量延续率 = 量比≥1.5 且居前板块次日收涨占比（非箱位口径）</Text>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
          {[
            ['短线操作（3d/10d）', '看「轮动周期天」「高切频次」—— 轮动周期越小、高切越频，说明短周期活跃，适合快进快出，避免追高隔日票'],
            ['中线布局（10d/20d）', '看「生命周期天」「放量延续率」—— 生命周期越长、放量延续率高，说明趋势持续性强，可分批中线建仓'],
            ['长期判断（20d/60d）', '看「生命周期天」—— 60 日窗口生命周期长即主线持续时间久，是中期主线候选，适合持仓穿越'],
          ].map(([t, desc]) => (
            <div key={t} style={{ flex: '1 1 220px', border: '1px solid var(--border)', borderRadius: 8, padding: 10, background: 'var(--bg-input)' }}>
              <Text strong>{t}</Text>
              <Text type="secondary" style={{ display: 'block', fontSize: 11 }}>{desc}</Text>
            </div>
          ))}
        </div>
      </Card>
    </Space>
  )
}

/** 市场研判页（Phase 3） */
export function MarketIntelPage() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [date, setDate] = useState<string>()

  const { data: dates } = useQuery({ queryKey: ['mi-dates'], queryFn: () => marketIntelDates(30) })
  const { data: mi, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['market-intel', date],
    queryFn: () => marketIntel(date),
    enabled: !!date || !!dates?.length,
  })

  const run = useTaskSubmit('market_intel', () => {
    message.success('市场研判任务已提交后台')
    qc.invalidateQueries({ queryKey: ['mi-dates'] })
    qc.invalidateQueries({ queryKey: ['market-intel'] })
  })
  const runRegime = useTaskSubmit('sector_forward', () => {
    message.success('行情结构前瞻已完成')
    qc.invalidateQueries({ queryKey: ['sector-regime-view'] })
  })
  const runVerify = useTaskSubmit('sector_forecast_verify', () => {
    message.success('前瞻验证回填已完成')
    qc.invalidateQueries({ queryKey: ['sector-regime-view'] })
  })

  const appetite: Record<string, { label: string; color: string; 含义: string }> = {
    进取: { label: '进取', color: 'red', 含义: '资金转进攻，可增配主线强势方向' },
    中性: { label: '中性', color: 'default', 含义: '资金偏好均衡，维持中性仓位右侧确认' },
    避险: { label: '避险', color: 'orange', 含义: '资金退守防御，控制仓位等待企稳' },
  }

  return (
    <div>
      <Space style={{ marginBottom: 10 }} wrap>
        <Select placeholder="选择研判日期" style={{ width: 160 }} value={date ?? dates?.[0]} onChange={setDate}
          options={(dates ?? []).map((d) => ({ label: d, value: d }))} />
        <Button type="primary" loading={runRegime.submit.isPending} onClick={() => runRegime.submit.mutate({ trade_date: date })}>
          刷新行情结构
        </Button>
        <Button loading={runVerify.submit.isPending} onClick={() => runVerify.submit.mutate({ forecast_date: date })}>
          回填验证
        </Button>
        <Button type="primary" loading={run.submit.isPending} onClick={() => run.submit.mutate({})}>
          立即研判（后台）
        </Button>
        <Button onClick={() => refetch()}>刷新</Button>
      </Space>

      {mi?.phase ? (
        <Alert
          style={{ marginBottom: 10 }}
          type="info" showIcon
          title={`阶段定性 · ${appetite[mi.risk_appetite ?? '']?.label ?? '（无）'}：${mi.phase}`}
          description={mi.summary ? `一句话总结：${mi.summary}` : undefined}
        />
      ) : null}

      <Tabs
        defaultActiveKey="regime"
        items={[
          {
            key: 'regime', label: '行情结构',
            children: <RegimeStructureTab date={date ?? dates?.[0]} />,
          },
          {
            key: 'basis', label: '市场判定依据',
            children: isError ? (
              <ErrorCard title="市场研判加载失败" message={error?.message} onRetry={() => refetch()} />
            ) : isLoading ? null : !mi?.phase ? (
              <EmptyState text="当日暂无市场研判，可点击上方「立即研判」生成。" actionLabel="立即研判" onAction={() => run.submit.mutate({})} />
            ) : (
              <Card size="small" style={{ marginBottom: 10, background: 'var(--bg-input)' }}
                title={<span>判定依据 <Text type="secondary" style={{ fontSize: 12 }}>支撑本轮阶段定性的关键数据与证据</Text></span>}>
              {(() => {
                const m = mi as unknown as Record<string, unknown>
                const vs = (mi.volume_signal ?? {}) as Record<string, unknown>
                const ra = mi.risk_appetite
                const ap = ra ? appetite[ra] : undefined
                const breadth = m.breadth ?? vs['分布']
                const leading = ((Array.isArray(m.leading_sectors) ? m.leading_sectors : Array.isArray(vs['放量板块']) ? vs['放量板块'] : vs['放量板块'] != null ? [vs['放量板块']] : []) as unknown[]).slice(0, 3)
                const evRaw = (Array.isArray(m.evidence) ? m.evidence.map(String) : m.evidence != null ? [String(m.evidence)] : []) as string[]
                const ev = evRaw.length ? evRaw.slice(0, 3) : (mi.core_conflict ?? '').split(/[。；\n]/).map((s) => s.trim()).filter(Boolean).concat(mi.summary ? [mi.summary] : []).slice(0, 3)
                const breadthItems = (breadth == null ? '' : fmt(breadth)).split(/[，,;；\n]/).map((s) => s.trim()).filter(Boolean)
                return (
                  <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                    <div style={{ flex: '1 1 260px', minWidth: 240 }}>
                      <Descriptions size="small" column={1} items={[
                        { key: 'ph', label: '阶段定性', children: <span>{mi.phase}{ap ? <Tag color={ap.color} style={{ marginLeft: 6 }}>{ap.label}</Tag> : null}</span> },
                        { key: 'bd', label: '市场广度', children: breadthItems.length ? <Space size={[4, 4]} wrap>{breadthItems.map((t, i) => <Tag key={i} style={{ marginInlineEnd: 0 }}>{t}</Tag>)}</Space> : <Text type="secondary">（未提供）</Text> },
                        { key: 'ml', label: '主线板块', children: leading.length ? <Space size={[4, 4]} wrap>{leading.map((s, i) => <Tag key={i} color="red" style={{ marginInlineEnd: 0 }}>{String(s)}</Tag>)}</Space> : <Text type="secondary">（未提供）</Text> },
                        { key: 'ra', label: '风险偏好', children: <span>{ap?.label ?? '（未提供）'}{ap?.含义 ? <Text type="secondary" style={{ display: 'block', fontSize: 12 }}>{ap.含义}</Text> : null}</span> },
                      ]} />
                    </div>
                    <div style={{ flex: '1 1 260px', minWidth: 240 }}>
                      <Text strong>作证证据</Text>
                      {ev.length ? <List size="small" dataSource={ev} renderItem={(it) => <List.Item style={{ padding: '2px 0' }}>{it}</List.Item>} />
                        : <Text type="secondary">（未提供）</Text>}
                    </div>
                  </div>
                )
              })()}
              </Card>
            ),
          },
          {
            key: 'conflict', label: '核心矛盾',
            children: mi?.core_conflict ? <div style={{ whiteSpace: 'pre-wrap' }}>{mi.core_conflict}</div>
              : <Text type="secondary">（该轮未输出）</Text>,
          },
          {
            key: 'volume', label: '板块量能信号',
            children: (() => {
              const vs = (mi?.volume_signal ?? {}) as Record<string, unknown>
              if (!Object.keys(vs).length) return <Text type="secondary">（该轮未输出量能信号）</Text>
              return (
                <Descriptions size="small" column={1} items={[
                  { key: 'fc', label: '放量板块', children: String(vs['放量板块'] ?? '（无/数据缺失）') },
                  { key: 'sc', label: '缩量板块', children: String(vs['缩量板块'] ?? '（无/数据缺失）') },
                  ...(vs['极端量能'] ? [{ key: 'ext', label: '极端量能', children: String(vs['极端量能']) }] : []),
                  ...(vs['分布'] != null ? [{ key: 'dist', label: '放量/缩量分布', children: String(vs['分布']) }] : []),
                ]} />
              )
            })(),
          },
          {
            key: 'operative', label: '操作含义',
            children: <DictTab dict={mi?.operative_meaning} empty="（该轮未输出操作含义）" />,
          },
          {
            key: 'watch', label: '次日盯盘点',
            children: <DictTab dict={mi?.next_day_watch} empty="（该轮未输出次日盯盘点）" />,
          },
          {
            key: 'rotation', label: '旧轮动归因',
            children: <SectorRotationTab />,
          },
          {
            key: 'raw',
            label: '原始返回',
            children: (
              <>
                <DeepModules mi={mi ?? ({} as MarketIntelInfo)} />
                <Collapse
                  size="small"
                  style={{ marginTop: 10, background: 'var(--bg-input)' }}
                  items={[{
                    key: 'raw',
                    label: '查看 AI 原始返回（高级/可追溯）',
                    children: (
                      <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0 }}>
                        {JSON.stringify(mi ?? {}, null, 2)}
                      </pre>
                    ),
                  }]}
                />
              </>
            ),
          },
        ]}
      />
    </div>
  )
}

export default MarketIntelPage
