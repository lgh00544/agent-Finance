import { useMemo, useState } from 'react'
import dayjs from 'dayjs'
import { Alert, App, Button, Card, DatePicker, Descriptions, Drawer, Empty, Select, Space, Table, Tag, Tooltip, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ReloadOutlined, StopOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { sectorRadarCollect, sectorRadarFeedback, sectorRadarInterpretRun, sectorRadarList } from '@/api/sectorRadar'
import type { SectorRadarItem } from '@/api/sectorRadar'

const { Text, Title, Paragraph } = Typography

const polarityMap: Record<string, { text: string; color: string }> = {
  positive: { text: '利好', color: 'red' },
  negative: { text: '利空', color: 'green' },
  neutral: { text: '中性', color: 'default' },
  mixed: { text: '多空混合', color: 'orange' },
  uncertain: { text: '不确定', color: 'default' },
}

function impactHint(item: SectorRadarItem) {
  const p = item.interpret?.polarity || 'uncertain'
  const confidence = (item.article.mapping_confidence || 0) > 0.6
  if (p === 'positive') return confidence ? '利好·高置信' : '利好·待解读'
  if (p === 'negative') return confidence ? '利空·高置信' : '利空·待解读'
  return p === 'mixed' ? '多空·待解读' : '中性·待解读'
}

function priorityScore(item: SectorRadarItem) {
  return Number(['positive', 'negative'].includes(item.interpret?.polarity || '')) +
    Number(item.interpret?.validator_status === 'accepted') +
    Number((item.article.mapping_confidence || 0) > 0.6)
}

function mappingLabel(method?: string) {
  return ({ exact_entity: '实体命中', exact_keyword: '关键词命中', source_tag: '来源行业标签', unmapped: '未映射' } as Record<string, string>)[method || ''] || method || '—'
}

function aiConfidence(item: SectorRadarItem) {
  const interpret = item.interpret as (NonNullable<SectorRadarItem['interpret']> & { validator_score?: number }) | null | undefined
  return interpret?.validator_score ?? interpret?.direction_confidence
}

function formatRawContent(content?: string) {
  return String(content || '')
    .replace(/\r\n?/g, '\n')
    .replace(/[ \t]+/g, ' ')
    .replace(/(?<!\n)(\d{1,2}[、．])/g, '\n$1')
    .replace(/([。！？])(?=[\u4e00-\u9fffA-Za-z])/g, '$1\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

function interpretState(item: SectorRadarItem) {
  if (!item.interpret) {
    return {
      message: 'AI 解读尚未生成',
      description: '这条消息已完成抓取和行业映射，但当前抓取任务未执行 AI 解读，因此没有 AI 评估结论。',
    }
  }
  if (!item.interpret.summary && !item.interpret.impact_mechanism) {
    return {
      message: 'AI 解读结果为空',
      description: '后台已返回解读记录，但摘要和影响机制均为空，可能是生成失败或历史数据不完整；当前不应视为有效 AI 结论。',
    }
  }
  return null
}

export default function NewsSectorPage() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [sectorCode, setSectorCode] = useState<string>()
  const [days, setDays] = useState(7)
  const [date, setDate] = useState<string>()
  const [selected, setSelected] = useState<SectorRadarItem | null>(null)
  const [selectedIds, setSelectedIds] = useState<number[]>([])

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['sector-radar', sectorCode, days, date],
    queryFn: () => sectorRadarList({ sector_code: sectorCode, days: date ? undefined : days, date }),
  })
  const collect = useMutation({
    mutationFn: () => sectorRadarCollect({
      sector_code: sectorCode, max_sectors: sectorCode ? 1 : 8,
      max_stocks: 5, auto_interpret: false, sleep_seconds: 0,
    }),
    onSuccess: (result) => {
      const skipped = result.articles_skipped_low_value
        ? `，跳过低价值公告 ${result.articles_skipped_low_value} 条`
        : ''
      const coverage = `扫描 ${result.sectors} 个行业 / ${result.stock_codes_scanned} 个标的，产出 ${result.sectors_with_articles} 个行业 / ${result.stock_codes_with_articles} 个标的`
      if (result.errors?.length) {
        message.warning(`抓取完成：${coverage}，新增 ${result.articles_new} 条${skipped}，数据源提示 ${result.errors.length} 项`)
      } else {
        message.success(`抓取完成：${coverage}，新增 ${result.articles_new} 条${skipped}，结果只进入观察型雷达`)
      }
      qc.invalidateQueries({ queryKey: ['sector-radar'] })
    },
  })
  const feedback = useMutation({
    mutationFn: (item: SectorRadarItem) => sectorRadarFeedback({
      article_id: item.article.id,
      interpret_id: item.interpret?.id,
      feedback_type: 'dismiss',
      reason: '页面标记无效',
    }),
    onSuccess: () => message.success('反馈已进入待审核队列，不会自动修改字典'),
  })
  const interpret = useMutation({
    mutationFn: (item: SectorRadarItem) => sectorRadarInterpretRun({
      sector_code: item.article.sector_codes?.[0],
      article_ids: [item.article.id],
    }),
    onSuccess: (result: { ok?: boolean; message?: string }) => {
      if (result?.ok) message.success('AI 解读已生成，正在刷新结果')
      else message.warning(result?.message || 'AI 解读未生成，请查看后端提示')
      qc.invalidateQueries({ queryKey: ['sector-radar'] })
    },
    onError: (error) => message.error(error instanceof Error ? error.message : 'AI 解读失败'),
  })
  const batchInterpret = useMutation({
    mutationFn: async (items: SectorRadarItem[]) => {
      const eligible = items.filter((item) => !item.interpret || item.interpret.validator_status !== 'accepted')
      const groups = new Map<string, number[]>()
      for (const item of eligible) {
        const sector = item.article.sector_codes?.[0]
        if (!sector) continue
        const ids = groups.get(sector) ?? []
        ids.push(item.article.id)
        groups.set(sector, ids)
      }
      for (const [sector_code, article_ids] of groups) {
        // 按行业分组逐批触发，避免混行业文章共用一个 sector_code
        // eslint-disable-next-line no-await-in-loop
        await sectorRadarInterpretRun({ sector_code, article_ids })
      }
      return { count: eligible.length, groups: groups.size }
    },
    onSuccess: (result) => {
      if (!result.count) {
        message.info('所选条目都已完成 AI 解读')
        return
      }
      message.success(`已发起 ${result.count} 条批量 AI 解读（${result.groups} 个行业分组）`)
      setSelectedIds([])
      qc.invalidateQueries({ queryKey: ['sector-radar'] })
    },
    onError: (error) => message.error(error instanceof Error ? error.message : '批量 AI 解读失败'),
  })

  const sectorOptions = useMemo(() => (data?.sectors || []).map((s) => ({
    value: s.sector_code, label: s.sector_name,
  })), [data?.sectors])
  const coverage = useMemo(() => {
    const items = data?.items || []
    const sectors = new Set(items.flatMap((item) => item.article.sector_codes || []))
    const stocks = new Set(items.flatMap((item) => item.article.stock_codes || []))
    const interpreted = items.filter((item) => item.interpret?.validator_status === 'accepted').length
    return { sectors: sectors.size, stocks: stocks.size, interpreted }
  }, [data?.items])
  const latestCapturedAt = useMemo(() => (data?.items || [])
    .map((item) => item.article.created_at)
    .filter(Boolean)
    .sort()
    .at(-1) || '—', [data?.items])
  const sortedItems = useMemo(() => [...(data?.items || [])].sort((a, b) => (
    priorityScore(b) - priorityScore(a) ||
    String(b.article.created_at || '').localeCompare(String(a.article.created_at || ''))
  )), [data?.items])
  const selectedSectorName = sectorOptions.find((s) => s.value === sectorCode)?.label
  const selectedItems = useMemo(() => (data?.items || []).filter((item) => selectedIds.includes(item.article.id)), [data?.items, selectedIds])

  const columns: ColumnsType<SectorRadarItem> = [
    {
      title: '消息',
      dataIndex: ['article', 'title'],
      width: 520,
      ellipsis: true,
      render: (_, item) => (
        <div style={{ lineHeight: 1.45, minWidth: 0 }}>
          <Tooltip title={<span>{item.article.title || '未命名消息'}（点击查看原文详情）</span>} placement="topLeft">
            <Button type="link" style={{ display: 'block', maxWidth: '100%', overflow: 'hidden', padding: 0, height: 22, textAlign: 'left', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} onClick={() => setSelected(item)}>
              <strong>{item.article.title || '未命名消息'}</strong>
            </Button>
          </Tooltip>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, minWidth: 0, overflow: 'hidden', whiteSpace: 'nowrap' }}>
            {(item.article.sector_codes || []).slice(0, 2).map((code) => <Tag key={code} color="blue">{code}</Tag>)}
            <Text type="secondary" ellipsis>影响面：{impactHint(item)}</Text>
          </div>
          <Text type="secondary" style={{ display: 'block', fontSize: 12, lineHeight: 1.4, whiteSpace: 'nowrap' }}>
            原文发布：{item.article.published_at || '—'} · 抓取入库：{item.article.created_at || '—'}
          </Text>
        </div>
      ),
    },
    {
      title: '重点度（高→低）',
      width: 100,
      render: (_, item) => {
        const score = priorityScore(item)
        return <Space size={2}>{[0, 1, 2].map((i) => <Tag key={i} color={i < score ? (item.interpret?.polarity === 'positive' ? 'red' : 'orange') : 'default'}>★</Tag>)}</Space>
      },
    },
    {
      title: '口径',
      width: 120,
      render: (_, item) => <Tag color="default">{item.article.source_scope === 'company_signal' ? '代理信号' : '行业新闻'}</Tag>,
    },
    {
      title: '映射',
      width: 150,
      render: (_, item) => (
        <Space direction="vertical" size={0}>
          <Text>{mappingLabel(item.article.mapping_method)}</Text>
          <Text type="secondary">{Math.round((item.article.mapping_confidence || 0) * 100)}%</Text>
        </Space>
      ),
    },
    {
      title: '方向',
      width: 110,
      render: (_, item) => {
        const p = polarityMap[item.interpret?.polarity || 'uncertain']
        return <Tag color={p.color}>{p.text}</Tag>
      },
    },
    {
      title: '证据',
      width: 120,
      render: (_, item) => item.interpret?.validator_status === 'accepted'
        ? <Tag color="blue">证据完整</Tag>
        : <Tag>待解读</Tag>,
    },
    {
      title: 'Shadow',
      width: 170,
      render: (_, item) => (
        <Text type="secondary">
          T1 {fmt(item.shadow?.t1_return)} / T3 {fmt(item.shadow?.t3_return)} / T5 {fmt(item.shadow?.t5_return)}
        </Text>
      ),
    },
    {
      title: '操作',
      width: 100,
      render: (_, item) => (
        <Space size={4}>
          {!item.interpret || item.interpret.validator_status !== 'accepted' ? (
            <Button size="small" onClick={() => interpret.mutate(item)} loading={interpret.isPending}>手动 AI 解读</Button>
          ) : null}
          <Button size="small" icon={<StopOutlined />} onClick={() => feedback.mutate(item)} loading={feedback.isPending}>无效</Button>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Alert type="warning" showIcon message="实验性消息雷达：只提供证据化信息整理，不直接作为买卖依据，不改变候选池。" />
      <Alert
        type="info"
        showIcon
        message={`${date ? `当前日期 ${date}` : `当前近 ${days} 日`}${selectedSectorName ? ` · 行业映射筛选：${selectedSectorName}` : ''}：${data?.total || 0} 条代理信号，覆盖 ${coverage.sectors} 个行业 / ${coverage.stocks} 个标的，已完成证据解读 ${coverage.interpreted} 条；最近抓取入库：${latestCapturedAt}。`}
      />
      {sectorCode ? <Alert type="warning" showIcon message="当前筛选按文章内容的行业映射，不代表公司所属行业；一条消息可能同时命中多个行业，请查看“映射”列的命中方式和置信度。" /> : null}
      <Alert type="warning" showIcon message="AI 解读不会在抓取后自动执行；未处理消息会保留在列表中，请点击「手动 AI 解读」逐条触发。" />
      <Space style={{ justifyContent: 'space-between', width: '100%' }} wrap>
        <Title level={3} style={{ margin: 0 }}>行业消息雷达</Title>
        <Space wrap>
          <Select allowClear placeholder="全部行业" style={{ width: 180 }} options={sectorOptions} value={sectorCode} onChange={setSectorCode} />
          <Select aria-label="时间范围" style={{ width: 130 }} value={days} onChange={setDays} options={[3, 7, 14, 30].map((d) => ({ value: d, label: `近 ${d} 日` }))} />
          <DatePicker allowClear style={{ width: 150 }} value={date ? dayjs(date) : null} onChange={(v) => setDate(v ? v.format('YYYY-MM-DD') : undefined)} placeholder="具体日期（入库日）" />
          <Button disabled={!selectedItems.length} onClick={() => batchInterpret.mutate(selectedItems)} loading={batchInterpret.isPending}>批量 AI 解读</Button>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
          <Button type="primary" onClick={() => collect.mutate()} loading={collect.isPending}>抓取</Button>
        </Space>
      </Space>
      <Table
        size="small"
        tableLayout="fixed"
        rowKey={(r) => r.article.id}
        columns={columns}
        dataSource={sortedItems}
        rowSelection={{
          selectedRowKeys: selectedIds,
          onChange: (keys) => setSelectedIds(keys as number[]),
        }}
        styles={{
          header: { cell: { padding: '8px 10px' } },
          body: { cell: { padding: '8px 10px' } },
        }}
        loading={isLoading}
        scroll={{ x: 1390 }}
        locale={{ emptyText: <Empty description="暂无行业消息雷达记录" /> }}
        pagination={{ pageSize: 12 }}
      />
      <Drawer width={720} title={selected?.article.title} open={!!selected} onClose={() => setSelected(null)}>
        {selected && (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Alert type="info" message={<Space wrap size={6}>
              <Tag color={polarityMap[selected.interpret?.polarity || 'uncertain'].color}>极性：{polarityMap[selected.interpret?.polarity || 'uncertain'].text}</Tag>
              <Tag>影响面：{selected.article.source_scope === 'company_signal' ? '成分股代理信号' : '行业级'}</Tag>
              <Tag>置信度：{Math.round((selected.article.mapping_confidence || 0) * 100)}%</Tag>
              <Tag color={selected.shadow ? 'blue' : 'default'}>{selected.shadow ? '已纳入 Shadow' : '未进入 Shadow'}</Tag>
            </Space>} />
            <Descriptions size="small" column={2} items={[
              { key: 'published', label: '原文发布时间', children: selected.article.published_at || '—' },
              { key: 'captured', label: '抓取入库时间', children: selected.article.created_at || '—' },
              { key: 'source', label: '来源', children: selected.article.source_name || '—' },
              { key: 'status', label: 'AI 处理状态', children: selected.interpret ? (selected.interpret.validator_status === 'accepted' ? '已完成' : '结果未通过审核') : '未处理' },
            ]} />
            {interpretState(selected) ? <Alert type="warning" showIcon {...interpretState(selected)!} /> : null}
            {!selected.interpret || selected.interpret.validator_status !== 'accepted' ? (
              <Button type="primary" loading={interpret.isPending} onClick={() => interpret.mutate(selected)}>手动生成 AI 解读</Button>
            ) : null}
            <Card size="small" title="AI 评估结果" style={{ background: 'var(--bg-input)' }}>
              <Paragraph style={{ marginBottom: 0 }}>
                {selected.interpret?.summary || selected.interpret?.impact_mechanism || '当前没有可展示的 AI 评估文本'}
              </Paragraph>
            </Card>
            <Title level={5}>AI 解读</Title>
            <Paragraph>{selected.interpret?.impact_mechanism || '影响机制：暂无。'}</Paragraph>
            <Text type="secondary">AI 评级置信度：{aiConfidence(selected) != null ? `${Math.round(Number(aiConfidence(selected)) * 100)}%` : '—'}</Text>
            <Title level={5}>原文证据</Title>
            <Descriptions size="small" column={1} items={(selected.interpret?.quote_evidence || []).flatMap((q, i) => [
              { key: `q-${i}-text`, label: `证据文本 ${i + 1}`, children: <Text mark>{q.quote || '—'}</Text> },
              { key: `q-${i}-scope`, label: '对应公司/行业', children: (selected.interpret?.affected_stock_codes || selected.article.sector_codes || []).join('、') || '—' },
              { key: `q-${i}-score`, label: 'AI 评分', children: selected.interpret?.information_score ?? '—' },
            ])} />
            <Card size="small" title="原始全文（已按句子整理）" style={{ background: 'var(--bg-input)' }}>
              <Paragraph ellipsis={{ rows: 6, expandable: true }} style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, marginBottom: 0 }}>
                {selected.article.content ? formatRawContent(selected.article.content) : '原文内容缺失'}
              </Paragraph>
            </Card>
          </Space>
        )}
      </Drawer>
    </Space>
  )
}

function fmt(v?: number | null) {
  return typeof v === 'number' ? `${v.toFixed(2)}%` : '-'
}
