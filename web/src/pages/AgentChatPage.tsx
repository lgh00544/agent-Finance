import { useState } from 'react'
import { App, Button, Card, Form, Input, Select, Space, Spin, Tabs, Tag, Typography, Upload } from 'antd'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { chatAgents, chatAsk, chatHistory, chatLearn, chatLearnConfirm, chatRule } from '@/api/chat'
import { taskDetail } from '@/api/tasks'
import { EmptyState } from '@/components/common'

const { Text } = Typography

/** Agent 对话页（Phase 4） */
export function AgentChatPage() {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [agent, setAgent] = useState<string>()
  const [askForm] = Form.useForm()
  const [ruleForm] = Form.useForm()
  const [askTid, setAskTid] = useState<string | null>(null)

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
    try { const r = await chatRule(agent, v.proposal); setAskTid(String(r.task_id)); ruleForm.resetFields() }
    catch (e) { message.error(e instanceof Error ? e.message : '提交失败') }
  }

  const learn = async (file: File) => {
    if (!agent) { message.warning('请先选择 Agent'); return }
    try { const r = await chatLearn(agent, file, file.name, ''); setAskTid(String(r.task_id)) }
    catch (e) { message.error(e instanceof Error ? e.message : '上传失败') }
  }

  const confirmLearn = async () => {
    if (!askTask?.result) return
    try {
      const res = askTask.result as { points_json?: string }
      const points = JSON.parse(res.points_json ?? '[]') as Array<Record<string, unknown>>
      const entries = points.filter((p) => (p.title as string) && (p.content as string))
      await chatLearnConfirm(agent!, entries)
      message.success(`已沉淀 ${entries.length} 个知识点`)
      setAskTid(null)
      qc.invalidateQueries({ queryKey: ['chat-history'] })
    } catch (e) { message.error(e instanceof Error ? e.message : '沉淀失败') }
  }

  const agentsList = agents ?? []
  const selAgent = agentsList.find((a) => a.agent === agent)

  return (
    <div>
      <Space style={{ marginBottom: 12 }} wrap>
        <Text>选择对话 Agent：</Text>
        <Select placeholder="选择 Agent" style={{ width: 200 }} value={agent} onChange={(v) => { setAgent(v); setAskTid(null) }}
          options={agentsList.map((a) => ({ label: a.name, value: a.agent }))} />
        {selAgent ? <Text type="secondary" style={{ fontSize: 12 }}>{selAgent.scope}</Text> : null}
      </Space>

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
                        return <div>
                          <div><b>回答</b>（信心度 <Text strong>{String((r?.confidence ?? '') as unknown)}</Text>）</div>
                          <div style={{ marginTop: 6, whiteSpace: 'pre-wrap' }}>{String(r?.answer ?? '')}</div>
                          {r?.sources ? <Text type="secondary" style={{ fontSize: 12 }}>依据来源：{String(r.sources)}</Text> : null}
                        </div>
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
              </Card>
            ),
          },
          {
            key: 'learn', label: '多模态学习',
            children: (
              <Card size="small" style={{ background: 'var(--bg-input)' }}>
                <Upload.Dragger accept="image/png,image/jpeg" beforeUpload={(f) => { learn(f); return false }} showUploadList={false}>
                  <div>点击或拖拽上传 K线图 / 战法文档 / 交易心得图片</div>
                </Upload.Dragger>
                {askTid && !askDone ? <Spin tip="识别与提炼中（大图约 1-2 分钟）…" style={{ marginTop: 12 }} /> : null}
                {askDone ? (
                  <div style={{ marginTop: 12 }}>
                    <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{JSON.stringify(askTask?.result, null, 2)}</pre>
                    <Button type="primary" onClick={confirmLearn}>确认并沉淀到知识库</Button>
                    <Button style={{ marginLeft: 8 }} onClick={() => setAskTid(null)}>丢弃本次结果</Button>
                  </div>
                ) : null}
              </Card>
            ),
          },
          {
            key: 'history', label: '对话历史',
            children: (
              <div>
                {(history ?? []).map((m) => (
                  <Card key={m.id} size="small" style={{ marginBottom: 8, background: 'var(--bg-input)' }}>
                    <Space wrap><Tag color="blue">{String(m.question ?? '').slice(0, 40) || '—'}</Tag><Text type="secondary">{String(m.created_at ?? '').slice(0, 16)}</Text></Space>
                    <div style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{String(m.answer ?? '')}</div>
                  </Card>
                ))}
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
