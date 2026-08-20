# TaskDrawer 升级：取消按钮 + 失败强化 + 伪进度 · Claude Code 执行指令

> **作者**：Lark
> **日期**：2026-08-19
> **改动范围**：仅 2 个前端文件，零后端改动，零 store 结构变更

---

## 1. 背景

TaskDrawer 是工单 6 产物（`D:\self\web\src\components\layout\TaskDrawer.tsx`，215 行），目前有 3 个体验缺陷：

1. **运行中任务无法取消**——用户误提交后只能干等到 timeout
2. **失败任务错误展示弱**——`<div>` 灰色小字截断 200 字，不够醒目
3. **运行中无进度反馈**——用户不知道执行到哪了

后端 `task_queue.cancel(tid)` 早已实现并测试过（`routes.py:250-257`，`task_queue.py:160`），`pending` / `running` 可取消、立即释放队列，无需动后端。

---

## 2. 改动清单

| # | 文件 | 改动 |
|---|---|---|
| 1 | `D:\self\web\src\api\tasks.ts` | 新增 `cancelTask(tid)` 函数 |
| 2 | `D:\self\web\src\components\layout\TaskDrawer.tsx` | 取消按钮 + 错误 Alert 强化 + 伪进度 Progress |

**严格红线**：
- 零后端改动（Python / SQL / 配置零改）
- 零 store 结构变更（`tasksStore.ts` 零改；只调既有 `updateTask`）
- 零新依赖（antd 6.6.1 自带 `Progress` / `Alert` / `App.useApp`，不再 install）
- 零 UI 库替换（仍走 antd + zustand + react-query 现有栈）

---

## 3. 详细规格

### 3.1 `api/tasks.ts` 追加（18 行 → 23 行）

在 `retryTask` 之后追加：

```ts
/** POST /api/tasks/{id}/cancel —— 后端已实现（routes.py:250-257），仅包装 */
export const cancelTask = (tid: string): Promise<{ task_id: string; status: string; canceled: boolean }> =>
  post(`/tasks/${tid}/cancel`)
```

**对照后端响应**（`routes.py:257` 已确认返回 `{"task_id": str, "status": "failed", "canceled": True}`）——类型一一对应。

### 3.2 `TaskDrawer.tsx` 改造

#### 改动 ①：顶部 import 修改

将 `Alert`、`Progress` **合并到现有 antd import 块**（原 L2-13 的 `App, Badge, Button, Card, Drawer, Empty, Modal, Space, Tag, Typography`），不要单独写第二行 `import { Alert, Progress } from 'antd'`（否则 eslint duplicate-import 报错）：

```ts
import {
  Alert,
  App,
  Badge,
  Button,
  Card,
  Drawer,
  Empty,
  Modal,
  Progress,
  Space,
  Tag,
  Typography,
} from 'antd'
```

并把 `cancelTask` 加到 `import { retryTask, taskDetail } from '@/api/tasks'` 这一行：

```ts
import { cancelTask, retryTask, taskDetail } from '@/api/tasks'
```

#### 改动 ②：添加 per-kind 预估总时长表（紧贴 `KIND_LABELS` 之后）

```ts
/** 任务 kind → 预估总时长（秒）。用于伪进度展示，不假装精确。 */
const KIND_ESTIMATED_SECONDS: Record<string, number> = {
  daily_pipeline: 180,
  batch_ask: 120,
  position: 45,
  score: 30,
  sell_decision: 30,
  monitor_all: 60,
  portfolio_sentinel: 90,
  market_intel: 45,
}

/** 伪进度：0~95，到上限卡死，不到 done 永远不满。 */
function fakeProgressPct(kind: string | undefined, elapsedMs: number): number {
  const totalSec = (kind && KIND_ESTIMATED_SECONDS[kind]) || 60
  const raw = Math.min(1, elapsedMs / 1000 / totalSec)
  // 上限 95%：done 之前永远不到 100%，防止"看着快完了"
  return Math.round(raw * 100 * 0.95)
}
```

#### 改动 ③：组件内新增 doCancel 处理器（紧贴 `doRemove` 之后）

