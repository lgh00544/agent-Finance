import { useState } from 'react'
import { App, Alert, Button, Card, Descriptions, Select, Space, Tabs, Typography } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { marketIntel, marketIntelDates } from '@/api/market'
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

  const appetite: Record<string, { label: string; color: string }> = {
    进取: { label: '进取', color: 'red' },
    中性: { label: '中性', color: 'default' },
    避险: { label: '避险', color: 'orange' },
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
                children: (() => {
                  const om = mi?.operative_meaning ?? {}
                  if (!Object.keys(om).length) return <Text type="secondary">（该轮未输出操作含义）</Text>
                  return <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{flatten(om)}</pre>
                })(),
              },
              {
                key: 'watch', label: '次日盯盘点',
                children: (() => {
                  const nw = mi?.next_day_watch ?? {}
                  if (!Object.keys(nw).length) return <Text type="secondary">（该轮未输出次日盯盘点）</Text>
                  return <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{flatten(nw)}</pre>
                })(),
              },
            ]}
          />

          <DeepModules mi={mi ?? ({} as MarketIntelInfo)} />

          <Card size="small" title="原始数据（可追溯，不编造）" style={{ marginTop: 10, background: 'var(--bg-input)' }}>
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0 }}>
              {JSON.stringify(mi ?? {}, null, 2)}
            </pre>
          </Card>
        </>
      )}
    </div>
  )
}

export default MarketIntelPage
