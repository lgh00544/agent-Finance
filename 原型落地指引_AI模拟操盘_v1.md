# 原型落地指引 · AI 模拟操盘独立入口 v1

- 原型位置：`D:\self\prototypes\governance-prototype-v2`（`index.html` / `app.js` / `styles.css`，纯静态、无依赖、无构建）
- 对应生产实现：`backend/app/services/paper_*.py` + `web/src/components/PaperTradingPanel.tsx` + `web/src/api/paper.ts`
- 文档日期：2026-11-20　原型完成日期：2026-11-19（含 11-20 的窄屏修复与影子状态词表修正）
- 当前状态：**只有原型**。`web/src`、`backend` 一行没动，没有 commit / push / 装依赖。
- 关联文档：`模拟操盘与策略反哺_方案.md`（后端设计）、`原型落地指引_就地裁决与连点_v1.md`（三队列交互范式，本文不重复）

---

## 0. 怎么读这份文档

每节末尾标注三类信息，落地时按标注办事：

| 标注 | 含义 |
|---|---|
| 【口径】 | 数字、文案、状态词必须逐字照搬，改了就等于改交易规则，要走规则审计 |
| 【换真接口】 | 原型里是内存重算，落地必须换成第 13 节的 endpoint，禁止乐观更新 |
| 【禁止照搬】 | 演示逻辑（假数据、本地时钟推进、随机化种子），第 17 节集中列 |

---

## 1. 原型在哪里、怎么看

```bash
cd /d/self/prototypes/governance-prototype-v2 && python -m http.server 8771
# 浏览器打开 http://127.0.0.1:8771/index.html#/paper
```

也可以直接双击 `index.html` 用 `file://` 打开（功能一致，只是深链参数写法略有差别）。

- 侧边栏入口：**今日 → AI 模拟操盘**（`app.js:648`，路由 `#/paper`）
- 页面右上角常驻按钮：新建模拟账户 / 暂停·继续运行 / 刷新行情 / 模拟巡检 / 立即补跑 / 归档账户
- 深链示例（可完整恢复现场，第 11 节）：
  - `#/paper?view=archived&acc=901&tab=contexts&pos=002049&filter=rejected`
  - `#/paper?acc=902&tab=reviews`

---

## 2. 为什么要单独一个入口（现状证据，不是审美问题）

| 现状 | 证据 | 后果 |
|---|---|---|
| 模拟盘面嵌在真实持仓页底部 | `web/src/pages/HoldingsPage.tsx:901` | 「AI 买了什么」和「我买了什么」同屏混排，盈亏口径极易看错 |
| 同一个面板在总览页又挂一份 | `web/src/pages/OverviewPage.tsx:360` | 两处重复渲染、两套局部状态，改动要同步两份 |
| 面板只有 5 个 Tab：持仓 / 流水 / 研究上下文 / 联网证据 / 告警 | `PaperTradingPanel.tsx:334-349` | **模拟复盘没有入口**，`paperReviews()` 只在 `ReviewsPage` 被消费 |
| 影子验证动作接口无人调用 | `web/src/api/paper.ts:201` 定义 `shadowPaperReview`，全仓无引用 | 审核通过之后链路断在前端，用户看不到「送入影子验证」 |
| 「为什么买」不可读 | 现有面板只有 `研究上下文` 表，取证工具链要展开行才看到 | 用户诉求「为什么买」无法一眼回答 |

用户的原话诉求：**直接看它买了什么、为什么买、赚亏多少、是否正常运行，不与自己的持仓混在一起。**
原型对这四问各给一个明确版面，并把账户状态（运行中 / 已暂停 / 已归档 + 下次调度时间 + 本轮推进到几点）常驻在页头。【口径】

---

## 3. 规则常量（与后端逐条对齐，已核对）

原型 `app.js:5663 PP_RULES` ↔ 后端 `backend/app/services/paper_execution.py:60-72`：

| 口径 | 原型 | 后端 | 一致 |
|---|---|---|---|
| 一手股数 | `lot: 100` | `LOT_SIZE = 100` | ✅ |
| 佣金 | `0.0003`，最低 5 元 | `COMMISSION_RATE=0.0003` / `COMMISSION_MIN=5.0` | ✅ |
| 印花税（仅卖出） | `0.0005` | `STAMP_TAX_RATE=0.0005` | ✅ |
| 过户费（双边） | `0.00001` | `TRANSFER_RATE=0.00001` | ✅ |
| 滑点 | `±5bp` | `SLIPPAGE_BPS = 5.0` | ✅ |
| 涨跌停默认幅度 | `10%` | `LIMIT_PCT_DEFAULT = 0.10`（创业板/科创板 20%、ST 5%、北交所 30% 按代码段推） | ✅ |
| 一手容差 | `0.05` | `CANDIDATE_POOL_LOT_TOLERANCE = 0.05` | ✅ |
| 首仓 / 加仓档 | 10% / 10% | `CANDIDATE_POOL_ALLOCATION = 0.10` | ✅ |
| 单票上限 | `maxAllocationPct: 20` | 与 live B 级 20% 对齐（后端注释明确：paper 无 A 级 30% 档，**有意不收敛**） | ✅ |
| 加仓触发 / 首次止盈 / 主止盈 / 硬止损 / 移动止损 | +3% / +8% / +15% / −8% / 5% | `CANDIDATE_POOL_ADD_TRIGGER_PCT=0.03`、`FIRST_TAKE_PCT=0.08` 等 | ✅ |
| 行情新鲜度 / 巡检间隔 | 10 分钟 / 5 分钟 | 巡检最小 5 分钟（更密的 cron 后端拒绝，原型表单同步拦截） | ✅ |
| 执行规则版本 | `paper-execution-v1` | `RULE_VERSION = "paper-execution-v1"` | ✅ |

