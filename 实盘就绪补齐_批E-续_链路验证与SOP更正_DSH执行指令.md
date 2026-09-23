# 实盘就绪补齐 · 批 E-续（链路验证 + SOP 更正）· DSH 执行指令

> **§0 元信息**
> 生成者 WorkBuddy（Lark）｜执行端 **DSH**｜决策人 sir
> 上游：`D:\self\实盘就绪补齐_方案.md`（**§2 G6 修正 + G10 新增 + §5 Go/No-Go 第 8a/9/10/12 条**）
> 前序：批 E 已执行（09-18），本轮为其**修正与补做**
> **前提**：本批**不改任何业务代码**（`push_alert` 可观测性属批 A，不在本批）；可在 09-18~09-22 观察期内执行
> **时间窗**：**避开 16:30–17:15**（探活/扫描/核对窗口），建议 17:20 后或次日 09:30–15:00 之间的非整点时段

---

## §一 目标

批 E 的 dry-run 因「系统内无有效持仓」走不通——**该前提由我方方案设定错误（要求真实持仓，而 sir 10-08 才入市），非执行问题**。本轮按修正口径补做三件事：

| # | 做什么 | 不做什么 |
|---|---|---|
| 1 | **链路验证（Go/No-Go 8a）**：用模拟盘走完 持仓→Monitor→Sell→Review，验证**代码链路通不通** | ❌ 不改代码（可观测性属批 A） |
| 2 | **更正 SOP §7 的事实错误** + 补「什么会推手机」全清单 | ❌ 不重写 SOP 其余部分 |
| 3 | 更新 Go/No-Go 清单第 8a / 9 / 10 / 12 条实测结果 | ❌ 不提前执行批 A–D |

---

## §二 架构约束

- **数据源红线澄清（关键）**：本批**允许**使用模拟盘 `id=30001`（`source_label=AI模拟`）做**链路连通性验证**——原红线禁止的是「用模拟盘**冒充**真实持仓」，**明确标注来源即不构成冒充**。
  - ⚠️ **但报告中每次出现模拟盘数据，必须写明「数据来源=模拟盘 id=30001」**，且**不得**据此产出任何「决策对不对」的结论（本批只验「通不通」）。
  - 若 sir 未认可此口径 → **停止本批**，等 sir 拍板，不擅自执行。
- **只读优先**：能 `GET` 就不用 `POST`；必须走写端点时**限定在模拟盘**，**绝不触碰真实持仓表**（当前为空，无需也不得新建）
- **解释器**：`D:/self/.venv/Scripts/python.exe`｜**环境**：Bash PATH 已损坏 → 用 PowerShell；stdout 不回显 → 落盘再 Read（PITFALLS #33/#34）

---

## §三 规则

### 3.1 链路验证（8a）必查项

| # | 环节 | 端点 | 通过判据 |
|---|---|---|---|
| 1 | 持仓可读 | `GET /paper/accounts/30001/positions` | 返回 rows 非空，字段含 `stock_code`/`shares`/`cost` |
| 2 | 盘中监控 | `POST /paper/accounts/30001/monitor` | 返回 `exit`/`reduce`/`hold` + severity，**无 404** |
| 3 | 卖出决策 | `POST /paper/accounts/30001/monitor` 或 Sell 对应入口 | 给出的**股数为 100 股整数倍**（sir 设计哲学硬要求） |
| 4 | 告警落库 | `GET /paper/accounts/30001/alerts` | 有记录，含 `alert_type`/`severity`/`message` |
| 5 | 成交流水 | `GET /paper/accounts/30001/executions` | 有记录 |
| 6 | 复盘可读 | `GET /paper/reviews` | Review 侧能读到上述记录（证明闭环打通） |
| 7 | 真实持仓空态的**行为正确性** | `POST /holdings/13/monitor`、`/sell-decision` | 应返 **404「持仓不存在或已平仓」**（已在批 E 验证，本轮复述确认即可，**不得为让它通过而新建持仓**） |

### 3.2 SOP §7 更正（事实错误）

**实查铁证**：
- `backend/app/services/feishu.py:28 push_alert()`：① `feishu_bridge_alert_direct=true` → 调 `_direct_alert(text)`，**返回值被丢弃**（`:40`）② `feishu_webhook_url` 为空 → `return False`（`:45`）
- **当前配置**：`FEISHU_BRIDGE_ALERT_DIRECT=true`（直发启用）／`FEISHU_WEBHOOK_URL` **空**（webhook 关闭）／`FEISHU_ADMIN_OPEN_IDS` 有值
- ⇒ **直发单聊实际送达，但 `pushed` 恒为 `False`** → 故「近 30 条 alert_log 全 `pushed=false`」**不能证明未送达**（此判读已在批 E 得出，正确）
- **但 SOP §7「盘前快筛不推手机」是错的**：`pre_market_screen.py:100` 确实调 `push_alert`，只因 `:96` 落库时 `pushed=False` **写死** → DB 上看不出来

