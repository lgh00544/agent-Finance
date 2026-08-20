# React 候选池页：默认仅显示最近一次生成 + AI 生成时间列 · Claude Code 执行指令

> **作者**：Lark
> **日期**：2026-08-20
> **改动范围**：仅 1 个 React 前端文件
> **依据**：sir 实测截图——列表显示多日累计 39 条；sir 期望默认只展示最近一次（按 trade_date 选最近一天），且每行展示「AI 生成时间（精确到秒）」

---

## 1. 背景与根因

### 1.1 数据真相（已实测）

```text
GET /api/candidates                      → 39 条（多日累计：8/20+8/19+8/18+...）
GET /api/candidates?date=2026-08-20      →  2 条（仅 8/20）
GET /api/candidates/dates                → ['2026-08-20', '2026-08-19', ...]  # 9 个去重日期
```

| trade_date | count | min_at | max_at | 是否同一批 |
|---|---|---|---|---|
| 2026-08-20 | 2 | 09:54:51.234 | 09:54:51.237 | ✅ 是（毫秒差） |
| 2026-08-19 | 2 | 18:13:36.116 | 18:13:36.120 | ✅ 是 |
| 2026-08-12 | 8 | 16:29:18.626 | 16:29:18.646 | ✅ 是 |

**结论**：同 `trade_date` 下所有候选**共用同一批生成时间**（毫秒级差），所以"最近一次生成结果" = `trade_date` 最大的那一天全部候选。后端返回结构已带 `created_at`（`repo.list_candidates` line 953），前端没用上。

### 1.2 React 端核心 bug

`web/src/pages/CandidatesPage.tsx:480-494`：
```tsx
const [date, setDate] = useState<string>()              // 始终 undefined
const { data: dates } = useQuery(...)                   // 异步加载
const { data: rows } = useQuery({
  queryKey: ['candidates', date],                        // 首次 = ['candidates', undefined]
  queryFn: () => candidates(date),                       // 首次 = candidates(undefined) → 39 条
  enabled: !!date || !!dates?.length,                    // dates 加载完后立刻触发 → 拉全表
})
```

`<Select value={date ?? dates?.[0]}>` 显示是 `'2026-08-20'`，但 **`date` state 始终是 undefined**——Select 是非受控显示，date state 没真正更新。`candidates()` 调用永远传 undefined。

### 1.3 缺失的展示

Table 列：`排名/股票 / 评级 / 理由 / 留痕`（4 列）——**没有「AI 生成时间」列**。`r.created_at` 字段已存在但未渲染。

---

## 2. 修复目标

1. **默认仅显示最近一次生成结果**：进入页面时自动把 `dates?.[0]`（最大 trade_date）写入 `date` state，按日期查（→ 8/20 的 2 条）
2. **Table 新增「AI 生成时间（精确到秒）」列**：显示 `YYYY-MM-DD HH:MM:SS`
3. **同日行展示一致**：同 trade_date 下所有行 `created_at` 在毫秒级，UI 上统一显示 "HH:MM:SS"（去掉日期，因为日期已被顶部 Select 体现）
4. **不破坏既有**：日期切换 / 手动触发 / 筛选 / 展开行 / 批量验证 / 留痕 modal 零回归

---

## 3. 红线（强制遵守）

| 红线 | 验证 |
|---|---|
| **只改 1 个文件**：`web/src/pages/CandidatesPage.tsx` | `git diff --name-only HEAD` 只列此文件 |
| **不改后端 / API / 选股逻辑 / 交易规则** | 后端 `repo.py::list_candidates` 零改动；API 路由零改动 |
| **不引入新依赖** | 复用 antd `Typography.Text` 即可，秒级格式化用 `dayjs`（项目已有） |
| **不破坏既有 4 列** | `排名/股票 / 评级 / 理由 / 留痕` 保留位置和 width，新增列插在「评级」和「理由」之间 |
| **改动可回滚** | 改动前 `cp CandidatesPage.tsx CandidatesPage.tsx.bak.latest_run` |

---

## 4. 详细规格

### 4.1 顶部 import 校验（已存在的复用）

`CandidatesPage.tsx` 顶部 `import` 区段确认含：
- `dayjs` —— 通常在 `@/utils` 或 `dayjs` 已有引入；若没有则 `import dayjs from 'dayjs'`
- `Typography` —— 已有

**不要**新增任何 import（dayjs 若未引入再加）。

### 4.2 修复 bug：dates 加载完自动 sync 到 date state

**位置**：`CandidatesPage.tsx:480-489`（在 `const { data: dates } = useQuery(...)` 之后立即加）

```tsx
// —— 关键修复：dates 加载完后把最近日期写入 date state，
// 否则 candidates() 会传 undefined → 拉全表 39 条。
// 同样修复 candidates/candidate-tradeable/candidate-conc 三个 query 的 enabled 链路。
useEffect(() => {
  if (!date && dates && dates.length > 0) {
    setDate(dates[0])
  }
}, [dates, date])
```

**为什么用 useEffect 而不是在 queryFn 里**：
- 不能在 queryFn 里 `setDate`（会触发无限循环）
- 不能改 Select 的 `value` 控制——它是受控的，需要 state 真正更新
- 这是 React Query + 受控 Select 的标准模式

### 4.3 改 enable 链路（让 date 触发而不是 dates）

**位置**：`CandidatesPage.tsx:485-494`

