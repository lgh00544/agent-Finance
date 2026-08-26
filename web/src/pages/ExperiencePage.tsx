import { useEffect, useState } from 'react'
import {
  App,
  Alert,
  Button,
  Card,
  Checkbox,
  Input,
  Modal,
  Radio,
  Segmented,
  Select,
  Slider,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getExperienceConfig,
  getExperienceList,
  getExperiencePending,
  reviewExperience,
  rollbackExperience,
  runExperienceWorker,
  searchExperience,
  setExperienceConfig,
} from '@/api/experience'
import { EmptyState, ErrorCard, StatusBadge, ConfidenceBar } from '@/components/common'
import type { Experience, ExperienceConfig } from '@/types'

const { Text } = Typography

const STAGE_TONE: Record<string, string> = { 选股: 'blue', 建仓: 'orange', 持仓: 'green' }
const IMPACT_BADGE = { high: <Tag color="red">高影响</Tag>, low: <Tag>低影响</Tag> }

// ================= M1 沉淀队列（只读看板） =================
function ExpQueuePanel() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [stage, setStage] = useState('全部')
  const { data: rows, isError, error, refetch } = useQuery({
    queryKey: ['exp-pending', stage],
    queryFn: () => getExperiencePending(stage === '全部' ? undefined : stage, undefined, 100),
  })
  const run = async () => {
    try {
      await runExperienceWorker()
      message.success('已提交识别任务，完成后待审核数自动更新')
      qc.invalidateQueries({ queryKey: ['exp-pending'] })
    } catch (e) {
      message.warning(e instanceof Error ? e.message : '提交失败')
    }
  }
  if (isError) return <ErrorCard title="沉淀队列加载失败" message={error?.message} onRetry={() => refetch()} />
  const list = rows ?? []
  return (
    <div>
      <Space style={{ marginBottom: 10 }} wrap>
        <Select value={stage} onChange={setStage} style={{ width: 100 }}
          options={['全部', '选股', '建仓', '持仓'].map((s) => ({ label: s, value: s }))} />
        <Button type="primary" onClick={run}>立即触发识别（当前 pending 队列）</Button>
      </Space>
      {!list.length ? (
        <EmptyState text="沉淀队列为空。任务执行完成后，经验摘要会自动进入队列等待识别。" icon="📭" />
      ) : (
        <Table size="small" rowKey="id" dataSource={list} pagination={{ pageSize: 20 }}
          columns={[
            {
              title: '摘要', dataIndex: 'summary', ellipsis: true,
              render: (v: string, r) => (
                <Space direction="vertical" size={0}>
                  <Text>{v}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>任务 {r.task_id} · {String(r.created_at ?? '').slice(0, 16)}</Text>
                </Space>
              ),
            },
            { title: '阶段', dataIndex: 'stage', width: 70, render: (v: string) => <Tag color={STAGE_TONE[v] ?? 'default'}>{v}</Tag> },
            {
              title: '状态', dataIndex: 'status', width: 90,
              render: (v: string) => <StatusBadge text={{ pending: '待识别', processing: '识别中', done: '已完成' }[v] ?? v} tone={({ pending: 'pending', processing: 'processing', done: 'ok' } as Record<string, string>)[v] ?? 'mute'} />,
            },
          ]} />
      )}
    </div>
  )
}

