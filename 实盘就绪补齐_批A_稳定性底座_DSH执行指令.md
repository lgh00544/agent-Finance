# 实盘就绪补齐 · 批 A（稳定性底座）· DSH 执行指令

> **§0 元信息**
> 生成者 WorkBuddy（Lark）｜执行端 **DSH**｜决策人 sir｜上游方案 `D:\self\实盘就绪补齐_方案.md` §2 G1
> **执行窗口**：**2026-09-23 及之后**（09-18~09-22 为批 1 观察期冻结期，本批改码+改调度，**冻结期内禁止执行**）
> 关联：`PITFALLS.md` #16 / #20 / #25 / #29 / #31 / #33 / #34

---

## §一 目标

消除「后端死了没人管、job 跑没跑看不见、内存一路涨」三个运行期盲区。

| # | 做什么 | 不做什么 |
|---|---|---|
| A1 | 新建后端进程守护（死亡自动拉起） | ❌ 不改 `main.py` / `scheduler/jobs.py` 的 job 逻辑 |
| A2 | `/api/jobs/status` 补 `last_run` + `last_status`（重启后不丢） | ❌ 不改任何 cron 的触发时间 |
| A3 | 内存增长定位并给结论 | ❌ 不顺手改 `cache.py` 实现 |
| A4 | **告警送达可观测**（方案 §2 G10）：`push_alert` 返回真实投递结果，区分「未配置」与「投递失败」 | ❌ 不改告警的触发条件与消息文案 |

**不做**：不动任何 Agent 判定、不动交易规则、不动前端页面布局。

---

## §二 架构约束

### 2.1 A1 进程守护（**必须独立于后端进程**）

- **新建** `D:\self\scripts\backend_watchdog.ps1`：循环探 `127.0.0.1:8000` → 不通则记录 + 拉起
- **部署方式**：Windows 计划任务（**普通用户交互会话**，非 WorkBuddy 沙箱）——沙箱内启动后端会 `PermissionError [WinError 5] CreateNamedPipe`（PITFALLS #31）
- **铁律**：
  1. 拉起前**先跑** `D:/self/net_check.py`，出网/TiDB 不通则**不拉起**（避免全量同步失败 + `error:universe`）
  2. 冷启动约 **6.8 分钟** bind :8000 → 建立**宽限期**（建议 600s），期内视为"启动中"，**不重复拉起**
  3. 拉起前按 PITFALLS #20 **归档** `backend-dev.stdout.log` / `.stderr.log`（改名带时间戳），否则崩溃现场丢失
  4. 守护自身写独立日志 `D:\self\logs\watchdog.log`，**不写后端日志**
  5. 拉起上限：同一自然日 ≤ 3 次；超过则只告警不再拉起（防"崩-拉-崩"死循环刷爆）

### 2.2 A2 job 可观测（**须重启后不丢**）

- **新建轻量表** `job_run_log`：`job_id`(PK) / `last_run`(DateTime) / `last_status`(String: ok|error) / `last_reason`(String NULL) / `updated_at`
- **挂载点**：`scheduler/jobs.py:908` 的 `BackgroundScheduler` 加 `add_listener`，监听 `EVENT_JOB_EXECUTED` / `EVENT_JOB_ERROR` → upsert 该表
- **暴露**：现有 `/api/jobs/status` 响应中每个 job **追加** `last_run` / `last_status`（**保持 `id` / `name` / `next_run` 字段不变**，前端不破）
- **解耦**：listener 只写 `job_run_log`，**不改任何 job 函数体**
- `last_reason` 取值：复用各 job 已有的 summary/结构化 reason；无则留 `NULL`（K227，不编造）

### 2.3 A3 内存定位（**先定位、后修**）