> 后端 `paper_execution.py:52-59` 的注释是本节最后一列的依据：**paper 与 live 的仓位档位差异是有意保留的**，落地时不要"顺手统一"。

---

## 4. 数据模型与账本不变量

### 4.1 表映射（原型对象 ↔ 生产表）

| 原型 | 生产表（`backend/app/db/models.py`） | 说明 |
|---|---|---|
| `acc` | `paper_account` (:1263) | 独立账本，`variant` / `mode` / `initial_cash` / `status` |
| `ppReplay().positions` | `paper_position` (:1281) | 原型不落表，**由流水回放算出**；生产是缓存表，落地时以回放口径校验缓存 |
| `acc.execs` | `paper_execution` (:1309) | 唯一事实源，含 `commission/stamp_tax/transfer_fee/total_amount/reject_reason` |
| `acc.reviews` | `paper_review` (:1350) | 模拟复盘 + 审核 + 影子状态 |
| `acc.slots/universe` | `paper_quote_snapshot` (:1372) | 每一格是一次可核验的行情快照 |
| `acc.contexts` | `paper_context` (:1397) | 研究取证（工具链、事实时点、研判结论） |
| `—`（原型并入 contexts） | `paper_web_evidence` (:1416) | 生产是独立表，落地时单独取数（现有面板已有「联网证据」Tab） |
| `acc.alerts` | `paper_alert` (:1439) | 模拟告警，`severity ∈ info/warning/critical` |

### 4.2 账本不变量【口径】

`ppReplay`（`app.js:6118`）：把 `execs` 按 `日期+时间` 升序重放一遍，**依次推出**现金、加权均价、当日冻结（T+1）、已实现盈亏。

- 成交是唯一事实源：任何页面数字都必须能由流水重算得到，禁止"手动改持仓"。
- 均价公式：`(旧均价×旧股数 + 价×股数) / (旧股数+股数)`，4 位小数。
- 当日买入计入 `blocked`，`available = shares − blocked`。
- 已实现盈亏：`卖出净额 − 均价×股数`（净额已扣佣金/印花税/过户费）。
- 派生仓位口径两列并存，不能混：
  - `allocatedPct`＝成本占比（展示用）
  - `planAllocPct`＝**建仓计划目标占比**（决策用，来自 `acc.plans[code].allocatedPct`）

### 4.3 行情序列的四种格子【口径】

`acc.universe[code].series[i]` 与槽位 `acc.slots[i]` 一一对应：

| 写法 | 含义 | 渲染成 |
|---|---|---|
| `123.45` | 正常取到价 | 现价 + 涨跌幅 |
| `{ p: 76.20, limitUp: true }` | 涨停封板 | 现价 + 「涨停」标记，买入必被拒 |
| `{ p: null }` | 本轮没取到价，但历史有有效价 | **参考行情**（回填上一轮有效价，只看不成交） |
| `{ p: null, ref: false }` | 连历史有效价都没有 | **行情暂缺 · 估值不完整** |
| `{ p: x, suspended: true }` | 停牌 | 标的停牌，双边都拒 |

---

## 5. 估值降级三态（最容易做错的一节）

`ppValuation`（`app.js:6169`）+ `ppQuote`（`:6081`）：

| 状态 | 触发条件 | 市值 / 总资产 / 盈亏 | 标签文案 | 允许成交 |
|---|---|---|---|---|
| `ok` | 全部持仓都有当前价 | 正常计算 | 模拟市值 / 模拟总资产 / 累计盈亏 | ✅ |
| `stale` | 任一持仓只有回填价 | **照算但改名** | **估算**模拟市值 / **估算**模拟总资产 / 估算累计盈亏 + 黄条「行情已过期，仅供参考」 | ❌ `price_missing`，note「只能作为参考，不允许用于成交」 |
| `partial_or_unavailable` | 任一持仓连回填价都没有 | **全部 `null`，显示 `—`** | 红条「模拟估值暂不完整」，账户芯片显示「估值暂不完整」 | ❌ |
| `suspended` | 标的停牌 | 该票价格照旧、双边拒单 | 「标的停牌」 | ❌ `suspended` |

