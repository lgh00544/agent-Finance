# 实盘操盘日流程 SOP v1

> 生成：DSH · 批E（实盘闭环 + SOP）｜上游方案 `实盘就绪补齐_方案.md` §2 G6 / §4.3 批 E｜目标时点：2026-10-08 上线
> 定位：**操盘向**（sir 照着走完一天）；治理向见 `系统治理闭环_使用与验收手册.md`
> 铁律：**系统不下单、不改仓、不自动执行**。所有买卖只在券商 App 手动完成，系统只做「记录 + 研判 + 告警」。

---

## 0. 每天开工前 30 秒（任何时段都先做）

| 步 | 动作 | 页面/端点 | 判读 |
|---|---|---|---|
| 0.1 | 后端活着吗 | 系统概览顶栏；`GET /api/health` → `{"status":"ok"}` | 非 ok → 见《异常处置卡》E1 |
| 0.2 | 前端活着吗 | 浏览器打开 `http://localhost:5173` | 白屏 → 见 E1（先查后端，前端 ≠ 后端） |
| 0.3 | 外部连接 | 系统概览「系统状态」卡；`GET /api/system/status` | `数据源/LLM/数据库/向量库` 四项 ok；数据源 detail 写「东财不可达，新浪降级链路正常」= 降级可用，非故障 |
| 0.4 | 今日持仓基线 | 持仓监控页；`GET /api/holdings?status=holding` | **空数组 = 系统侧无有效持仓 → Monitor/Sell/止盈计划/红线全部为空**（实测 2026-09-18 即此状态） |
| 0.5 | 持仓数对不对 | 同上，与券商 App 持仓逐只核对 | 不一致 → 先走 §6「真实成交 → 系统录入」，再谈研判 |

> 2026-09-18 实测：`/api/holdings` 13 条全部 `status=exited`、`shares=0`；`/holdings?status=holding` → []。
> 意味着：**Monitor / Sell / 止盈计划 / 红线扫描当日无输入**，不是系统坏了。

---

## 1. 盘前 08:30–09:25

| 时点 | 看哪个页面 | 端点 | 判读口径 |
|---|---|---|---|
| 08:30 起 | 系统概览 | `GET /api/dashboard` | `modules.system.connections` 全 ok；`modules.datasource_stats` 看 `success_rate_pct / degraded_use`（降级可用 ≠ 故障，见 §7） |
| 08:30 起 | 系统概览 → 市况评分 | `GET /api/market-condition` | `total_score` + `band` + `cap`；**必看 `trade_date` 是否为今日/上一交易日**（2026-09-18 实测返回 `trade_date=2026-09-16`，陈旧 → 只作参考并记「市况评分陈旧」） |
| 09:15 | （同花顺采集 job 已下线，本批不使用） | — | 今日盈亏改「推算」口径（批 D），不以同花顺为准 |
| 09:15–09:25 | 持仓监控 | `POST /api/holdings/{hid}/monitor`（逐只）或页面「全量监控」 | 需 `status=holding`；输出 `action(hold/reduce/exit)` + `severity(info/warning/critical)` |
| 09:25 | 盘前快筛结果 | 告警日志页筛 `盘前快筛`；`GET /api/alerts` | 快筛告警 `pushed=false`→ **不会推到手机**，必须自己看页面；内容读 `message` + `action`（如「集合竞价跌幅 -4.72%，建议今日暂缓」） |
| 09:25 | 候选池怎么筛 | 每日候选池页 | `GET /api/candidates?date=<最新日期>`（先 `GET /api/candidates/dates` 取可用日期）；`GET /api/candidates/tradeable?date=&limit=` |
| 09:25 | 可交易候选状态 | 每日候选池页 | `status=pending` 表示**当日可交易标记尚未生成**（`ensure_if_missing` 触发后才能用）；`count=0` 不得当成「无候选」结论，记 `pending` |
| 09:25–09:30 | 建仓计划 | 建仓计划页 | `GET /api/positions?code=&limit=`；`plan.status=proposed` → 人工决定是否接；接则 `POST /api/plan/{id}/status {status:accepted}` |

**盘前必答（对应执行指令 §3.4）**
1. 市况评分在哪看 → 系统概览「市况评分」卡（`/api/market-condition`），先看 `trade_date` 再看分。
2. 候选池怎么筛 → 每日候选池页；日期用 `/candidates/dates` 给出的最新交易日，`tradeable` 为 `pending` 时不当结论用（K227）。
3. 盘前快筛 9:25 结果怎么看 → 告警日志页 `盘前快筛` 标签；**页面看，不等手机**。

