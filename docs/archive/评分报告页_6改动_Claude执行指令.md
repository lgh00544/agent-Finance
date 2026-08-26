# 评分报告页 · 6 改动一次性执行指令（Claude Code）

## 〇 元信息
执行者：Claude Code。决策人：sir。范围：仅 `web/src/pages/ScoresPage.tsx` 单文件。原则：后端 0 改动、复用已有 API（scores/candidates/agentSuggestions）、不引新库、改动 ≤ 150 行。

## 一 目标
让「评分报告」页从「50+ 条平铺看不懂」变成「3 摘要 + 6 因子色条 + Tab 分层」,sir 30 秒内完成「今日值得看的票」筛选。

| # | 改动 | 数据源 |
|---|---|---|
| 1 | 顶部 3 摘要卡（今日 A 级 / B 级 / 已被采纳）| `scores()` + `agentSuggestions()` |
| 2 | 列加 6 因子色条（动/催/估/主/资/基 6 格）| `detail.factors` |
| 3 | 默认 sort 综合分降序,采纳优先 | 已有 |
| 4 | Tab 拆分：今日 / 历史 A 级（≥70）/ 已采纳 | 已有 |
| 5 | `in_candidate` 列（与候选池交叉）| `candidates()` |
| 6 | `risk_list` 计数 + 红点 | `risk_list.length` |

## 二 架构约束
- **单文件**：`web/src/pages/ScoresPage.tsx` —— 不动 types / api / 后端
- **复用已有**：`scores()` / `candidates()` / `agentSuggestions()` / `StockScoreInfo` / `ConfidenceBar` —— 不新增 api 函数
- **不引新库**：仅用 antd 已有 `Card` / `Tabs` / `Tag` / `Badge` / `Tooltip` / `Statistic`
- **不动 detail 结构**：6 因子从 `detail.factors` 读，缺时显示「—」

## 三 规则

### 3.1 顶部摘要卡（行 1）
- **位置**：`useQuery` 之后,`Table` 之前,3 个 `<Card>` 横排
- **卡 1：今日 A 级** = `allRows.filter(r => r.trade_date === dates?.[0] && r.grade === 'A').length`
- **卡 2：今日 B 级** = 同上 grade === 'B'
- **卡 3：已被采纳** = `agentSuggestions` 中 `suggest_status === 'approved'/'adopted'` 且 `target_agent === 'position'` 的 stock_code 集合 与今日评分交集
- 数字用 `<Statistic>` 红色 A / 橙色 B / 绿色采纳

### 3.2 6 因子色条列
- 列宽 `width: 220`,固定
- 标题：'6 因子'
- 渲染：从 `detail.factors` 取 6 项,按固定顺序「动量/催化/估值/主线契合/资金面/基本面质量」
- **每因子一格（6 格横排）**：
  - 背景色：score ≥7 绿（var(--up)）/ 4-6 黄（var(--warn)）/ <4 灰（var(--mute)）/ 缺 — 灰
  - 数字：`<Text style={{fontSize:11}}>{score ?? '—'}</Text>`
  - `Tooltip title={factor.reason ?? '（无依据）'}` —— 鼠标悬停看 LLM 写的依据
- 因子顺序在 `detail.factors` 中可能乱序 —— 用 `find(f => f.factor === '动量')` 等 6 次定位,**禁止** index 假设

### 3.3 默认排序
- `Table.defaultSortOrder` 综合分降序
- 二级排序：采纳优先（agentSuggestions 集合 membership）

### 3.4 Tab 拆分
- `<Tabs>` 三个 Tab：
  - **今日** = `r.trade_date === dates?.[0]`
  - **历史 A 级** = `r.score >= 70`
  - **已采纳** = `r.stock_code` ∈ adopted set
- 每个 Tab 独立显示摘要卡对应数字

### 3.5 `in_candidate` 列
- `width: 80`,固定
- 渲染：调用 `candidates()`(已有 api) 拿候选池 stock_code 集合 → 命中显示 `<Tag color="blue">在池</Tag>`,未命中 `—`
- 注意：`candidates()` 默认拉最新一天,可在 useQuery 加 `date: dates?.[0]` 限定同一天

### 3.6 `risk_list` 计数
- 列宽 `width: 80`
- `risk_list.length >= 3` 红色 Badge;`1-2` 橙色;`0` 灰
- `Tooltip title={risk_list.join('；')}` 悬停看风险清单

## 四 执行顺序
1. 顶部加 `useQuery(['agent-suggestions'], agentSuggestions)` 取采纳集合
2. `dates?.[0]` 计算今日 date
3. 渲染 3 个摘要卡(Statistic + Card)
4. columns 数组插入 '6 因子' 列 + '在候选池' 列 + '风险' 列
5. `Table.defaultSortOrder` 综合分降序
6. `<Tabs>` 包住 `<Table>`,3 Tab 各传 filtered 数据
7. 跑 `cd web && npx tsc --noEmit` 零错
8. 跑 `cd web && npx oxlint src/pages/ScoresPage.tsx` 零错
9. `npm run build` 绿

## 五 验证清单
- [ ] 顶部 3 摘要卡显示数字(空态显「—」)
- [ ] 6 因子色条正确渲染 6 格 + 鼠标悬停显示依据
- [ ] 综合分降序默认
- [ ] 3 Tab 切换正确(今日/历史 A/已采纳)
- [ ] `in_candidate` 命中显示蓝 Tag
- [ ] `risk_list≥3` 红 Badge
- [ ] tsc + oxlint + build 全绿
- [ ] 不动 detail 结构(只读)
- [ ] 不引新依赖

## 六 红线
1. **绝不动后端**——所有数据从已有 3 个 API 读
2. **绝不动 types**——`StockScoreInfo` 已够用
3. **绝不动 api/**——scores/candidates/agentSuggestions 已有
4. **绝不写 6 因子硬编码 index**——必须按 `f.factor === '动量'` 定位
5. **绝不显示完整 reason 文本在列表**——只 Tooltip 悬停
6. 改动预算 ≤ 150 行,超出停下报 sir

**Claude 端省 token 约束**：①不复读本提示词（只 grep path:line）②只动 ScoresPage.tsx 单文件 ③不写大段注释（docstring≤3行）④复用已有 `ConfidenceBar`/`StockLabel`/`EmptyState` 组件 ⑤不写新测试（前端靠 tsc+build）⑥报告 ≤ 10 行。
