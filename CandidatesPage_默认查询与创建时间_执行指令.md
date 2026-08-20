# CandidatesPage 优化二：默认查今天 + 列表展示「创建时间」

## 背景

sir 在交付了工单 10（ProfilePage 漏页）和工单 9（ReviewsPage 大补）之后，又针对 CandidatesPage 提了两点优化：

1. **页面默认查询今天的候选池**——目前进入页面时 `date` 是 undefined，虽然 Select 的 `value={date ?? dates?.[0]}` 表面看是 fallback 到 `dates[0]`，但 `dates` 是异步加载的，进入瞬间 Select 会出现"未选中"空态，且 `useQuery` 的 `enabled` 是 `!!date || !!dates?.length`——第一帧 `date` 为 undefined 且 `dates` 还没回来时，列表会短暂空白、并可能在用户视觉上感觉"没有默认查今天"。
2. **列表缺「创建时间」列**——Candidate 类型只有 `trade_date` 没有 `create_time`，但 trade_date 在候选池场景下本质就是"该候选被创建 / 纳入候选池的日期"（候选池每日生成），用户视角就是"创建时间"。

本工单不改动后端、不改动 API 层、不改动类型定义，仅前端 CandidatesPage.tsx 单文件改造，约 8 行。

## 来源文件（已读）

- `D:\self\web\src\pages\CandidatesPage.tsx`（L482-666 为主）
  - L486：`const [date, setDate] = useState<string>()` —— date 默认 undefined
  - L490：`useQuery({ queryKey: ['candidate-dates'], queryFn: () => candidateDates(30) })`
  - L491-495：candidates 查询 enabled: `!!date || !!dates?.length`
  - L557-563：日期 Select `value={date ?? dates?.[0]}`、`onChange={setDate}`
  - L609-660：Table 列定义（无"创建时间"列）
- `D:\self\web\src\api\candidates.ts:13`：`candidateDates(limit=30): Promise<string[]>` 已能拿到日期列表
- `D:\self\web\src\types\index.ts:43-52`：`Candidate` 字段含 `trade_date: string`，无 `create_time`

## 改动 1 个文件：`web\src\pages\CandidatesPage.tsx`

### 改动 1 — 默认查今天（约 4 行）

在 `CandidatesPage` 组件内部、`useQuery` 之前新增一个 `useEffect`，**当 dates 加载完成且当前未手动选过日期时，自动把 date 设置为 dates[0]**：

```tsx
// 默认查询当天的候选池（dates[0] 是最新一天）
useEffect(() => {
  if (!date && dates && dates.length > 0) {
    setDate(dates[0])
  }
}, [date, dates])
```

为什么放 useEffect 而不是直接 `const [date, setDate] = useState(() => dates?.[0])`：
- `dates` 是异步 query 数据，组件 mount 时 `dates` 还是 undefined，useState 初始化拿不到；
- 不能用 `useMemo` 派生——派生值不能 setState，必须走 effect；
- 已经验证过工单 10 ProfilePage 里同类"异步数据回填到 controlled state"的写法（用 useEffect 而不是 render 阶段直接调 setState，避免死循环）。

### 改动 2 — Table 增加「创建时间」列（约 4 行）

在 columns 数组里，**「排名/股票」列之后、「评级」列之前**，插入一个新列：

```tsx
{
  title: '创建时间', key: 'trade_date', width: 110,
  render: (_: unknown, r: Candidate) => (
    <Text type="secondary" style={{ fontSize: 12 }}>{r.trade_date || '—'}</Text>
  ),
},
```

**为什么直接展示 trade_date**：
- 后端候选池每日生成，`r.trade_date` 就是该候选被纳入候选池的日期；
- 候选池无独立的"创建时间"字段，不引入额外 API 调用；
- 旧版 Streamlit 也是用 trade_date 当日期展示（口径一致）。

## 红线（不可破）

- **不改动后端**：本工单不动 `backend/app/**` 任何文件。
- **不改动 API 层**：本工单不动 `web/src/api/**` 任何文件。
- **不改动类型定义**：本工单不动 `web/src/types/**` 任何文件。Candidate 没有 create_time 字段就展示 trade_date，不新增字段、不加 cast 绕过类型。
- **不改 useQuery enabled**：仍是 `!!date || !!dates?.length`，本次只是补上"dates 加载完自动回填 date"的逻辑，让 enabled 的第一个分支能尽快为真。
- **不改 useQuery key**：仍是 `['candidates', date]`、`['candidate-tradeable', date]`、`['candidate-conc', date]`，回填 date 后会自动 refetch。
- **不引入新依赖**：用现有 antd 的 `Typography.Text`，不引入 dayjs/moment。
- **不改 LABEL_COLORS / TIER_MAP / QUICK_QUESTIONS / SCOPE_LABELS 常量**：与工单 11（AI 判定标签）配套，不重复定义。
- **回滚**：若改动后页面出现异常（死循环 / 空白 / 报错），执行 `git checkout -- web/src/pages/CandidatesPage.tsx` 回滚本工单。

## 验收清单（必须全过）

1. `cd D:\self\web && npx tsc --noEmit` 通过，0 error。
2. `cd D:\self\web && npx oxlint src/pages/CandidatesPage.tsx` 通过，0 error / 0 warn。
3. 浏览器进入 /candidates，**第一次进入**（清除 localStorage / 关闭再开）页面应自动展示当天候选，**不出现"未选中日期"的空态**。
4. 日期 Select 默认显示的是 `dates[0]`（最新日期），手动切换日期后 Select 与列表同步刷新。
5. Table 多出一列「创建时间」，值为 `r.trade_date`，列宽 110px（不挤压「排名/股票」280px 列）。
6. 列表渲染顺序：「排名/股票 | 创建时间 | 评级 | 理由 | 留痕」（理由列变 ellipsis 不变）。
7. 后端接口未新增：`/api/candidates`、`/api/candidates/dates`、`/api/candidates/tradeable`、`/api/candidate/concentration` 调用参数不变。
8. 联动工单 11（AI 判定标签）：列表行「排名/股票」列仍展示可建仓 Tag，"创建时间"列独立展示 trade_date，**两列不互相挤占宽度**。

## 交付要求

执行完成后回报：
- 修改的文件路径 + 改动行号区间
- tsc / oxlint 输出（截图或文本）
- 浏览器实测：进入 /candidates 截图（展示默认日期、列表行含"创建时间"列）
- 验收清单 8 项逐条 ✅/❌ + 备注

未通过任意一项不算完成，继续修直到全过。
