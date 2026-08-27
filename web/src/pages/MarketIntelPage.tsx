import { type CSSProperties, useState } from 'react'
import { App, Alert, Button, Card, Collapse, Descriptions, List, Select, Space, Tabs, Tag, Typography } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { marketIntel, marketIntelDates, sectorPatterns, sectorRotation } from '@/api/market'
import { useTaskSubmit } from '@/hooks/useTaskSubmit'
import { EmptyState, ErrorCard } from '@/components/common'
import type { MarketIntelInfo } from '@/types'

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
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      {vc ? <Alert type="info" showIcon message={`量能成色：${String(vc)}`} /> : null}

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

/** 板块轮动 Tab：状态徽章 + top10 表 + 归因卡片（可展开 reason_chain）+ 规律表 */
function SectorRotationTab() {
  const { data: rot } = useQuery({ queryKey: ['sector-rotation'], queryFn: () => sectorRotation() })
  const { data: pats } = useQuery({ queryKey: ['sector-patterns'], queryFn: () => sectorPatterns() })

  const stateColor: Record<string, string> = {
    mainline: 'var(--up)', rotation: 'var(--warn)', chaos: 'var(--err)',
  }
  const launchList = rot?.launch?.length ? rot.launch : (rot?.launch_reasons ?? [])

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={12}>
      <Alert
        type="info" showIcon
        message={
          <span>
            轮动状态 ·{' '}
            <Text style={{ color: stateColor[rot?.rotation_state ?? ''] }}>{rot?.rotation_state ?? '（数据缺失）'}</Text>
            {rot?.rotation_state ? <> · churn {rot?.churn_rate ?? '—'} · 主线 {rot?.mainline_sector ?? '无'}</> : null}
          </span>
        }
      />

      {rot?.top10?.length ? (
        <Card size="small" title="今日 top10 板块" style={{ background: 'var(--bg-input)' }}>
          <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
            <thead>
              <tr><th style={thStyle}>排名</th><th style={thStyle}>板块</th><th style={thStyle}>涨幅%</th><th style={thStyle}>量比</th></tr>
            </thead>
            <tbody>
              {rot.top10.map((r, i) => (
                <tr key={i}>
                  <td style={tdStyle}>{r.rank_no ?? i + 1}</td>
                  <td style={tdStyle}>{r.sector_name ?? '—'}</td>
                  <td style={{ ...tdStyle, color: (r.change_pct ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }}>{r.change_pct ?? '—'}</td>
                  <td style={tdStyle}>{r.volume_ratio ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : <Text type="secondary">（当日无 top10 快照，可手动触发板块轮动分析）</Text>}

      {launchList.length ? (
        <Card size="small" title="启动归因（可展开 reason_chain 证据链）" style={{ background: 'var(--bg-input)' }}>
          {launchList.map((lr, i) => (
            <Card key={i} size="small" style={{ marginBottom: 6, background: 'var(--bg-input)' }}>
              <Text strong>{lr.sector_name ?? '—'}</Text> · {lr.reason_tags || '（数据缺失）'}
              <div style={{ fontSize: 13 }}>{lr.reason_text || '（数据缺失）'}</div>
              {lr.reason_chain ? (
                <details style={{ marginTop: 4 }}>
                  <summary style={{ cursor: 'pointer', fontSize: 12 }}>reason_chain 证据链</summary>
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: '4px 0 0' }}>
                    {typeof lr.reason_chain === 'string' ? lr.reason_chain : JSON.stringify(lr.reason_chain, null, 2)}
                  </pre>
                </details>
              ) : null}
            </Card>
          ))}
        </Card>
      ) : <Text type="secondary">（当日无启动归因）</Text>}

      <Card size="small" title="多窗口规律（3/10/20/60 日）" style={{ background: 'var(--bg-input)' }}>
        <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={thStyle}>窗口</th><th style={thStyle}>轮动周期(天)</th><th style={thStyle}>生命周期(天)</th>
              <th style={thStyle}>高切频次</th><th style={thStyle}>放量延续率(量比≥1.5)</th>
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
        <Button type="primary" loading={run.submit.isPending} onClick={() => run.submit.mutate({})}>
          立即研判（后台）
        </Button>
        <Button onClick={() => refetch()}>刷新</Button>
      </Space>

      {!dates?.length ? (
        <EmptyState text="当日暂无市场研判，可点击上方「立即研判」生成（后台约 1-2 分钟）。" icon="🧠"
          actionLabel="立即研判" onAction={() => run.submit.mutate({})} />
      ) : isLoading ? null : isError ? (
        <ErrorCard title="市场研判加载失败" message={error?.message} onRetry={() => refetch()} />
      ) : (
        <>
          {mi?.phase ? (
            <Alert
              style={{ marginBottom: 10 }}
              type="info" showIcon
              message={`阶段定性 · ${appetite[mi.risk_appetite ?? '']?.label ?? '（无）'}：${mi.phase}`}
              description={mi.summary ? `一句话总结：${mi.summary}` : undefined}
            />
          ) : null}

          {mi?.phase ? (
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
          ) : null}

          <Tabs
            items={[
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
                key: 'rotation', label: '板块轮动',
                children: <SectorRotationTab />,
              },
            ]}
          />

          <DeepModules mi={mi ?? ({} as MarketIntelInfo)} />

          <Collapse
            size="small"
            style={{ marginTop: 10, background: 'var(--bg-input)' }}
            items={[{
              key: 'raw',
              label: '查看 AI 原始返回（高级/可追溯）',
              children: (
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>此处为模型返回原文，普通用户无需展开</Text>
                  <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: '8px 0 0' }}>
                    {JSON.stringify(mi ?? {}, null, 2)}
                  </pre>
                </div>
              ),
            }]}
          />
        </>
      )}
    </div>
  )
}

export default MarketIntelPage
