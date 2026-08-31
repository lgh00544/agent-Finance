# 持仓盈亏修复 · 建仓流水缺失（A 补数据 + B 兜底）· Claude Code 执行指令

> 生成者：Lark · 决策人：sir（2026-08-27 拍板「做」）· 中等任务 ≤150 行改动
> 根因复盘：山东墨龙(002490, holding_id=13) 实亏 ¥1048，复盘显示 +59.05%。根因 = 建仓首笔不写 buy 流水，review.py:40-51 用「Σ卖−Σ买」口径算盈亏 → 底仓成本被漏计。

## 一、目标

1. **A 数据侧治本**：建仓自动补开仓 buy 流水 + 一次性回填存量持仓缺失流水
2. **B 计算侧兜底**：review 盈亏改总成本口径
3. 对 holding_id=13 重跑复盘，覆盖错误结论

## 二、规则（金额/口径定死）

- **开仓流水补法**：缺失开仓 buy 金额 = `holding.cost − Σ已有 buy 流水 amount`；股数 = 首条 buy 的 `before_shares`（无任何 buy 流水则 = 当时 shares）；价格 = 金额÷股数 四舍五入 2 位（与实盘分位一致）。验证锚点：墨龙应为 1000股 × ¥8.45 = ¥8450，补后 Σbuy == cost ±0.01
- **幂等标记**：补写流水 `note='建仓补录'`；执行前查同 holding 是否已存在该 note，有则跳过，禁止重复插入
- **B 口径**：exited 持仓 `pnl_pct = (Σsell_amount − cost)/cost × 100`；cost 缺失或 ≤0 时回退旧公式并在 trace 标注。补齐流水后新旧口径应一致（差异 <0.1%）
- K227：数据对不上（Σbuy 与 cost 差 >2%）→ 如实保留旧值 + 日志告警，禁止硬凑

## 三、执行顺序

1. `backend/app/db/repo.py`：新增 `ensure_opening_trade(holding_row)` —— 判断该持仓是否存在 `note='建仓补录'` 流水或缺首笔（首条 buy 的 before_shares>0 或无 buy），按 §二规则插入 TradeRecord；`insert_holding(:1143)` 末尾调用（新建仓即带流水）
2. 新建 `backend/scripts/backfill_opening_trades.py`：遍历全部 holding（含 exited），逐只调 `ensure_opening_trade`，打印每只补录结果汇总（补了几只、各补多少）
3. 跑一次回填脚本（真实 dev.db），**核对墨龙：出现 1000股@8.45 note=建仓补录**
4. `backend/app/agents/review.py:40-51`：pnl_pct 改 §二 B 口径（exited 用 cost 公式），trace 追加一行口径说明
5. 测试 `backend/tests/test_opening_trade.py`（3 例）：①insert_holding 自动产生 buy 流水且金额=entry_price×shares ②回填幂等不重复插 ③exited 缺流水持仓 review 后 pnl_pct 为负值正确（仿墨龙构造：cost>Σ原buy）
6. 全量回归：`test_review*` `test_track_verify_attribution` `test_holdings*` 相关用例不回归
7. 重跑复盘：POST 任务 `{"kind":"review","params":{"holding_id":13,"exit_date":"2026-08-27"}}`（或前端触发），确认新结论为亏损 ≈ −5%
8. commit `[持仓盈亏修复] 建仓流水补全 + 复盘总成本口径`

## 四、验证清单

- [ ] 墨龙 trade_record 出现 `note='建仓补录'` 1000@8.45，Σbuy==20985±0.01
- [ ] 重跑后 review_result.holding_id=13 的 pnl_pct ≈ −4.99（容差 ±0.5）
- [ ] 回填脚本二次运行 0 条新增（幂等）
- [ ] 全部存量持仓 Σbuy vs cost 偏差 <2%，超差名单打进报告

## 五、红线

1. 不动 agent_call/push_alert_node；不动 Discover/Score/Monitor 链路
2. 只动 repo.py（新增+insert_holding 尾调）/ scripts 回填（新文件）/ review.py pnl 段 / 新测试文件；禁止顺手改其他
3. 不删不改任何既有 trade_record（只增补）；补错可按 note 整体撤销
4. 测试 3 例封顶；docstring ≤3 行；报告 ≤10 行（①文件清单 ②测试 ③回填统计 ④墨龙复核值 ⑤遗留）

## 六、沟通节点

- 回填遇到 Σbuy≠cost 且差 >2% 的持仓 → 不强行补，列清单报 sir
- 任一测试不过 → 停手报 sir，不 commit 半成品
