# 决策可信度增强 · 批次4（前端审计卡片）

## 〇 元信息
- 生成者：TradingAgentTeam（决策可信度增强第4批次）
- 执行者：Claude Code / DSH（后端+React 前端）
- 决策人：sir
- 依赖方案：`D:\self\决策可信度增强_市况严格度与审计底稿_方案.md`（已 5 处修正 in-place）
- 前置批次：批1 市况严格度 ✅ / 批2 A层候选audit ✅ / 批3 B层block_details ✅（均验收通过）
- 执行起点：主分支 main 最新（batch1-3 已重启 backend 生效）
- 原则：React 新版优先；不算数据只展示；缺字段显「-」兜底；不引新库

## 一 目标
展示批2/批3 已落库的两层审计，让「候选为何可建仓/被拒」在前端可追溯：
1. **上游严格度横幅**：当日最终严格度（宽松/标准/严格/极严）+ 市况档位
2. **审计 Tab**：候选 detail.audit 的 6 项判定（market_gate/tier_gate/stop_loss/profit_risk_ratio/major_negative/pool_position），passed/badge + evidence + verdict 降档 note
3. **拒判明细 Tooltip**：行内 label Tag 的 Tooltip 从单行 block_reason 升级为「block_reason + block_details 逐项 {rule, passed, evidence}」

**不做什么**：
- 不改后端判定/rank/upsert 签名/权重（红线）
- 不改 Streamlit（React 新版优先铁律）
- 不引新 UI 库，只用已有 Tag/Tooltip/Table expanded/Tabs/Alert
- 不重读方案全文（本文件已含全部所需 path:line）

## 二 架构约束
- **后端只薄改 1 处**：`routes.py:344 market_condition` 返回加 `strictness` 字段（调用 `_day_strictness`）——**不得污染 `tradeable_view`**（test_candidate_tradeable.py:327 锁死其键集合 `{date,count,plan_candidate_count,total,items}`）
- **前端只改 2 个文件**：`web/src/pages/CandidatesPage.tsx` + `web/src/types/index.ts`（仅加可选类型注解，不动 Candidate.detail/CandidateTradeable.items 的 Record 宽松结构）
- 审计/block_details 均从已有 JSON 读，**不新增任何后端字段/端点**

## 三 规则
- **严格度数据源**：`market-condition` 端点（`routes.py:344`）JSON 加 `strictness`，值取 `candidate_tradeable._day_strictness(trade_date)`（含 MarketIntel 修正的当日最终严格度）。审核 broker 用 `market_condition.total_score + market_band_info(score)[3]` 兜底（band 已是基底严格度，`repo.py:194`）
- **审计 Tab 结构**（读 Candidate.detail.audit）：
  - `audit.decisions` 数组（6项：market_gate → 市况打分带 band→/tier_gate→评级档位/stop_loss→止损约束/profit_risk_ratio→盈亏比/ major_negative→重大利空排查/pool_position→位置距52高）
  - 每项渲染：`label` + badge（passed=绿/未过=红，缺失=灰「-」）+ `evidence` 灰字
  - 顶部：`verdict`（降档后有效档）+ `passed_ratio`（如 `5/6`）+ `note`（非空才显示「降档原因：…」）
  - 空/缺字段 → 整 Tab 显示 EmptyState（兼容存量候选无 audit）
- **拒判 Tooltip**（读 tradeable 项 detail.block_details）：
  - 取 items 每一项 `detail.block_details`（数组，缺→空）
  - Tooltip title = `block_reason` + 换行 + 逐条 `{rule}：{passed?'通过':'未过'}——{evidence}`；block_details 空 → 回落现有单行 block_reason 文案（保持 :649 现状）
  - 仍以 `tv.block_reason` 平铺列为兜底（旧记录无 block_details 时）
- **严格度横幅**：页面顶部 `Alert`（或 StatusBar 区），显示「今日严格度：{strictness}｜市况 {band} {grade}」，strictness 缺→不显示（后备band）不报错

## 四 执行顺序
1. **后端**：`app/api/routes.py:344` 改 `market_condition()` 返回 dict 加 `"strictness": _day_strictness(row_trade_date)`（row 为 `get_latest_market_condition()` 结果含 trade_date；丢失/空 None 时 strict 置 `None` 前端降级）。处理导入：`from app.services.candidate_tradeable import _day_strictness`（模块顶或函数内 lazy，避免循环）
2. **types**：`web/src/types/index.ts` 加 `AuditDecision {key,label,passed,evidence}` + `MarketAudit {verdict;passed_ratio;note;decisions:AuditDecision[]}` + `BlockDetail {rule;passed;evidence}`（可选字段，宽松）
3. **CandidatesPage**：
   a. 顶部取 `market-condition` 数据（有则读 strict/band/grade），渲染严格度横幅 Alert/Tag
   b. `CandidateExpand`（:65）新增「审计」Tab：`const audit=(detail.audit as Record...)`，decisions 渲染 + verdict/ratio/note
   c. :642-655 Tooltip 升级：拉起 `tv.detail.block_details`，逐条耗时拼 block_reason 后显示
4. **编译验证**：`cd web && tsc` 零错；`grep -c` 核对 audit/block_details 引用落地
5. **回归**：后端 `test_candidate_tradeable.py`（24）仍绿、`test_batch_chat.py`（12）仍绿——确认没污染判定/平铺列

## 五 验证清单
- [ ] `routes.py:344` 后 `market /api/market-condition` 响应含 `strict` 字段
- [ ] CandidatesPage 顶部横幅显示严格度 + 市况档（缺时降级不报错）
- [ ] 候选展开行有「审计」Tab，6项 passed/evidence 正确，verdict+ratio+note 显示
- [ ] 行内 label 的 Tooltip 显示 block_reason + block_details 逐条（旧记录无 block_details 显「-」）
- [ ] `tsc` 零错 + 36 后端测试全绿（不污染判定）

## 六 红线（不可越）
1. 绝不改后端判定/评估级/rank/`upsert_candidate_tradeable` 签名——前端只能读，不能改
2. React 新版优先，Streamlit 一律不动
3. 不引新库/新组件，仅用本文件既有组件
4. 存量候选无 audit/block_details → 缺字段显「-」/不显示，不得报错
5. 改动行数预算：中等 ≤ 80 行（前后端合计），超出停下报 sir

**Claude Code 端省 token 约束**（必守）：
1. 不复读本提示词已固化信息（只 grep path:line 关键标识确认位置）
2. 只动上面列的 3 个文件，禁止顺手改其他文件
3. 不写大段注释（docstring ≤ 3 行，函数体内无 # 注释）
4. 复用已有组件（Tag/Tooltip/Table expanded/Alert），禁止自造
5. 测试不新增后端用例（前端改动 + 后端 1 薄字段，跑既有 36 回归即可），不做防万一多写
6. 执行完毕报告 ≤ 10 行：①改了哪几个文件 ②编译/测试结果 ③遗留风险