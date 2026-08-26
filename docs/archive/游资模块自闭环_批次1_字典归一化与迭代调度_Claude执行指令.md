# 游资模块自闭环修复 · 批次1（字典归一化 + iteration 上线）

## 〇 元信息
执行者：Claude Code / DSH。决策人：sir。目的：让游资模块"自己能跑"——胜率有数据、页面有数字、iteration 自动算。不动上层 Agent 注入。
执行起点：main 最新。原则：最小改动 + 仅修复归一化核心 bug + 复用已有 `_normalize_seat`。

## 一 根因（已实测定位）
- `hot_money_review.py:39 collect_signals` 用 `profile.seat_code`（简称"中信证券上海分公司"）**直接比对** 龙虎榜 `seat_name`（全称"中信证券股份有限公司上海分公司"），永远 0 命中 → 7/7 游资 signals=0 → win_rate_5d 全 null。
- `db/repo.py:1888 _normalize_seat` 已存在并被 `get_profile_by_seat:1868` 复用，**但 service 侧 `collect_signals` 没复用**——只此一处核心 bug。
- 实测：赵老哥「中信证券上海分公司」_normalize → "中信 上海分公司"，龙虎榜 top10 "中信证券股份有限公司上海分公司" → "中信 上海分公司"，归一后命中。

## 二 目标
1. 跑一次 `run_win_rate_iteration` 后，7 个游资 win_rate_5d 至少 1-2 个有数字（不是全 null）
2. `hot_money_win_rate_job` 注册到调度（每日 16:30 收盘后跑）
3. 不动 `aggregate_for_stock`（`map_seat_to_actor` 走 `get_profile_by_seat` 已归一化 OK）
4. 不动任何 Agent prompt、不动 tradeable_view、不动上层业务

**不做什么**：
- 不接第二源（ths/sina，B 类问题，留后续批次）
- 不补 3d 口径（lhb_type 全 1d 是抓取侧问题，留后续）
- 不动 `hot_money.py`（map_seat_to_actor 已 OK）
- 不动任何 Agent 注入
- 不动前端（HotMoneyPage 字段已对齐 DB schema）
- 不改 review_log 外的可追溯字段

## 三 规则
- **归一化函数**：把 `db/repo.py:1888 _normalize_seat` 改为**模块级** `normalize_seat`（去掉下划线，公开），停用词列表不变（"股份有限公司" "有限责任公司" "证券营业部" "营业部" "证券" "分公司"）
- **collect_signals 修复**（`hot_money_review.py:32`）：
  - 把 `profile.seat_code + co_seats` 全部用 `normalize_seat` 归一化
  - 拉 `list_lhb_flows(lhb_type="1d", limit=2000)` 全量（不按席位过滤 SQL）
  - 内存比对：`if normalize_seat(f.seat_name) in {normalized_seats} and net>0`
  - 同一 (stock_code, trade_date) 取最大净买（保留现有逻辑）
- **iteration 调度**（`scheduler/jobs.py`）：
  - 新增 `hot_money_win_rate_job()` 函数：调 `hot_money_review.run_win_rate_iteration()`，异常不抛 + 写 logger
  - 在 `start_scheduler` 注册 cron：工作日 16:30（`daily_discover` 16:10 后 + `market_intel` 16:20 后），misfire_grace_time=3600，id="hot_money_win_rate"，name="游资胜率迭代"
- **测试**：新增 `tests/test_hot_money_signals_normalize.py` 3 例：①赵老哥简称→全称命中（最关键）②国泰君安旧名→国泰海通新名命中（改名兼容）③ 简称"华鑫上海"→全称"华鑫证券有限责任公司绍兴胜利东路证券营业部"**不**命中（主体不一致正确剔除）
- **不污染既有**：4 端点（profiles/flows/traces/win_rate_iteration）签名不动；前端 HotMoneyPage 不动

## 四 执行顺序
1. `db/repo.py:1888` `_normalize_seat` → `normalize_seat`（导出）
2. `services/hot_money_review.py:32-54` 改 `collect_signals`：归一化内存比对
3. `scheduler/jobs.py` 新增 `hot_money_win_rate_job`（仿 `dragon_tiger_job:322` 异常吞掉模式），在 `start_scheduler` 注册 16:30 cron
4. `tests/test_hot_money_signals_normalize.py` 新建 3 用例，跑绿
5. **手动跑一次** `run_win_rate_iteration()`（用 conftest 测试库或本地 sqlite 副本），断言 7 个游资至少 1 个 win_rate_5d 非空
6. 跑既有 `test_hot_money_inject.py` + `test_dragon_tiger_source.py` 全绿（不污染）

## 五 验证清单
- [ ] `normalize_seat("中信证券股份有限公司上海分公司") == "中信 上海分公司"`
- [ ] 赵老哥 collect_signals 返回 ≥1 信号
- [ ] 7 游资 iteration 后 win_rate_5d 至少 1 个非 null
- [ ] 16:30 cron 注册（看 main.py / start_scheduler）
- [ ] 既有 test_hot_money_inject 7 测 + test_dragon_tiger_source 7 测全绿

## 六 红线
1. 不动任何 Agent prompt / collect 段
2. 不改 tradeable_view / 评估级 / upsert 签名
3. 不接第二源 / 不补 3d 口径（留后续批次）
4. React 新版优先，Streamlit 不动
5. 改动预算 ≤ 80 行（实际估计 40-50 行），超出停下报 sir

**Claude 端省 token 约束**：
1. 不复读本提示词（只 grep path:line）
2. 只动 3 文件：repo.py / hot_money_review.py / jobs.py + 新建 1 测试
3. 不写大段注释（docstring ≤ 3 行）
4. 复用已有 `_normalize_seat` 逻辑（改名 + 导出，不重写）
5. 测试 3 例就够（按指令列的 3 例，不多写）
6. 报告 ≤ 10 行：①改了哪几个文件 ②测试结果（绿数/失败数）③ 7 游资 win_rate_5d 实际有数字的数量 ④遗留风险
