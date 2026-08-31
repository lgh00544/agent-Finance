# 批次 C' · 行情结构识别层 · Claude Code 执行指令

## §0 元信息

生成者：WorkBuddy。执行者：Claude Code / DSH。范围：仅 C'。
原则见 `D:\self\AGENTS.md`，详细口径见 `D:\self\行情结构与板块轮动前瞻_调整方案.md`。

## §一 目标

新建 `services/sector_regime.py`、`sector_regime_forecast` 表/ORM/repo，
输出并落库：

```text
current_regime: mainline / rotation / chaos
regime_stage: start / confirm / accelerate / diverge / fade / unknown
regime_confidence: 0~1
forward_bias_t1: continue / switch / fade / uncertain
forward_bias_t3: continue / switch / fade / diverge / uncertain
forward_bias_t5: mainline_confirm / new_mainline_switch / fade / invalid_rotation / uncertain
evidence
```

不做：D' 板块级前瞻、E'-1/E'-2 验证、F' 注入和前端、原 C 归因子改造、
LangGraph 主图节点、`agent_call`、`sector_snapshot` 首页热路径。

## §二 架构约束

- 新文件：`backend/app/services/sector_regime.py`，≤150 行，docstring ≤3 行。
- 新表：`sector_regime_forecast`，DDL 见调整方案 §4.1，追加 `backend/app/db/init.sql`。
- 新 ORM：`SectorRegimeForecast`，放在 `SectorDailyRankLog` 后。
- 新 repo：`upsert_sector_regime_forecast(row)`、`get_sector_regime_forecast(trade_date)`。
- 新 job：`sector_regime_job`，工作日 15:40。
- 复用 B 的 `calc_churn_rate`、`calc_streak(days=10/20)`、
  `list_sector_daily_by_date`、`list_sector_daily_history`、
  `list_sector_daily_dates`、`fetch_board_box_positions`。
- 不改 `discover.py` 的 `build_rotation_context` 调用点。
- C' 必须独立于原 C 归因子；归因子失败不能阻断 C'。

## §三 规则

### 3.1 窗口

- `3d`：最近 3 个交易日 top5 churn 平均。
- `10d`：最近 10 日最高连续 top5 天数及主线板块。
- `20d`：今日 top3 在最近 20 日进入 top5 的频率。
- `60d`：top5 板块 60 日箱位中位数。

### 3.2 evidence

`evidence` 必须包含：

```text
top5_churn_3d
leader_streak_max_10d
leader_streak_sector
top3_persistence_20d
breadth_expansion_10d
volume_confirm_3d
box_position_median_60d
```

数据不足仍落库，设置 `evidence.data_insufficient=true`、`confidence=0.2`。
箱位失败时 `box_position_median_60d=null`，不阻断状态判定。

### 3.3 current_regime

- `mainline`：`leader_streak_max_10d >= 3` 且 `top3_persistence_20d >= 0.6`。
- `rotation`：`top5_churn_3d >= 0.6` 且 `leader_streak_max_10d < 3`。
- 其他：`chaos`。

### 3.4 regime_stage

仅 mainline 使用；rotation/chaos 固定 `unknown`：

- `start`：streak=2。
- `confirm`：streak≥3 且主线仍在今日 top3。
- `accelerate`：streak≥3、`volume_confirm_3d > 0.2`、箱位≥0.7。
- `diverge`：streak≥3 且 `top5_churn_3d >= 0.5`。
- `fade`：streak<3 且箱位≥0.7。
- 其他：`unknown`。

### 3.5 forward_bias

- t1：`continue | switch | fade | uncertain`
- t3：`continue | switch | fade | diverge | uncertain`
- t5：`mainline_confirm | new_mainline_switch | fade | invalid_rotation | uncertain`
- t3/t5 是 t1 的细化，不要求三窗口枚举互斥。

按 regime/stage 的纯代码规则确定；证据冲突或样本不足使用 `uncertain`。

### 3.6 confidence

- mainline：`min(1, 0.7 + 0.1*min(streak, 3))`。
- rotation：`min(0.8, 0.5 + 0.1*min(churn*10, 3))`。
- chaos：`0.4`。
- `data_insufficient=true` 时覆盖为 `0.2`。

## §四 实现参考

风格沿用 `backend/app/services/sector_rotation.py`：纯代码、repo、
`logger.warning` 降级。调度参考 `backend/app/scheduler/jobs.py` 的现有 cron。
repo 仿 `upsert_sector_rank_log`，同日期删后插。

## §五 执行顺序

1. `init.sql` 末尾追加 `sector_regime_forecast` DDL。
2. `models.py` 加 `SectorRegimeForecast`。
3. `repo.py` 加 upsert/get。
4. 新建 `sector_regime.py`，实现 `judge_regime()`。
5. `jobs.py` 注册工作日 15:40 的 `sector_regime_job`。
6. 新建 `tests/test_sector_regime.py`，覆盖：
   - 主线确认；
   - 轮动加速；
   - 混沌数据冲突；
   - 单日强势不判主线。
7. 只运行 `backend/tests/test_sector_regime.py -q`。
8. 手跑 `judge_regime()`，确认 evidence 7 字段齐全。
9. commit：
   `feat(regime): batch C' 行情结构识别层`
   不 push。

## §六 验证清单

- [ ] init 增量成功
- [ ] ORM 无循环引用
- [ ] repo get/upsert 可调用
- [ ] 4 个测试通过
- [ ] scheduler 可见 `sector_regime_job`，时间 15:40
- [ ] evidence 含 7 个必需字段
- [ ] 未新增 LangGraph 节点
- [ ] 未调用 agent_call
- [ ] 未修改 sector_snapshot
- [ ] commit 不 push
