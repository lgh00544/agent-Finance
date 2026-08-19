import { useEffect, useState } from 'react'
import {
  App,
  Badge,
  Button,
  Card,
  Drawer,
  Empty,
  Modal,
  Space,
  Tag,
  Typography,
} from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, SyncOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { retryTask, taskDetail } from '@/api/tasks'
import { useRunningCount, useTasks, useTasksStore, type TaskEntry } from '@/store/tasksStore'

const { Text } = Typography

/** 任务 kind → 中文名（供 Drawer 与其他地方复用） */
export const KIND_LABELS: Record<string, string> = {
  daily_pipeline: '每日挖掘',
  batch_ask: '批量验证',
  position: '建仓方案',
  score: '评分',
  sell_decision: '卖出决策',
  monitor_all: '全量监控',
  portfolio_sentinel: '组合哨兵',
  market_intel: '市场研判',
}

export function kindLabel(kind?: string): string {
  if (!kind) return ''
  return KIND_LABELS[kind] ?? kind
}

function fmtElapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}m ${r}s`
}

function shortId(id?: string): string {
  if (!id) return ''
  return id.length > 6 ? id.slice(-6) : id
}

/** 任务详情弹窗 */
function TaskDetailModal({ entry, onClose }: { entry: TaskEntry | null; onClose: () => void }) {
  return (
    <Modal title={`任务详情：${kindLabel(entry?.kind)} #${shortId(entry?.task_id)}`}
      open={!!entry} onCancel={onClose} footer={null} width={560}>
      <pre style={{ whiteSpace: 'pre-wrap', background: 'var(--bg-input)', padding: 12, borderRadius: 6, fontSize: 11, maxHeight: 420, overflow: 'auto' }}>
        {entry ? JSON.stringify({ kind: entry.kind, task_id: entry.task_id, status: entry.status,
          error: entry.error, result: entry.result, params: entry.params }, null, 2) : ''}
      </pre>
    </Modal>
  )
}

