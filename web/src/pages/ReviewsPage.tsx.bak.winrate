import { useState } from 'react'
import {
  App,
  Alert,
  Button,
  Card,
  Drawer,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { reviews } from '@/api/reviews'
import { agentSuggestions, approveSuggestion, adoptSuggestion, rejectSuggestion } from '@/api/suggestions'
import { trackVerifyDates, trackVerifyList, trackVerifyStats, runTrackVerify, runTrackSuggest } from '@/api/track'
import { EmptyState, ErrorCard, StatCard, StatCardGrid, StockLabel } from '@/components/common'
import type { ReviewInfo } from '@/types'

const { Text } = Typography
const SUG_STATUS: Record<string, { label: string; color: string }> = {
  pending: { label: '待审核', color: 'orange' },
  approved: { label: '已采纳', color: 'green' },
  rejected: { label: '已驳回', color: 'default' },
}

/** 复盘详情抽屉（黑盒：结论 + 交易记录 + 卖出决策 + 留痕） */
function ReviewDrawer({ r, open, onClose }: { r: ReviewInfo; open: boolean; onClose: () => void }) {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  if (!r) return null
  const fb = (r.feedback ?? {}) as Record<string, unknown>
  const suggestion = (fb.profile_suggestion ?? {}) as Record<string, unknown>

  const adopt = () => modal.confirm({
    title: '采纳建议并更新偏好档案', okText: '确认采纳',
    content: '该建议将写入偏好档案，版本+1，全部 Agent 立即生效。',
    onOk: async () => {
      try { await adoptSuggestion(r.id); message.success('已采纳'); qc.invalidateQueries({ queryKey: ['reviews'] }) }
      catch (e) { message.error(e instanceof Error ? e.message : '采纳失败') }
    },
  })

  return (
    <Drawer title={r.stock_name ? `${r.stock_code} ${r.stock_name}` : r.stock_code} open={open} onClose={onClose} width={600}>
      <Space direction="vertical" style={{ width: '100%' }} size={12}>
        <Alert type="info" showIcon message={`离场 ${r.exit_date} · 持仓 ${r.hold_days} 天 · 盈亏 ${r.pnl_pct ?? '—'}%`} />
        <Card size="small" title="计划兑现度" style={{ background: 'var(--bg-input)' }}>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, margin: 0 }}>{JSON.stringify(r.plan_vs_actual ?? {}, null, 2)}</pre>
        </Card>
        <Card size="small" title="经验教训" style={{ background: 'var(--bg-input)' }}>
          <div>{r.lesson || '（无）'}</div>
        </Card>
        {suggestion.field ? (
          <Card size="small" title={`交易偏好优化建议（第 ${r.suggest_iteration ?? 1} 版·${SUG_STATUS[r.suggest_status ?? '']?.label ?? '待审核'}）`}
            style={{ background: 'var(--bg-input)' }}>
            <div>修改 <code>{String(suggestion.field)}</code> → {String(suggestion.value)}</div>
            <div><Text type="secondary">{String(suggestion.reason ?? '')}</Text></div>
            {r.suggest_status === 'pending' ? (
              <div style={{ marginTop: 8 }}>
                <Button type="primary" onClick={adopt}>采纳建议并更新偏好档案</Button>
              </div>
            ) : r.suggest_status === 'adopted' ? <Text type="success">已采纳并生效</Text> : null}
          </Card>
        ) : null}
      </Space>
    </Drawer>
  )
}

