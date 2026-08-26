# 板块轮动分析模块 · 5 批次合一 · Claude Code 执行指令

> 生成者：Lark · 执行者：Claude Code/DSH · 决策人：sir · 2026-08-26
> 方案定稿：`D:\self\板块轮动分析_方案.md`（v2，已拍板）· 本指令只放「做什么+规则+顺序+红线」，详细背景/Schema 见方案 §二~§十
> 执行起点：main 最新 · 终点：批次 E 收口 commit（不 push）· 各批次独立 commit

## 一、目标（5 批次）

A 全板块日快照 → B 轮动状态判定 → C 归因子 Agent → D 多窗口规律 → E 注入+前端。
每批次独立可交付、可测试、独立 commit；依赖按序。

## 二、架构约束（解耦铁律）

1. **不新增 LangGraph 节点、不动 `backend/app/graph/graphs.py:20-32` 主图 6 节点**
2. 子 Agent 走独立 `agent_call`（`backend/app/agents/common.py:249`）+ 落库，仿 `router.py:220 run_market_intel` 模式
3. 候选池总 Agent 注入：仿 `discover.py:667` 的 `hot_money_context`/`horizon_context` 文本段模式
4. 不动 `agent_call`/`push_alert_node` 内部逻辑；不碰 `sector_snapshot` 现有表结构（top5 首页热路径零影响）
5. 复用 akshare 既有接口 + SimpleCache，不引新库

## 三、规则（字段/阈值/口径）

**新表 3 张**（见方案 §2.1/2.2/2.3 完整 DDL）：
- `sector_daily_snapshot`：全板块每日快照（change_pct/rank_no/up_count/down_count/volume_ratio/turnover_rate/leading_*，唯一键 trade_date+sector_name）
- `sector_daily_rank_log`：轮动状态（rotation_state/churn_rate/top5_overlap/mainline_sector，唯一键 trade_date）
- `sector_launch_reason`：启动归因（reason_tags/reason_text/**reason_chain**/evidence JSON/confidence，唯一键 trade_date+sector_name）

**阈值（代码定死，调整走 review_log）**：
- churn_rate = 1 − (今日 top5 ∩ 昨日 top5)/5
- `mainline` 主线市：存在板块 streak≥3 且 top3 当日仍在
- `rotation` 轮动市：churn≥0.6 且无 streak≥3 板块；否则 `chaos`

**归因标签**：policy/news/fund/oversold/earnings/overseas/rotation（可多选逗号分隔）

**数据纪律（K227）**：东财缺失字段如实 NULL；reason_chain 引用的每条证据必须是 evidence 里真实字段；缺数据不得编造。

**运行策略（sir 拍板）**：每日固定 1 次 cron（15:35，收盘后），以当日最后一次为准（同 trade_date 删后插）；手动触发 API `POST /api/market/sector-rotation/run`。

## 四、执行顺序

### 批次 A · 数据底座（≤150 行）

1. `backend/app/db/init.sql` 追加 3 张表 DDL（`IF NOT EXISTS` 幂等，仿 `init.sql:255` sector_snapshot）
2. `backend/app/db/models.py` 加 3 个 ORM 类（仿 `models.py:656 SectorSnapshot`）
3. `backend/app/db/repo.py` 加方法（仿 `repo.py:218 upsert_sector_snapshot` 删后插）：
   - `upsert_sector_daily_snapshot(rows)` 全板块
   - `list_sector_daily_by_date(trade_date)` + `list_sector_daily_history(sector_name, days)`
   - `upsert_sector_rank_log(row)` + `get_sector_rank_log(trade_date)`
4. `backend/app/services/sector_daily.py` 新建：`refresh_sector_daily_snapshot()` —— 调 `akshare_source.fetch_industry_spot`（`akshare_source.py:1030`），全板块排序落库（不截取 top5，字段从 `_BOARD_COLS:93` 映射 up_count/down_count/volume_ratio/turnover_rate）
5. `backend/app/scheduler/jobs.py` 注册 cron：`sector_daily_job` 工作日 15:35（仿 `jobs.py:470` market_accuracy 注册写法）
6. 测试 `tests/test_sector_daily.py`：3 例（①全板块落库 N>5 ②删后插幂等 ③缺字段 NULL）
7. 跑绿 + commit `[批次A] 板块轮动：全板块日快照 3 表 + cron`

### 批次 B · 轮动状态判定（≤120 行）

1. `backend/app/services/sector_rotation.py` 新建：
   - `calc_churn_rate(today_top5, yesterday_top5)`
   - `calc_streak(sector_name, days)` 板块连续居 top5 天数
   - `judge_rotation_state()` 状态机（mainline/rotation/chaos），读 sector_daily_snapshot 历史
2. 复用 `akshare_source.fetch_board_box_positions`（`akshare_source.py:1048`）算 top5 板块 10 日/60 日箱位
3. 状态 + 指标落 `sector_daily_rank_log`
4. 测试 `tests/test_sector_rotation.py`：3 例（①churn=1 全换 ②streak≥3 判 mainline ③churn≥0.6 无 streak 判 rotation）
5. 跑绿 + commit `[批次B] 板块轮动：状态机 + churn/streak 指标`