// ================= M2 每日 Digest（批量过目，低影响） =================
function ExpDigestPanel({ onGoHigh }: { onGoHigh: (eid: number) => void }) {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const { data: rows, isError, error, refetch } = useQuery({
    queryKey: ['exp-pending-review'],
    queryFn: () => getExperienceList('pending_review', undefined, undefined, 500),
  })
  const list = rows ?? []
  const high = list.filter((r) => r.impact === 'high')
  const digest = list.filter((r) => r.impact !== 'high')

  if (isError) return <ErrorCard title="Digest 加载失败" message={error?.message} onRetry={() => refetch()} />
  if (!list.length) return <EmptyState text="当前无待过目经验。识别 Worker 产出新经验后会出现在这里。" icon="📭" />

  const approveOne = async (r: Experience) => {
    try {
      await reviewExperience(r.id, 'approve')
      message.success(`已通过：${r.title.slice(0, 20)}`)
      qc.invalidateQueries({ queryKey: ['exp-pending-review'] })
    } catch (e) { message.warning(e instanceof Error ? e.message : '操作失败') }
  }
  const rejectAll = async (reason: string) => {
    let ok = 0
    for (const r of digest) {
      try {
        await reviewExperience(r.id, 'reject', reason)
        ok++
      } catch { /* 单条失败不中断 */ }
    }
    message.success(`批量驳回 ${ok}/${digest.length} 条`)
    qc.invalidateQueries({ queryKey: ['exp-pending-review'] })
    qc.invalidateQueries({ queryKey: ['exp-pending'] })
  }

  return (
    <div>
      {high.length ? (
        <Alert type="warning" showIcon style={{ marginBottom: 10 }}
          message={`⛔ 高影响 ${high.length} 条：涉及规则/标准修改，必须走 M3 硬审核（两步确认），不可在此批量通过`}
          action={high.map((r) => (
            <Button key={r.id} size="small" onClick={() => onGoHigh(r.id)} style={{ marginLeft: 4 }}>
              前往硬审核 → {r.title.slice(0, 12)}
            </Button>
          ))} />
      ) : null}
      {digest.length ? (
        <>
          <Space style={{ marginBottom: 8 }}>
            <Button size="small" type="primary" onClick={() => { digest.forEach((r) => approveOne(r)) }}>
              全部通过（{digest.length}）
            </Button>
            <RejectAllBtn onConfirm={rejectAll} count={digest.length} />
          </Space>
          {digest.map((r) => (
            <Card key={r.id} size="small" style={{ background: 'var(--bg-input)', marginBottom: 8 }}>
              <Space direction="vertical" style={{ width: '100%' }} size={6}>
                <Space wrap>
                  <Text strong>{r.title}</Text>
                  <Tag color={STAGE_TONE[r.stage ?? ''] ?? 'default'}>{r.stage}</Tag>
                  {IMPACT_BADGE[r.impact ?? 'low']}
                </Space>
                <div>{r.body}</div>
                <ConfidenceBar confidence={r.confidence ?? 0} />
                <Text type="secondary" style={{ fontSize: 12 }}>创建 {String(r.created_at ?? '').slice(0, 16)}</Text>
                <Space>
                  <Button size="small" type="primary" onClick={() => approveOne(r)}>通过</Button>
                  <RejectOneBtn r={r} />
                </Space>
              </Space>
            </Card>
          ))}
        </>
      ) : (
        <EmptyState text={high.length ? '暂无低影响待过目经验（高影响项已在上方转 M3）。' : '暂无待过目低影响经验。'} icon="✅" />
      )}
    </div>
  )
}

function RejectAllBtn({ onConfirm, count }: { onConfirm: (reason: string) => void; count: number }) {
  const { message, modal } = App.useApp()
  return (
    <Button size="small" danger onClick={() => {
      let reason = ''
      modal.confirm({
        title: `批量驳回 ${count} 条低影响经验`,
        content: (
          <Input.TextArea placeholder="统一驳回理由（必填，全部生效）" rows={3} onChange={(e) => { reason = e.target.value }} />
        ),
        okText: '确认全部驳回',
        okButtonProps: { danger: true },
        onOk: () => {
          if (!reason.trim()) { message.error('驳回理由必填'); return Promise.reject() }
          onConfirm(reason.trim())
        },
      })
    }}>全部驳回</Button>
  )
}

function RejectOneBtn({ r }: { r: Experience }) {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState('')
  return (
    <>
      <Button size="small" danger onClick={() => setOpen(true)}>驳回</Button>
      <Modal title={`驳回：${r.title.slice(0, 20)}`} open={open} onCancel={() => { setOpen(false); setReason('') }}
        footer={[
          <Button key="c" onClick={() => { setOpen(false); setReason('') }}>取消</Button>,
          <Button key="ok" type="primary" danger disabled={!reason.trim()} onClick={async () => {
            try {
              await reviewExperience(r.id, 'reject', reason.trim())
              message.success('已驳回')
              qc.invalidateQueries({ queryKey: ['exp-pending-review'] })
              setOpen(false); setReason('')
            } catch (e) { message.warning(e instanceof Error ? e.message : '操作失败') }
          }}>确认驳回</Button>,
        ]}>
        <Input.TextArea placeholder="驳回理由（必填，留痕可追溯）" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
      </Modal>
    </>
  )
}