铁律【口径】：
1. **绝不用成本价伪造市值**。缺价就是 `null`，宁可整页金额不显示。
2. `factAsOf = min(所有参与估值的事实时点)`——取最旧那条，页面显示「行情事实时间」用这个值。
3. 降级不影响历史：流水、取证、复盘照常展示，只有金额口径改名。
4. 顶栏提示与账户芯片、指标卡、持仓卡四处口径必须一致（`ppQuoteTag:6698`、`ppFactsHtml:6811`）。

---

## 6. 执行器拒绝分支全表（穷举）

`ppExecute`（`app.js:6213`）只做换算，不判断"该不该动"。后端同口径产生点：`paper_execution.py:189-207`（涨跌停/停牌/缺价）、`:400`、`:413`、`:792`。

| `reject_reason` | 前端中文 | 触发条件 |
|---|---|---|
| `price_missing` | 价格缺失 | 无价 **或** 只有参考行情（`referenceOnly`） |
| `suspended` | 标的停牌 | 快照 `suspended` |
| `limit_up` | 涨停无法买入 | 买入方向且封板 |
| `limit_down` | 跌停无法卖出 | 卖出方向且跌停 |
| `not_tradeable` | 未通过可建仓验证 | 买入但没有 `planId`（无建仓计划来源） |
| `already_holding` | 已有模拟持仓 | 非 `add` 动作却已持仓 |
| `plan_or_price_missing` | 建仓计划或价格缺失 | 计划字段缺失 |
| `cash_or_plan_position_too_small` | 资金或计划仓位不足一手 | 首仓换算后 < 100 股 |
| `ai_add_blocked_cash_or_lot` | 加仓换算后不足一手或现金不够 | 加仓换算后 < 100 股 / 现金不够（含逐手退让后归零） |
| `single_stock_target_reached` | 单票目标仓位已用满 | 计划目标已 ≥ 20% 还想加仓 |
| `no_position` | 没有对应模拟持仓 | 卖出但空仓 |
| `t_plus_one_or_no_lot` | 当日买入不可卖出，或可卖数量不足一手 | `available <= 0` |
| `ai_reduce_unavailable_or_invalid` | 可卖不足一手，或模型未给出减仓比例 | `reduceRatio` 缺失/越界——**代码不代为猜测** |
| `ai_reduce_below_one_lot` | 减仓换算后不足一手 | `floor(available×ratio/100)×100 == 0` |
| `future_data` | 资料晚于决策时点 | 取证快照日晚于本次决策时点（闸门拒整轮研判） |
| `llm_unavailable` | AI 研判暂不可用 | 研判层无输出，执行层不自己编意图 |

买入换算顺序【口径】：目标金额 `initial_cash×allocPct%` → 手数（含 5% 容差进位）→ **现金不足则逐手退让** → 仍不足一手才拒。退让只减不加，绝不透支现金。

单票上限三层一致（本轮修复项，落地不要退化）：
1. 决策层 `ppDecideAI:6364` 只在 `headroom = 20% − planAllocPct` 内提议，`headroom≤0.05` 直接给「本轮不加仓」并写理由；
2. 执行层 `ppExecute:6224-6246` 用 `min(模型要求, headroom)` 压缩，压到 0 就 `single_stock_target_reached`，压缩成功时 note 写明「模型要求 X%，按上限只剩 Y%，压缩到 Z% 执行」；
3. 计划元数据 `ppApplyPlan:6349` 累加时 `Math.min(20, 现有+本轮)` 封顶——**计划目标永远不会超过 20%**。

---

## 7. 研判层：两种变体 + 取证留痕

| 变体 | 谁决定动作 | 代码 | 页面表现 |
|---|---|---|---|
| `candidate_pool` 候选池自主加减仓 | LLM 决定 `add / reduce / exit / hold` 与幅度 | `ppDecideAI:6364` | 「模拟巡检」按浮盈档位＋AI 判断出意图，再交给执行器 |
| `current_gate` 现有门禁链路 | 监控信号给方向，卖出研判给比例 | `ppDecideGate:6407` | 走后端既有门禁口径，AI 只裁决"减多少" |

取证记录（`研究取证` Tab）必须回答三件事，缺一件就是不合格：
1. **用了哪些工具**：`get_quote / get_daily_kline / get_news / get_financial / get_fund_flow / search_knowledge / get_sector_regime / get_position_risk`，历史回放模式还会带 `paper_web.search`；
2. **事实时点**：每条工具结果带 `asOf`，页面顶部落 `fact_as_of`；
3. **模式与价格口径**【口径】`ppDecisionTrace:6279`：`historical_snapshot` → 标「冻结快照收盘价」，`live_paper` → 标「现价」。标错等于把历史成绩说成实时成绩。

监控→告警→研判→成交是一条链：`ppRunMonitor:6438` 出信号 → `ppDecideAI/ppDecideGate` 出动作 → `ppCommit:6301` 写流水并把取证 `contextId` 挂上 → 卖出成交才生成模拟复盘（`side==='sell'`）。方向由动作推导：`add→buy`、`reduce/exit→sell`。

---

## 8. 五个 Tab 的页面规格

