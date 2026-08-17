import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { submitTask, taskDetail } from '@/api/tasks'
import type { TaskInfo } from '@/types'

/**
 * 任务队列操作 hook：提交后台任务 → 轮询 /api/tasks/{id} 直到 done/failed → 完成回调。
 * 用于 sell_decision / position / daily_pipeline / market_intel / score /
 * portfolio_sentinel / monitor_all 等 7 个走任务队列的 kind（禁止裸调同步接口）。
 * 返回 { submit, poll, reset }；submit.error 可区分 ConflictError（409，已有同类任务）。
 */
export function useTaskSubmit(kind: string, onDone?: (result: unknown) => void) {
  const qc = useQueryClient()
  const [tid, setTid] = useState<string | null>(null)

  const submit = useMutation({
    mutationFn: (params?: Record<string, unknown>) => submitTask(kind, params),
    onSuccess: (data) => setTid(data.task_id),
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