---

## 2. 盘中 09:30–15:00

### 2.1 系统自动在跑什么（不需要手动触发）

| job | 节奏 | 作用 | 备注 |
|---|---|---|---|
| `monitor` | 交易时段每 5 分钟 | 全部有效持仓走 Monitor | 有 `status=holding` 才动 |
| `portfolio_sentinel` | 每 10 分钟 | 组合级风控（回撤/集中度/板块退潮/时间止损） | 有告警才推飞书汇总 |
| `quote_snapshot_refresh` | 每 5 分钟 | 持仓价快照 | — |
| `sector_refresh` | 每 5 分钟 | 板块刷新 | — |

### 2.2 盘中三步

| 步 | 页面 | 端点 | 判读 |
|---|---|---|---|
| 2.2.1 看告警 | 告警日志页（`/alerts`） | `GET /api/alerts?limit=N` | `severity`：`critical`（红，立刻处理）/ `warning`（橙）/ `info`（灰，仅留痕）；`source`：`monitor`=持仓监控、`portfolio_sentinel`=组合哨兵、`pre_market`=盘前快筛（**不推手机**） |
| 2.2.2 看单只结论 | 持仓监控 → 行「详情」 | `POST /api/holdings/{hid}/monitor` | `action`：`hold`=持有 / `reduce`=减仓 / `exit`=清仓；`severity=critical` 优先处理；信息含触发条件与建议动作 |
| 2.2.3 看卖出测算 | 持仓监控 → 详情「卖出决策」 | `POST /api/holdings/{hid}/sell-decision`（异步提交）→ `GET /api/holdings/{hid}/sell-decisions` | 建议 `sell/partial/hold` + 置信度 + 建议股数；**股数必为 100 整数倍**（页面已按手换算） |
| 2.2.4 看止盈档位 | 持仓监控 → 详情「止盈与仓位计划」或系统概览 | `GET /api/holdings/take-profit-plan`（`?force=true` 击穿 10 分钟缓存） | 读 `stop_loss / take_profit / tp1 / tp2 / ladder_stop_*`；空 `rows` = 无有效持仓 |
| 2.2.5 看红线 | 持仓监控行「红线」列徽章 | `GET /api/red_line_check`（全量）/ `GET /api/red_line_check/{code}`（单只） | 徽章四色：绿=无、黄=预警、红=触发、灰=无数据；C1 占比 / C2 日内回撤 / C3 止损 / C4 突破，另 K139 SOP、K226 派发期、K189 对倒。**阈值不可改**：C1 60% / C2 30% / C3 = 成本×0.92 |

### 2.3 加仓/减仓怎么执行（人工动作 → 系统录入）

| 实际动作 | 录入端点 | 必填 | 录入后自动发生 |
|---|---|---|---|
| 买入建仓 | `POST /api/holdings` | `stock_code / stock_name / entry_date / entry_price / shares(>0 且 100 整数倍)` | 生成持仓；建议立即 `POST /holdings/{hid}/monitor` |
| 加仓 | `POST /api/holdings/{hid}/add` | `price / shares(100 整数倍) / trade_date` | 加权成本重算、C3 止损=新成本×0.92、写 `buy` 流水 |
| 减仓 | `POST /api/holdings/{hid}/exit` | `price / shares(100 整数倍) / trade_date` | 写 `sell` 流水；`shares` 清零则置 `exited` 并**自动触发 ReviewAgent 复盘** |
| 修正成本 | `POST /api/holdings/{hid}/cost` | `cost_price(>0) / reason(必填)` | 联动 C3 止损重算、写 `adjust` 流水 |

> 红线纪律：**C3 破位（价 ≤ 成本×0.92）不补仓**；前端录入价低于成本×0.92 会黄字警告，最终以后端为准。
> 当日录入必须与券商 App 完全一致；差异次日按 §6 对账。

---

## 3. 盘后 15:00–17:00

