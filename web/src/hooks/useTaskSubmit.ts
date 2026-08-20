import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { submitTask, taskDetail } from '@/api/tasks'
import { useTasksStore } from '@/store/tasksStore'
import type { TaskInfo } from '@/types'

/**
 * 任务队列操作 hook：提交后台任务 → 轮询 /api/tasks/{id} 直到 done/failed → 完成回调。
 * 用于 sell_decision / position / daily_pipeline / market_intel / score /
 * portfolio_sentinel / monitor_all / batch_ask 等走任务队列的 kind（禁止裸调同步接口）。
 * 透明接入全局任务 store（TaskDrawer 展示），调用方零感知；不向外暴露 store。
 * 返回 { submit, poll, reset }；submit.error 可区分 ConflictError（409，已有同类任务）。
 */
export function useTaskSubmit(kind: string, onDone?: (result: unknown) => void) {
  const qc = useQueryClient()
  const addTask = useTasksStore((s) => s.addTask)
  const updateTask = useTasksStore((s) => s.updateTask)
  const [tid, setTid] = useState<string | null>(null)

  const submit = useMutation({
    mutationFn: (params?: Record<string, unknown>) => submitTask(kind, params),
    onSuccess: (data, params) => {
      // 入队全局任务面板（完成状态由轮询更新）
      addTask({
        task_id: data.task_id,
        kind,
        params,
        status: 'pending',
        started_at: Date.now(),
      })
      setTid(data.task_id)
    },
  })

  const poll = useQuery<TaskInfo>({
    queryKey: ['task', tid],
    queryFn: () => taskDetail(tid!),
    enabled: !!tid,
    refetchInterval: (q) => {
      const status = q.state.data?.status
      return status === 'done' || status === 'failed' ? false : 2000
    },
    // 任务失败/完成不再轮询；后端不可达等瞬时错误用 retry 兜底
    retry: 1,
  })

  // 轮询每次返回 → 同步全局 store（状态变化或每 2s tick）
  useEffect(() => {
    const t = poll.data
    if (!tid || !t) return
    const terminal = t.status === 'done' || t.status === 'failed'
    updateTask(tid, {
      status: t.status,
      error: t.error ?? null,
      result: t.result,
      finished_at: terminal ? Date.now() : undefined,
    })
  }, [tid, poll.data, updateTask])

  // 轮询层面失败（后端不可达等）→ 标记 failed
  useEffect(() => {
    if (tid && poll.error) {
      updateTask(tid, {
        status: 'failed',
        error: poll.error instanceof Error ? poll.error.message : '任务查询失败',
        finished_at: Date.now(),
      })
    }
  }, [tid, poll.error, updateTask])

  useEffect(() => {
    const t = poll.data
    if (t && (t.status === 'done' || t.status === 'failed')) {
      if (t.status === 'done') onDone?.(t.result)
      qc.invalidateQueries()
      setTid(null)
    }
  }, [poll.data, onDone, qc])

  const reset = () => setTid(null)

  return { submit, poll, reset }
}

