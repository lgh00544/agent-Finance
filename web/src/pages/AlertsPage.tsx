import { useState } from 'react'
import { Button, Card, Progress, Select, Space, Table, Tag, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { alerts } from '@/api/alerts'
import { useTasks } from '@/store/tasksStore'
import { EmptyState, ErrorCard, StockLabel } from '@/components/common'
import type { AlertInfo } from '@/types'

const { Text } = Typography

const SEV_COLOR: Record<string, string> = { critical: 'red', warning: 'orange', info: 'blue' }
const SEV_LABEL: Record<string, string> = { critical: '严重', warning: '警告', info: '一般' }

// 资金告警关键字（前端 client-side 过滤，不动后端）
const MONEY_KW = ['钱', '止损', '止盈', '减仓', '跌停', '涨停', '盈利']
// 后台任务 kind → 中文名（无映射时回落 kind 原文）
const TASK_LABEL: Record<string, string> = {
  daily_pipeline: '每日挖掘', monitor_all: '全量监控', portfolio_sentinel: '组合哨兵',
  sell_decision: '卖出决策', track_verify: '选股验证', run_suggest: '建议生成',
  knowledge_import: '知识导入', distribution_phase: '派发期判定',
}

function fmtDuration(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m${s % 60}s`
}

/** 告警日志页（重点分层：资金告警置顶 / 后台任务状态 / 完整日志折叠） */
export function AlertsPage() {
  const [sev, setSev] = useState('all')
  const [type, setType] = useState('全部类型')
  const [logOpen, setLogOpen] = useState(false) // 完整日志默认折叠

  const { data: rows, isError, error, refetch } = useQuery({ queryKey: ['alerts'], queryFn: () => alerts() })
  const tasks = useTasks() // 复用 tasksStore 已有任务数据，不新建接口

  if (isError) return <ErrorCard title="告警日志加载失败" message={error?.message} onRetry={() => refetch()} />
  const all = rows ?? []
  const types = Array.from(new Set(all.map((r) => r.alert_type ?? '未知')))

  // 🔴 资金告警：critical + 消息/动作含资金关键字，截前 5
  const moneyAlerts = all
    .filter((r) => r.severity === 'critical' &&
      MONEY_KW.some((k) => (r.message ?? '').includes(k) || (r.action ?? '').includes(k)))
    .slice(0, 5)

  // 🟡 后台任务：running / failed
  const taskList = tasks.filter((t) => t.status === 'running' || t.status === 'failed')

  const filtered = all.filter((r) =>
    (sev === 'all' || (r.severity ?? '') === sev) &&
    (type === '全部类型' || (r.alert_type ?? '') === type)
  )

  const cols = [
    {
      title: '股票', key: 'stock', width: 160,
      render: (_: unknown, r: AlertInfo) => <StockLabel code={r.stock_code} name={r.stock_name} />,
    },
    {
      title: '级别', dataIndex: 'severity', width: 90,
      render: (v: string) => <Tag color={SEV_COLOR[v] ?? 'default'}>{SEV_LABEL[v] ?? v}</Tag>,
    },
    { title: '类型', dataIndex: 'alert_type', width: 130, render: (v: string) => v ?? '—' },
    { title: '消息', dataIndex: 'message', ellipsis: true },
    {
      title: '推送', dataIndex: 'pushed', width: 80,
      render: (v: boolean) => (v ? <Tag color="green">✓ 已推送</Tag> : <Tag>—</Tag>),
    },
    { title: '时间', dataIndex: 'created_at', width: 150, render: (v: string) => String(v ?? '').slice(0, 16) },
  ]

  return (
    <div>
      {/* 🔴 资金告警（置顶，最高优先级；0 条整段不渲染） */}
      {moneyAlerts.length ? (
        <Card title="🔴 资金告警" size="small" style={{ borderColor: '#ff4d4f', marginBottom: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 8 }}>
            {moneyAlerts.map((a) => (
              <div key={a.id} style={{ padding: 8, borderRadius: 6, background: 'var(--bg-input)' }}>
                <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                  <StockLabel code={a.stock_code} name={a.stock_name} />
                  <Tag color="red">严重</Tag>
                </Space>
                <div style={{ fontSize: 12, marginTop: 4 }}>{String(a.message ?? '')}</div>
                <Space style={{ width: '100%', justifyContent: 'space-between', marginTop: 6 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>{String(a.created_at ?? '').slice(5, 16)}</Text>
                  <Button size="small" type="link" onClick={() => setLogOpen(true)}>立即查看</Button>
                </Space>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      {/* 🟡 后台任务状态（running 进度条 + 耗时；failed 红色高亮） */}
      <Card title="🟡 后台任务状态" size="small" style={{ borderColor: '#faad14', marginBottom: 12 }}>
        {taskList.length ? (
          <Space direction="vertical" style={{ width: '100%' }} size={8}>
            {taskList.map((t) => {
              const running = t.status === 'running'
              const dur = fmtDuration((t.finished_at ?? Date.now()) - t.started_at)
              return (
                <div key={t.task_id}>
                  <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Text strong>{TASK_LABEL[t.kind] ?? t.kind}</Text>
                    <Tag color={running ? 'blue' : 'red'}>{running ? '执行中' : '失败'}</Tag>
                    <Text type="secondary" style={{ fontSize: 12 }}>耗时 {dur}</Text>
                  </Space>
                  {running ? (
                    <Progress percent={100} showInfo={false} status="active" strokeColor="#faad14"
                      style={{ marginTop: 2, marginBottom: 0 }} />
                  ) : null}
                  {t.error ? <Text type="danger" style={{ fontSize: 12, display: 'block' }}>{String(t.error)}</Text> : null}
                </div>
              )
            })}
          </Space>
        ) : (
          <Text type="secondary">暂无运行中任务</Text>
        )}
      </Card>

      {/* 🟢 完整告警日志（默认折叠，点击「展开完整日志」查看原 Table） */}
      <Card
        title="🟢 完整告警日志"
        size="small"
        extra={<Button size="small" type="primary" onClick={() => setLogOpen(true)}>展开完整日志</Button>}
        style={{ marginBottom: 12 }}
      >
        {logOpen ? (
          !all.length ? (
            <EmptyState text="暂无告警记录。持仓监控在交易时段每 3 分钟自动运行。" icon="🛡️" />
          ) : (
            <>
              <Space style={{ marginBottom: 10 }} wrap>
                <Select value={sev} onChange={setSev} style={{ width: 110 }}
                  options={[
                    { label: '全部级别', value: 'all' },
                    { label: '严重', value: 'critical' },
                    { label: '警告', value: 'warning' },
                    { label: '一般', value: 'info' },
                  ]} />
                <Select value={type} onChange={setType} style={{ width: 130 }}
                  options={[{ label: '全部类型', value: '全部类型' }, ...types.map((t) => ({ label: t, value: t }))]} />
                <Text type="secondary">共 {filtered.length} 条 · 统计时间 {String(all[0]?.created_at ?? '').slice(0, 16)}</Text>
              </Space>
              {!filtered.length ? (
                <EmptyState text="当前筛选条件下无匹配告警。" icon="🔍" />
              ) : (
                <Table<AlertInfo> rowKey="id" size="small" columns={cols} dataSource={filtered} pagination={{ pageSize: 20 }} />
              )}
            </>
          )
        ) : (
          <Text type="secondary">完整日志已折叠，点击右上角「展开完整日志」查看全部告警。</Text>
        )}
      </Card>
    </div>
  )
}

export default AlertsPage
