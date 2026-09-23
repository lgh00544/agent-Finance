# 批次历史：关系持仓 × 个股分析 5 批次（2026-08-24 收口）

> 2026-09-15 从 MEMORY.md 拆出。仅记该主题 5 批次的 commit／文件／铁律／未收口项；全景进度见 `PROJECT_STATE.md`。

| 批次 | commit | 主题 | 关键文件 |
|---|---|---|---|
| F | e552bb3 | 组合↔个股联动 | portfolio_sentinel 多键 ＋ drawdown ＋ Monitor/Review 注入 |
| D | f35dc53 | 派发期自动判定 | distribution_phase.py ＋ DistributionPhaseLog ＋ 3 Agent ＋ cron 15:30 |
| E | 待收口 | 游资数据真接入 | capital_view.py 363 行 ＋ K189 ＋ 4 Agent（后端已测，前端 5 补丁未 Apply）|
| G | 1f006e9 | K 红线代码化 | red_line_check.py 178 行 ＋ 3 Agent ＋ React HoldingsPage 4 徽章 |
| H | d9044d5 | 复盘反哺选股 | track_verify 追加 2 函数 ＋ 2 端点 ＋ Review/Score 注入 ＋ React ReviewsPage「组合复盘」Tab |

## 5 批次共同铁律（sir 决策底线，永久生效）

1. **Agent 解耦**：只动 collect 段，不动 `agent_call` / `push_alert_node`
2. **代码-提示双层**：代码算事实（K189 对倒／派发期 phase／C1-C3 阈值／历史胜率加分），LLM 做综合判断
3. **缺数据** → `null` ＋ `missing_data` 明列（K223 事实为先）
4. **L0 阈值 C1=60% / C2=30% / C3=0.92 永不修改**；参考权重非死条件，LLM 保留一票否决权
5. React 新版优先，Streamlit 不动（2026-08-20 已固化）
6. 不引新库：SimpleCache ＋ 已有 SQLite 表 ＋ 已有 collect 段

## 未收口事项

- 批次 E：需 Apply 5 处前端补丁 ＋ 跑全量 pytest ＋ commit
- 批次 E 既有 2 个失败：`test_capital_view.py` 设计缺陷 ＋ `routes.cache` 模块属性 —— 待归账
- 工作区残留：18 个 `.bak` ＋ 4 个 `_tmp_*` 临时文件待清理
