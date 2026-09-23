# 实盘就绪补齐 · 批 E-续2（持仓链运行级验证 / Go-No-Go 8a）· DSH 执行指令

> **§0 元信息**
> 生成者 WorkBuddy（Lark）｜执行端 **DSH**｜决策人 sir
> 上游：`D:\self\实盘就绪补齐_方案.md`（**§2 G6 修正 v2 + G11 新增**）
> 前序：批 E、批 E-续 已执行；本轮为 **8a 的第二次修正**（第一版选错验证对象）
> **前提**：**不改任何业务代码**；**生产库（TiDB ＋ `data/dev.db`）零变更**
> **时间窗**：避开 16:30–17:15；建议 17:20 后或次日 09:35–14:30

---

## §一 目标与背景

### 1.1 为什么重做 8a

第一版 8a 用**模拟盘**验证链路，理由是"它有数据"。实查证明**两条链不同**：

| 链路 | 入口 | 说明 |
|---|---|---|
| **sir 实盘链** | `routes.py:1618 graph_router.run_monitor(hid)` → LangGraph → `agents/monitor.py` | **sir 10-08 要走的就是这条** |
| 模拟盘链 | `paper_monitor.py:115` → `paper_analysis.monitor_position()` | 仅复用 `agents.monitor._trade_math`（纯计算），**不含 live quote/news/repository 节点** |

⇒ **用模拟盘验不出实盘链的问题**；且模拟盘链当前本身是坏的（`3/3 status=error`，见方案 G11 / B5）。

### 1.2 本批要做什么

用 **本地 SQLite 副本库 + 副本内演练持仓**，对 **sir 实盘链**做**运行级**验证 —— 生产库与 `holdings` 表**全程不动**，验证后丢弃副本。

| # | 做什么 | 不做什么 |
|---|---|---|
| 1 | 建副本库 + 演练持仓 | ❌ 不碰 TiDB；不碰 `data/dev.db`；不 `POST /holdings` |
| 2 | 运行级跑通 `run_monitor` / Sell / 止盈 / 红线 | ❌ 不改任何业务代码、不加测试用例进仓库 |
| 3 | 校验输出齐全性 + 100 股整数倍 | ❌ 不产出「决策对不对」的结论 |
| 4 | 更新 Go/No-Go 第 8a 条 | ❌ 不执行批 A–D |

---

## §二 架构约束

### 2.1 副本隔离（**本批最关键**）

- **复用已有机制**：`backend/scripts/dev_run.py:74-85 _init_local_schema()` 展示了「把 `db_session.engine` 重绑到本地 SQLite 再还原」的既有做法；`sync_manager.local_engine()` 负责定位本地 SQLite
- **做法**：把本地 SQLite **复制**为 `data/chain_verify_<YYYYMMDD>.db`（若有 `-wal`/`-shm` 一并复制），让本次验证**只读写副本**
- **生产库零变更验收**：跑前记录 `data/dev.db` 的 md5 + 行数；跑后**必须一致**
- **禁止**：改 `sync_manager.py`、改 `dev_run.py`、改 `config.py` 的默认值

### 2.2 演练持仓标注（防污染底线）

- 副本内插入的持仓行**必须**在 `note` 字段写明 `演练-批E续2-<日期>-非真实持仓`
- `entry_date` 用**最近交易日**；`shares` 用 **100 的整数倍**（建议 200）
- `stock_code` 选**主板票**（如 600xxx），避免涨跌停口径混淆
- 只插 **1 条**

### 2.3 不做决策结论

本批只验「**链路通不通 / 输出全不全**」，**不得**对演练持仓的 signal 做任何「该不该卖」的判断。

---

## §三 规则

| # | 验证环节 | 判据 |
|---|---|---|
| 1 | `graph_router.run_monitor(hid)` | **无异常抛出**；返回含 `holding_signal` |
| 2 | signal 字段齐全 | 含 `action` ∈ {exit, reduce, hold} + `severity` + `message` |
| 3 | **股数 100 整数倍** | 若该环节产出股数 → 必须 `% 100 == 0`；若不产出，**明确指出股数由哪一环产出**并单独验该环（对齐 sir 设计哲学：展示层只给可执行数字） |
| 4 | Sell 决策 | 走 SellAgent 入口能产出 `sell`/`partial`/`hold` + 置信度；`partial` 时必须带可执行股数 |
| 5 | 止盈计划 | `take_profit` 分档产出（TP1/TP2/移动止盈档位）齐全 |
| 6 | 红线检查 | `red_line_check` 产出 C1–C3 判定，字段齐全 |
| 7 | 落库留痕 | 监控/决策记录正确写入**副本**（非生产库），可读回 |
| 8 | **生产库零变更** | `data/dev.db` md5 + 行数跑前跑后一致；TiDB 无写入 |
| 9 | 副本清理 | 验证后删除 `data/chain_verify_*.db`（含 `-wal`/`-shm`） |