| Tab | 内容 | 关键列 / 字段 | 就地动作 |
|---|---|---|---|
| 模拟持仓 | 卡片栅格 `.pp-grid`（4/2/1 列） | 现价或最后价格、浮动盈亏、持仓/可卖、成本、占比、止损与两档止盈、行情状态标签 | 点卡换标的（`pp-pos`）；`↑/↓` 键盘切换（`app.js:8165`）；卡内「看 K 线」同屏对照（`pp-kline`）；展开详情含建仓计划、取证、拒绝记录 |
| 模拟流水 | 表格 + 筛选 | 时间、方向·动作、代码、状态、价格、股数、金额、费用、拒绝原因、关联取证 | 筛选：全部 / 已成交 / 已拒绝 / 买入方向 / 卖出方向（`PP_FILTERS:6952`，写入 hash）；「看这笔取证」跳 `contexts` 并定位展开 |
| 研究取证 | 手风琴列表 | 阶段（研究 / 监控+卖出研判 / 持仓动作）、模式、事实时点、工具链明细、被拒原因、外部证据、置信度 | 单条展开/收起（`pp-ctx`）、从流水直达并滚动定位（`pp-ctx-open`）、「手动研究取证」开抽屉 |
| 模拟告警 | 时间线 | 级别（常规 / 风险提醒 / 紧急风险）、来源、时间、正文、关联取证 | 点告警跳对应取证记录 |
| 模拟复盘 | 卡片列表 | 结论、可复用经验、事实闸门缺项、审核意见＋置信度、支持/反面/边界观点、影子状态与说明 | AI 审核这一条 / 人工复审 / 送入影子验证（详见第 10 节） |

页头常驻信息（缺一不可）【口径】：运行状态 + 下次调度时间 + 本轮推进到的时点（`slots` 游标）+ 初始资金 + 行情事实时间 + 行情来源与状态 + 四个金额指标 + 静态原型说明条。

---

## 9. 就地操作与表单校验清单

| 动作 | 禁用条件 | 校验 | 成功后 |
|---|---|---|---|
| 刷新行情 `pp-quote` | 已归档 | 无 | 游标 +1；toast「行情已刷新 · 时点」；若有降级票，逐票列名并警告；口径切「估算…」或「模拟估值暂不完整」 |
| 模拟巡检 `pp-monitor` | 已归档 | 无 | 出信号→研判→执行；每条拒绝都落流水并写中文原因；卖出成交才建复盘 |
| 立即补跑 `pp-run` | 已归档 / 无待处理意图 | 意图队列非空 | 逐条执行 `ppRunIntents:6523`；toast 汇总「成交 N 笔 / 拒绝 M 笔 / 行情降级 …」 |
| 暂停·继续 `pp-toggle` | 已归档 | 无 | 状态改写 + 说明「调度不再触发，历史全部保留」 |
| 新建模拟账户 `pp-new` → `pp-new-save` | — | 名称非空；初始资金 ≥ 1 万（否则「连一手都算不出来」）；巡检间隔 ≥ 5 分钟；研判版本与执行规则版本非空 | 自动带 3 条候选池建仓意图；toast 报账户号与口径 |
| 手动研究取证 `pp-research` → `pp-research-run` | 已归档 | 代码 6 位数字；证据 ≤ 5 条且必须完整 `http(s)`；历史回放必须填冻结快照日期 | 生成取证记录并自动切到该 Tab + 滚动定位；快照日晚于决策时点 → 判 `future_data`，本轮不产生任何意图 |
| 归档账户 `pp-archive` → `pp-archive-confirm` | 已归档 | **两步**：第 1 步只列影响面（停调度 / 保留历史 / 不再估值 / 原因必填），第 2 步才收原因；原因必填 | 状态 `archived`，页面转只读，切到「已归档」视图可见；从第 2 步「返回」可回第 1 步且原因不丢 |
| AI 审核复盘 `pp-review-audit` | 非 pending | 事实闸门优先：缺 `candidate_id/score_id/plan_id/trade_date/fact_as_of` 一律未通过 | 通过→影子「待启动」；未通过→影子「被拦截」；toast 明写「不代表正式规则已采纳（rule_change 没有新增）」 |
| 人工复审 `pp-review-manual` → `pp-review-save` | — | 结论二选一 + **理由必填**（空理由：toast「理由不能为空」，表单不关，状态不变） | 理由按「人工复审：…」原样留痕；通过也只到影子「待启动」 |
| 送入影子验证 `pp-review-shadow` | 影子状态非「待启动」 | 仅 `pending` 可点 | 状态「影子验证中」＋说明「只跟踪假设表现，不改动任何正式规则」 |

---

## 10. 事实隔离与审核链（本项目最硬的红线）

```
模拟成交 → 模拟复盘(pending) → 事实闸门 → AI 审核 → 通过 → 影子验证 → 长期跟踪
                                  ↑ 缺来源就 fail，永远进不了影子
                 人工复审（必填理由）可覆盖 AI 结论，覆盖后依然只进影子
```

