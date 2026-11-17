import { Alert, Button, Card, Empty, Popconfirm, Space, Table, Tag, Typography, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  decideFactorStatus, factorIcHistory, getFactorStatus,
  type FactorIcRow, type FactorStatusRow,
} from '@/api/factors'

const { Title, Text } = Typography

const columns: ColumnsType<FactorIcRow> = [
  { title: '因子', dataIndex: 'factor_name', key: 'factor_name' },
  { title: 'ID', dataIndex: 'factor_id', key: 'factor_id' },
  { title: '类别', dataIndex: 'category', key: 'category' },
  { title: '月份', dataIndex: 'period', key: 'period' },
  { title: 'IC', dataIndex: 'ic', key: 'ic', render: (v: number | null) => v == null ? '—' : v.toFixed(4) },
  { title: 'IR', dataIndex: 'ir', key: 'ir', render: (v: number | null) => v == null ? '—' : v.toFixed(4) },
  { title: '胜率', dataIndex: 'hit_rate', key: 'hit_rate', render: (v: number) => `${(v * 100).toFixed(1)}%` },
  { title: '样本', dataIndex: 'sample_size', key: 'sample_size' },
  { title: '排名', dataIndex: 'rank_in_category', key: 'rank_in_category' },
  { title: '状态', dataIndex: 'status', key: 'status', render: (v: string, row) => {
    const color = v === 'deprecated_candidate' ? 'red' : row.sample_size < 100 ? 'gold' : row.ic != null && Math.abs(row.ic) >= 0.02 ? 'green' : 'gold'
    const text = v === 'deprecated_candidate' ? '判定失效' : v === 'active' ? '正常' : v
    return <Tag color={color}>{text}</Tag>
  } },
]

export default function FactorIcPage() {
  const qc = useQueryClient()
  const { data = [], isLoading, isError } = useQuery({
    queryKey: ['factor-ic-history'],
    queryFn: () => factorIcHistory(undefined, undefined, 500),
  })
  const { data: statusRows = [] } = useQuery({ queryKey: ['factor-status'], queryFn: getFactorStatus })
  const proposals = statusRows.filter(r => r.status === 'proposed')

  const decide = useMutation({
    mutationFn: ({ fid, status, reason }: { fid: string; status: 'active' | 'deprecated'; reason: string }) =>
      decideFactorStatus(fid, status, reason),
    onSuccess: (_d, v) => {
      message.success(v.status === 'deprecated' ? `${v.fid} 已下线` : `${v.fid} 已驳回恢复`)
      qc.invalidateQueries({ queryKey: ['factor-status'] })
      qc.invalidateQueries({ queryKey: ['factor-ic-history'] })
    },
    onError: () => message.error('操作失败，请稍后重试'),
  })

  const proposalColumns: ColumnsType<FactorStatusRow> = [
    { title: '因子 ID', dataIndex: 'factor_id', key: 'factor_id' },
    { title: '判定理由', dataIndex: 'reason', key: 'reason', render: (v: string | null) => v ?? '—' },
    { title: '来源', dataIndex: 'decided_by', key: 'decided_by', render: (v: string) => v === 'auto' ? '自动回测' : '人工' },
    { title: '提出时间', dataIndex: 'updated_at', key: 'updated_at', render: (v: string | null) => v ? v.replace('T', ' ').slice(0, 19) : '—' },
    { title: '操作', key: 'action', render: (_v, row) => (
      <Space>
        <Popconfirm title={`确认下线 ${row.factor_id}？`} description="下线后该因子不再参与每日打分，可随时改回。"
          onConfirm={() => decide.mutate({ fid: row.factor_id, status: 'deprecated', reason: '人工确认失效' })}>
          <Button danger size="small" loading={decide.isPending}>确认下线</Button>
        </Popconfirm>
        <Button size="small" onClick={() => decide.mutate({ fid: row.factor_id, status: 'active', reason: '人工驳回：经核查仍有效' })}>
          驳回
        </Button>
      </Space>
    ) },
  ]

  return <Card>
    <Title level={3}>因子 IC 月度回测</Title>
    <Text type="secondary">IC 为因子对未来 20 个交易日涨跌的预测力；|IC| 低于 0.02 视为无预测力。负值只代表方向相反，不代表失效。</Text>

    {proposals.length ? <>
      <Alert
        style={{ margin: '16px 0 8px' }}
        type="warning"
        showIcon
        message={`有 ${proposals.length} 个因子连续 3 个月 |IC| < 0.02，待你决定是否下线`}
        description="回测只出结论、不自动生效。确认下线后该因子立即退出每日打分；驳回则继续保留。"
      />
      <Table rowKey="factor_id" size="small" pagination={false} columns={proposalColumns} dataSource={proposals} />
    </> : null}

    <div style={{ marginTop: 16 }}>
      {isError ? <Typography.Text type="danger">回测历史暂不可用</Typography.Text> : null}
      {data.length
        ? <Table rowKey="id" loading={isLoading} columns={columns} dataSource={data} pagination={{ pageSize: 25 }} />
        : <Empty description="暂无回测历史" />}
    </div>
  </Card>
}
