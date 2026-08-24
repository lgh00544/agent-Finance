# 关系持仓批次 G · K 红线代码化 · DSH/Claude Code 执行指令

> 方案：`关系持仓_个股分析_优化方案.md` §三模块4 · 依赖：批次 E（`wash_suspect`）+ 批次 D（`distribution_phase`）

## 一、目标

C1/C2/C3/C4 + K139 SOP + K226 + K189 由"prompt 原则"升级为"代码可注入事实层"，注入 Monitor/Sell/Position 三 Agent + React 持仓页四色徽章。

## 二、范围

| # | 改动 | 文件 |
|---|---|---|
| 1 | 新建 `services/red_line_check.py`（纯计算，按持仓逐行扫描）| `backend/app/services/red_line_check.py`（新建）|
| 2 | 路由 | `backend/app/api/routes.py` 加 `GET /api/red_line_check` + `GET /api/red_line_check/{code}` |
| 3 | 注入 3 Agent collect 段 | `backend/app/agents/{monitor,sell,position}.py` |
| 4 | React 持仓页 4 徽章 | `web/src/pages/HoldingsPage.tsx`（C1/C2/C3/K139 四色绿/黄/红/灰）|
| 5 | 测试 + commit | `backend/tests/test_red_line_check.py`（新建 ≤ 5 用例）|

## 三、规则

**C1 单只占比**：当前价 × 股数 / 总资产，**≤ 60% 触发**（**L0 红线阈值不改**）。
**C2 单票日内回撤**：当日 (cost - low) / cost，**≤ -30% 触发**。
**C3 止损**：cost × 0.92，当前价 ≤ 触发。
**C4 突破**：当前价 ≥ 持仓期最高价 → `c4_high_break: true`。
**K139 SOP 持盈不持亏**：trailing_stop = cost + (现价 - cost) × 0.5；stage ∈ {试探仓/持有观察/+5%减仓/+10%减仓/跌破C3}。
**K226 派发期主体**：9 大主体减仓数 → alert_level ∈ {无/中等派发/强派发}（**复用 D 派发期** `phase≥2` 触发）。
**K189 对倒**：从 E 注入的 `capital_view_context.wash_suspect` 读取，无数据 → null。

**Schema（每持仓一行）**：
{"stock_code":"601138","c1_cap_pct":17.6,"c1_alert":false,"c2_alert":false,"c3_stop_loss":59.0,"c3_alert":false,"c4_high_break":true,"pnl_pct":1.86,"k139_sop":{"trailing_stop":65.17,"stage":"持有观察","next_action":"持有观察"},"k226_subject_count":0,"k226_alert_level":"无","k189_wash_suspect":false}

**纪律**：缺数据字段显式 `null`，不补 0/不补均值；K139/K226 是参考权重非死条件，LLM 保留一票否决权。

**注入点**（3 Agent）：
- Monitor `collect_quote` 段末追加 `【红线扫描】{red_line_check}`
- Sell `collect_sell_input` 段末追加 `【K139 SOP 触发判定】{k139_sop}`
- Position `collect_position_input` 段引用 C1/C2 软上限 + K192 吸筹末期策略

**前端徽章**（React 优先，Streamlit 不动）：C1/C2/C3/K139 四色——绿(无)/黄(预警)/红(触发)/灰(无数据)；悬停显示触发条件（如"C3 止损 59.00 距 -0.5%"）。

## 四、执行顺序（6 步）

1. **读已有代码**：仿 `holding_view.py` 纯计算风格 / `services/capital_view.py` Schema / `services/distribution_phase.py` 多源拼接风格 / `agents/{monitor,sell,position}.py` collect 段 / `web/src/pages/HoldingsPage.tsx`（React 优先）。
2. **新建 `services/red_line_check.py`**：`compute_red_line(holdings: list, prices: dict, total_asset: float) -> list[dict]` 按 Schema 返回；K189 字段读取 `SimpleCache().get(f"capital_view:{date}:{code}")` 复用 E 已落缓存；K226 读取 `distribution_phase:{date}:{code}` 复用 D 已落缓存。
3. **路由**：`routes.py` 加 `GET /api/red_line_check`（全量）+ `GET /api/red_line_check/{code}`（单只） + 必要 import。
4. **注入 3 Agent**：`monitor.py`/`sell.py`/`position.py` collect 段按 §三位置追加；调用 `compute_red_line()` + 读缓存拼字符串。
5. **前端 React 徽章**：`HoldingsPage.tsx` 表格右侧每行加 4 个 Tag（color 映射按 §三 4 色 + 悬停 Tooltip）。
6. **测试 + commit**：新建 `tests/test_red_line_check.py` ≤ 5 用例——①C1 占比超 60% 触发 c1_alert=true ②C3 当前价 ≤ cost×0.92 触发 c3_alert=true ③K139 trailing_stop 计算正确 + stage 推进 ④K189 缓存缺失→null 不伪造 ⑤3 Agent collect 注入字段可读出。跑：`pytest tests/test_red_line_check.py -v && pytest tests/ -v && cd web && npm run build`。全绿后 commit（不 push）：
git add -A && git commit -m "[批次G] K红线代码化：red_line_check + 5阈值(K139/K226/K189复用D/E) + 3 Agent 注入 + React 4 徽章"

## 五、红线 + 省 token

**5 红线**：①L0 阈值（C1=60%/C2=30%/C3=0.92）不改 ②K139/K226 是参考非死条件 ③缺数据→null 不补 0 ④不动 Streamlit ⑤不引新库（K189 复用 E 缓存 + K226 复用 D 缓存）。

**Claude Code 端省 token**：①只读方案 §三模块 4 关键段，禁止复读 ②只动本批次 5 类文件，禁止顺手改 ③复用 `holding_view.py`/`capital_view.py`/`distribution_phase.py`/`SimpleCache` 已实现 ④测试 ≤ 5 ⑤报告 ≤ 10 行。**代码侧最小改动 ≤ 200 行**，超出→停下报告 sir。

## 六、沟通节点

每步骤完成后输出 ①改了哪些文件 ②测试结果 ③遗留风险；遇字段含义不清→停下问；遇红线触碰（必须改 L0 阈值）→立即停。完成后停等验收，再进批次 H（复盘反哺，依赖 G 的 K139 + D 的派发期）。
