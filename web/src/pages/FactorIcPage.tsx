import { Card, Empty, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useQuery } from '@tanstack/react-query'
import { factorIcHistory, type FactorIcRow } from '@/api/factors'

const { Title } = Typography

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
    return <Tag color={color}>{v}</Tag>
  } },
]

export default function FactorIcPage() {
  const { data = [], isLoading, isError } = useQuery({ queryKey: ['factor-ic-history'], queryFn: () => factorIcHistory(undefined, undefined, 500) })
  return <Card>
    <Title level={3}>因子 IC 月度回测</Title>
    {isError ? <Typography.Text type="danger">回测历史暂不可用</Typography.Text> : null}
    {data.length ? <Table rowKey="id" loading={isLoading} columns={columns} dataSource={data} pagination={{ pageSize: 25 }} /> : <Empty description="暂无回测历史" />}
  </Card>
}