| 时点 | 做什么 | 页面 | 端点 | 判读 |
|---|---|---|---|---|
| 15:05 | 今日盈亏（推算） | 系统概览「今日盈亏」 | `GET /api/account/summary`（含 `pnl`）；`POST /api/account/refresh` 手动刷新 | **推算口径**（批 D 后橙色 Tag），非券商实际值；有疑问以券商为准 |
| 16:00 | T+N 验证 | 评分报告 / 每日候选池 | `GET /api/scores?date=&limit=`；job `track_verify`（16:00） | 看候选池后续 N 日表现；验证结论只在页面看，不改规则 |
| 16:10 | 每日潜力挖掘 | 系统概览任务/trace | job `daily_discover`（16:10） | 失败不影响当日闭环 |
| 17:00 前 | 复盘 | 交易复盘页 | `GET /api/reviews?code=&limit=`；`GET /api/portfolio_attribution?days=30` | 清仓当日 ReviewAgent 已自动落库；读 `pnl_pct / plan_vs_actual / lesson / suggest_*` |
| 17:00 前 | 经验沉淀 | 经验沉淀页 | job `experience_worker`（次日 02:00） | 当日未必产出，次日看 |
| 17:05 | 真实成交 vs 系统持仓对账 | — | `D:/self/.venv/Scripts/python.exe D:/self/holdings_recon.py <券商导出CSV>` | 差异表 `code | 系统值 | 真实值 | 差额 | 判定`；容忍 shares 差 0、cost_price 差 ≤0.001；**脚本只读、不自动修正**，按给出的 `/add` / `/exit` / `/cost` 动作人工修 |
| 17:10 | 记当日日志 | `.workbuddy/memory/<日期>.md` | — | 记：告警条数、执行动作、未解释差异 |

---

## 4. 决策口径（评级/信号/红线在流程中的定位）

**优先级（冲突时从上到下）**

1. **sir 人工判断 + 券商实际持仓** —— 唯一权威。系统不下单。
2. **K 红线体系（L0，不可改）** —— C1 单票占比 60% / C2 日内回撤 30% / C3 止损=成本×0.92；C3 触发即执行，不等 LLM 复核。
3. **Monitor / Sentinel 的 `critical` 告警** —— 立即人工复核并在当日处置。
4. **SellAgent 卖出决策** —— 参考（含置信度与建议股数）；与实际冲突时记入复盘，不盲从。
5. **止盈计划档位** —— 参考（tp1 减 1/3、止损上移成本；tp2 为黄金分割/压力共振）。
6. **市况评分 `band/cap`** —— 决定**总仓位上限**（如 `cap=10` 即中性偏积极）；评分 `trade_date` 陈旧时降级为参考。
7. **评级 A/B/C 与 `signal_trigger` 信号** —— **10-08 前不作为择时依据**：信号批 2 需 ≥1 个月触发数据，到 10-08 仅约 8 个交易日 → 样本 <30 → `insufficient_sample`，无结论（方案 §2 G7）。信号面板只当**事实展示**看。
8. **派发期 / 资本视图 / K139 / K226 / K189** —— 参考权重，LLM 一票否决，不单独触发交易。

**一句话口径**：红线 > 组合/个股 critical 告警 > 卖出决策 > 止盈档位 > 市况仓位上限；评级与信号仅作事实参考，10-08 前不进决策链。

---

## 5. 数据新鲜度红线（K227）

- 每个数都要问「这是哪天的」：市况评分看 `trade_date`、候选池看日期筛选项、告警看 `created_at`、持仓看 `quote_time`。
- 缺失/陈旧一律**照实记录 + 不做结论**，禁止用估算值填补。
- 页面出现 `数据暂未更新（实时源不可用…）`、`数据不足`、`pending`、`null` → 按 §7 处理，不得当作「无风险 / 无候选 / 无告警」。

---

## 6. 真实成交 → 系统录入（每日闭环的入口）

1. 券商 App 导出/抄录当日成交：代码、方向、价格、股数、日期。
2. 按 §2.3 表逐笔录入（买入用 `POST /holdings`，加仓/减仓用 `/add` / `/exit`，成本不符用 `/cost`）。
3. 17:05 跑 `holdings_recon.py`，差异逐条定位；脚本给修正动作，人工执行。
4. 差异未解释完 → 记入当日 memory，次日盘前再核（禁止「先放过」）。

---

## 7. 告警通道现状（2026-09-18 实测 + 批 E-续更正，务必按此预期）

### 7.1 什么会推手机（全量调用点：6 个来源 / 7 处 `push_alert`，逐行实查）