- 审核通过**不写** `rule_change`、不改任何阈值。正式规则改动只能走 `#/system/rules` 的人工门禁并留痕（页底闭环条明写）。【口径】
- 人工复审的留痕方式：`audit_reason` 以 `人工复审：` 开头——后端 `_paper_audit_label`（`routes.py:1481`）正是用这个前缀区分「人工复核通过/未通过」与「AI 审核通过/未通过」，`audit_mode` 字段由此推导（`routes.py:1494`）。原型同口径。
- 后端状态词表（落地以此为准）：
  - `paper_review.audit_status ∈ pending / passed / failed`（`repo.py:3613`）
  - `shadow_status ∈ not_started / pending / blocked / active`；审核未通过时后端置 `blocked`（`repo.py:3615-3616`），`mark_paper_shadow` 要求 `audit_status == 'passed'` 否则 409（`repo.py:3640-3646`）
- 原型 ↔ 后端 词表映射（【口径】，别把两套词混用）：

| 语义 | 原型 | 后端 |
|---|---|---|
| 待审 | `audit:'pending'` | `pending` |
| 通过 | `audit:'pass'` | `passed` |
| 未通过 | `audit:'fail'` | `failed` |
| 影子未进入 / 待启动 / 验证中 / 被拦截 | `shadow:'not_started' / 'pending' / 'active' / 'blocked'` | 同字面值 |

> 11-20 修掉的坑：影子状态曾复用账户词表的 `active` / 审核词表的 `pending`，界面显示成「运行中」「待AI审核」。现在走独立词表 `PP_SHADOW_LABELS`（`app.js:5698`）。
> **落地时同样的坑就在眼前**：生产 `PaperTradingPanel.tsx:29` 定义 `active: '运行中'`、`:26` 定义 `pending: '处理中'`，直接拿通用 `label()` 渲染 `shadow_status` 就会复现这个 bug；`ReviewsPage.tsx:1509` 目前是把英文原值 `pending/active` 直接显示。做法：给影子状态单独一张映射表（第 10 节词表列），或后端直接下发 `shadow_status_label`。

---

## 11. 深链与状态恢复

`syncPaperHash`（`app.js:7456`）写、`parseRoute`（`app.js:732-752`）读，参数白名单校验后才生效：

| 参数 | 取值 | 说明 |
|---|---|---|
| `acc` | 账户号 | 命中归档账户时自动把 `view` 切到 `archived` |
| `view` | `current` / `archived` | 账户列表分段 |
| `tab` | `positions/executions/contexts/alerts/reviews` | 五个 Tab |
| `pos` | 6 位代码 | 当前展开的持仓 |
| `filter` | 空 / `filled` / `rejected` / `buy` / `sell` | 流水筛选（本轮补上，之前刷新即丢） |
| `ctx` | 取证记录号 | 直接跳到取证明细并定位 |

默认状态 `app.js:468-474`：`ppAcc:901`、`ppView:'current'`、`ppTab:'positions'`、`ppPos:'603501'`、`ppFilter:''`、`ppForm:null`。【换真接口】落地时用 `useSearchParams` 等价实现，`ctx` 直达要保留（从告警/流水跳取证是排障主路径）。

---

## 12. 视觉与响应式

- 设计令牌沿用原型全局 `:root`（详见 `原型落地指引_v1_方案.md` 第 2 节），本模块 CSS 集中在 `styles.css:1379-1455`（`.pp-*` 共 71 条规则）。
- 状态色语义全局一致：红涨绿跌沿用 A 股习惯，`gold` = 待办/关注，`blue` = 影子验证中，`red` = 拒绝/拦截，`green` = 通过/成交，`mute` = 未进入/已归档。
- 断点：
  - `≤1180px`：`.pp-grid` 2 列
  - `≤700px`：`.pp-grid` 1 列、`.pp-facts` 收紧间距、**`.pp-bar` 页头切换行改为逐条换行**（11-20 修复：390px 下账户芯片＋「我的真实持仓」链接把页面撑到 544px）
- 宽表格（模拟流水 1267px）放横向滚动容器内，页面本身不出现横向滚动条——这是期望行为。
- 已验证宽度：1908 / 1280 / 825 / 701 / 700 / 430 / 390 / 360，`#/paper` 均无页面级横向溢出。

---

## 13. 接口契约映射（落地直接照抄）

