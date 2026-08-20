import { create } from 'zustand'

/** 后台任务全局 store（内存态，路由刷新即重置）。
 * useTaskSubmit 透明写入：提交入队 → 轮询更新 → 失败标记。
 * 已完成任务 30s 后从视图隐藏（不真删，按 task_id 仍可查）。 */

export type TaskStatus = 'pending' | 'running' | 'done' | 'failed'

export interface TaskEntry {
  task_id: string
  kind: string
  params?: Record<string, unknown>
  status: TaskStatus
  error?: string | null
  result?: unknown
  started_at: number
  finished_at?: number
  lastViewedAt: number
}

interface TasksState {
  tasks: Record<string, TaskEntry>
  addTask: (entry: Omit<TaskEntry, 'lastViewedAt'>) => void
  updateTask: (task_id: string, patch: Partial<TaskEntry>) => void
  removeTask: (task_id: string) => void
  clearDone: () => void
}

const HIDE_AFTER_MS = 30_000

export const useTasksStore = create<TasksState>((set) => ({
  tasks: {},
  addTask: (entry) =>
    set((s) => {
      // 按 task_id 唯一去重，不创建重复
      if (s.tasks[entry.task_id]) return s
      return { tasks: { ...s.tasks, [entry.task_id]: { ...entry, lastViewedAt: Date.now() } } }
    }),
  updateTask: (task_id, patch) =>
    set((s) => {
      const cur = s.tasks[task_id]
      if (!cur) return s
      const nextStatus = patch.status ?? cur.status
      // 任务进入终态（done/failed）时刷新 lastViewedAt，开启 30s 隐藏计时
      const terminal = nextStatus === 'done' || nextStatus === 'failed'
      const lastViewedAt = (terminal && cur.status !== nextStatus) ? Date.now() : cur.lastViewedAt
      return { tasks: { ...s.tasks, [task_id]: { ...cur, ...patch, task_id, lastViewedAt } } }
    }),
  removeTask: (task_id) =>
    set((s) => {
      const cur = s.tasks[task_id]
      // 仅允许删除 done/failed
      if (!cur || (cur.status !== 'done' && cur.status !== 'failed')) return s
      const next = { ...s.tasks }
      delete next[task_id]
      return { tasks: next }
    }),
  clearDone: () =>
    set((s) => {
      const next: Record<string, TaskEntry> = {}
      for (const [id, t] of Object.entries(s.tasks)) {
        if (t.status === 'done' || t.status === 'failed') continue
        next[id] = t
      }
      return { tasks: next }
    }),
}))

/** 触达过视图（viewedAt）后若已完成超 30s 则视为可隐藏 */
function isHidden(t: TaskEntry, now: number): boolean {
  if ((t.status === 'done' || t.status === 'failed') && now - t.lastViewedAt > HIDE_AFTER_MS) {
    return true
  }
  return false
}

/** 按 started_at desc 的可见任务数组 */
export function useTasks(): TaskEntry[] {
  const tasks = useTasksStore((s) => s.tasks)
  const now = Date.now()
  return Object.values(tasks)
    .filter((t) => !isHidden(t, now))
    .sort((a, b) => b.started_at - a.started_at)
}

/** 运行中（pending/running）任务数 */
export function useRunningCount(): number {
  const tasks = useTasksStore((s) => s.tasks)
  return Object.values(tasks).filter((t) => t.status === 'pending' || t.status === 'running').length
}