### 批次 C · 归因子 Agent（≤180 行）

1. `backend/app/services/sector_launch_reason.py` 新建：
   - `collect_evidence(sector_name)` 代码层证据：量比/换手/涨跌家数（已落库）+ 领涨股连板（`akshare_source.fetch_daily_kline:924`）+ 主力净流入（`fetch_fund_flow:956`）+ 新闻条数（`fetch_news:1017`）+ 箱位（批次 B）
   - `run_launch_reason(trade_date)` 子 Agent：对 top10 板块各一次 `agent_call`（`common.py:249`，agent="sector_launch_reason"，model_level=LIGHT），输入证据 JSON → 输出 reason_tags/reason_text/**reason_chain**/confidence
   - 落 `sector_launch_reason`（同 trade_date 删后插）
2. `agent_prompts/` 新增 `sector_launch_prompt.py`（SYSTEM + build_prompt）：明确要求 reason_chain 写出「通过什么消息/数据判定」，且证据必须引用 evidence 内字段
3. `backend/app/graph/router.py` 加 `run_sector_rotation(trade_date)`（仿 `router.py:220`）
4. `backend/app/api/routes.py`：
   - `_TASK_KINDS`（`routes.py:62`）加 `"sector_rotation": ("板块轮动分析", ...)`
   - 新增 `@router.post("/market/sector-rotation/run")`（仿 `routes.py:272` market_intel/run）
5. 测试 `tests/test_sector_launch_reason.py`：3 例（①证据采集字段齐全 ②reason_chain 非空且引用 evidence ③删后插幂等）
6. 跑绿 + commit `[批次C] 板块轮动：归因子 Agent + reason_chain + 手动触发`

### 批次 D · 多窗口规律（≤150 行）

1. `backend/app/services/sector_rotation_pattern.py` 新建：
   - 3/10/20/60 日窗口：轮动周期天数、板块累计强度 top10、streak≥5 主线候选、趋势斜率
   - `analyze_patterns(days)` 返回 4 规律：①轮动周期 ②启动→退潮生命周期 ③高切低频次 ④放量+箱位突破次日延续率
2. `backend/app/api/routes.py` 加 `GET /api/market/sector-patterns` + `GET /api/market/sector-rotation`（当日状态+top10+归因）
3. 测试 `tests/test_sector_rotation_pattern.py`：2 例（①窗口统计正确 ②空数据返回空结构不报错）
4. 跑绿 + commit `[批次D] 板块轮动：多窗口规律 + 2 API`

### 批次 E · 注入 + 前端（≤200 行）

1. `backend/app/agents/discover.py` `llm_final`（`:667`）追加 `rotation_ctx` 注入段（仿 `hot_money_context` 模式）：读当日 `sector_rotation_agent` 结果组装文本（rotation_state/churn/mainline/top5 归因），传入 `discover_prompt.build_final_prompt`（`discover_prompt.py:149` 加参数）
2. `backend/app/agents/market_intel.py` collect 段追加：段 10 轮动状态 + 段 11 强势板块归因（缺数据→"（数据缺失）"）
3. `agent_prompts/market_intel_prompt.py` 加 2 行消费说明
4. React `web/src/pages/MarketIntelPage.tsx` 加 Tab「板块轮动」：当日状态徽章 + top10 表 + 归因卡片（可展开 reason_chain）+ 规律表
5. 测试：跑 `tests/test_market_intel.py` 不回归 + `cd web && npm run build` 零错
6. 跑绿 + commit `[批次E] 板块轮动：Discover 注入 + MarketIntel + React Tab`

## 五、红线

1. 不新增 LangGraph 节点、不动 `graphs.py:20-32` 主图
2. 不动 `agent_call`/`push_alert_node` 内部；不碰 `sector_snapshot` 现有表结构
3. 阈值 churn=0.6/streak=3 代码定死，调整走 review_log
4. 不引新库、不接新数据源；React 新版优先，Streamlit 不动（除非 API 变更阻塞）
5. 缺数据如实 NULL/"（数据缺失）"，reason_chain 证据必须真实存在（K227）
6. 改动行数预算：A≤150/B≤120/C≤180/D≤150/E≤200，超出停下报 sir

**Claude Code 端省 token 约束**：
①不复读方案全文，只 grep `sector_daily_snapshot`/`rotation_state`/`reason_chain` 确认行号
②只动本批列出的文件，禁止顺手改其他
③复用 `agent_call`/`upsert_sector_snapshot`/`fetch_industry_spot` 已有实现，禁止重写
④函数 docstring ≤3 行，函数体内不写注释（除关键 trade-off）
⑤测试用例按指令列的数量写，禁止多写
⑥每批报告 ≤10 行：①文件清单 ②测试结果 ③遗留风险

## 六、沟通节点

- 任一批测试不通过 → 立即停手报告 sir，不 commit 半成品
- 任一批 commit 后 → 报告 commit hash + 测试结果，停等 sir 验收进下一批
- 批次 E 收口 → 报告 5 个 commit hash + 全链路验证 + 手动触发 API 可用性，停等 sir 验收
