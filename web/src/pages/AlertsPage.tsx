import { useState } from 'react'
import { Select, Space, Table, Tag, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { alerts } from '@/api/alerts'
import { EmptyState, ErrorCard, StockLabel } from '@/components/common'
import type { AlertInfo } from '@/types'

const { Text } = Typography

const SEV_COLOR: Record<string, string> = { critical: 'red', warning: 'orange', info: 'blue' }
const SEV_LABEL: Record<string, string> = { critical: '严重', warning: '警告', info: '一般' }

/** 告警日志页（Phase 3，最轻） */
export function AlertsPage() {
  const [sev, setSev] = useState('all')
  const [type, setType] = useState('全部类型')

  const { data: rows, isError, error, refetch } = useQuery({ queryKey: ['alerts'], queryFn: () => alerts() })

  if (isError) return <ErrorCard title="告警日志加载失败" message={error?.message} onRetry={() => refetch()} />
  const all = rows ?? []
  const types = Array.from(new Set(all.map((r) => r.alert_type ?? '未知')))

  const filtered = all.filter((r) =>
    (sev === 'all' || (r.severity ?? '') === sev) &&
    (type === '全部类型' || (r.alert_type ?? '') === type)
  )

  if (!all.length) {
    return <EmptyState text="暂无告警记录。持仓监控在交易时段每 3 分钟自动运行。" icon="🛡️" />
  }

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
    </div>
  )
}

export default AlertsPage