/** 右下角悬浮后台任务面板 */
export function TaskDrawer() {
  const { message, modal } = App.useApp()
  const [open, setOpen] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const [retryTid, setRetryTid] = useState<string | null>(null)
  const [detailEntry, setDetailEntry] = useState<TaskEntry | null>(null)
  const tasks = useTasks()
  const running = useRunningCount()
  const total = tasks.length
  const { removeTask, clearDone, updateTask } = useTasksStore()

  // 每秒刷新计时
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  // 重试后重新轮询原 task_id 直到终态
  const retry = useQuery({
    queryKey: ['task', retryTid],
    queryFn: () => taskDetail(retryTid!),
    enabled: !!retryTid,
    refetchInterval: (q) => {
      const st = q.state.data?.status
      return st === 'done' || st === 'failed' ? false : 2000
    },
  })
  useEffect(() => {
    const t = retry.data
    if (!retryTid || !t) return
    updateTask(t.task_id, {
      status: t.status,
      error: t.error ?? null,
      result: t.result,
      finished_at: (t.status === 'done' || t.status === 'failed') ? Date.now() : undefined,
    })
    if (t.status === 'done' || t.status === 'failed') setRetryTid(null)
  }, [retryTid, retry.data, updateTask])
  useEffect(() => {
    if (retryTid && retry.error) setRetryTid(null)
  }, [retryTid, retry.error])

  const doRetry = (entry: TaskEntry) => {
    retryTask(entry.task_id)
      .then((r) => {
        // 后端复用原 task_id 重新入队
        updateTask(r.task_id, { status: 'pending', error: null, finished_at: undefined })
        setRetryTid(r.task_id)
        message.success(`已重新入队：${kindLabel(entry.kind)} #${shortId(r.task_id)}`)
      })
      .catch((e: Error) => message.error(`重试失败：${e.message}`))
  }

  const doRemove = (entry: TaskEntry) => {
    // 仅 done/failed 可移除（store 内部也强校验）
    removeTask(entry.task_id)
  }

  const doClearDone = () => {
    modal.confirm({
      title: '清空已完成任务',
      content: '将移除面板中所有已完成（done/failed）任务记录。运行中的任务不受影响。',
      okText: '确认清空',
      cancelText: '取消',
      onOk: clearDone,
    })
  }

  const copyId = async (id?: string) => {
    if (!id) return
    try {
      await navigator.clipboard.writeText(id)
      message.success(`已复制任务 ID：${id}`)
    } catch {
      message.info(`任务 ID：${id}`)
    }
  }

  return (
    <>
      <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 200 }}>
        <Badge count={running} size="small" offset={[-4, 0]}>
          <Button
            type={running > 0 ? 'primary' : 'default'}
            shape="round"
            icon={running > 0 ? <SyncOutlined spin /> : undefined}
            onClick={() => setOpen(true)}
          >
            ⏱ 任务（{running}/{total}）
          </Button>
        </Badge>
      </div>

      <Drawer
        title={
          <Space>
            <span>后台任务</span>
            {running > 0 ? <Tag color="blue">{running} 运行中</Tag> : <Tag>空闲</Tag>}
            <Button size="small" disabled={!tasks.length} onClick={doClearDone}>清空已完成</Button>
          </Space>
        }
        width={420}
        open={open}
        onClose={() => setOpen(false)}
      >
        {!tasks.length ? (
          <Empty description={<span>暂无后台任务</span>} style={{ marginTop: 60 }}>
            <Text type="secondary">所有提交都会显示在这里</Text>
          </Empty>
        ) : (
          tasks.map((t) => {
            const elapsedBase = (t.finished_at ?? now) - t.started_at
            const elapsed = t.status === 'running' || t.status === 'pending' ? now - t.started_at : elapsedBase
            const runningNow = t.status === 'running' || t.status === 'pending'
            return (
              <Card key={t.task_id} size="small" style={{ marginBottom: 10, background: 'var(--bg-input)' }}>
                <Space style={{ width: '100%' }} wrap>
                  {t.status === 'pending' ? <SyncOutlined style={{ color: 'var(--text-mute)' }} /> :
                    t.status === 'running' ? <SyncOutlined spin style={{ color: 'var(--primary)' }} /> :
                    t.status === 'done' ? <CheckCircleOutlined style={{ color: 'var(--ok)' }} /> :
                    <CloseCircleOutlined style={{ color: 'var(--err)' }} />}
                  <Text strong>{kindLabel(t.kind)}</Text>
                  <Text code style={{ fontSize: 11 }}>#{shortId(t.task_id)}</Text>
                  <Tag color={t.status === 'done' ? 'green' : t.status === 'failed' ? 'red' : t.status === 'running' ? 'blue' : 'default'}>
                    {t.status === 'pending' ? '排队中' : t.status === 'running' ? '运行中' : t.status === 'done' ? '已完成' : '失败'}
                  </Tag>
                  <Text type="secondary" style={{ marginLeft: 'auto', fontSize: 12 }}>
                    {runningNow ? `${fmtElapsed(elapsed)}` : fmtElapsed(elapsed)}
                  </Text>
                </Space>
                <Space style={{ marginTop: 8 }} wrap>
                  <Button size="small" onClick={() => setDetailEntry(t)}>查看详情</Button>
                  <Button size="small" onClick={() => copyId(t.task_id)}>复制 ID</Button>
                  {t.status === 'failed' ? <Button size="small" danger onClick={() => doRetry(t)}>重试</Button> : null}
                  {!runningNow ? <Button size="small" type="text" onClick={() => doRemove(t)}>移除</Button> : null}
                </Space>
                {t.error ? (
                  <div style={{ marginTop: 8, color: 'var(--err)', fontSize: 12 }}>
                    {t.error.length > 200 ? `${t.error.slice(0, 200)}…` : t.error}
                  </div>
                ) : null}
              </Card>
            )
          })
        )}
      </Drawer>

      <TaskDetailModal entry={detailEntry} onClose={() => setDetailEntry(null)} />
    </>
  )
}
