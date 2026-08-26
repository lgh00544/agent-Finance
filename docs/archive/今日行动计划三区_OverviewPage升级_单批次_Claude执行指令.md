# 今日行动计划三区 · OverviewPage 升级单批次（Claude Code）

## 〇 元信息
执行者：Claude Code。决策人：sir。前置：scheduler 诊断全绿，/api/dashboard 已聚合 12 个 modules（含 candidates/holdings/market_condition/candidate_tradeable/plans/scores/pending_suggestions）。原则：前端单文件改造，后端 0 改动，复用 dashboard 接口，不引新库。

## 一 目标
把 OverviewPage 从"7 个分散 Card + 4 个 StatCard"升级为"3 大主题区"，sir 进站第一屏 30 秒看完今日动作：

| 主题区 | 内容 | 数据源 |
|---|---|---|
| **① 市况速览**（顶部） | 当日 band/grade/strictness + 综述 + 3 大指数涨跌幅 + 热门板块 top3 | `dashboard.modules.market_condition` + `market/indices` + `hotSectors()` |
| **② 今日可建仓** | 候选池 tradeable.count + top3 标的（代码/名称/grade/综合分） | `dashboard.modules.candidate_tradeable.items` |
| **③ 持仓关注** | 持仓 N 只 + 4 个子项分类（止盈/止损/红线/质量低）每类 1-3 只 | `dashboard.modules.holdings` |

**不做**：不动后端 / 不动 router / 不引新库 / 不改 StatCard 组件本体 / 不重写 dashboard 聚合 / 不删任何现有 Card。

## 二 架构约束
- **单文件**：`web/src/pages/OverviewPage.tsx`（386 行, 现有 7 Card + 4 StatCard）
- **不动类型**：`DashboardData` 已含 modules 任意对象
- **复用已有**：`dashboard()` / `holdingQuotes()` / `hotSectors()` 已有 api 函数
- **新增不引依赖**：仅用 antd 已有 `Card` / `Tabs` / `Tag` / `Progress` / `Space` / `Badge` / `EmptyState`
- **保持向下兼容**：现有 7 Card（任务执行/定时任务/板块/止盈/持仓/评分）全部保留，不删

## 三 规则

### 3.1 顶部「市况速览」横幅（替换原 4 个 StatCard 的位置）
- 新增一行 Card：宽屏横排 4 列，移动端 2 列
- 字段 1：市况 band（如「强势」Tag 颜色按 `marketCondition.band`）
- 字段 2：综合分（marketCondition.total_score）/100
- 字段 3：当日严格度（marketCondition.strictness）Tag，按档位 4 色（宽松绿/标准蓝/严格橙/极严红）
- 字段 4：3 大指数涨跌幅（读 `market/indices` 已有调用或 store）
- 副标题：marketCondition.summary 一行（无→"—"）
- 数据缺失时全"—"降级，不报错

### 3.2 「今日可建仓」中区 Card
- 位置：原 StatCardGrid 下方
- 标题：「今日可建仓」
- 顶部：tradeable.count + tradeable.total（例"3 / 39 只"），用 StatCard 小块
- 主体：tradeable.items 取前 3，每只一行：
  - `<StockLabel>` + grade Tag + 综合分(score) + 1 个最强因子（如「催化 8/10」）读 detail.factors
- 不足 3 只：占位「—」不报错
- 0 只：EmptyState "今日无可建仓标的"

### 3.3 「持仓关注」Card（替换原"当前持仓概览"Card 的位置）
- 位置：原持仓 Card 位置
- 标题：「持仓关注」
- 顶部：持仓总数 N
- 主体：4 个分类（Tabs 或折叠面板）：
  - **止盈触发**：holdings 中 `take_profit_hit=true` 或类似字段
  - **止损触发**：holdings 中 `stop_loss_hit=true`
  - **红线预警**：holdings 中 `red_line_warning=true`
  - **质量低**：holdings 中 `quality_score<60`
  - 每类最多列 3 只：`<StockLabel>` + Tag 提示原因
- 每类 0 只：「无」灰 Tag
- 字段名以 holdings 实际数据为准（grep `holdings` / `quality` / `take_profit` 查 dashboard.py 实际返回）

## 四 执行顺序
1. 读 `web/src/pages/OverviewPage.tsx` 全文 + `backend/app/services/dashboard.py` 确认 holdings 实际字段
2. 在 StatCardGrid 位置后插入「市况速览」Card（4 列）
3. 在市况速览下方插入「今日可建仓」Card（tradeable top3）
4. 替换原"当前持仓概览"Card 为「持仓关注」Card（4 分类）
5. 跑 `cd web && npx tsc --noEmit` 零错
6. 跑 `cd web && npx oxlint src/pages/OverviewPage.tsx` 零错
7. `npm run build` 绿
8. 提交：`git add web/src/pages/OverviewPage.tsx && git commit -m "feat(overview): 今日行动计划三区(市况速览/可建仓/持仓关注) - dashboard 复用"` + push

## 五 验证清单
- [ ] 顶部「市况速览」显示 4 列（band/grade/strictness/指数），数据缺失降级
- [ ] 「今日可建仓」显示 tradeable.count + top3 标的
- [ ] 0 可建仓时 EmptyState 不报错
- [ ] 「持仓关注」4 分类标签 + 每类 0/1-3 只
- [ ] 现有 7 Card（任务/调度/板块/止盈/评分）全部保留
- [ ] tsc + oxlint + build 三绿
- [ ] 不动后端 / types / api

## 六 红线
1. **绝不动后端** —— /api/dashboard 已有 12 modules 全够用
2. **绝不动 types** —— DashboardData 已含 modules
3. **绝不动 api 函数** —— 复用已有
4. **绝不删现有 7 Card** —— 任务/调度/板块/止盈/评分全部保留
5. **绝不在持仓关注 Card 编造字段** —— 以 dashboard.py 实际返回为准
6. 改动预算 ≤ 200 行，超出停下报 sir

**Claude 端省 token 约束**：①不复读本提示词（只 grep `path:line`）②只动 OverviewPage.tsx 单文件 ③不写大段注释（docstring ≤ 3 行）④复用已有 `StatCard`/`StockLabel`/`EmptyState` 组件 ⑤不写新测试（前端靠 tsc+build）⑥报告 ≤ 10 行。