/** 复盘列表 + 黑盒详情（点击行展开） */
function ReviewsList() {
  const [drawerR, setDrawerR] = useState<ReviewInfo | null>(null)
  const { data: rows, isError, error, refetch } = useQuery({ queryKey: ['reviews'], queryFn: () => reviews() })
  if (isError) return <ErrorCard title="复盘加载失败" message={error?.message} onRetry={() => refetch()} />
  const list = rows ?? []
  if (!list.length) return <EmptyState text="暂无复盘记录。在「持仓监控」页录入人工卖出后自动触发复盘。" icon="🔁" />

  const cols = [
    {
      title: '股票', key: 'stock', width: 180,
      render: (_: unknown, r: ReviewInfo) => <StockLabel code={r.stock_code} name={r.stock_name} />,
    },
    { title: '离场日', dataIndex: 'exit_date', width: 100 },
    { title: '持仓天数', dataIndex: 'hold_days', width: 90, render: (v: number) => v ?? '—' },
    {
      title: '盈亏', dataIndex: 'pnl_pct', width: 100,
      render: (v: number) => <Text style={{ color: (v ?? 0) >= 0 ? 'var(--up)' : 'var(--down)' }}>{v >= 0 ? '+' : ''}{v ?? 0}%</Text>,
    },
    { title: '建议状态', dataIndex: 'suggest_status', width: 90, render: (v: string) => <Tag color={SUG_STATUS[v]?.color ?? 'default'}>{SUG_STATUS[v]?.label ?? v}</Tag> },
    { title: '生成', dataIndex: 'created_at', width: 150, render: (v: string) => String(v ?? '').slice(0, 16) },
  ]

  return (
    <>
      <Table<ReviewInfo> rowKey="id" size="small" dataSource={list} columns={cols} pagination={{ pageSize: 20 }}
        onRow={(r) => ({ onClick: () => setDrawerR(r) })} />
      <ReviewDrawer r={drawerR!} open={!!drawerR} onClose={() => setDrawerR(null)} />
    </>
  )
}

/** 选股准确率验证（track verify，直调） */
function TrackVerify() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [date, setDate] = useState<string>()
  const { data: dates } = useQuery({ queryKey: ['tv-dates'], queryFn: () => trackVerifyDates() })
  const { data: rows } = useQuery({
    queryKey: ['tv-list', date],
    queryFn: () => trackVerifyList(date ?? ''),
    enabled: !!date || !!dates?.length,
  })
  const { data: stats } = useQuery({ queryKey: ['tv-stats'], queryFn: () => trackVerifyStats('t5') })

  const wr = stats?.win_rate
  const avg = stats?.avg_pct
  const runVerify = async () => { try { await runTrackVerify(false); message.success('T+N 验证已提交后台'); qc.invalidateQueries({ queryKey: ['tv-list'] }) } catch (e) { message.error(e instanceof Error ? e.message : '失败') } }
  const runSuggest = async () => { try { await runTrackSuggest(); message.success('建议生成已提交后台') } catch (e) { message.error(e instanceof Error ? e.message : '失败') } }

  return (
    <div>
      <Space style={{ marginBottom: 10 }} wrap>
        <Select placeholder="选择日期" style={{ width: 140 }} value={date ?? dates?.[0]} onChange={setDate}
          options={(dates ?? []).map((d) => ({ label: d, value: d }))} />
        <Button onClick={runVerify}>手动验证（T+N）</Button>
        <Button onClick={runSuggest}>生成建议</Button>
      </Space>
      <StatCardGrid>
        <StatCard label="胜率" value={wr != null ? `${(wr * 100).toFixed(1)}%` : '无数据'}
          tone={wr != null ? (wr >= 0.5 ? 'ok' : wr < 0.4 ? 'err' : 'warn') : 'mute'}
          sub={`盈利 ${stats?.wins ?? 0} 笔 / 共 ${stats?.n ?? 0} 笔`} />
        <StatCard label="平均涨幅" value={avg != null ? `${avg >= 0 ? '+' : ''}${avg.toFixed(2)}%` : '无数据'}
          tone={avg != null ? (avg > 0 ? 'up' : avg < 0 ? 'down' : 'mute') : 'mute'} />
        <StatCard label="盈亏比" value={stats?.pl_ratio != null ? stats.pl_ratio.toFixed(2) : '—'} tone="mute" />
        <StatCard label="样本量" value={stats?.n ?? 0} tone="mute" sub="T+5 已到期" />
      </StatCardGrid>
      <Table size="small" rowKey="id" dataSource={rows ?? []} pagination={{ pageSize: 10 }}
        columns={[
          { title: '股票', key: 'stock', render: (_: unknown, r: Record<string, unknown>) => <StockLabel code={String(r.stock_code ?? '')} name={String(r.stock_name ?? '')} /> },
          { title: '选中日', dataIndex: 'select_date', width: 100 },
          { title: 'T+3', dataIndex: 't3_pct', width: 70, render: (v: unknown) => v != null ? `${v}%` : '—' },
          { title: 'T+5', dataIndex: 't5_pct', width: 70, render: (v: unknown) => v != null ? `${v}%` : '—' },
          { title: 'T+10', dataIndex: 't10_pct', width: 80, render: (v: unknown) => v != null ? `${v}%` : '—' },
          { title: '最大回撤%', dataIndex: 'max_drawdown', width: 90, render: (v: unknown) => v ?? '—' },
        ]} />
    </div>
  )
}

