import { useEffect, useState } from 'react'
import { App, Button, Card, Form, Input, Select, Space, Spin, Tabs, Tag, Typography, Upload } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { chatAgents, chatAsk, chatHistory, chatLearn, chatLearnConfirm, chatRule } from '@/api/chat'
import { taskDetail } from '@/api/tasks'
import { EmptyState } from '@/components/common'

const { Text } = Typography
const STATUS_TONE: Record<string, string> = { 待确认: 'orange', 已完成: 'green', 归档: 'default' }
const VERDICT_TONE: Record<string, string> = { adopted: 'green', partial: 'orange' }
const VERDICT_LABEL: Record<string, string> = { adopted: '已采纳', partial: '部分采纳' }

interface LearnPoint { title: string; content: string; tags: string[]; agent_tag: string }

/** Agent 对话页（Phase 4） */
export function AgentChatPage() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [agent, setAgent] = useState<string>()
  const [askForm] = Form.useForm()
  const [ruleForm] = Form.useForm()
  const [askTid, setAskTid] = useState<string | null>(null)
  const [ruleTid, setRuleTid] = useState<string | null>(null)
  const [description, setDescription] = useState('')
  const [points, setPoints] = useState<LearnPoint[]>([])
  const [histStatus, setHistStatus] = useState<Record<string, string>>({})

  const { data: agents } = useQuery({ queryKey: ['agents'], queryFn: chatAgents })
  const { data: history } = useQuery({
    queryKey: ['chat-history', agent],
    queryFn: () => chatHistory(agent!, 30),
    enabled: !!agent,
  })
  const { data: askTask } = useQuery({
    queryKey: ['chat-task', askTid],
    queryFn: () => taskDetail(askTid!),
    enabled: !!askTid,
    refetchInterval: (q) => {
      const st = q.state.data?.status
      return st === 'done' || st === 'failed' ? false : 2000
    },
  })
  const askDone = askTask && (askTask.status === 'done' || askTask.status === 'failed')
  const { data: ruleTask } = useQuery({
    queryKey: ['chat-rule-task', ruleTid],
    queryFn: () => taskDetail(ruleTid!),
    enabled: !!ruleTid,
    refetchInterval: (q) => {
      const st = q.state.data?.status
      return st === 'done' || st === 'failed' ? false : 2000
    },
  })
  const ruleDone = ruleTask && (ruleTask.status === 'done' || ruleTask.status === 'failed')

  useEffect(() => {
    try { setHistStatus(JSON.parse(localStorage.getItem(`chat-status-${agent}`) ?? '{}')) } catch { setHistStatus({}) }
  }, [agent])

  useEffect(() => {
    if (askDone && askTask?.status === 'done') {
      const res = askTask.result as { points_json?: string } | undefined
      try {
        const parsed = JSON.parse(res?.points_json ?? '[]') as Array<Record<string, unknown>>
        setPoints(parsed.map((p) => ({
          title: String(p.title ?? ''), content: String(p.content ?? ''),
          tags: Array.isArray(p.tags) ? p.tags.map(String) : String(p.tags ?? '').split(',').filter(Boolean),
          agent_tag: String(p.agent_tag ?? 'all'),
        })))
      } catch { setPoints([]) }
    }
  }, [askDone, askTask])

  const updatePoint = (i: number, key: keyof LearnPoint, v: unknown) => {
    setPoints((prev) => prev.map((p, j) => (j === i ? { ...p, [key]: v } : p)))
  }

  const send = async (question: string) => {
    if (!agent) { message.warning('请先选择 Agent'); return }
    try {
      const r = await chatAsk(agent, question)
      setAskTid(String(r.task_id))
      askForm.resetFields()
    } catch (e) { message.error(e instanceof Error ? e.message : '提交失败') }
  }

  const submitRule = async (v: { proposal: string }) => {
    if (!agent) { message.warning('请先选择 Agent'); return }
    try { const r = await chatRule(agent, v.proposal); setRuleTid(String(r.task_id)); ruleForm.resetFields() }
    catch (e) { message.error(e instanceof Error ? e.message : '提交失败') }
  }

  const learn = async (file: File) => {
    if (!agent) { message.warning('请先选择 Agent'); return }
    try { const r = await chatLearn(agent, file, file.name, description); setAskTid(String(r.task_id)); setPoints([]) }
    catch (e) { message.error(e instanceof Error ? e.message : '上传失败') }
  }

  const confirmLearn = async () => {
    const entries = points.filter((p) => p.title && p.content)
    if (!entries.length) { message.warning('无可沉淀的有效条目（标题与正文需非空）'); return }
    try {
      await chatLearnConfirm(agent!, entries as unknown as Record<string, unknown>[])
      message.success(`已沉淀 ${entries.length} 个知识点`)
      setAskTid(null)
      setPoints([])
      qc.invalidateQueries({ queryKey: ['chat-history'] })
    } catch (e) { message.error(e instanceof Error ? e.message : '沉淀失败') }
  }

  const cycleStatus = (id: number | undefined) => {
    const key = String(id ?? '')
    const cur = histStatus[key] ?? '待确认'
    const next = cur === '待确认' ? '已完成' : cur === '已完成' ? '归档' : '待确认'
    const nextMap = { ...histStatus, [key]: next }
    setHistStatus(nextMap)
    try { localStorage.setItem(`chat-status-${agent}`, JSON.stringify(nextMap)) } catch { /* noop */ }
  }

  const agentsList = agents ?? []
  const selAgent = agentsList.find((a) => a.agent === agent)

  return (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Text>选择对话 Agent：</Text>
        <Select placeholder="选择 Agent" style={{ width: 200 }} value={agent}
          onChange={(v) => { setAgent(v); setAskTid(null); setRuleTid(null); setPoints([]) }}
          options={agentsList.map((a) => ({ label: a.name, value: a.agent }))} />
      </Space>
      {selAgent ? (
        <Space style={{ marginBottom: 12 }} wrap align="start">
          <Card size="small" title="职责范围" style={{ background: 'var(--bg-input)', width: 380 }}>{selAgent.scope || '—'}</Card>
          <Card size="small" title="知识库来源" style={{ background: 'var(--bg-input)', width: 380 }}>{selAgent.knowledge || '—'}</Card>
        </Space>
      ) : null}

      {!agent ? <EmptyState text="请先选择对话 Agent。" icon="💬" /> : (
        <Tabs items={[
          {
            key: 'ask', label: '文字提问',
            children: (
              <Card size="small" style={{ background: 'var(--bg-input)' }}>
                <Form form={askForm} onFinish={(v) => send(v.question)} layout="inline"
                  initialValues={{ question: '' }}>
                  <Form.Item name="question" style={{ flex: 1 }}>
                    <Input placeholder="向 Agent 提问（基于专属知识库 + 全局基线回答）" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit">提问（后台处理）</Button>
                </Form>
                {askTid && !askDone ? <div style={{ marginTop: 12, color: 'var(--text-dim)' }}>Agent 思考中…（任务 {askTid}）</div> : null}
                {askDone ? (
                  <Card size="small" style={{ marginTop: 12, background: 'var(--bg-card)' }}>
                    {askTask?.status === 'failed'
                      ? <Text type="danger">处理失败：{String(askTask.error ?? '')}</Text>
                      : (() => {
                        const r = askTask?.result as Record<string, unknown> | undefined
                        const ann = (r?.announcement ?? {}) as Record<string, unknown>
                        const verdict = (r?.announcement_verdict ?? {}) as Record<string, unknown>
                        const items = (ann.items ?? []) as Array<Record<string, unknown>>
                        const sentiment = String(verdict.sentiment ?? '')
                        const annTone = sentiment === '利好' ? 'green' : sentiment === '利空' ? 'red' : 'default'
                        return (
                          <Space direction="vertical" style={{ width: '100%' }}>
                            <div><b>回答</b>（信心度 <Text strong>{String((r?.confidence ?? '') as unknown)}</Text>）</div>
                            <div style={{ whiteSpace: 'pre-wrap' }}>{String(r?.answer ?? '')}</div>
                            {r?.scope_note ? <Text type="secondary" style={{ fontSize: 12 }}>范围说明：{String(r.scope_note)}</Text> : null}
                            {r?.sources ? <Text type="secondary" style={{ fontSize: 12 }}>依据来源：{String(r.sources)}</Text> : null}
                            {(Object.keys(ann).length || Object.keys(verdict).length) ? (
                              <Card size="small" title={`最新公告查询 · ${String(ann.stock_code ?? '')}（近 ${String(ann.query_days ?? 7)} 日）`}
                                style={{ background: 'var(--bg-input)' }}>
                                <Space direction="vertical" style={{ width: '100%' }} size={4}>
                                  {Object.keys(verdict).length ? (
                                    <>
                                      <div><Tag color={annTone}>{sentiment || '待定'}</Tag> <Text>{String(verdict.reason ?? '')}</Text></div>
                                      {verdict.cross_check ? <Text type="secondary">交叉验证：{String(verdict.cross_check)}</Text> : null}
                                      {verdict.risk_note ? <Text type="danger">风险提示：{String(verdict.risk_note)}</Text> : null}
                                    </>
                                  ) : null}
                                  {items.length ? (
                                    <Space direction="vertical" style={{ width: '100%' }} size={4}>
                                      {items.slice(0, 8).map((it, i) => {
                                        const url = String(it.url ?? '')
                                        const title = String(it.title ?? '')
                                        const okUrl = url && url !== '链接未提供'
                                        return (
                                          <div key={i} style={{ fontSize: 13 }}>
                                            <Text type="secondary" style={{ fontSize: 12 }}>{String(it.published_at ?? '').slice(0, 16)} </Text>
                                            {okUrl ? <a href={url} target="_blank" rel="noreferrer">{title}</a> : title}
                                            <Text type="secondary" style={{ fontSize: 12 }}>（{String(it.source ?? '东财')} · {String(it.ann_type ?? '其他')}）</Text>
                                            {it.summary ? <div style={{ fontSize: 12 }}><Text type="secondary">{String(it.summary).slice(0, 120)}</Text></div> : null}
                                          </div>
                                        )
                                      })}
                                    </Space>
                                  ) : <Text type="secondary">{String(ann.message ?? '未查询到该标的近期公开公告')}</Text>}
                                </Space>
                              </Card>
                            ) : null}
                          </Space>
                        )
                      })()}
                    <Button size="small" style={{ marginTop: 8 }} onClick={() => setAskTid(null)}>清空本次回答</Button>
                  </Card>
                ) : null}
              </Card>
            ),
          },
          {
            key: 'rule', label: '规则调教',
            children: (
              <Card size="small" style={{ background: 'var(--bg-input)' }}>
                <Form form={ruleForm} onFinish={submitRule}>
                  <Form.Item name="proposal" label="规则提案" rules={[{ required: true, message: '请输入规则提案' }]}>
                    <Input.TextArea rows={4} placeholder="如：建议把换手率关注阈值从 >15% 调整为 >12%" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit">提交校验（后台处理）</Button>
                </Form>
                {ruleTid && !ruleDone ? <div style={{ marginTop: 12, color: 'var(--text-dim)' }}>规则校验中…（任务 {ruleTid}）</div> : null}
                {ruleDone ? (
                  <Card size="small" style={{ marginTop: 12, background: 'var(--bg-card)' }}>
                    {ruleTask?.status === 'failed'
                      ? <Text type="danger">校验失败：{String(ruleTask.error ?? '')}</Text>
                      : (() => {
                        const r = ruleTask?.result as Record<string, unknown> | undefined
                        const verdict = String(r?.verdict ?? '')
                        const tone = VERDICT_TONE[verdict] ?? 'default'
                        const label = VERDICT_LABEL[verdict] ?? (verdict ? '维持原规则' : '—')
                        return (
                          <Space direction="vertical" style={{ width: '100%' }}>
                            <div><Tag color={tone}>{label}</Tag> {r?.rule_title ? <Text strong>规则：{String(r.rule_title)}</Text> : null}</div>
                            {r?.reason ? <div><b>依据</b>：{String(r.reason)}</div> : null}
                            {r?.conflict_note ? <Text type="warning">冲突核查：{String(r.conflict_note)}</Text> : null}
                            {r?.knowledge_id ? <Text type="secondary">知识库关联 ID：{String(r.knowledge_id)}</Text> : null}
                          </Space>
                        )
                      })()}
                    <Button size="small" style={{ marginTop: 8 }} onClick={() => setRuleTid(null)}>清空本次校验</Button>
                  </Card>
                ) : null}
              </Card>
            ),
          },
          {
            key: 'learn', label: '多模态学习',
            children: (
              <Card size="small" style={{ background: 'var(--bg-input)' }}>
                <Input.TextArea placeholder="补充说明（可选，≤500 字）：描述这张图想表达的战法/要点…" maxLength={500} rows={2}
                  value={description} onChange={(e) => setDescription(e.target.value)} style={{ marginBottom: 8 }} />
                <Upload.Dragger accept="image/png,image/jpeg" beforeUpload={(f) => { learn(f); return false }} showUploadList={false}>
                  <div>点击或拖拽上传 K线图 / 战法文档 / 交易心得图片（未输说明也可正常上传）</div>
                </Upload.Dragger>
                {askTid && !askDone ? <Spin tip="识别与提炼中（大图约 1-2 分钟）…" style={{ marginTop: 12 }} /> : null}
                {askDone ? (
                  <Space direction="vertical" style={{ width: '100%', marginTop: 12 }} size={10}>
                    {(() => {
                      const res = askTask?.result as Record<string, unknown> | undefined
                      return (
                        <>
                          <Space wrap>
                            <Tag color="blue">引擎：{String(res?.engine ?? '—')}</Tag>
                            {description ? <Tag color="purple">用户说明：{description}</Tag> : null}
                          </Space>
                          {res?.summary ? <div><b>提炼摘要：</b>{String(res.summary)}</div> : null}
                        </>
                      )
                    })()}
                    {points.length ? (
                      <>
                        <Text type="secondary" style={{ fontSize: 12 }}>逐条核对并编辑后确认沉淀：</Text>
                        {points.map((p, i) => (
                          <Card key={i} size="small" title={`知识点 ${i + 1}`} style={{ background: 'var(--bg-input)' }}>
                            <Space direction="vertical" style={{ width: '100%' }}>
                              <Input placeholder="标题" value={p.title} onChange={(e) => updatePoint(i, 'title', e.target.value)} />
                              <Input.TextArea placeholder="正文" rows={3} value={p.content} onChange={(e) => updatePoint(i, 'content', e.target.value)} />
                              <Space wrap>
                                <Input placeholder="标签（逗号分隔）" style={{ width: 240 }} value={p.tags.join(',')}
                                  onChange={(e) => updatePoint(i, 'tags', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))} />
                                <Select placeholder="目标 Agent" style={{ width: 180 }} value={p.agent_tag}
                                  onChange={(v) => updatePoint(i, 'agent_tag', v)}
                                  options={[{ label: '全部通用', value: 'all' }, ...agentsList.map((a) => ({ label: a.name, value: a.agent }))]} />
                              </Space>
                            </Space>
                          </Card>
                        ))}
                      </>
                    ) : null}
                    <Space>
                      <Button type="primary" onClick={confirmLearn}>确认并沉淀到知识库</Button>
                      <Button onClick={() => { setAskTid(null); setPoints([]) }}>丢弃本次结果</Button>
                    </Space>
                  </Space>
                ) : null}
              </Card>
            ),
          },
          {
            key: 'history', label: '对话历史',
            children: (
              <div>
                {(history ?? []).map((m) => {
                  const st = histStatus[String(m.id)] ?? '待确认'
                  return (
                    <Card key={m.id} size="small" style={{ marginBottom: 8, background: 'var(--bg-input)' }}>
                      <Space wrap>
                        <Tag color="blue">{String(m.question ?? '').slice(0, 40) || '—'}</Tag>
                        <Tag color={STATUS_TONE[st] ?? 'default'} style={{ cursor: 'pointer' }} onClick={() => cycleStatus(m.id)}>{st}（点击切换）</Tag>
                        <Text type="secondary">{String(m.created_at ?? '').slice(0, 16)}</Text>
                      </Space>
                      <div style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{String(m.answer ?? '')}</div>
                    </Card>
                  )
                })}
                {!(history ?? []).length ? <EmptyState text="暂无对话历史。" icon="💬" /> : null}
              </div>
            ),
          },
        ]} />
      )}
    </div>
  )
}

export default AgentChatPage