// ================= M3 高影响审核（两步确认三重安全） =================
function ExpReviewPanel({ selEid, setSelEid }: { selEid: number | null; setSelEid: (n: number | null) => void }) {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [action, setAction] = useState<'approve' | 'reject'>('approve')
  const [reason, setReason] = useState('')
  const [confirm, setConfirm] = useState(false)

  const { data: highList } = useQuery({
    queryKey: ['exp-high'],
    queryFn: () => getExperienceList('pending_review', undefined, undefined, 100),
    select: (rows) => rows.filter((r) => r.impact === 'high'),
  })
  const selected = selEid ?? highList?.[0]?.id ?? null

  if (!selected) return <EmptyState text="当前无高影响经验待审核。" icon="🛡️" />

  const cur = (highList ?? []).find((r) => r.id === selected)

  const canSubmit = confirm && (action === 'approve' || reason.trim().length > 0)

  const submit = async () => {
    try {
      await reviewExperience(selected, action, action === 'reject' ? reason.trim() : '')
      message.success(`审核已提交：${cur?.title.slice(0, 20) ?? ''} → ${action === 'reject' ? '已驳回' : '已生效'}`)
      // 清空状态（React useState 天然清理残留，无需手动 pop widget key）
      setReason(''); setConfirm(false); setAction('approve')
      setSelEid(null)
      qc.invalidateQueries({ queryKey: ['exp-pending-review'] })
      qc.invalidateQueries({ queryKey: ['exp-high'] })
      qc.invalidateQueries({ queryKey: ['exp-list'] })
      qc.invalidateQueries({ queryKey: ['exp-pending'] })
      qc.invalidateQueries({ queryKey: ['exp-pending-review-count'] })
    } catch (e) {
      message.warning(e instanceof Error ? e.message : '操作失败')
    }
  }

  const curDetail = (highList ?? []).find((r) => r.id === selected)

  return (
    <div>
      <Alert type="error" showIcon style={{ marginBottom: 10 }}
        message="⚠️ 高影响经验审核 — 此操作可能修改交易规则或研判标准，请谨慎确认"
        description="批准后该经验将注入全部相关 Agent；驳回必须填写理由（留痕可追溯）。" />
      <Space style={{ marginBottom: 10 }}>
        <Select
          value={selected}
          onChange={(v) => { setSelEid(v); setReason(''); setConfirm(false) }}
          style={{ width: 260 }}
          options={(highList ?? []).map((r) => ({ label: `${r.title.slice(0, 20)}`, value: r.id }))} />
      </Space>
      {curDetail ? (
        <Card size="small" style={{ background: 'var(--bg-input)', marginBottom: 10 }}>
          <Space direction="vertical" style={{ width: '100%' }} size={6}>
            <Space wrap>
              <Text strong style={{ fontSize: 15 }}>{curDetail.title}</Text>
              <Tag color={STAGE_TONE[curDetail.stage ?? ''] ?? 'default'}>{curDetail.stage}</Tag>
              {IMPACT_BADGE[curDetail.impact ?? 'low']}
              <Text type="secondary">置信度 {curDetail.confidence?.toFixed(2) ?? '—'}</Text>
            </Space>
            <div>{curDetail.body}</div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              来源：{curDetail.source_summary ?? '（无来源摘要）'} · 任务 {curDetail.source_task_id ?? '—'}
              · 创建 {String(curDetail.created_at ?? '').slice(0, 16)}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>最后审核：{curDetail.last_reviewed_at ?? '（尚未审核）'}</Text>
          </Space>
        </Card>
      ) : null}
      <Space direction="vertical" style={{ width: '100%', maxWidth: 420 }} size={8}>
        <Radio.Group value={action} onChange={(e) => setAction(e.target.value)} optionType="button" buttonStyle="solid"
          options={[{ label: '批准', value: 'approve' }, { label: '驳回', value: 'reject' }]} />
        {action === 'reject' ? (
          <Input.TextArea placeholder="驳回理由（必填，留痕可追溯）" rows={3}
            value={reason} onChange={(e) => setReason(e.target.value)} />
        ) : null}
        <Checkbox checked={confirm} onChange={(e) => setConfirm(e.target.checked)}>
          我已确认上述操作后果
        </Checkbox>
        <Button type="primary" disabled={!canSubmit} onClick={submit}>
          确认提交
        </Button>
      </Space>
    </div>
  )
}