| 来源 | 位置（文件:行） | 触发条件 |
|---|---|---|
| **盘前快筛** | `services/pre_market_screen.py:100` | 当日有异常候选（集合竞价 ±阈值） |
| **市况切换** | `services/pre_market_screen.py:206` | 市况切换 |
| **Monitor 规则兜底** | `agents/monitor.py:273` | LLM 不可用 + 浮亏超硬性阈值（critical） |
| **Monitor 正常信号** | `agents/monitor.py:294 / :302` | LLM 输出 `exit` / `reduce`（或 severity 达 warning/critical） |
| **组合哨兵兜底** | `agents/portfolio_sentinel.py:370` | 组合回撤 / 集中度阈值触发（critical） |
| **组合哨兵正常** | `agents/portfolio_sentinel.py:433` | 组合风控告警（汇总一条） |

去重：`monitor` 按 `code+alert_type+当日`（24h），等级变化可重推（30min 冷却）；组合哨兵汇总当日一次。

### 7.2 确认不推手机

| 项 | 依据 |
|---|---|
| 「止盈触发 / 接近止盈」 | `services/take_profit.py` 全文 **0 处 `push_alert`**（grep 实证）；`_check_tp_alerts` 只 `insert_alert(..., False)` → 仅落库 + 页面 |

> ⚠️ **批 E 更正**：原版 §7 写「盘前快筛不推手机」**是错的**——`pre_market_screen.py:100` 确实调 `push_alert`（异常候选汇总会推手机）。
> 之所以在 DB 上看不出来：`:91-96` 逐条落库时 `pushed=False` 是**写死**的，与推送结果无关。

### 7.3 `pushed` 字段判读口径（重要）

> **`alert_log.pushed` 不可用于判断是否送达。**
> - **3 处写死 `False`**：`pre_market_screen.py:96`、`portfolio_sentinel.py:422`、`portfolio_sentinel.py:448`；
> - **5 处反映 webhook 结果**：`pre_market_screen.py:206`、`monitor.py:273/294/302`、`portfolio_sentinel.py:370/433`；
> - 当前 `FEISHU_WEBHOOK_URL` **为空**（webhook 关闭）+ `FEISHU_BRIDGE_ALERT_DIRECT=true`（直发启用）→ `push_alert` 恒返 `False`。
> 故 **`pushed=false` 恒成立，既不能证明送达、也不能证明未送达**。

**判断送达只能靠三样**：① 手机目视 ② `feishu_sender` 直发日志（`飞书直发成功: <open_id>`）③ 直发接口返回。

### 7.4 通道配置与实测（2026-09-18）

- `FEISHU_WEBHOOK_URL` 空（webhook 关闭）／`FEISHU_BRIDGE_ALERT_DIRECT=true`（直发单聊启用）／`FEISHU_BOT_ENABLE=true`／`FEISHU_ADMIN_OPEN_IDS` 有值。
- 批 E 实测：取 `tenant_access_token` 成功 → `send_text` 返回 `True`（已发 1 条标注「批E告警通道验证」测试消息，手机侧待 sir 目视确认）。
- ⚠️ 已知缺陷（G10，属批 A）：`_direct_alert` 用 `except Exception` 全吞（`feishu.py:24`），open_id 失效/网络失败**静默无声**；`push_alert` 丢弃直发返回值（`feishu.py:40`）→ 系统自己不知道有没有送到。

### 7.5 日志在哪（回溯用）

- 后端日志在**工作区根目录**：`backend-dev.stdout.log`（唯一带时间戳、可回溯）、`backend-dev.stderr.log`（**无时间戳**、多为 tqdm/进度条，判异常只 grep `Traceback`；PITFALLS #30）。`D:/self/logs/*.log` 全是 0 字节旧文件，**不要看**。
- **重启会覆盖 `backend-dev.stdout.log`**（PITFALLS #20）→ 重要现场先复制归档。
- 2026-09-18 实测：stdout 845,988 B / 4,656 行（09-17 20:13:50 → 09-18 13:52:41，约 **1.16 MB/天**）→ 回溯优先 grep `ERROR`/`Traceback` + 查 `alert_log` 表。

---

## 8. 异常

见 `实盘异常处置卡_v1.md`（E1–E6）。任何异常都先在本 SOP §0 做 30 秒自检，再按卡处置。

---

## 9. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1 | 2026-09-18 | 首版（批 E 产出）；基于当日实测端点/字段核对 |
| v1.1 | 2026-09-18 | 批 E-续更正 §7：删「盘前快筛不推手机」（事实错误）、补 7 处推送清单 + `pushed` 判读口径 + 日志位置；保留「止盈不推」并注明依据 |