/** 复盘建议列表（agent_suggestions） */
function Suggestions() {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const { data: rows } = useQuery({ queryKey: ['agent-sug'], queryFn: () => agentSuggestions() })
  const list = rows ?? []
  if (!list.length) return <EmptyState text="暂无优化建议。" icon="💡" />

  const act = (r: (typeof list)[number], action: 'approve' | 'adopt' | 'reject') => {
    const confirmMap: Record<string, { title: string; fn: () => Promise<unknown> }> = {
      approve: { title: `确认采纳建议：${r.rule_name}`, fn: () => approveSuggestion(r.id) },
      adopt: { title: `应用生效：${r.rule_name}（硬规则需二次确认）`, fn: () => adoptSuggestion(r.id, true) },
      reject: { title: `驳回建议：${r.rule_name}`, fn: () => rejectSuggestion(r.id, '人工驳回') },
    }
    modal.confirm({
      title: confirmMap[action].title,
      okText: '确认', okButtonProps: action === 'reject' ? { danger: true } : { type: 'primary' as const },
      onOk: async () => {
        try {
          await confirmMap[action].fn()
          message.success('已提交')
          qc.invalidateQueries({ queryKey: ['agent-sug'] })
        } catch (e) { message.error(e instanceof Error ? e.message : '操作失败') }
      },
    })
  }

  return (
    <Table size="small" rowKey="id" dataSource={list} pagination={{ pageSize: 10 }}
      columns={[
        { title: 'Agent', dataIndex: 'target_agent', width: 100 },
        { title: '规则', dataIndex: 'rule_name', ellipsis: true },
        { title: '当前→建议', key: 'val', width: 160, render: (_: unknown, r: (typeof list)[number]) => <Text>{(r.current_value ?? '—')} → {r.suggested_value ?? '—'}</Text> },
        { title: '状态', dataIndex: 'status', width: 80, render: (v: string) => <Tag color={SUG_STATUS[v]?.color ?? 'default'}>{SUG_STATUS[v]?.label ?? v}</Tag> },
        {
          title: '操作', key: 'ops', width: 200,
          render: (_: unknown, r: (typeof list)[number]) => (
            <Space size={4}>
              {r.status === 'pending' ? <Button size="small" onClick={() => act(r, 'approve')}>采纳</Button> : null}
              {r.status === 'pending' ? <Button size="small" onClick={() => act(r, 'reject')}>驳回</Button> : null}
              {r.status === 'approved' ? <Button size="small" type="primary" onClick={() => act(r, 'adopt')}>应用</Button> : null}
            </Space>
          ),
        },
      ]} />
  )
}

/** 交易复盘页（Phase 4 黑盒规范） */
export function ReviewsPage() {
  return (
    <div>
      <Tabs items={[
        { key: 'reviews', label: '每日复盘报告', children: <ReviewsList /> },
        { key: 'track', label: '选股效果验证', children: <TrackVerify /> },
        { key: 'sug', label: '策略闭环建议', children: <Suggestions /> },
      ]} />
    </div>
  )
}

export default ReviewsPage
