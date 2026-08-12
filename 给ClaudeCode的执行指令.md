# 给 Claude Code 的执行指令（复制整段粘贴到 Claude Code 终端）

## 任务
按以下步骤处理本项目（D:\space\self\self）「每日候选池卡死、8/12 无候选」问题。完整排查结论与方案在 `候选池卡死_排查与优化方案.md`（项目根目录）。请严格按序执行，每步验证后再进入下一步。

## Step 1 · 先读方案
读取 `候选池卡死_排查与优化方案.md`，了解已定位的根因：
- 根因 = 8/12 11:17 手动触发的 discover 任务卡死（status=running 2 小时未完成），占着 daily_pipeline 任务锁，后续 discover 全部 409 拒绝 → 候选池停在 8/10。
- 慢的根因 = discover 威科夫阶段对 300 只股票逐个拉 400 天 kline，东财主源降级时 15s 超时 × 300 只拖死。

## Step 2 · 应急恢复（先让 8/12 候选池出来）
1. 用你平时的同一套方式重启后端（你之前是通过 Git Bash `SYNC_ON_START=false ./.venv/Scripts/python.exe backend/scripts/dev_run.py` 拉的）。**重启务必确认**：
   - 彻底停掉当前所有后端实例（`Get-NetTCPConnection -LocalPort 8000` 确认 8000 已被释放，PID 98488 及 bash 拉起的 104608 那组都要清干净）；
   - 只启动一个后端实例，不要多开。
2. 启动后验证后端起来了（`http://127.0.0.1:8000` 可访问）。
3. 手动触发 discover：
   ```
   POST http://127.0.0.1:8000/api/jobs/discover/run
   ```
   - 期望返回 `task_id`（不能再 409）。
4. 轮询直到完成：
   ```
   GET http://127.0.0.1:8000/api/tasks/recent?limit=3
   ```
   - 看到 `daily_pipeline` 任务 `status=done` 且 `error` 为空。
5. 确认真实落库：
   ```
   GET http://127.0.0.1:8000/api/jobs/status    → last_discover 有今天日期
   ```
   并在数据库确认：
   ```
   SELECT MAX(trade_date), MAX(created_at) FROM stock_candidate;
   ```
   应出现 `2026-08-12`。
6. 若仍卡死：看 `data/logs/app.log` 是否又有「kline 已降级到备用接口」刷屏；若东财持续降级，先暂停并回报，不要反复重试。

## Step 3 · 根治（重点，防止再发生）
按方案 B 实施，代码改动如下：

### 3.1 后台任务卡死超时终结（backend/app/services/task_queue.py）
- 给 long-running 任务（daily_pipeline / monitor_all）设**超时上限 30~40 分钟**。
- 超时未完成 → 强制 `status=failed, error="timeout"` 并**释放 active/task lock**，让新 discover 可提交。
- 新增**手动取消接口** `POST /api/tasks/{tid}/cancel`，允许 kill 掉 running 状态的卡死任务（当前 running 无法干预，只能等）。

### 3.2 discover 数据获取整体超时 + 容错（backend/app/agents/discover.py:_fill_wyckoff_columns）
- 300 只威科夫计算整体加**超时预算（10 分钟）**，超时未算完的股打 WARNING 跳过/用空结构列继续，绝不无限等。
- 单请求超时 `15s → 5s`（backend/app/datasource/akshare_source.py）。

### 3.3 多实例防护（可选但推荐）
- 后端启动时检测 8000 端口已被占用则**拒绝再启动**（防止 run_dev.bat 和 Claude Code 各拉一份、两个 APScheduler 抢同一把 daily_discover 锁）。

## Step 4 · 验证清单（全部通过才交付）
- [ ] `POST /api/jobs/discover/run` 返回 task_id（不再 409）。
- [ ] 单次 discover 东财正常时几分钟内完成，`status=done`。
- [ ] `stock_candidate` 出现 `trade_date=2026-08-12`。
- [ ] `GET /api/jobs/status` 的 `last_discover` 不再是 null。
- [ ]（可选）任务超时会自动释放锁，新 discover 可正常提交。

## 约束
- 所有改动先备份原文件（cp 一份 .bak），改完向我（父亲）展示 diff 确认后再生效。
- 不要改动数据库结构、不要动 .env、不要动与本次问题无关的代码。
- 遇到阻塞（东财持续降级、重启起不来、验证不通过）先停下回报，不要盲目重试或带病继续。
