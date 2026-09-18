import { Card, Skeleton, Tag } from 'antd'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { useQuery } from '@tanstack/react-query'
import { get } from '@/api/client'
import { EmptyState, ErrorCard } from '@/components/common'

type AnchorKind = 'select' | 'entry' | 'exit' | 'now'
type KlineRow = { date: string; open: number; high: number; low: number; close: number; volume: number }
type KlineChartProps = {
  code: string
  name?: string
  anchorDate: string
  anchorKind: AnchorKind
  days?: number
  height?: number
}
type KlineResponse = { klines: Array<Record<string, unknown>>; status?: string; detail?: string }

const anchorLabels: Record<AnchorKind, { label: string; color: string }> = {
  select: { label: '选中日', color: '#3b82f6' },
  entry: { label: '建仓日', color: '#eab308' },
  exit: { label: '离场日', color: '#ef4444' },
  now: { label: '当前日', color: '#10b981' },
}

function shiftDate(date: string, offset: number) {
  const d = new Date(`${date}T00:00:00`)
  if (Number.isNaN(d.getTime())) return date
  d.setDate(d.getDate() + offset)
  return d.toISOString().slice(0, 10)
}

function normalize(rows: Array<Record<string, unknown>>): KlineRow[] {
  return rows.map((r) => ({
    date: String(r.date ?? ''),
    open: Number(r.open),
    high: Number(r.high),
    low: Number(r.low),
    close: Number(r.close),
    volume: Number(r.volume ?? 0),
  })).filter((r) => r.date && [r.open, r.high, r.low, r.close, r.volume].every(Number.isFinite))
    .sort((a, b) => a.date.localeCompare(b.date))
}

function movingAverage(rows: KlineRow[], period: number): Array<number | null> {
  return rows.map((_, i) => i + 1 < period ? null : Number((rows.slice(i - period + 1, i + 1)
    .reduce((sum, row) => sum + row.close, 0) / period).toFixed(2)))
}

export function KlineChart({ code, name, anchorDate, anchorKind, days = 60, height = 320 }: KlineChartProps) {
  const anchor = anchorLabels[anchorKind]
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['kline-chart', code, anchorDate, days],
    queryFn: () => get<KlineResponse>(`/kline/${code}`, {
      start: shiftDate(anchorDate, -Math.max(1, Math.floor(days / 2))),
      end: shiftDate(anchorDate, Math.max(1, Math.floor(days / 2))),
    }),
    enabled: !!code && !!anchorDate,
    staleTime: 5 * 60_000,
    retry: 0,
  })
  const title = `${code} ${name || ''} K线 · ${anchorDate} ±${days}日`
  if (isLoading) return <Card size="small" title={title}><Skeleton active paragraph={{ rows: 6 }} /></Card>
  if (isError) return <Card size="small" title={title}><ErrorCard title="K线加载失败" message={error instanceof Error ? error.message : '无法读取 K 线'} onRetry={() => refetch()} /></Card>
  const rows = normalize(data?.klines ?? [])
  if (!rows.length) {
    if (data?.status === 'upstream_error') return <Card size="small" title={title}><ErrorCard title="上游行情源暂时不可用" message="东财/新浪均失败，已重试仍失败，请稍后点重试" detail={data.detail} onRetry={() => refetch()} /></Card>
    return <Card size="small" title={title}><EmptyState text="该股在所选窗口内无交易日数据" /></Card>
  }
  const dates = rows.map((r) => r.date)
  const option: EChartsOption = {
    animation: false,
    tooltip: { trigger: 'axis' },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [{ left: 42, right: 16, top: 24, height: '64%' }, { left: 42, right: 16, top: '76%', height: '16%' }],
    xAxis: [{ type: 'category', data: dates, boundaryGap: true, axisLabel: { color: '#9ca3af' } }, { type: 'category', data: dates, gridIndex: 1, axisLabel: { show: false } }],
    yAxis: [{ scale: true, axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: 'rgba(60,80,120,0.2)' } } }, { gridIndex: 1, axisLabel: { color: '#9ca3af' }, splitLine: { show: false } }],
    series: [
      { type: 'candlestick', data: rows.map((r) => [r.open, r.close, r.low, r.high]), itemStyle: { color: '#ef4444', color0: '#10b981', borderColor: '#ef4444', borderColor0: '#10b981' }, markLine: { symbol: ['none', 'none'], data: [{ xAxis: anchorDate }], lineStyle: { color: anchor.color, type: 'dashed' }, label: { formatter: anchor.label } } },
      { type: 'line', data: movingAverage(rows, 5), smooth: true, symbol: 'none', lineStyle: { color: '#e5e7eb', width: 1 } },
      { type: 'line', data: movingAverage(rows, 10), smooth: true, symbol: 'none', lineStyle: { color: '#fbbf24', width: 1 } },
      { type: 'line', data: movingAverage(rows, 20), smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1 } },
      { type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: rows.map((r) => ({ value: r.volume, itemStyle: { color: r.close >= r.open ? '#ef4444' : '#10b981' } })) },
    ],
  }
  return <Card size="small" title={title} extra={<Tag color="blue">{anchor.label} · {anchorDate}</Tag>}><ReactECharts option={option} style={{ height }} notMerge /></Card>
}
