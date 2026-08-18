import { Card, Skeleton } from 'antd'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'

interface ChartCardProps {
  title: string
  option: EChartsOption
  height?: number
  loading?: boolean
  extra?: React.ReactNode
}

/** 图表卡片封装（标题 + ECharts + Loading 态），Phase 3 起统一管理图表 */
export function ChartCard({ title, option, height = 280, loading, extra }: ChartCardProps) {
  return (
    <Card size="small" title={title} extra={extra}
      style={{ background: 'var(--bg-card)', marginBottom: 12 }}>
      {loading ? (
        <Skeleton active paragraph={{ rows: 6 }} />
      ) : (
        <ReactECharts option={option} style={{ height }} notMerge />
      )}
    </Card>
  )
}

/** 热门行业横向条形图 option（涨红跌绿） */
export function hotSectorBarOption(rows: Array<{ board_name?: string; change_pct?: number | null }>) {
  const data = (rows ?? []).map((r) => ({
    name: r.board_name ?? '—',
    value: Number(r.change_pct ?? 0),
  }))
  return {
    grid: { left: 8, right: 16, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: '{value}%', color: '#9ca3af' }, splitLine: { lineStyle: { color: 'rgba(60,80,120,0.2)' } } },
    yAxis: { type: 'category', data: data.map((d) => d.name).reverse(), axisLabel: { color: '#e5e7eb' } },
    tooltip: { trigger: 'axis', formatter: (p: unknown) => {
      const item = (p as Array<{ name: string; value: number }>)[0]
      return `${item.name}：${item.value >= 0 ? '+' : ''}${item.value.toFixed(2)}%`
    } },
    series: [{
      type: 'bar',
      data: data.map((d) => ({
        value: d.value,
        itemStyle: { color: d.value >= 0 ? '#ef4444' : '#10b981', borderRadius: 2 },
      })).reverse(),
      barWidth: 14,
    }],
  } as EChartsOption
}