| 原型动作 | 后端 endpoint（`app/api/routes.py`） | `web/src/api/paper.ts` |
|---|---|---|
| 列账户（含归档分段） | `GET /paper/accounts:1349` | `paperAccounts({include_archived})` :167 |
| 新建账户 | `POST /paper/accounts:1357` | `createPaperAccount({name, initial_cash})` :169 |
| 页头指标与估值口径 | `GET /paper/accounts/{id}/summary:1371` | `paperSummary` :171 |
| 暂停 / 继续 | `POST /paper/accounts/{id}/status:1382` | `setPaperAccountStatus` :189 |
| 归档 | `POST /paper/accounts/{id}/archive:1394` | `archivePaperAccount(id, reason)` :191 |
| 模拟持仓 | `GET /paper/accounts/{id}/positions:1404` | `paperPositions` :173 |
| 刷新行情 | `POST /paper/accounts/{id}/quotes/refresh:1412` | `refreshPaperQuotes` :187 |
| 手动研究取证 | `POST /paper/accounts/{id}/contexts:1419` | `collectPaperContext` :183 |
| 模拟巡检 | `POST /paper/accounts/{id}/monitor:1432` | `monitorPaper(id, tradeDate?)` :185 |
| 取证列表 / 联网证据 | `GET …/contexts:1442`、`GET …/web-evidence:1448` | `paperContexts` :177、`paperWebEvidence` :179 |
| 模拟告警 / 模拟流水 | `GET …/alerts:1454`、`GET …/executions:1460` | `paperAlerts` :181、`paperExecutions` :175 |
| 立即补跑 | `POST /paper/accounts/{id}/run:1467` | `runPaper` :195 |
| 模拟复盘列表 | `GET /paper/reviews?account_id:1490` | `paperReviews` :193 |
| 新建复盘 | `POST /paper/accounts/{id}/reviews:1502` | （面板侧未用，由卖出链路自动产生） |
| AI 审核 | `POST /paper/reviews/{id}/ai-audit:1513` | `auditPaperReview` :197 |
| 人工复审 | `POST /paper/reviews/{id}/audit:1537`（`verdict ∈ pass/fail`，`reason` **min_length=1**） | `manualAuditPaperReview` :199 |
| 送入影子验证 | `POST /paper/reviews/{id}/shadow:1557`（未通过审核返回 409） | `shadowPaperReview` :201 ← **前端目前没人调用** |

服务层对应：`paper_valuation.py`（估值与降级）、`paper_execution.py`（执行器与拒绝原因）、`paper_analysis.py` / `paper_context.py`（研判与取证）、`paper_monitor.py`（巡检信号）、`paper_web.py`（证据抓取）、`app/agents/paper_review.py`（复盘 AI 审核）。

---

## 14. 现状缺口清单（落地要补的，按优先级）

| # | 缺口 | 证据 | 处置 |
|---|---|---|---|
| 1 | 没有独立路由与菜单入口 | `web/src` 内 `PaperTradingPanel` 只挂在两页 | 新建 `pages/PaperTradingPage.tsx` + 路由 + 侧边栏「今日」组第 4 项 |
| 2 | 面板缺「模拟复盘」Tab | `PaperTradingPanel.tsx:334-349` | 复用 `paperReviews(accountId)`，卡片式（原型 `ppReviewHtml:7072` 为规格） |
| 3 | 影子验证动作无人调用 | `shadowPaperReview` 全仓零引用 | 复盘卡片上补「送入影子验证」，409 时给中文提示 |
| 4 | 中文词表缺 4 个执行器原因键，且 `partial` 含义冲突 | 生产已有映射表 `PaperTradingPanel.tsx:24-47`，但**没有** `single_stock_target_reached / ai_add_blocked_cash_or_lot / ai_reduce_unavailable_or_invalid / ai_reduce_below_one_lot` 四个键（会掉成「暂未记录」）；且生产 `partial = 部分缺失`（行情语义），本模块 `partial = 部分减仓`（动作语义） | 按第 6 节补齐四个键；`partial` 动作不要复用同一个键，改叫 `partial_reduce` 或在动作列单独走 action 词表 |
| 5 | 深链状态不可恢复 | 现有面板用局部 `useState` | Tab / 账户 / 筛选 / 取证记录全部进 URL search params |
| 6 | 键盘换标的、K 线同屏对照未接 | 原型 `app.js:8165` | 与既有 `K线共享组件` 批次一起接 |
| 7 | 两处重复挂载 | `HoldingsPage.tsx:901`、`OverviewPage.tsx:360` | 迁走后只留「AI 模拟操盘 →」入口链接，不删数据口径 |

---

## 15. 落地批次建议

| 批 | 内容 | 可验收标准 |
|---|---|---|
| 批 1 | 独立路由 + 页面壳（页头 6 项状态、四个指标、降级条）；面板从两页摘出改为链接 | 深链 `?acc=&tab=` 可恢复；缺价账户显示 `—` 而不是伪造金额 |
| 批 2 | 持仓 + 流水（筛选、拒绝中文原因、跳取证）+ K 线共享组件接入 | 现金/均价/可卖全部等于流水回放；单票占比 ≤ 20% |
| 批 3 | 取证 + 告警（含手动取证抽屉与 `future_data` 拦截） | 取证记录必带工具链与事实时点；历史回放不得出现未来资料 |
| 批 4 | 模拟复盘 + AI 审核 + 人工复审 + 送入影子验证 | 第 10 节红线全部通过；`rule_change` 表零新增 |

前端边界照仓库纪律：**只改 `web/src/`，不动 `streamlit/pages/`**；交易规则与研判标准表 auto-merge 永不修改。

---

## 16. 验收断言（逐条执行，期望值写死）

### 引擎口径（可纯函数验证，无需 UI）

