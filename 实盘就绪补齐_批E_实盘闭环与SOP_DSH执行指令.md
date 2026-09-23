# 实盘就绪补齐 · 批 E（实盘闭环 + SOP）· DSH 执行指令

> **§0 元信息**
> 生成者 WorkBuddy（Lark）｜执行端 **DSH**｜决策人 sir｜上游方案 `D:\self\实盘就绪补齐_方案.md`
> **冻结期批次**：本批**不改任何业务代码**（仅新增只读脚本 + 产出文档），可在 09-18~09-22 观察期内执行。
> 目标时点：2026-10-08 实盘上线前完成。

---

## §一 目标

把「系统能给决策」变成「sir 每天能照着做，且做的内容基于真实持仓」。

| # | 做什么 | 不做什么 |
|---|---|---|
| 1 | 真实持仓 dry-run：1–2 只**真实已持仓**票走完 建仓→Monitor→Sell→Review | ❌ 不改 `agents/*`、不改 `services/{take_profit,red_line_check,plan_quant,candidate_tradeable}.py` |
| 2 | 建立「真实成交 vs 系统持仓」对账口径 + 只读对账脚本 | ❌ 不改 `holdings` 相关端点逻辑 |
| 3 | 验证飞书盘中告警能到手机 | ❌ 不改 `monitor_job` / `portfolio_sentinel_job` 逻辑 |
| 4 | 产出《实盘操盘日流程 SOP》 | ❌ 不新增后端路由 |
| 5 | 产出《异常处置卡》 | ❌ 不 commit / push / tag |
| 6 | 产出《10-08 Go/No-Go 清单》核对结果 | ❌ 不引新库 |

---

## §二 架构约束