---

## §四 执行顺序

1. **前置**：`net_check.py` 四项全通（本环节依赖行情源 + LLM）；记录 `data/dev.db` 的 md5 + 行数
2. **建副本**：复制本地 SQLite → `data/chain_verify_<YYYYMMDD>.db`（含 `-wal`/`-shm`）
3. **写验证脚本** `D:\self\chain_verify.py`（**新建，落 `D:\self\`，不进 `backend/`**）
   - 复用 `dev_run.py:74-85` 的重绑手法，把 engine 指向**副本**
   - 插 1 条演练持仓（按 §2.2 标注）→ 逐项跑 §3 的 1–7 → 打印结构化结果
   - 结束后清理副本内的插入行（副本反正要删）
   - 用法：`D:/self/.venv/Scripts/python.exe D:/self/chain_verify.py`
4. **跑验证** → 原始输出落 `.workbuddy/batchE2b_evidence_20260918/`
5. **清理**：删副本（含 `-wal`/`-shm`）；**复验 `data/dev.db` md5 与行数未变**
6. **更新** `D:\self\实盘GoNoGo清单_核对_20260930.md` 第 8a 条（附逐项结果 + 证据路径）
7. **报告**（≤10 行：8a 逐项结论 / 生产库零变更证明 / 遗留风险）

> 若步骤 3 发现需要改业务代码才能跑通 → **停下报告 sir**，不在本批改码。

---

## §五 验证清单

- [ ] 副本 `data/chain_verify_*.db` 已建立；`data/dev.db` **md5 跑前跑后一致**
- [ ] 演练持仓仅 1 条，`note` 含 `演练-批E续2-<日期>-非真实持仓`，`shares % 100 == 0`
- [ ] `run_monitor(hid)` 无异常，返回含 `holding_signal`
- [ ] signal 含 `action` + `severity` + `message`
- [ ] **股数 100 整数倍**：已验，或明确指出产出环节并已单独验证
- [ ] Sell 决策链路产出齐全（`partial` 时含可执行股数）
- [ ] 止盈分档产出齐全
- [ ] `red_line_check` C1–C3 字段齐全
- [ ] 副本内留痕可读回
- [ ] **TiDB 与 `data/dev.db` 均无写入**（md5/行数双证）
- [ ] 副本已清理，无 `-wal`/`-shm` 残留
- [ ] `git status` 中 **`backend/app/**`、`web/src/**` 零变更**；新增仅 `D:\self\chain_verify.py`
- [ ] 未 commit / push / tag

---

## §六 红线

1. **不碰交易规则与研判标准**：K 红线体系、C1–C3（60%/30%/0.92）、`take_profit.py` / `red_line_check.py` / `plan_quant.py` / `candidate_tradeable.py`、`agent_prompts/*.py` 阈值**一律不动**
2. **不改任何业务代码**（含 `sync_manager.py` / `dev_run.py` / `config.py`）；发现需改码 → 停下报告
3. **生产库零变更**：不写 TiDB、不写 `data/dev.db`、不 `POST /holdings`、不调任何写生产库的端点
4. **演练持仓必须标注**（`note` 字段），且只存在于副本
5. **不产出决策结论**：只验"通不通 / 全不全"
6. **数据缺失不编造（K227）**：缺字段 → 记为缺失并如实报告，不补值
7. **不提前执行批 A–D**；不 commit / push / tag；不引新库；不顺手改其他文件
8. **新增文件仅** `D:\self\chain_verify.py` + 证据目录；**不进 `backend/tests/`**
9. 改动行数超预算（脚本 ≤150 行）→ 停下报告 sir

**省 token 约束**：不复读本指令已固化信息（只 `grep`/`Read` 关键行确认）；不写超范围代码；docstring ≤3 行；复用已有函数（`dev_run.py` 重绑手法、`sync_manager.local_engine()`、`graph_router.run_monitor`、`repo.*`）；报告 ≤10 行。