```ts
const doCancel = (entry: TaskEntry) => {
  modal.confirm({
    title: '取消任务',
    content: `确认取消【${kindLabel(entry.kind)} #${shortId(entry.task_id)}】？取消后该任务标记为失败。`,
    okText: '确认取消',
    cancelText: '继续执行',
    okButtonProps: { danger: true },
    onOk: () =>
      cancelTask(entry.task_id)
        .then((r) => {
          // 后端 cancel 后把 status 置 failed + canceled=true
          // store 走 updateTask 走"正常失败"流程，触发既有 isHidden(30s) 与重试按钮
          updateTask(r.task_id, {
            status: 'failed',
            error: '已手动取消',
            finished_at: Date.now(),
          })
          message.success(`已取消：${kindLabel(entry.kind)} #${shortId(r.task_id)}`)
        })
        .catch((e: Error) => {
          // 后端 400 = 任务已终态（done/failed），cancel 不可用
          // toast 提示 + 立即拉一次真实状态刷新 store，消除"运行中"假象
          message.error(`取消失败：${e.message}`)
          taskDetail(entry.task_id)
            .then((t) =>
              updateTask(t.task_id, {
                status: t.status,
                error: t.error ?? null,
                result: t.result,
                finished_at: (t.status === 'done' || t.status === 'failed') ? Date.now() : undefined,
              }),
            )
            .catch(() => {})
        }),
  })
}
```

**为什么用 `updateTask(status=failed)` 而不是新增 store action**：
- store 已有 `updateTask(task_id, patch: Partial<TaskEntry>)`，参数与 cancel 后端响应完全兼容
- 走失败态后，`failed` 标签自动出现、`重试`按钮自动出现、`移除`按钮自动出现、30s 后 isHidden 自动隐藏——**所有既有终态 UI 逻辑零改动**
- 不引入新状态、不破坏 TaskStatus 类型（'pending'|'running'|'done'|'failed'）

#### 改动 ④：失败展示从 `<div>` 换 `<Alert>`（替换原 line 158-162 整段）

**原代码**（删除）：
```tsx
{t.error ? (
  <div style={{ marginTop: 8, color: 'var(--err)', fontSize: 12 }}>
    {t.error.length > 200 ? `${t.error.slice(0, 200)}…` : t.error}
  </div>
) : null}
```

**替换为**：
```tsx
{t.error ? (
  <Alert
    type="error"
    showIcon
    message={t.status === 'failed' && t.error === '已手动取消' ? '已手动取消' : '执行失败'}
    description={
      <div style={{ maxHeight: 120, overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
        {t.error}
      </div>
    }
    style={{ marginTop: 8 }}
  />
) : null}
```

**对照改动点**：
- 灰色小字 → 红色 `<Alert type="error">`（antd 自带警示图标 + 浅红底，醒目）
- 200 字截断 → 完整展示，`maxHeight: 120` + `overflowY: auto` + `whiteSpace: pre-wrap`（保留换行 + 滚动）
- 取消导致的失败单独标"已手动取消"，与"执行失败"区分（避免误判）

#### 改动 ⑤：取消按钮（紧贴「复制 ID」按钮之后）

**原代码**（在 doRetry 按钮前后，对照实际 line 145-148）：
```tsx
<Button size="small" onClick={() => setDetailEntry(t)}>查看详情</Button>
<Button size="small" onClick={() => copyId(t.task_id)}>复制 ID</Button>
{t.status === 'failed' ? <Button size="small" danger onClick={() => doRetry(t)}>重试</Button> : null}
```

**改为**：
```tsx
<Button size="small" onClick={() => setDetailEntry(t)}>查看详情</Button>
<Button size="small" onClick={() => copyId(t.task_id)}>复制 ID</Button>
{t.status === 'failed' ? <Button size="small" danger onClick={() => doRetry(t)}>重试</Button> : null}
{(t.status === 'pending' || t.status === 'running') ?
  <Button size="small" danger onClick={() => doCancel(t)}>取消</Button> : null}
```

**说明**：
- 取消按钮仅在 `pending` / `running` 状态出现
- `danger` 红框（与重试按钮视觉一致，用户容易识别为"破坏性操作"）
- 点击 → `modal.confirm` 二次确认 → 调 `cancelTask` → `updateTask(status=failed)` 走终态

#### 改动 ⑥：伪进度 Progress（紧贴 `<Space>` 按钮行之后，错误 Alert 之前）

**新增 JSX**（对照原代码 line 134-156 在 `</Space>` 与错误展示之间的位置）：

```tsx
{(t.status === 'pending' || t.status === 'running') ? (
  <Progress
    percent={fakeProgressPct(t.kind, elapsed)}
    size="small"
    showInfo={false}
    strokeColor="var(--primary)"
    style={{ marginTop: 6 }}
  />
) : null}
```

**为什么用 `elapsed`（line 130 已算好的已耗时）**：
- 已有变量 `elapsed` 表示 `now - t.started_at`，单位毫秒
- `fakeProgressPct` 接受 ms，与既有计算口径一致
- 复用 `now` 每秒刷新（line 122 `setInterval`），进度条自然每 1s 推进

---

## 4. 验收清单

### 4.1 功能验收（手动跑）

- [ ] `api/tasks.ts` 编译通过，`cancelTask` 在 IDE 自动补全里出现
- [ ] 提交一个 `daily_pipeline` 任务（Dashboard 触发）
- [ ] TaskDrawer 中"运行中"卡片出现「取消」红色按钮
- [ ] 点击取消 → 二次确认弹窗 → 确认 → toast 提示「已取消」
- [ ] 卡片 1s 内状态变为「失败」+ 标签「失败」+ 出现「重试」按钮 + 红色 Alert 显示「已手动取消」
- [ ] 任务卡片底部出现 Progress 进度条（视觉推进 < 95%）
- [ ] 任务执行 2s 内完成 → 进度条归零 + 「已完成」标签
- [ ] 后端 cancel 返回 400（任务已终态不可取消）→ catch toast 提示「取消失败」+ taskDetail 刷新真实状态，卡片不再卡在"运行中"
- [ ] 失败的 daily_pipeline 任务错误文本（如 stack trace 多行）→ 红色 Alert 完整展示 + 滚动而非截断

### 4.2 类型/编译验收

- [ ] `tsc --noEmit` 0 error
- [ ] `eslint src/components/layout/TaskDrawer.tsx src/api/tasks.ts` 0 error
- [ ] antd 组件 import 全部命中现有 6.6.1 版本（不引入新依赖）
- [ ] `TaskEntry` / `TaskStatus` 类型零改

### 4.3 回归验收

- [ ] 既有 `useTaskSubmit` 提交流程不受影响（不破坏 addTask 调用方）
- [ ] 既有 `clearDone` / `removeTask` / `doRetry` 行为零改
- [ ] 既有"已完成后 30s 自动隐藏"逻辑（isHidden）零改

---

## 5. 红线（必须遵守）

| 红线 | 验证方式 |
|---|---|
| **不动后端** | `backend/` 路径下零文件改动 |
| **不新增 store 字段** | `tasksStore.ts` 零改动 |
| **不修改 TaskStatus 类型** | 仍为 `'pending' \| 'running' \| 'done' \| 'failed'` |
| **不引入新依赖** | `package.json` 零改动；Progress/Alert/App 来自 antd 6.6.1 |
| **不替换 UI 库** | 仍走 antd + zustand + react-query |
| **取消走 updateTask，不新增 action** | 走既有 `updateTask(task_id, patch)` 走"失败态"自然终态 |
| **进度上限 95%** | `Math.round(raw * 100 * 0.95)` 强卡，不到 100% |
| **取消后任务可重试** | 因状态变 failed → 「重试」按钮自然出现，逻辑闭环 |

---

## 6. 回滚方案

| 失败点 | 回滚 |
|---|---|
| 取消按钮 / 二次确认交互反人类 | `git checkout HEAD -- web/src/components/layout/TaskDrawer.tsx web/src/api/tasks.ts` |
| Alert 样式与暗色主题冲突 | 改 `<Alert>` 的 `style.background` 调暗色，或退回原 `<div>` |
| 伪进度被误读为真实进度 | 改 `Math.round(raw * 100 * 0.95)` 为 `* 0.7`（更明显是"估算"） |
| 整体执行失败 | 还原 2 文件，store 不改所以无连锁影响 |

---

## 7. 实施顺序（建议 4 步）

1. **Step 1**（API 层）：`api/tasks.ts` 末尾追加 `cancelTask` 5 行
2. **Step 2**（数据/处理器）：`TaskDrawer.tsx` 顶部 import + `KIND_ESTIMATED_SECONDS` 表 + `fakeProgressPct` + `doCancel`
3. **Step 3**（UI 改造）：失败 `<div>` → `<Alert>`、取消按钮、Progress 三处 JSX
4. **Step 4**（验收）：tsc + eslint + 手动跑 §4.1 验收清单

---

## 8. 预期效果

| 维度 | 现状 | 预期 |
|---|---|---|
| 运行中任务可中断 | ❌ 干等 timeout | ✅ 1 次点击 + 确认 → 立即终态 |
| 失败任务错误可见性 | 灰色小字截断 | 红色 Alert 完整滚动 |
| 运行中任务视觉反馈 | 仅有 Spinner 图标 | Spinner + 进度条（伪） |
| 取消后状态闭环 | — | 自动出「重试」按钮（沿用 failed 态） |
| 后端 / store 改动 | — | **零** |

---

## 9. 实测前置证据

| 引用点 | 文件:行 | 已验证 |
|---|---|---|
| `POST /api/tasks/{tid}/cancel` 端点 | `backend/app/api/routes.py:250-257` | ✅ |
| 后端返回 `{task_id, status:"failed", canceled:true}` | routes.py:257 | ✅ |
| `task_queue.cancel(tid)` 实现 | `backend/app/services/task_queue.py:160` | ✅ |
| `updateTask(task_id, patch: Partial<TaskEntry>)` 签名 | `web/src/store/tasksStore.ts:24` | ✅ |
| `TaskEntry` 字段：status/started_at/finished_at/error 都有 | tasksStore.ts:9-19 | ✅ |
| `TaskStatus = 'pending' \| 'running' \| 'done' \| 'failed'` | tasksStore.ts:7 | ✅ |
| antd 版本含 Progress + Alert | `web/package.json:15`（6.6.1） | ✅ |
| `App.useApp()` 的 modal/message 已用 | TaskDrawer.tsx:82 | ✅（可复用） |
| `elapsed` 变量已算好（`now - t.started_at`） | TaskDrawer.tsx:130 | ✅（可直接喂 fakeProgressPct） |
| `KIND_LABELS` 已有 8 个 kind | TaskDrawer.tsx:23-32 | ✅（per-kind 表复用同一批 kind 字符串） |
