# 关系持仓批次 D · 后半段续跑 · Claude Code 执行指令

> 生成：Lark · 执行：Claude Code（D:\self）· 决策：sir · 方案：`关系持仓_个股分析_优化方案.md` §三模块1
> 前提：前半段已在你工作区落地（distribution_phase.py / models / init.sql / session / repo / monitor.py collect 已改），本指令只补后半段。**已改文件禁止重写，直接复用。**
> 起点：§一下面第 1 项 · 终点：commit（不 push，等 sir 新会话验收）

## 一、后半段范围（6 项，按序做完一起 commit）

1. **`agents/sell.py` collect 注入**：在 `portfolio_risk_context` 后追加 `distribution_phase_context`，调 `compute_distribution_phase(symbol, trade_date)`，读 `phase_label/confidence/six_dim`，`missing_data` 并入。
2. **`agents/score.py` collect 注入**：collect_data 里 `state["distribution_phase_context"]` = 计算结果；`llm_score` 的 data_pack 带上；phase≥2 时作为风险提示（评分上限 -10，**不单独占一维**）。
3. **`api/routes.py` 加路由**：`GET /api/distribution_phase/{stock_code}` 返回完整 6 维 + phase + confidence；query `?force=true` 跳缓存（仿已有 profile 端点风格）。
4. **`scheduler/jobs.py` 加 cron**：`distribution_phase_job`，每日 15:30，遍历"今日候选 + 当前持仓"逐只判定，结果落 `distribution_phase_log` 表；注册到 job_status（仿 `sector_refresh_job` 的 `:228` + `:395/:423`）。
5. **新建 `tests/test_distribution_phase.py` ≤ 5 用例**：①6维时间计算正确 ②缺数据→null+missing_data ③缺3维→confidence低+phase_label加`?` ④路由返回完整6维 ⑤3 个 collect 段正确注入字段（monitor 已改，用 mock 验证 sell/score）。
6. **跑测试 + commit**：
```
pytest tests/test_distribution_phase.py -v
pytest tests/ -v
mypy backend/app/services/distribution_phase.py
```
预期：`test_distribution_phase.py` 5 passed，全量回归不引入新失败，mypy 零错。通过后 commit（不 push）：
```
git add -A
git commit -m "[批次D] 派发期自动判定落地：6维计算 + DistributionPhaseLog 表 + 3 Agent 注入 + 路由 + cron"
```

## 二、红线（与主指令一致）

1. 不动 agent_call / push_alert_node
2. 不碰交易规则表（6 维阈值参考非死条件）
3. 不编造数值（缺→null+missing_data）
4. 不动 Streamlit
5. 不引新库（仿 sector_snapshot 走 SQLite）

**Claude Code 端省 token**：①只补后半段 6 项，禁止重写前半段已改文件 ②复用已有函数（`compute_distribution_phase`/`_ensure_distribution_phase_table`/`sector_refresh_job` 模板） ③docstring ≤3 行，函数体内不写 # 注释 ④测试 ≤5 个 ⑤报告 ≤10 行（改了什么+测试结果+遗留风险）。**代码侧最小改动 ≤150 行**，超出→停下报告 sir。

## 三、沟通节点

完成 6 项 + commit 后，报告①改了哪些文件 ②测试结果（5 passed / 全量 N passed）③遗留风险。遇字段含义不清→停下问；遇红线触碰→立即停。等 sir 新会话独立验收，确认后再进批次 E。
