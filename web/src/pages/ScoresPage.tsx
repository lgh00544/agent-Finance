import { useMemo, useState } from 'react'
import {
  App,
  Alert,
  Button,
  Card,
  Collapse,
  Descriptions,
  Input,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { scores } from '@/api/scores'
import { stockNames } from '@/api/candidates'
import { useTaskSubmit } from '@/hooks/useTaskSubmit'
import { EmptyState, ErrorCard, StockLabel } from '@/components/common'
import { ConfidenceBar } from '@/components/common'
import type { StockScoreInfo } from '@/types'

const { Text } = Typography
const GRADE_TONE: Record<string, string> = { A: 'red', B: 'orange', C: 'blue' }

const SIGNAL_TONE: Record<string, string> = { 看多: 'red', 中性: 'default', 看空: 'green' }

/** v4.0 六因子评分卡：因子名 + 得分 + 结论 + 依据（signal 为结论，reason 为依据） */
function FactorCards({ detail }: { detail: Record<string, unknown> }) {
  const factors = (detail.factors as Array<Record<string, unknown>>) ?? []
  return (
    <div>
      {factors.length ? (
        factors.map((f, i) => {
          const score = Number(f.score ?? 0)
          const signal = String(f.signal ?? '')
          return (
            <div key={String(f.factor ?? i)} style={{ marginBottom: 10, padding: 8, borderRadius: 6, background: 'var(--bg-input)' }}>
              <Space style={{ alignItems: 'center' }}>
                <Text style={{ width: 110, fontWeight: 600 }}>{String(f.factor ?? '—')}</Text>
                <div className="conf-bar" style={{ width: 160 }}>
                  <div className="conf-bar-fill high" style={{ width: `${Math.max(0, Math.min(100, (score / 10) * 100))}%` }} />
                </div>
                <Text strong>{score}/10</Text>
                {signal ? <Tag color={SIGNAL_TONE[signal] ?? 'default'}>{signal}</Tag> : null}
              </Space>
              {f.reason ? <div style={{ marginTop: 4 }}><Text type="secondary">依据：{String(f.reason)}</Text></div> : null}
            </div>
          )
        })
      ) : (
        <EmptyState text="（该轮未输出因子明细）" icon="—" />
      )}
      {detail.potential_flag ? (
        <Alert type="warning" showIcon style={{ marginTop: 8 }}
          message="⚠️ 潜力标识：催化强但动量弱，可能尚未被定价" />
      ) : null}
      {detail.cross_validation_note ? (
        <Alert type="info" showIcon style={{ marginTop: 8, whiteSpace: 'pre-wrap' }} message={String(detail.cross_validation_note)} />
      ) : null}
      {detail.final_advice ? (
        <Alert type="success" showIcon style={{ marginTop: 8, whiteSpace: 'pre-wrap' }} message={String(detail.final_advice)} />
      ) : null}
    </div>
  )
}

/** 详情 Tab：六因子评分 / 事实依据与操作建议 / 风险提示 + 原始数据折叠 */
function ScoreDetail({ r }: { r: StockScoreInfo }) {
  const detail = (r.detail ?? {}) as Record<string, unknown>
  const factors = detail.factors as Array<Record<string, unknown>> | undefined
  const dims = Object.entries(detail).filter(([, v]) => v && typeof v === 'object' && 'score' in (v as object) && !Array.isArray(v))
  const risks = r.risk_list ?? []
  const hasExtra = !!(detail.confidence_tier || detail.stock_type || detail.macro_view
    || detail.meso_view || detail.micro_view || detail.position_hint || detail.focus_type)

  const items = [
    {
      key: 'dims', label: '六因子评分',
      children: factors?.length ? (
        <FactorCards detail={detail} />
      ) : (
        // 旧格式降级：{维度名: {score, verdict, advice/comment}} 字典
        <div>
          {dims.length ? (
            dims.map(([name, v]) => {
              const vv = v as { score?: number; verdict?: string; advice?: string; comment?: string }
              const score = Number(vv.score ?? 0)
              const verdict = String(vv.verdict ?? '')
              const color = verdict === '支持' ? 'var(--up)' : verdict === '风险' ? 'var(--warn)' : 'var(--text-mute)'
              return (
                <div key={name} style={{ marginBottom: 6 }}>
                  <Space>
                    <Text style={{ width: 90, fontWeight: 600 }}>{name}</Text>
                    <div className="conf-bar" style={{ width: 200 }}>
                      <div className="conf-bar-fill high" style={{ width: `${Math.max(0, Math.min(100, score))}%`, background: color }} />
                    </div>
                    <Text type="secondary">{score.toFixed(0)}</Text>
                    {verdict ? <Tag color={verdict === '支持' ? 'red' : verdict === '风险' ? 'orange' : 'default'}>{verdict}</Tag> : null}
                  </Space>
                  {(vv.advice || vv.comment) ? <div style={{ marginLeft: 96 }}><Text type="secondary">{String(vv.advice ?? vv.comment)}</Text></div> : null}
                </div>
              )
            })
          ) : (
            <EmptyState text="（该轮未输出分项明细）" icon="—" />
          )}
          {detail.final_advice ? (
            <Alert type="success" showIcon style={{ marginTop: 8, whiteSpace: 'pre-wrap' }} message={String(detail.final_advice)} />
          ) : null}
        </div>
      ),
    },
  ]
  if (hasExtra) {
    items.push({
      key: 'extra', label: '事实依据与操作建议',
      children: (
        <Descriptions size="small" column={1} items={[
          ...(detail.confidence_tier ? [{
            key: 'k202', label: 'K202 信心度检查',
            children: `${String(detail.confidence_tier)}${detail.confidence_pct != null ? `（参考 ${detail.confidence_pct}%）` : ''}`,
          }] : []),
          ...(detail.stock_type ? [{ key: 'type', label: '派发期校验（标的类型定位）', children: String(detail.stock_type) }] : []),
          ...(detail.macro_view || detail.meso_view || detail.micro_view ? [{
            key: '3d', label: '三维验证',
            children: `宏观 ${String(detail.macro_view ?? '（无）')}；中观 ${String(detail.meso_view ?? '（无）')}；微观 ${String(detail.micro_view ?? '（无）')}`,
          }] : []),
          ...(detail.focus_type ? [{ key: 'focus', label: '关注类型', children: String(detail.focus_type) }] : []),
          ...(detail.position_hint ? [{ key: 'hint', label: '参考建议', children: String(detail.position_hint) }] : []),
        ]} />
      ),
    })
  }
  items.push({
    key: 'risk', label: '风险提示',
    children: (
      <div>
        {risks.length ? risks.map((risk, i) => <div key={i}>⚠️ {String(risk)}</div>)
          : <EmptyState text="（无）" icon="—" />}
      </div>
    ),
  })

  return (
    <div style={{ marginTop: 8 }}>
      <Card size="small" style={{ background: 'var(--bg-input)', marginBottom: 8 }}>
        <Space wrap>
          <StockLabel code={r.stock_code} name={r.stock_name} />
          <Text>{r.trade_date}</Text>
          <Tag color={GRADE_TONE[r.grade ?? ''] ?? 'default'}>{r.grade ?? '未评级'} 级</Tag>
          <Tag color="blue">综合分 {r.score ?? '—'}</Tag>
        </Space>
        <ConfidenceBar confidence={(r.score ?? 0) / 100} caption={`综合分 ${r.score ?? '—'} / 100`} />
      </Card>

      <Tabs defaultActiveKey="dims" items={items} />

      <Collapse
        ghost
        size="small"
        style={{ marginTop: 4 }}
        items={[{
          key: 'raw', label: <Text type="secondary">原始数据（审计）</Text>,
          children: (
            <pre style={{ background: 'var(--bg-input)', padding: 12, borderRadius: 6, whiteSpace: 'pre-wrap', fontSize: 11 }}>
              {JSON.stringify({ detail: r.detail, risk_list: r.risk_list }, null, 2)}
            </pre>
          ),
        }]}
      />
    </div>
  )
}

/** 评分报告页（Phase 2） */
export function ScoresPage() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [keyword, setKeyword] = useState('')
  const [dateF, setDateF] = useState<string>()
  const [selId, setSelId] = useState<number | null>(null)
  const [manualCode, setManualCode] = useState('')

  const { data: allRows, isError, error, refetch } = useQuery({ queryKey: ['scores'], queryFn: () => scores() })

  // 名称补全
  const missing = (allRows ?? []).filter((r) => !r.stock_name || r.stock_name === r.stock_code).map((r) => r.stock_code)
  const { data: names } = useQuery({
    queryKey: ['stock-names', missing.join(',')],
    queryFn: () => stockNames(missing),
    enabled: missing.length > 0,
  })

  const dates = useMemo(() => Array.from(new Set((allRows ?? []).map((r) => r.trade_date))).sort().reverse(), [allRows])

  const filtered = useMemo(() => (allRows ?? []).filter((r) => {
    const kw = keyword.trim()
    if (kw && !r.stock_code.includes(kw) && !(r.stock_name ?? '').includes(kw)) return false
    if (dateF && r.trade_date !== dateF) return false
    return true
  }), [allRows, keyword, dateF])

  if (isError) return <ErrorCard title="评分报告加载失败" message={error?.message} onRetry={() => refetch()} />

  const manualScore = useTaskSubmit('score', () => {
    message.success('打分任务已提交后台')
    qc.invalidateQueries({ queryKey: ['scores'] })
  })

  const selRow = filtered.find((r) => r.id === selId) ?? filtered[0] ?? null

  const genPlan = useTaskSubmit('position', () => {
    message.success('建仓方案生成任务已提交后台')
    qc.invalidateQueries({ queryKey: ['plans'] })
  })

  return (
    <div>
      <Space style={{ marginBottom: 10 }} wrap>
        <Input placeholder="按代码或名称搜索" style={{ width: 220 }} value={keyword}
          onChange={(e) => setKeyword(e.target.value)} />
        <Select placeholder="全部日期" allowClear style={{ width: 130 }} value={dateF} onChange={setDateF}
          options={dates.map((d) => ({ label: d, value: d }))} />
        <Button onClick={() => refetch()}>刷新</Button>
      </Space>

      {!filtered.length ? (
        <EmptyState text="暂无匹配的评分数据。" icon="🔍" />
      ) : (
        <>
          <Table<StockScoreInfo>
            rowKey="id" size="small" dataSource={filtered}
            pagination={{ pageSize: 20 }}
            rowClassName={(r) => (r.id === selRow?.id ? 'ant-table-row-selected' : '')}
            onRow={(r) => ({ onClick: () => r.id != null && setSelId(r.id) })}
            columns={[
              {
                title: '股票', key: 'stock', width: 180,
                render: (_: unknown, r: StockScoreInfo) => (
                  <StockLabel code={r.stock_code} name={names?.[r.stock_code] ?? r.stock_name} />
                ),
              },
              { title: '日期', dataIndex: 'trade_date', width: 100 },
              {
                title: '综合分', dataIndex: 'score', width: 90,
                render: (v: number) => <Text strong>{v ?? '—'}</Text>,
              },
              {
                title: '评级', dataIndex: 'grade', width: 90,
                render: (v: string) => (v ? <Tag color={GRADE_TONE[v] ?? 'default'}>{v} 级</Tag> : '—'),
              },
              {
                title: '操作', key: 'ops', width: 150,
                render: (_: unknown, r: StockScoreInfo) => (
                  <Button size="small" loading={genPlan.submit.isPending}
                    onClick={(e) => {
                      e.stopPropagation()
                      genPlan.submit.mutate({ stock_code: r.stock_code, stock_name: r.stock_name ?? '' })
                    }}>
                    生成建仓方案
                  </Button>
                ),
              },
            ]}
          />
          {selRow ? <ScoreDetail r={selRow} /> : null}
        </>
      )}

      <Card size="small" title="手动打分" style={{ marginTop: 16, background: 'var(--bg-input)' }}>
        <Space>
          <Input placeholder="6 位股票代码" style={{ width: 180 }} maxLength={6} value={manualCode}
            onChange={(e) => setManualCode(e.target.value)} />
          <Button type="primary" loading={manualScore.submit.isPending}
            onClick={() => manualScore.submit.mutate({ stock_code: manualCode, stock_name: '' })}>
            触发打分（后台）
          </Button>
        </Space>
      </Card>
    </div>
  )
}

export default ScoresPage