- **新建对象**：仅 2 个只读脚本 + 3 份文档，落 `D:\self\`
- **解耦铁律**：
  - 只读脚本**禁止写任何表**（含 `signal_trigger` / `holdings` / `review_log`）
  - 只读脚本禁止调 `tradeable_view()`（`ensure_if_missing` 会触发 ~900 次 DB 查询，PITFALLS #3）
  - 脚本只读 TiDB/SQLite + `/api/*` 只读端点，不碰后端进程
- **解释器**：`D:/self/.venv/Scripts/python.exe`（**不是** `python`）
- **环境**：Bash 工具 PATH 已损坏（PITFALLS #33）→ 一律用 PowerShell；PowerShell stdout 不回显（#34）→ **结果落盘再 Read**

---

## §三 规则

### 3.1 dry-run 用票选择

- 从 `GET /holdings` 取**真实持仓**（`is_paper=false` 或等价标识，按实际字段名）
- 选 **1 只主板 + 1 只创业板/科创板**（覆盖 ±10% 与 ±20% 涨跌停口径）
- **禁止用 paper_accounts（模拟盘）数据冒充真实持仓**

### 3.2 对账口径

```
对账项 = 每只持仓的 (stock_code, shares, cost_price)
真实侧 = sir 实际成交（券商 App 导出 / 手工录入，作为基准）
系统侧 = GET /holdings 返回
差异容忍 = shares 差 0 股；cost_price 差 ≤ 0.001
```
- 差异输出：`code | 系统值 | 真实值 | 差额 | 判定`
- **不自动修正**，只报告 + 给出修正动作（`POST /holdings/{hid}/add` 或 `/cost`）

### 3.3 告警到达验证

- 触发方式：**用 1 只持仓临时设一个必触发的红线条件**（如把成本改成远高于现价使浮亏超阈值）→ 等下一个 `portfolio_sentinel` 巡检周期（每 10 分钟）或手动 `POST /holdings/{hid}/monitor`
- 判据：手机飞书收到告警，且内容含股票名/触发条件/建议动作
- **验证完必须把成本改回真实值**（用 `/cost` 端点），并在报告中记录"已还原 + 还原后值"

### 3.4 SOP 必含时段

| 时段 | 必答问题 |
|---|---|
| 盘前 08:30–09:25 | 看哪个页面？市况评分在哪看？候选池怎么筛？盘前快筛 9:25 结果怎么看？ |
| 盘中 09:30–15:00 | 告警在哪个页面？Monitor 结论怎么读（exit/reduce/hold + severity）？加/减仓怎么执行？ |
| 盘后 15:00–17:00 | T+N 验证、复盘、经验沉淀各在哪？今日盈亏（推算）怎么读？ |
| 异常 | 见 §四 异常处置卡 |

---

## §四 执行顺序

1. **探测现状**
   - `GET /api/health`、`GET /api/jobs/status`（46 job）
   - `GET /holdings`：列出现有持仓及字段（`stock_code` / `shares` / `cost_price` / 是否有 paper 标识）
   - 确认 `GET /holdings/{hid}/trades`、`GET /holdings/take-profit-plan`、`GET /red_line_check/{stock_code}` 均有数据返回
2. **dry-run（逐票、逐环节留档）**
   - 建仓：对 1 只真实持仓调用 `POST /holdings/{hid}/monitor` → 记录 `exit/reduce/hold` + severity
   - 卖出决策：`POST /holdings/{hid}/sell-decision` → 记录 `sell/partial/hold` + 置信度 + 股数（**须是 100 股整数倍**）
   - 止盈计划：`GET /holdings/take-profit-plan` → 记录各档价位
   - 红线：`GET /red_line_check/{stock_code}` → 记录 C1–C3 触发情况
   - 流水：`GET /holdings/{hid}/trades` → 记录条数
   - 复盘：确认 Review 侧能读到上述记录
   - **全部只读/查询 + 必要的决策端点，不真正改持仓股数**
3. **写只读对账脚本** `D:\self\holdings_recon.py`
   - 输入：真实侧 CSV（路径由 sir 提供，缺则用 `--dry` 用系统值自比对验证脚本本身）
   - 输出：差异表 + 判定 + 建议动作；**只读不写**
   - 用法：`D:/self/.venv/Scripts/python.exe D:/self/holdings_recon.py <csv路径>`
4. **告警到达验证**（按 §3.3，验证完还原）
5. **写 3 份文档**（落 `D:\self\`）
   - `实盘操盘日流程_SOP_v1.md`（§3.4 四时段 + 每步的页面/端点/判读口径 + 决策口径一节：评级/信号在流程中的定位）
   - `实盘异常处置卡_v1.md`（≥6 类异常：进程死 / 断网 / TiDB 挂 / 数据缺失陈旧 / job 未跑 / 告警重复；每类给「识别特征 → 立即动作 → 禁止动作」）
   - `实盘GoNoGo清单_核对_20260930.md`（按方案 §5 十一条逐条填实测结果 + Go/No-Go）
6. **报告**（≤12 行：dry-run 结论 / 对账脚本路径+首跑结果 / 告警是否到达 / 3 份文档路径 / 遗留风险）

---

## §五 验证清单

- [ ] `GET /holdings` 返回真实持仓（非 paper），字段名已记录
- [ ] 2 只真实票的 `monitor` / `sell-decision` / `take-profit-plan` / `red_line_check` / `trades` 全部有返回且留档
- [ ] `sell-decision` 给出的股数为 **100 股整数倍**
- [ ] `holdings_recon.py` 首跑输出差异表，脚本**零写操作**（跑前后 `holdings` 行数不变）
- [ ] 手机飞书收到 1 条盘中告警；成本已还原为真实值并二次核对
- [ ] 3 份文档落 `D:\self\`，SOP 含四时段 + 决策口径，处置卡含 ≥6 类异常
- [ ] 全程未改业务代码（`git status` 中 `backend/app/**`、`web/src/**` 无新增变更）
- [ ] 未 commit / push / tag

---

## §六 红线

1. **不碰交易规则与研判标准**：K 红线体系、C1–C3 阈值（60%/30%/0.92）、`take_profit.py` / `red_line_check.py` / `plan_quant.py` / `candidate_tradeable.py`、`agent_prompts/*.py` 阈值**一律不动**
2. **不改 Agent 判定逻辑**，不动 `graphs.py:20-32` LangGraph 节点
3. **只读脚本禁止任何写库**；不动后端进程、不重启
4. **数据缺失不编造（K227）**：缺数据 → 输出 `None` + `reason`，禁止估算/填充
5. **告警验证必须还原**：改动过的 `cost_price` 必须还原并二次核对
6. **不新增后端路由**；不引新库；不顺手改其他文件
7. **不 commit / push / tag**
8. 改动行数超预算（脚本 ≤120 行、文档不计）→ 停下报告 sir

**省 token 约束**：不复读本指令已固化信息；不写超范围代码；docstring ≤3 行、函数体内不写注释；复用已有函数（`holding_view.py` / `portfolio_summary.py` / `paper_valuation.py:42 fetch_quotes()` 同款报价链）；测试不多写；报告 ≤12 行。