// ================= M4 经验库 =================
function ExpLibraryPanel() {
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  const [q, setQ] = useState('')
  const [stage, setStage] = useState('全部')
  const [onlyAuto, setOnlyAuto] = useState(false)
  const [incRolled, setIncRolled] = useState(false)
  const [searched, setSearched] = useState(false)

  const { data: searchRows } = useQuery({
    queryKey: ['exp-search', q, stage, searched],
    queryFn: () => searched ? searchExperience(stage === '全部' ? undefined : stage, q || undefined, 50) : Promise.resolve([]),
    enabled: searched,
  })
  const { data: listRows } = useQuery({
    queryKey: ['exp-list', stage],
    queryFn: () => getExperienceList(undefined, stage === '全部' ? undefined : stage, undefined, 100),
    enabled: !searched,
  })
  const { data: rolledRows } = useQuery({
    queryKey: ['exp-rolled', stage],
    queryFn: () => getExperienceList('rolled_back', stage === '全部' ? undefined : stage, undefined, 100),
    enabled: incRolled,
  })

  let rows: Experience[] = []
  if (searched) rows = searchRows ?? []
  else {
    rows = listRows ?? []
    if (incRolled) rows = [...rows, ...(rolledRows ?? [])]
  }
  if (onlyAuto) rows = rows.filter((r) => r.auto_merged === 1)

  const rollback = async (r: Experience) => {
    try {
      await rollbackExperience(r.id)
      message.success('已回滚，该经验不再注入 Agent')
      qc.invalidateQueries({ queryKey: ['exp-list'] })
      qc.invalidateQueries({ queryKey: ['exp-search'] })
    } catch (e) { message.warning(e instanceof Error ? e.message : '回滚失败') }
  }
  const confirmRollback = (r: Experience) => {
    modal.confirm({
      title: '回滚确认',
      content: `回滚后该经验将不再注入 Agent：\n\n${r.title}\n\n（自动合并项误合并可恢复，写入 review_log 留痕）`,
      okText: '确认回滚', okButtonProps: { danger: true }, cancelText: '取消',
      onOk: () => rollback(r),
    })
  }

  return (
    <div>
      <Space style={{ marginBottom: 10 }} wrap>
        <Input.Search placeholder="全文搜索（FTS5，仅已生效经验）" style={{ width: 240 }}
          onSearch={(v) => { setQ(v); setSearched(true) }} allowClear
          onChange={(e) => { if (!e.target.value) { setSearched(false); setQ('') } }} />
        <Select value={stage} onChange={setStage} style={{ width: 100 }}
          options={['全部', '选股', '建仓', '持仓'].map((s) => ({ label: s, value: s }))} />
        <Checkbox checked={onlyAuto} onChange={(e) => setOnlyAuto(e.target.checked)}>仅自动合并</Checkbox>
        <Checkbox checked={incRolled} onChange={(e) => setIncRolled(e.target.checked)}>含已回滚</Checkbox>
      </Space>
      {!rows.length ? (
        <EmptyState text={searched ? '搜索无匹配经验。' : '无匹配经验。调整搜索/筛选条件，或等待识别 Worker 产出新经验。'} icon="🔍" />
      ) : (
        <Table size="small" rowKey="id" dataSource={rows} pagination={{ pageSize: 20 }}
          columns={[
            {
              title: '经验', dataIndex: 'title', ellipsis: true,
              render: (v: string, r) => (
                <Space direction="vertical" size={0}>
                  <Space wrap>
                    <Text>{v}</Text>
                    <Tag color={STAGE_TONE[r.stage ?? ''] ?? 'default'}>{r.stage}</Tag>
                    {r.auto_merged === 1 ? <Tag color="purple">🤖 自动</Tag> : <Tag>👤 人工</Tag>}
                    <StatusBadge text={({ active: '已生效', rolled_back: '已回滚', rejected: '已驳回', pending_review: '待审核' } as Record<string, string>)[r.status ?? ''] ?? r.status ?? ''}
                      tone={({ active: 'ok', rolled_back: 'rolled_back' } as Record<string, string>)[r.status ?? ''] ?? 'mute'} />
                    {IMPACT_BADGE[r.impact ?? 'low']}
                  </Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>{r.body.slice(0, 60)}{r.body.length > 60 ? '…' : ''}</Text>
                </Space>
              ),
            },
            { title: '置信度', dataIndex: 'confidence', width: 120, render: (v: number) => <ConfidenceBar confidence={v ?? 0} /> },
            {
              title: '操作', key: 'ops', width: 90,
              render: (_: unknown, r: Experience) => (r.status === 'active' && r.auto_merged === 1) ? (
                <Button size="small" type="primary" onClick={() => confirmRollback(r)}>回滚</Button>
              ) : null,
            },
          ]}
          expandable={{
            expandedRowRender: (r) => (
              <Space direction="vertical" size={4}>
                <div><b>正文：</b>{r.body}</div>
                <Text type="secondary">来源：{r.source_summary ?? '（无来源摘要）'} · 任务 {r.source_task_id ?? '—'}</Text>
                <Text type="secondary">影响 {r.impact} · 创建 {String(r.created_at ?? '').slice(0, 16)} · 最后审核 {r.last_reviewed_at ?? '—'}</Text>
                {(r.status === 'active' && r.auto_merged === 1) ? (
                  <Button size="small" danger onClick={() => confirmRollback(r)}>回滚该经验（不再注入 Agent）</Button>
                ) : null}
              </Space>
            ),
          }} />
      )}
    </div>
  )
}

