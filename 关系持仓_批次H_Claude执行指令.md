# 关系持仓批次 H · 复盘反哺选股 · DSH/Claude Code 执行指令

> 方案：`关系持仓_个股分析_优化方案.md` §三模块5 · 依赖：G（K139）+ D（派发期 phase）

## 一、目标

把"哪只票拖累组合"从凭印象升级为代码可计算事实：组合曲线 + 贡献者瀑布 + 周期复利 + Score 历史胜率加分/扣分。

## 二、范围

| # | 改动 | 文件 |
|---|---|---|
| 1 | 追加 2 函数（不动现有）| `backend/app/services/track_verify.py` 加 `build_portfolio_attribution(days)` + `build_stock_cycle_attribution(code)` |
| 2 | 路由 | `backend/app/api/routes.py` 加 `GET /api/portfolio_attribution?days=30` + `GET /api/stock_cycle_attribution/{code}` |
| 3 | 注入 2 Agent collect 段 | `backend/app/agents/{review,score}.py` |
| 4 | React 复盘页三段 UI | `web/src/pages/ReviewsPage.tsx` 顶部组合曲线 + 中部瀑布 + 底部周期表（echarts）|
| 5 | 测试 + commit | `backend/tests/test_track_verify_attribution.py`（新建 ≤ 5 用例）|

## 三、规则

**组合曲线**（`build_portfolio_attribution(period_days)`）：
- 输入：复盘周期天数（默认 30）
- 输出：`{"portfolio_curve":[{date, total_pnl_pct}], "contributors":[{stock_code, contribution_pct, pnl_amount, holding_days}], "drag_analysis":"最大拖累者 X (Y%)"}`
- 口径：按日累计 `Σ(单票 pnl) / 总成本` 作为该日组合盈亏（写死在代码 + 注释 + 单测，不依赖 LLM）

**周期复利**（`build_stock_cycle_attribution(stock_code)`）：
- 输入：股票代码
- 输出：该股历史多次操作的"周期复利"——多次买入/卖出汇总总盈亏 + 平均持仓天数 + 最佳/最差周期

**注入点**（2 Agent）：
- Review `collect_review_input` 末尾：复盘顶部展示组合曲线 + 每只历史持仓卡片"对组合贡献度"（正绿/负红）；同代码多次操作 → 折叠"周期复利"汇总
- Score `collect_score_input` 在 D 派发期 + E 游资字段**后**追加：读 `build_stock_cycle_attribution(code)`；**历史胜率 ≥ 60%** → 资金维度追加 +5 分；**历史拖累率 ≥ 30%** → 资金维度扣 -10 分；**缺失历史** → 标"无历史数据"，不加分不扣分

**前端三段**（React 优先，Streamlit 不动）：ReviewsPage 顶部 echarts 组合曲线 / 中部瀑布图 / 底部周期表

## 四、执行顺序（6 步）

1. **读已有代码**：`services/track_verify.py`（仅追加函数，不动现有 `_group_stats` / `_calc_stats`）+ 仿 `holding_view.py` 纯计算风格 + `agents/review.py` collect 段（批次 F 注入的 portfolio_attribution 后追加）+ `agents/score.py` collect 段（D 派发期 + E 游资后）+ `web/src/pages/ReviewsPage.tsx`（React 优先）。
2. **追加 2 函数**：`build_portfolio_attribution(period_days: int) -> dict` 按 §三 Schema 返回；`build_stock_cycle_attribution(stock_code: str) -> dict` 返回周期复利；行数预算 ≤ 120 行（两函数体）。
3. **路由**：`routes.py` 加 2 端点 + 必要 import + 分页参数（`?days=30` 默认）。
4. **注入 2 Agent**：Review `collect_review_input` 段末 + Score `collect_score_input` 段（在 D + E 之后追加）。
5. **前端 React 三段**：ReviewsPage 顶部 echarts 折线 + 中部瀑布（bar chart）+ 底部周期表（Table）；用 `redLineCheck` 风格的小组件解构。
6. **测试 + commit**：新建 `tests/test_track_verify_attribution.py` ≤ 5 用例——①组合曲线按日累计计算正确 ②贡献度排序正确（最大贡献者识别）③拖累分析正确 ④周期复利多次操作汇总正确 ⑤Score collect 注入字段可读 + 缺历史不伪造。跑：`pytest tests/test_track_verify_attribution.py -v && pytest tests/ -v && cd web && npm run build`。全绿后 commit（不 push）：
git add -A && git commit -m "[批次H] 复盘反哺选股：portfolio_attribution + cycle_attribution + Review/Score 注入 + React 三段 UI"

## 五、红线 + 省 token

**5 红线**：①不动 track_verify 现有函数（仅追加）②不动 ReviewAgent 节点结构（仅 collect 段）③贡献度口径写死代码不依赖 LLM ④不动 Streamlit ⑤不引新库（仿 track_verify 风格读既有 SQLite 表）。

**Claude Code 端省 token**：①只读方案 §三模块 5 关键段，禁止复读全文 ②只动本批次 5 类文件，禁止顺手改 ③复用 `track_verify._group_stats`/`_calc_stats`/`holding_view.build_holding_view` 已实现 ④测试 ≤ 5 ⑤报告 ≤ 10 行。**代码侧最小改动 ≤ 200 行**，超出→停下报告 sir。

## 六、沟通节点

每步骤完成后输出 ①改了哪些文件 ②测试结果 ③遗留风险；遇字段含义不清→停下问；遇红线触碰（必须改 track_verify 现有函数）→立即停。**完成后 H 是关系持仓 × 个股分析 5 批次的最后一批**——全部绿后进总验收（curl 5 个新端点 + 4 个前端页 + 跑全量回归 + 出 5 批次收口报告）。
