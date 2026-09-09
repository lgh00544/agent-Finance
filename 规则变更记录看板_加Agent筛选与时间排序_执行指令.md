# 规则变更记录看板·加 Agent 筛选 + 时间排序_执行指令

## 目标
`D:\self\web\src\pages\RuleChangesPage.tsx` 顶部筛选行 line 272-278 已有"搜索 + Agent 多选(基于 `agentOptions` 已是 target_agent 动态) + 类型多选"——等等，**当前 line 275 那个 Select 实际就是 target_agent 多选**（`agentOptions` 来源 `rowsView.map(r => r.target_agent)`）。

但 sir 实测说"再加一个目标 agent 筛选"——可能他没注意到已有，或希望它更显眼/改个更明确的 placeholder。

补充：**再加时间排序切换**（升序/降序）——明确缺失。

## 改动点
| 位置 | 改什么 |
|---|---|
| line 275 Agent Select | placeholder 改为"目标 Agent（多选）"，与"类型"对仗更明确 |
| line 156 附近 state | 新增 `const [sortOrder, setSortOrder] = useState<'desc' \| 'asc'>('desc')` |
| line 178 附近 filter 之后 | `rowsView` 输出前 `.sort((a,b) => String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')) * (sortOrder === 'desc' ? 1 : -1))` |
| line 276 类型 Select 之后 | 加 Radio.Group 切换 `sortOrder`：`时间 ↓` / `时间 ↑`（默认 ↓） |

## 红线
1. 不动看板、卡片、拖拽、流转逻辑、Drawer、各 modal 确认
2. 时间排序只影响**当前页已加载数据**显示顺序；不调后端、不动 queryFn
3. 卡片与 Drawer 内"时间"显示文案不动（line 110 卡片 line 54 Drawer 已有）
4. 改动 ≤ 30 行，不新增文件

## 验收
1. 顶部筛选行可见：搜索 / 目标 Agent（多选）/ 类型（多选）/ 时间 ↓↑ 切换
2. 时间 ↓（默认）：最新规则在「通过 / 驳回重审 / 人工审 / 驱动待审」各列顶部
3. 切到 ↑：旧规则排到顶部
4. 拖拽跨列、Drawer 打开、重新审核/回滚/驳回 modal 不受影响
