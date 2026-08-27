# 板块轮动 · 实跑验证修复 · Claude Code 执行指令

> 生成者：Lark（2026-08-27）· 执行者：Claude Code · 决策人：sir
> 背景：板块轮动 5 批次（A-E）已落地 commit，实跑验证发现 2 个设计缺口 + 1 个测试残留
> 前置：`D:\self\板块轮动分析_5批次_Claude执行指令.md`（批次实现细节）

## 一、目标（3 步修复）

1. **补丁 1（cron 闭环断链）**：`sector_daily_job`（cron 15:35）拉完快照后**不触发判定+归因** → `sector_daily_rank_log` / `sector_launch_reason` 永远不会被自动填上。修复：refresh 成功后追加调 `run_sector_rotation()`
2. **补丁 2（手动触发不拉快照）**：`POST /api/market/sector-rotation/run` 只判定+归因、**不先 refresh** → 盘中（15:35 前）触发必报「2026-08-27 无全板块日快照」（今日实测）。修复：`_task_sector_rotation` 先 refresh 再 run
3. **清理测试残留**：`data/dev.db` `sector_daily_snapshot` 有 1 条测试假数据 `('2026-08-26','半导体',3.0,1,'em')`（test_sector_daily 写生产库），会污染 3/10/20/60 日窗口规律统计。修复：DELETE 该条

## 二、架构约束

- 只动 2 个文件：`backend/app/scheduler/jobs.py` + `backend/app/api/routes.py`；另清 1 条 DB 数据
- 不动 `run_sector_rotation` / `refresh_sector_daily_snapshot` 内部逻辑（批次 B/C 已验收）
- 不新增测试（改动小，回归验证即可）；不引新库

## 三、规则

- **补丁 1**：`jobs.py:251 sector_daily_job` 的 `if result.get("success"):` 分支内（cache.set 之后），追加：
  - `from app.graph.router import run_sector_rotation`（函数内 import，仿现有风格）
  - `run_result = run_sector_rotation()` 并 `logger.info("板块轮动判定+归因完成: %s", ...)`（成功/失败都记，失败不抛）
  - 保持 finally release_lock 结构不变
- **补丁 2**：`routes.py:105 _task_sector_rotation` 改为：先 `refresh_sector_daily_snapshot()`（结果记入返回 dict 的 `refresh` 字段），再 `run_sector_rotation()`；refresh 失败不中断，把 error 透传
- **清理**：`.venv/Scripts/python.exe` 执行 `DELETE FROM sector_daily_snapshot WHERE trade_date='2026-08-26'`（仅删测试残留，确认无真实数据）

## 四、执行顺序

1. 改 `jobs.py` sector_daily_job（补丁 1，+6 行）
2. 改 `routes.py` _task_sector_rotation（补丁 2，+8 行）
3. 清 DB 测试残留（1 条 SQL）
4. 验证：
   ```bash
   python -m pytest backend/tests/test_sector_daily.py backend/tests/test_sector_rotation.py -q
   python -c "import ast; ast.parse(open('backend/app/scheduler/jobs.py',encoding='utf-8').read()); ast.parse(open('backend/app/api/routes.py',encoding='utf-8').read())"
   ```
   预期：测试全绿 + 语法零错
5. **重启后端**（加载新代码）：杀 8000 端口进程 → `SYNC_ON_START=false .venv/Scripts/python.exe backend/scripts/dev_run.py` 后台起 → 确认 `GET /api/jobs/status` 含「板块轮动日快照」
6. commit：`[板块轮动修复] cron 闭环 + 手动触发先拉快照 + 清测试残留`

## 五、红线

1. 不动批次 B/C 已验收的 `run_sector_rotation` / `refresh_sector_daily_snapshot` 内部逻辑
2. 不新增 LangGraph 节点、不动 agent_call / push_alert_node
3. 不改阈值（churn=0.6 / streak=3）；不改表结构
4. K227：refresh 失败如实返回 error，不编造数据
5. 改动行数预算 ≤ 40 行，超出停下报告

**省 token 6 条**：①不复读 5 批次指令全文，只 grep `sector_daily_job` / `_task_sector_rotation` 定位 ②只动 2 文件+1 SQL ③复用已有 `run_sector_rotation` / `refresh_sector_daily_snapshot` ④docstring ≤3 行 ⑤不新增测试 ⑥报告 ≤10 行

## 六、沟通节点

- 任一验证不通过 → 停手报告 sir
- commit 后 → 报告 commit hash + 测试结果 + 重启确认，停等验收
- 备注：akshare 东财/新浪板块接口当前均拉取失败（返回非 JSON，反爬/网络），真实数据链路待数据源恢复后由 sir 手动触发复核