**SOP 必须补的「什么会推手机」全清单（7 个调用点，全量实查）**：

| 来源 | 位置 | 触发条件 |
|---|---|---|
| **盘前快筛** | `pre_market_screen.py:100` | 当日有异常候选 |
| 市况切换 | `pre_market_screen.py:206` | 市况切换 |
| Monitor 规则兜底 | `monitor.py:273` | 浮亏超阈值（critical） |
| Monitor 正常 | `monitor.py:294/302` | LLM 输出 exit / reduce |
| 组合哨兵兜底 | `portfolio_sentinel.py:370` | 回撤/集中度（critical） |
| 组合哨兵正常 | `portfolio_sentinel.py:433` | 组合风控告警 |

**确认不推手机**：`take_profit.py`（止盈触发）不在上述 7 处 → SOP §7 该条**正确，保留**。

### 3.3 `pushed` 字段判读口径（写入 SOP）

> **`alert_log.pushed` 不可用于判断是否送达。** 它在 3 处写死 `False`（`pre_market_screen.py:96`、`portfolio_sentinel.py:422/448`），在 5 处反映 **webhook** 结果，而当前 webhook 关闭、走直发 → **恒为 False**。
> 判断送达只能靠：**手机目视** / `feishu_sender` 日志 / 直发接口返回。

---

## §四 执行顺序

1. **前置确认**：`GET /api/health` 200；`GET /api/paper/accounts` 确认 `id=30001` 存在且 `source_label=AI模拟`
2. **链路验证 8a**：按 §3.1 逐项走，**每项留原始响应**（落 `.workbuddy/batchE2_evidence_20260918/`）
3. **SOP 更正**：改 `D:\self\实盘操盘日流程_SOP_v1.md` §7 —— ① 删「盘前快筛不推手机」 ② 补 §3.2 七点推送清单 ③ 补 §3.3 `pushed` 判读口径 ④ 保留「止盈不推」并注明依据（`take_profit.py` 无 push_alert）
4. **更新 Go/No-Go 清单** `D:\self\实盘GoNoGo清单_核对_20260930.md`：第 8a（按本轮结果）、第 9（✅ 通道通过，附依据）、第 10（⚠️ SOP 已更正）、第 12（❌ `pushed` 不可信 → 待批 A）
5. **报告**（≤10 行：8a 逐项结论 / SOP 改了什么 / Go-No-Go 变动 / 遗留风险）

> 时间窗纪律：若当前处于 **16:25–17:15**，**推迟执行**，不得占用探活/扫描/核对窗口。

---

## §五 验证清单

- [ ] `GET /paper/accounts/30001/positions` 非空，字段名已记录
- [ ] Monitor 环节无 404，返回含 `exit/reduce/hold` + severity
- [ ] **卖出股数为 100 股整数倍**（若该环节不给股数，记录"本环节不产出股数"并指出股数由哪一环产出）
- [ ] alerts / executions / reviews 三个 GET 均有记录 → 闭环打通
- [ ] `POST /holdings/13/monitor` 仍返 404「持仓不存在或已平仓」（**未新建任何持仓**）
- [ ] SOP §7 已更正：删错误表述 + 补 7 点推送清单 + 补 `pushed` 判读口径 + 保留「止盈不推」及依据
- [ ] Go/No-Go 第 8a/9/10/12 条已更新实测结果
- [ ] **每处模拟盘数据均标注「数据来源=模拟盘 id=30001」**，且**未产出任何决策结论**
- [ ] `git status` 中 **`backend/app/**`、`web/src/**` 零新增变更**（本批不改码）
- [ ] 未 commit / push / tag；根目录零残留（除目标文档与证据目录）

---

## §六 红线

1. **不碰交易规则与研判标准**：K 红线体系、C1–C3（60%/30%/0.92）、`take_profit.py` / `red_line_check.py` / `plan_quant.py` / `candidate_tradeable.py`、`agent_prompts/*.py` 阈值**一律不动**
2. **不改 Agent 判定逻辑**，不动 `graphs.py:20-32`
3. **不改 `push_alert` / `feishu.py`**（可观测性属批 A，本批只写清事实）
4. **不得新建真实持仓**（`POST /holdings` 本批禁用）；不得触碰真实持仓表
5. **模拟盘使用必须标注来源**，且不得据此产出决策结论
6. **数据缺失不编造（K227）**：缺数据 → `None` + `reason`
7. **不提前执行批 A–D**（改码/重启/基线提交一律 09-23 起）
8. **不 commit / push / tag**
9. **不引新库**；不顺手改其他文件；改动限定在 SOP 文档 + GoNoGo 清单 + 证据目录

**省 token 约束**：不复读本指令已固化信息（只 `grep` 关键标识确认行号）；不写超范围代码；docstring ≤3 行；复用已有脚本（`holdings_recon.py`）；报告 ≤10 行。