// ================= M5 设置 =================
function ExpSettingsPanel() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const { data: cfg, isError, error, refetch } = useQuery<ExperienceConfig>({
    queryKey: ['exp-config'],
    queryFn: getExperienceConfig,
  })
  const [conf, setConf] = useState<number>(0.85)
  const [auto, setAuto] = useState<boolean>(true)
  const [sleep, setSleep] = useState<number>(3)
  const [backlog, setBacklog] = useState<number>(50)

  // 后端 config 全 string → number 化（加载完成同步一次状态）
  useEffect(() => {
    if (cfg) {
      setConf(Number(cfg.confidence_threshold) || 0.85)
      setAuto(cfg.auto_merge_enabled === '1')
      setSleep(Number(cfg.worker_sleep_sec) || 3)
      setBacklog(Number(cfg.digest_backlog_threshold) || 50)
    }
  }, [cfg])

  if (isError) return <ErrorCard title="设置加载失败" message={error?.message} onRetry={() => refetch()} />

  const save = async () => {
    try {
      await setExperienceConfig({
        confidence_threshold: String(conf),
        auto_merge_enabled: auto ? '1' : '0',
        worker_sleep_sec: String(sleep),
        digest_backlog_threshold: String(backlog),
      })
      message.success('设置已保存，热加载生效（无需重启）')
      qc.invalidateQueries({ queryKey: ['exp-config'] })
    } catch (e) { message.error(e instanceof Error ? e.message : '保存失败') }
  }

  return (
    <Space direction="vertical" style={{ width: '100%', maxWidth: 520 }} size={16}>
      <Card size="small" title="分流策略" style={{ background: 'var(--bg-input)' }}>
        <div style={{ marginBottom: 8 }}>自动合并置信阈值：<Text strong>{conf.toFixed(2)}</Text></div>
        <Slider min={0.5} max={0.95} step={0.05} value={conf} onChange={setConf} />
        <div style={{ marginBottom: 8 }}>
          自动合并开关：{' '}
          <Switch checked={auto} onChange={setAuto} />
        </div>
        <div style={{ marginBottom: 4 }}>Worker 批间限流（秒）：<Text strong>{sleep}</Text></div>
        <Slider min={0} max={30} value={sleep} onChange={setSleep} />
        <div style={{ marginBottom: 4 }}>积压触发阈值：<Text strong>{backlog}</Text></div>
        <Slider min={10} max={200} value={backlog} onChange={setBacklog} />
      </Card>
      <Card size="small" title="调度与模型" style={{ background: 'var(--bg-input)' }}>
        <div>调度 cron：<code>{cfg?.worker_cron ?? '0 2 * * *'}</code>（每日 02:00 主跑 + 30min 积压探针）</div>
        <div style={{ marginTop: 6 }}>识别模型：<code>{cfg?.worker_model ?? 'flash'}</code>（deepseek-v4-flash 云端轻量模型）</div>
      </Card>
      <Button type="primary" onClick={save}>保存设置（热加载生效）</Button>
    </Space>
  )
}

// ================= 经验沉淀页（Phase 3.5） =================
const TABS = [
  { label: 'M1 沉淀队列', value: 'M1' },
  { label: 'M2 每日 Digest', value: 'M2' },
  { label: 'M3 高影响审核', value: 'M3' },
  { label: 'M4 经验库', value: 'M4' },
  { label: 'M5 设置', value: 'M5' },
]

function ExpPanelRoot() {
  const [tab, setTab] = useState('M1')
  const [selEid, setSelEid] = useState<number | null>(null)
  return (
    <div>
      <Segmented value={tab} onChange={(v) => setTab(String(v))} options={TABS} style={{ marginBottom: 14 }} />
      {tab === 'M1' && <ExpQueuePanel />}
      {tab === 'M2' && <ExpDigestPanel onGoHigh={(eid) => { setSelEid(eid); setTab('M3') }} />}
      {tab === 'M3' && <ExpReviewPanel selEid={selEid} setSelEid={setSelEid} />}
      {tab === 'M4' && <ExpLibraryPanel />}
      {tab === 'M5' && <ExpSettingsPanel />}
    </div>
  )
}

export function ExperiencePage() {
  return <ExpPanelRoot />
}

export default ExperiencePage