**原**：
```tsx
const { data: dates } = useQuery({ queryKey: ['candidate-dates'], queryFn: () => candidateDates(30) })
const { data: rows } = useQuery({
  queryKey: ['candidates', date],
  queryFn: () => candidates(date),
  enabled: !!date || !!dates?.length,
})
const { data: tradeable } = useQuery({
  queryKey: ['candidate-tradeable', date],
  queryFn: () => candidateTradeable(date),
  enabled: !!date || !!dates?.length,
})
const { data: conc } = useQuery({
  queryKey: ['candidate-conc', date],
  queryFn: () => candidateConcentration(date),
  enabled: !!date || !!dates?.length,
})
```

**改为**：
```tsx
const { data: dates } = useQuery({ queryKey: ['candidate-dates'], queryFn: () => candidateDates(30) })
const { data: rows } = useQuery({
  queryKey: ['candidates', date],
  queryFn: () => candidates(date ?? ''),        // 已 sync 后 date 必有值；空串兜底
  enabled: !!date,                              // 强依赖 date（4.2 useEffect 保证 date 必有值）
})
const { data: tradeable } = useQuery({
  queryKey: ['candidate-tradeable', date],
  queryFn: () => candidateTradeable(date ?? ''),
  enabled: !!date,
})
const { data: conc } = useQuery({
  queryKey: ['candidate-conc', date],
  queryFn: () => candidateConcentration(date ?? ''),
  enabled: !!date,
})
```

**注意**：保留原 tv-stats-t5 queryKey 不变（这是无日期的全局统计）。

### 4.4 Table 新增「AI 生成时间」列

**位置**：`CandidatesPage.tsx:609-639`（Table columns 数组）

**插入位置**：在 `评级` 列（line 619-625）**之后**、`理由` 列（line 626-629）**之前**，插入新列：

```tsx
{
  title: 'AI 生成时间',
  key: 'generated_at',
  width: 170,
  render: (_: unknown, r: Candidate) => {
    // r.created_at 形如 '2026-08-20 09:54:51.237753'
    // 截到秒：去掉微秒 + 用空格分隔 date / time 让两列更易扫读
    const raw = String(r.created_at ?? '')
    if (!raw) return <Text type="secondary">—</Text>
    const [d, tFull] = raw.split(' ')
    const t = (tFull ?? '').split('.')[0] ?? ''  // 取 HH:MM:SS，去掉 .μs
    return (
      <div style={{ fontSize: 12, lineHeight: 1.4 }}>
        <div>{d}</div>
        <div style={{ color: 'var(--color-text-secondary, #888)' }}>{t}</div>
      </div>
    )
  },
},
```

**视觉说明**：
- 日期 `2026-08-20` 在上、时间 `09:54:51` 在下，时间用 secondary 灰色弱化——日期信息已在顶部 Select 体现，时间才是新增强信息
- 适配 Cell width=170 紧凑两行

### 4.5 文案微调：EmptyState / StatCard 文案

**位置**：`CandidatesPage.tsx:601` EmptyState

**原**：
```tsx
<EmptyState text="当日无候选。可点击上方「手动触发每日挖掘」重新生成。" icon="🔍" />
```

**改为**：
```tsx
<EmptyState text="该交易日暂无候选。可点击上方「手动触发每日挖掘」重新生成。" icon="🔍" />
```

（"当日" → "该交易日"，更准确：可能切到历史日期也无候选。）

**位置**：`CandidatesPage.tsx:569-570` StatCard sub

**原**：
```tsx
<StatCard label="可自动生成建仓计划" value={Number(tradeable?.plan_candidate_count ?? 0)}
  tone="info" sub="评级 A/B 且暂无方案" />
```

**保持不变**（无相关 bug）。

---

## 5. 验收清单

### 5.1 功能验收（手动）

- [ ] `npm run build` 0 error
- [ ] `npx tsc --noEmit -p web/tsconfig.json` 0 error
- [ ] 重启 React 前端 → 打开候选池页
- [ ] Network 面板：`GET /api/candidates?date=2026-08-20` 返回 **2 条**（不是 39 条）
- [ ] Table 仅显示 8/20 的 2 行候选，**没有 8/19、8/18、8/17 等历史日期的候选**
- [ ] Table 新增「AI 生成时间」列，显示 `2026-08-20` + `09:54:51`（秒级）
- [ ] 切到「选择日期」下拉 8/19 → Table 显示 2 行，AI 生成时间为 18:13:36
- [ ] 切到 8/12 → Table 显示 8 行，时间统一 16:29:18
- [ ] 切回 8/20 → 仍是 2 行
- [ ] 顶部 Select 默认值自动是 `2026-08-20`（不再需要手动点选）
- [ ] 筛选 Segmented「可建仓 A+B / 观察 C」仍按 trade_date 内的 rows 过滤
- [ ] 手动触发每日挖掘按钮：点击后候选数变化时 Table 刷新
- [ ] 展开行 / 批量验证面板 / 留痕 Modal 零回归

### 5.2 静态验收

- [ ] `grep -nE "AI 生成时间|generated_at" web/src/pages/CandidatesPage.tsx | wc -l` ≥ 3
- [ ] `grep -nE "if \(!date && dates" web/src/pages/CandidatesPage.tsx | wc -l` ≥ 1
- [ ] `git diff --name-only HEAD` 仅出现 `web/src/pages/CandidatesPage.tsx`
- [ ] 确认 backend `repo.list_candidates` / API 路由**零改动**：`git diff HEAD -- backend/`

---

## 6. 回滚

```bash
cp web/src/pages/CandidatesPage.tsx web/src/pages/CandidatesPage.tsx.bak.latest_run

# 回滚：
mv web/src/pages/CandidatesPage.tsx.bak.latest_run web/src/pages/CandidatesPage.tsx
```