| # | 断言 | 期望 |
|---|---|---|
| E1 | `ppReplay` 与页面指标同源 | 现金、均价、可卖、已实现全部由 `execs` 重放得到；`state` 里改一个金额必显式走 `ppCommit` |
| E2 | 参考行情不能成交 | `ppExecute(..., {referenceOnly:true})` → `rejected / price_missing` |
| E3 | 缺价不伪造 | 任一持仓 `status:'unavailable'` → `marketValue/equity/pnl` 均为 `null`，标签「模拟估值暂不完整」 |
| E4 | 整手 | 买入股数 `% 100 === 0`；含 5% 容差进位 |
| E5 | T+1 | `available:0` 卖出 → `t_plus_one_or_no_lot` |
| E6 | 不猜比例 | 减仓意图无 `reduceRatio` → `ai_reduce_unavailable_or_invalid` |
| E7 | 涨跌停 | `limitUp` 买入 → `limit_up`；`limitDown` 卖出 → `limit_down` |
| E8 | 单票上限 | `planAllocPct=20` 再加仓 → `single_stock_target_reached`；`planAllocPct=15` 加 10% → 压缩成 5% 并写 note；`ppApplyPlan` 后目标 ≤ 20 |

### 交互与链路（UI 点击验证）

| # | 步骤 | 期望 |
|---|---|---|
| U1 | 点「刷新行情」两次 | 游标推进两次；金额随价格变化；有降级票时 toast 列名并警告 |
| U2 | 点「模拟巡检」 | 信号→研判→执行全链路；每条拒绝都有中文原因；只有卖出成交才新增复盘 |
| U3 | 「归档账户」连点两次 | 第 1 次只出影响面清单，第 2 次才出原因输入；空原因提交被拦（toast「还差归档原因」） |
| U4 | 新建账户填 5000 元 | 被拦：「初始资金至少 1 万元，否则连一手都算不出来」 |
| U5 | 取证选历史回放、日期填到决策时点之后 | 记录被标 `future_data`，本轮零意图，告警写明拒绝原因 |
| U6 | 复盘：AI 审核缺 `score_id` 的条目 | 未通过，影子状态显示「影子验证被拦截」，理由含「事实闸门未通过」 |
| U7 | 复盘：人工复审选通过、理由留空 | toast「理由不能为空」，表单不关，`audit/mode/shadow` 三字段不变 |
| U8 | 复盘：人工复审填理由并通过 | 显示「人工复核通过 + 人工覆盖 AI」，影子「影子验证待启动」，出现「送入影子验证」按钮 |
| U9 | 点「送入影子验证」 | 影子「影子验证中」＋说明「不改动任何正式规则（rule_change 无新增）」 |
| U10 | 全流程任意路径 | `state.rules` 长度不变、复盘队列里不出现 `paper` 行的用户裁决入口（口径见 `原型落地指引_就地裁决与连点_v1.md` 第 3 节） |
| U11 | 深链 `?view=archived&acc=901&tab=contexts&pos=002049&filter=rejected` | 刷新后逐项还原；已归档账户四个动作按钮 disabled |
| U12 | 390px 宽 | 无页面级横向滚动；页头三行堆叠；表格在容器内横滑 |

---

## 17. 原型里哪些是演示逻辑，**不要照搬**

| 原型行为 | 落地要求 |
|---|---|
| 点「刷新行情 / 模拟巡检 / 立即补跑」把 `cursor` +1，用 `slots` 假装交易时间 | 真实行情与调度由后端 `scheduler` 驱动，前端只轮询/失效重取，禁止本地推进时钟 |
| 三个种子账户（901 候选池自主 / 902 现有门禁 / 903 已归档）与 7 格价格序列写死在 `PP_ACCOUNT_SEED:5711` | 全部来自 `/paper/accounts` 等接口；`universe.series` 对应 `paper_quote_snapshot` |
| LLM 意图来自写死的 `acc.intents` 队列 | 走真实研判 Agent；`llm_unavailable` 时不得由代码补意图 |
| `ppReplay` 全量重算代替 `paper_position` 表 | 生产读缓存表，但必须保留一条校验：缓存与回放不一致时以回放为准并报 `AlertLog` |
| 新建账户自动塞 3 条候选池意图、自定义代码造 `自定义标的 123456` 的价格序列 | 生产不允许凭空造标的与行情；无候选就显示空态 |
| 手动取证的证据摘要写「正文在正式端由抓取服务落盘并算哈希」 | 接 `paper_web.py`，展示真实 `excerpt/content_hash/fact_as_of` |
| 网页正文里的指令完全不执行（只当证据） | **这条要保留并且必须落地成约束**：外部正文进 prompt 前按不可信内容处理 |
| 归档时间写死 `2026-11-16 17:30`、复盘时间取 `slots` 值 | 用后端返回的时间戳 |
| 归档"只读"靠禁用按钮实现 | 后端也要拦（`_paper_account_for_request` + 状态校验），前端禁用只是体验 |
| 拒绝原因中文写在前端 `PP_LABELS` | 键名以后端为准，中文映射集中一份常量，勿在组件里散写 |

---

## 18. 原型对照位置（`governance-prototype-v2`）

