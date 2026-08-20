# OverviewPage 「今日候选」stat card 修正（改真实数据）

## 背景

sir 反馈：OverviewPage 上「今日候选」stat card 显示 **5**，但 CandidatesPage 候选池只查到 2 天且都是"观察"级别——怀疑 OverviewPage 的数字是虚假的。

经核实：
- OverviewPage 的 5 来自 `dashboard.modules.candidates` = `repo.list_candidates(limit=5)`，`date=None` **不过滤日期**，只取最新 5 条候选（可能是最近几天的，不一定是今天）。
- **真实"今日可建仓"数据已经在 `dashboard.modules.candidate_tradeable.count` 里**（对应当日 `is_tradeable=1` 的数量，且与 CandidatesPage 候选池页同源 `repo.list_candidate_tradeable`）。
- **问题根因**：stat card label 写的是「今日候选」，但数据源是「最新 5 条候选」——**label 与数据源不一致**造成误导。

## 目标

把 stat card 改为「今日可建仓」，数据源切到 `mods.candidate_tradeable.count`，副标注明数据日期，与 CandidatesPage 候选池页保持一致。

## 改动范围

**只动一个文件**：`D:\self\web\src\pages\OverviewPage.tsx`

**改动量**：约 3 行（替换 StatCard + 加 1 个解构变量）

## 改动详情

### 改动 1：解构 `candidate_tradeable` 模块（约 +1 行）

位置：L104 附近 `candidates` 解构后追加

```tsx
const candidates = (mods.candidates as Array<Record<string, unknown>>) ?? []
const tradeable = (mods.candidate_tradeable as { date?: string; count?: number; total?: number }) ?? {}
```

### 改动 2：替换「今日候选」StatCard（约 +3 行）

位置：L122

```tsx
// 改前
<StatCard label="今日候选" value={candidates.length} tone="ok" sub="最新一轮候选池" />

// 改后
<StatCard
  label="今日可建仓"
  value={tradeable.count ?? 0}
  tone={(tradeable.count ?? 0) > 0 ? 'ok' : 'warn'}
  sub={`${tradeable.date ?? '今日'} · 候选池 ${tradeable.total ?? 0} 只`} />
```

## 数据流闭环（关键，让 sir 一眼能核）

| stat card 显示 | 数据源 | 与谁同源 |
|---|---|---|
| 今日可建仓 N | `dashboard.modules.candidate_tradeable.count` | `repo.list_candidate_tradeable(today, limit=50)` 中 `is_tradeable=1` 的数量 |
| 候选池 M 只 | `dashboard.modules.candidate_tradeable.total` | 同上查询的 `len(items)` |
| 数据日期 | `dashboard.modules.candidate_tradeable.date` | `time.strftime("%Y-%m-%d")` 当天 |

sir 切到 CandidatesPage 选同一天，"可建仓"列 Tag 数量 = OverviewPage stat card 数字（完全对得上）。

## 红色约束（必须遵守）

1. **不动后端**（`backend/app/`）：dashboard.py 已经有 `candidate_tradeable` 模块，无需新增/修改。
2. **不动 API 层**（`web/src/api/`）。
3. **不动类型定义**（`web/src/types/`）：`mods` 已经在 L101 cast 为 `any`，不需要改类型。
4. **不引入新依赖**。
5. **不删除 `candidates` 解构**：保留 L104 的 candidates 变量以备未来需要"最近 N 条候选"展示。
6. **不修改其它 stat card**：持仓 / 告警 / 市况卡片零改动。
7. **不修改 stat card 颜色规则**：保持 `(tradeable.count ?? 0) > 0 ? 'ok' : 'warn'` —— count=0 时用 warn 提醒"今日无可建仓"。
8. **不弹 toast、不弹 modal、不跳转**：纯展示。

## 兼容性说明

- `mods.candidate_tradeable` 后端已稳定返回（dashboard.py:45-55），前端只是切数据源，无破坏风险。
- 当后端 `candidate_tradeable` 查询异常时，dashboard.py:54 已经 `except` 返回 `{count: 0, total: 0}`，前端展示会显示 0 / 0 + `今日`（因为 date 是 `time.strftime("%Y-%m-%d")` 在 except 前已赋值）。
- 上一份 `OverviewPage_持仓概览_执行指令.md` 的 holdingQuotes 改动与本指令**互不冲突**：holdingQuotes 是另一个 useQuery，stat card 区域只改这一行。

## 验收清单（8 项，必须全过）

1. [ ] OverviewPage 顶部 stat card 第 1 张卡片 label **从"今日候选"改为"今日可建仓"**。
2. [ ] stat card value 显示的数字 = `dashboard.modules.candidate_tradeable.count`（后端日志可见，或浏览器 DevTools Network 看 `/dashboard` 响应）。
3. [ ] stat card sub 文案显示形如 `2026-08-20 · 候选池 X 只`，日期为今日。
4. [ ] 切到 CandidatesPage 选同日，"可建仓"列 Tag 数量与 stat card value 一致。
5. [ ] 当日 `count=0` 时 stat card 显示 0，tone 变 warn（黄色边框/背景）。
6. [ ] `tsc --noEmit` 0 error。
7. [ ] `pnpm lint`（oxlint）0 error。
8. [ ] 浏览器手动刷新后 stat card 数字稳定不变（dashboard staleTime 30s 内复用缓存）。

## 回滚命令

```bash
git checkout -- D:\self\web\src\pages\OverviewPage.tsx
```

## 关联文件（只读参考，不要改）

- `D:\self\backend\app\services\dashboard.py`（L45-55 `_module_tradeable_view`）
- `D:\self\backend\app\data\repo.py`（`list_candidate_tradeable` 函数）
- `D:\self\web\src\pages\CandidatesPage.tsx`（候选池页，与 stat card 共用数据源）

## 改动总览

| 改动点 | 位置 | 行数 | 备注 |
|---|---|---|---|
| 解构 candidate_tradeable | L104 附近 | +1 | 与 candidates 并列解构 |
| 替换「今日候选」StatCard | L122 | +4（替换 +1）| label 改为"今日可建仓" + sub 显示日期与候选池总数 |
| **合计** | — | **+5** | **仅 OverviewPage.tsx 一个文件** |
