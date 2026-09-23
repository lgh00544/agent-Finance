# 因子 IC 回测 · 批 2 收尾 v5（单目标 1 文件 + 1 commit）

## 目标

把当前已落但未提交的代码（factor_ic.py + tests + cron + API 框架）一次性 commit 完结。**不再压行数、不再压红线、不再追"完美"**。

## 已落代码（git status 中）

- `backend/app/services/factor_ic.py`（factor_ic service）
- `backend/tests/test_factor_ic.py`（5 例单测已过）
- `backend/app/scheduler/jobs.py`（+cron 函数）
- `backend/app/db/models.py`（+FactorIcHistory ORM）
- `backend/tests/test_score_factors.py`（修测试）

## 执行 3 步

1. **git status --short** 看实际文件清单
2. **git diff --stat** 确认行数（在合理范围即可，**不**再追求 ≤ 437）
3. **git add + commit** 一把到位（commit 提示词见下）

## 验证（可选）

- `pytest tests/test_factor_ic.py -q` → 期望 5 passed
- `pytest tests/test_score_factors.py -q` → 期望 ≥ 30 passed（之前 32/32）
- 不强求全部 pass；如有 fail 报给 sir 即可

## commit 提示词

```bash
cd /d/self && git add backend/app/services/factor_ic.py \
  backend/tests/test_factor_ic.py \
  backend/app/scheduler/jobs.py \
  backend/app/db/models.py \
  backend/tests/test_score_factors.py \
  backend/scripts/ && \
git commit -m "[因子IC回测 批2] 月度 cron + IC/IR/胜率 + 失效判定 + 修批1测试

- factor_ic.py: 36 月回测 + spearman IC + 滚动 3 月 IR + 失效判定
- cron 每月 1 号 02:00 run_factor_ic_backtest_job
- FactorIcHistory ORM + 5 例单测全过
- 修批1: test_score_factors f05 fixture + f13 缺失路径

阶段 1 基建期批 2（人主导）→ 批 3 自迭代框架"
```

## 报告

≤ 5 行：①改了哪几个文件 path:line ②pytest 数量 ③commit hash ④遗留（如有）

## 启动

```bash
codex --approval-mode auto-edit --no-auto-commits --cd D:\self
```

开场白：
> "执行 `D:\self\因子IC回测_批2_收尾v5.md`（30 行极简）。3 步：git status 看清单 + commit 一把到位 + 报告 ≤ 5 行。**不**再追行数、不再压红线。完成 ≤ 5 分钟。"

**异常熔断**：重新连接 ≥ 2/5 / 引入新库 / 改动 > 800 行（远超合理业务量）/ 总耗时 > 15 分钟。