- **只诊断不修**：采集 `PID` / `RSS(K)` / `cache.SimpleCache` 的 `key 数` 时序，建议 5 分钟粒度连续采集 ≥4 小时
- 采集脚本 `D:\self\mem_probe.py`（只读，**不改后端**）：采样写入 `D:\self\logs\mem_probe.csv`
- 观察对象按嫌疑度：`monitor`（每 3 分钟）/ `portfolio_sentinel`（每 10 分钟）/ `sector_refresh` + `quote_snapshot_refresh`（每 5 分钟）/ `experience_worker_probe`（每 30 分钟）
- **产出结论**：① 增长是「泄漏」还是「稳态后不再涨」 ② 若是泄漏，指出嫌疑 job 与嫌疑缓存 key 前缀 ③ 修复建议（**不在本批实现**）

### 2.4 A4 告警送达可观测（**背景：2026-09-18 批 E 新发现**）

**现状缺陷（实查）**：`services/feishu.py:28 push_alert()`
- 直发通道 `_direct_alert(text)` 的**返回值被丢弃**（`:40`）→ 成功/失败都无痕；且 `_direct_alert` 用 `except Exception` 全吞（`:24`）
- `feishu_webhook_url` 为空时直接 `return False`（`:45`），**与「投递失败」无法区分**
- 当前配置：`FEISHU_BRIDGE_ALERT_DIRECT=true` / `FEISHU_WEBHOOK_URL` **空** → **恒返回 False，但直发实际送达** → `alert_log.pushed` 完全不可信

**要求**：
1. `push_alert` 返回**真实投递结果**：把「直发成功数」与「webhook 结果」分开记录，**不得丢弃 `_direct_alert` 的结果**
2. `_direct_alert` 改为**返回投递结果**（成功条数 / 异常），不再静默吞异常
3. 三种状态必须可区分：`not_configured`（无任何通道）／`delivered`（至少一条通道成功）／`failed`（有通道但全失败）
4. 落库字段：`alert_log` 增 `push_channel`（`direct`/`webhook`/`both`/`none`）+ `push_result`（`delivered`/`failed`/`not_configured`）
5. **同步修 3 处写死 `pushed=False` 的落库点**（`pre_market_screen.py:96`、`portfolio_sentinel.py:422`/`448`）→ 改真实结果
6. **不改**告警触发条件、不改消息文案、不改 `severity` 分级、不动 7 个调用点的位置

---

## §三 规则

| 项 | 值 |
|---|---|
| 探活地址 | `127.0.0.1:8000`（判据见 `net_check.py`） |
| 守护轮询间隔 | 60s |
| 冷启动宽限期 | 600s |
| 单日拉起上限 | 3 次 |
| `job_run_log` 主键 | `job_id`（upsert，不累积历史行） |
| 内存采集粒度 | 5 min，连续 ≥4h |
| 内存达标线 | 24h 增幅 **< 200 MB** |

---

## §四 执行顺序

1. `HEAD` 与工作区现状记录（`git rev-parse HEAD` + `git status --short | wc -l`）
2. **备份先行**：动后端前按 PITFALLS #20 归档当前 `backend-dev.stdout.log` / `.stderr.log`
3. **A1**：写 `scripts/backend_watchdog.ps1` → 注册计划任务 → **实测**：手工 kill 后端 PID → 观察 90s 内是否自动恢复（含宽限期不重复拉起的行为）
4. **A2**：加 `job_run_log` 表（走现有迁移风格，`db/models.py` + `db/session.py`）→ 加 scheduler listener → `/api/jobs/status` 追加字段 → 重启后端 → 观察 1 个盘后窗口，确认 16:00/16:10/16:20/16:30/16:35/16:50 六个关键 job 的 `last_run` 被写入
5. **A3**：写 `mem_probe.py` → 连续采集 ≥4h → 出结论（泄漏 or 稳态 + 嫌疑前缀）
6. **A4**：改 `feishu.py`（`_direct_alert` 返回结果 + `push_alert` 三态）→ `alert_log` 加 2 字段 → 修 3 处写死 `pushed=False` → **实测**：在 webhook 关闭 + 直发开启下，调一次测试告警 → 确认 `push_result=delivered` 且 `push_channel=direct`
7. 报告（≤10 行：改了什么文件 / A1–A4 实测结果 / 遗留风险）