| 看什么 | 位置 |
|---|---|
| 菜单入口 / 路由 / 渲染挂载 | `app.js:648`、`:732`（参数解析 `:733-752`）、`:7470` |
| 状态默认值 | `app.js:468-474` |
| 规则常量 | `app.js:5663 PP_RULES` |
| 中文词表 / 影子独立词表 | `app.js:5671 PP_LABELS`、`:5698 PP_SHADOW_LABELS`、`:5699 ppShadowLabel` |
| Tab 定义 / 种子账户 | `app.js:5705 PP_TABS`、`:5711 PP_ACCOUNT_SEED`（901/902/903 在 `:5713/5886/5958`） |
| 数据装载与序号 | `app.js:6035 ppData`、`:6055 ppNextId` |
| 行情三态 | `app.js:6081 ppQuote` |
| 账本回放 | `app.js:6118 ppReplay` |
| 估值与降级改名 | `app.js:6169 ppValuation`、`:6164 ppProtect`、`:6028 ppFees` |
| 执行器（含单票上限压缩） | `app.js:6213 ppExecute`、`:6207 ppSlip` |
| 取证 trace / 落库入口 | `app.js:6279 ppDecisionTrace`、`:6301 ppCommit`、`:6349 ppApplyPlan` |
| 研判两变体 | `app.js:6364 ppDecideAI`、`:6407 ppDecideGate` |
| 巡检 / 补跑 / 刷新 | `app.js:6438 ppRunMonitor`、`:6523 ppRunIntents`、`:6599 ppRefreshQuotes` |
| 复盘审核链 | `app.js:6609 ppAuditReview`、`:6635 ppManualReview`、`:6646 ppShadowStart` |
| 页面与分区渲染 | `app.js:6714 renderPaper`、`:6769 ppBannerHtml`、`:6793 ppMetricHtml`、`:6811 ppFactsHtml`、`:6828/6849/6876` 持仓、`:6954` 流水、`:6987/7000` 取证、`:7042` 告警、`:7062/7072` 复盘 |
| 抽屉表单 | `app.js:7116 ppReadForm`、`:7124` 新建、`:7153` 取证、`:7176` 归档两步 |
| toast 汇总 | `app.js:7197 ppRoundToast` |
| 就地操作派发（24 个 `pp-*`） | `app.js:7217-7454` |
| 键盘换标的 | `app.js:8165` |
| 样式 | `styles.css:1379-1455`（`.pp-banner/.pp-grid/.pp-facts/.pp-table/.pp-review` + 1180/700 两个断点；页头换行规则 `:1451-1454`） |

---

## 19. 本轮原型验证记录（2026-11-20）

方法：`node --check app.js` 语法闸门；页面内真点击 + 状态断言；跨文档同源 `iframe` 模拟视口做响应式；内置浏览器的截图在本会话不可信（`visibilityState=hidden` 会返回过期帧），**结论一律以 DOM/状态断言为准**。下表全部在最终构建（词表修复后、全新加载、种子状态未被测试污染）上重跑一遍。

| 组 | 断言 | 结果 |
|---|---|---|
| 引擎 | E1–E8 全量 13 条：现金回放同源、stale 不可成交、unavailable 不伪造、整手、T+1、减仓比例缺失不猜、涨跌停、单票上限拒绝、headroom 压缩正例（要求 10% → 按剩余额度 5% 成交并写明压缩） | 13/13 PASS |
| 复盘链 | 种子条目 8802 直接显示「影子验证被拦截」；U6 事实闸门拦截；U7 空理由被拦且状态不变；U8 人工复审覆盖 → 「影子验证待启动」；U9 送入影子 → 「影子验证中」；取消按钮正常收表单 | PASS |
| 隔离 | 审核前后 `state.rules` 恒为 8，未新增任何规则/建议/经验条目 | PASS |
| 交互 | 切视图 / 切账户 / 五个 Tab / 刷新行情（降级票如实提示「参考行情…不能用于成交」，口径改「估算模拟总资产」） | PASS |
| 深链 | `?acc=901&tab=executions&filter=rejected` 逐项还原（含本轮补的 `filter`） | PASS |
| 响应式 | 1280 / 825 / 701 / 700 / 390 / 360 修复后无页面级横向溢出（390 修复前 544；1908 修复前已验证，新规则只作用于 ≤700px）；390 页头三行堆叠无裁切 | PASS |
| 回归 | 18 条路由全渲染，console 0 error | PASS |

本轮改动（4 处，全部在原型内）：
- `app.js:6757` 页头切换行加 `pp-bar` 作用域类；`styles.css:1451-1454` 窄屏换行规则（只作用于 `#/paper`，其它模块的 `.cp-toolbar` 不受影响）
- `app.js:5697-5699` 影子验证独立词表 `PP_SHADOW_LABELS` + `ppShadowLabel`；`:7082` 复盘卡改用影子专用渲染
- `app.js:6622`、`:6641` 审核未通过时影子状态对齐后端 `blocked`；种子复盘 8802 同步（`app.js:5860`）

遗留（**别的模块**，只报告未改）：`#/candidates` 390px 溢出 41px（表格 `SPAN.mono.dim` 列）、`#/holdings` 390px 溢出 27px（`hd-concl-reds` 风险提示按钮组）。
