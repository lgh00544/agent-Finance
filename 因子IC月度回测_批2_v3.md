# 因子 IC 月度回测 · 批 2 v3（codex 极简版）

## §0 任务

36 月回测 + IC/IR/胜率 + 失效判定 + cron + API + 前端 + 5 例单测。**改动 ≤ 437 行**。项目 `D:\self`。

## §一 25 因子清单（必严格按 id）

| 大类 | id | 名称 | 分位 |
|---|---|---|---|
| 动量 | f01-f05 | MA20偏离度/MACD状态/20日收益/量比/威科夫相位 | f01/03/04 |
| 催化 | f06-f08 | 业绩催化/政策催化/行业事件 | - |
| 估值 | f09-f12 | PE/PB/PEG/PS | 全 |
| 资金 | f13-f17 | 主力净流入占比/北向/游资/龙虎榜/融资融券 | f13 |
| 质量 | f18-f21 | ROE/毛利率/经营现金流/资产负债率 | 全 |
| 主线 | f22-f25 | 板块强度/板块资金/轮动位置/板块拥挤度 | f22/23 |

## §二 新增/改

**新建**：
- `backend/app/services/factor_ic.py`（≤ 120）`run_backtest` / `calc_ic` / `calc_ir` / `judge_status`
- `backend/scripts/migrate_factor_ic.py`（≤ 30）
- `backend/tests/test_factor_ic.py`（≤ 80）5 例
- `web/src/pages/FactorIcPage.tsx`（≤ 100）
- `web/src/api/factors.ts`（≤ 30）

**改**：
- `backend/app/scheduler/jobs.py` +5（cron 每月 1 号 02:00 `run_factor_ic_backtest_job`）
- `backend/app/db/models.py` +30（`FactorIcHistory` ORM）
- `backend/app/api/routes.py` +40（`GET /api/factor-ic-history`）
- `web/src/components/layout/SideMenu.tsx` +2（FactorIc 入口）

**不动**：25 因子函数 / factor_registry / LangGraph / score_prompt / LLM Schema

## §三 关键规则

- 回测窗口 36 月 / forward_return 20 交易日 / IC = spearman（scipy）/ IR = 滚动 3 月 / 样本 < 100 不入 IR
- **失效判定**：IC 连续 3 月 < 0.02 → `status='deprecated_candidate'`
- 跑批 ≤ 30 分钟（5000 × 25 × 36）
- **必须复用** `factor_registry.list_active()` + `DataAdapter` + `app.datasource.get_datasource()`
- 缺数据返 None + reason（K227 禁编造）
- 不引新库（scipy + pandas + numpy 已有）
- docstring ≤ 3 行

## §四 6 步执行

1. `FactorIcHistory` ORM + 迁移（30 min）
2. `factor_ic.py` service（2 h）
3. cron + API（45 min）
4. 5 例单测（1 h）
5. 前端 FactorIcPage + SideMenu（1 h）
6. 实跑 1 次 3 年回测，900 条落库验证（30 min）

## §五 验证

- [ ] 表迁移成功
- [ ] 25 因子 × 36 月 = 900 条落库
- [ ] 失效判定正确
- [ ] 5 例单测全过
- [ ] API + 前端展示
- [ ] 跑批 ≤ 30 分钟

## §六 grep 起点

```bash
grep -n "list_active" backend/app/services/factor_registry.py
grep -n "DataAdapter" backend/app/factors/data_adapter.py
grep -n "add_job\|cron" backend/app/scheduler/jobs.py
grep -n "class.*Base" backend/app/db/models.py | head -5
grep -n "list_all_stocks" backend/app/db/repo.py | head -3
```

## §七 commit（完成后给）

```bash
cd /d/self && git add backend/app/services/factor_ic.py backend/app/scheduler/jobs.py backend/app/db/models.py backend/scripts/migrate_factor_ic.py backend/app/api/routes.py backend/tests/test_factor_ic.py web/src/pages/FactorIcPage.tsx web/src/components/layout/SideMenu.tsx web/src/api/factors.ts && git commit -m "[因子IC回测 批2] 月度 cron + IC/IR/胜率 + 失效判定

- factor_ic.py: 36 月回测 + spearman IC + 滚动 3 月 IR + 失效判定
- cron 每月 1 号 02:00 run_factor_ic_backtest_job
- FactorIcHistory ORM + 900 条/3 年落库
- GET /api/factor-ic-history + 前端 FactorIcPage
- 失效: IC 连续 3 月 < 0.02 → deprecated_candidate
- 5 例单测全过"
```

## §八 完成报告

```
① 改了什么（9 文件 path:line）
② 5 例单测 passed
③ 25 因子 × 3 年回测耗时（分钟）
④ IC 排名前 3 / 末 3（仅 ID）
⑤ 失效判定列表
⑥ 遗留风险
```

## §九 省 token 6 铁律

1. 不复读已固化信息
2. 只动 §二 列的文件
3. docstring ≤ 3 行
4. 复用 `factor_registry` + `DataAdapter` + `get_datasource()`
5. 5 例单测不多写
6. 报告 ≤ 10 行

## §十 启动

```bash
codex --approval-mode auto-edit --no-auto-commits --cd D:\self
```

开场白：执行 `D:\self\因子IC月度回测_批2_v3.md`（极简 130 行）。先 grep §六 5 个起点确认行号，禁止 read 全文。完成报告按 §八 6 项 + §七 commit。

**异常熔断（任一即 ctrl+c）**：重新连接 ≥ 2/5 / 30 分钟无文件创建 / 改 LangGraph 或 LLM Schema / 引入新库 / 总耗时 > 2.5 小时 / 改动超 437 行。