> 步骤 3、4、6 需重启后端 → **必须在 09-23 及之后**，且**避开 16:00–17:15 窗口**（盘后 job 密集期）。

---

## §五 验证清单

- [ ] `scripts/backend_watchdog.ps1` 存在；计划任务已注册且**非**沙箱会话
- [ ] kill 后端 → **90s 内**自动恢复 `127.0.0.1:8000` LISTENING
- [ ] 冷启动宽限期内**未重复拉起**（watchdog 日志可证）
- [ ] 出网不通时**不拉起**（可模拟验证）
- [ ] 单日拉起上限 3 次生效（日志可证）
- [ ] 拉起前归档了 stdout/stderr（归档文件名带时间戳）
- [ ] `job_run_log` 表存在且**重启后 `last_run` 不丢**
- [ ] `/api/jobs/status` 每个 job 含 `last_run` + `last_status`，**`id`/`name`/`next_run` 未被破坏**
- [ ] 6 个关键盘后 job 当日 `last_run` 均写入
- [ ] `mem_probe.csv` 有 ≥4h 数据；给出「泄漏 or 稳态」明确结论
- [ ] `push_alert` 可区分 `not_configured` / `delivered` / `failed` 三态
- [ ] `_direct_alert` 结果**不再被丢弃**；异常不再被静默吞掉
- [ ] `alert_log` 含 `push_channel` + `push_result`，且 3 处写死 `pushed=False` 已改真实结果
- [ ] 实测：webhook 关闭 + 直发开启下，测试告警落 `push_result=delivered` / `push_channel=direct`
- [ ] 告警**触发条件与消息文案未变**（7 个调用点位置未动）
- [ ] `GET /api/health` 返回 ok；`git status` 中**无交易规则/Agent/前端**相关变更

---

## §六 红线

1. **不碰交易规则与研判标准**：K 红线体系、C1–C3（60%/30%/0.92）、`take_profit.py` / `red_line_check.py` / `plan_quant.py` / `candidate_tradeable.py`、`agent_prompts/*.py` 阈值**一律不动**
2. **不改任何 cron 的时间与 id**（`signal_scan` 16:50 / `daily_discover` 16:10 / `market_intel` 16:20 / `monitor` 每 3 min 等一律保持）
3. **不改 Agent 判定逻辑**，不动 `graphs.py:20-32`
4. **守护脚本禁止改后端代码**，只做「探活 → 归档 → 拉起」
5. **不动前端**（`web/src/**` 本批禁止变更）
6. **数据缺失不编造（K227）**：`last_reason` 无值留 `NULL`
7. **不自动 commit / push / tag**（基线锁定在批 C 统一做）
8. **不引新库**（守护用 PowerShell 原生能力；`mem_probe.py` 用 `psutil` 若已在依赖内，否则用 PowerShell `Get-Process` 采样）
9. **不顺手改其他文件**：改动限定在 `scripts/backend_watchdog.ps1`（新建）、`mem_probe.py`（新建）、`backend/app/scheduler/jobs.py`（仅 add_listener）、`backend/app/api/routes.py`（仅 `/api/jobs/status` 追加字段）、`backend/app/db/models.py` + `session.py`（仅加表/迁移）、`backend/app/services/feishu.py`（仅 `push_alert` / `_direct_alert` 返回值与三态）、`backend/app/db/models.py`（`alert_log` 加 2 字段）、`backend/app/services/pre_market_screen.py` + `backend/app/agents/portfolio_sentinel.py`（**仅**改 3 处 `pushed=False` 为新结果，其余不动）
10. **不改告警的触发条件 / 消息文案 / severity 分级**；不改 7 个 `push_alert` 调用点的位置与顺序
11. **改动行数超预算**（简单 ≤50 行业务代码，脚本另计）→ 停下报告 sir

**省 token 约束**：不复读本指令已固化信息（只 `grep` 关键标识确认行号）；不写超范围代码；docstring ≤3 行、函数体内不写注释；复用已有函数与迁移风格；测试不多写；报告 ≤10 行。
