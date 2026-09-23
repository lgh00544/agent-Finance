# 因子 IC 实跑回测 · 批 2 v4（独立会话极简版）

## §0 任务

独立会话：实跑 1 次 3 年回测 + 落库 + 失效判定。**已落代码**：
- `backend/app/services/factor_ic.py`（已建 + 测试通过）
- `backend/app/db/models.py`（FactorIcHistory ORM 已加）
- `backend/app/scheduler/jobs.py`（cron 函数已加）
- `backend/tests/test_factor_ic.py`（5 例已过）

**改动 ≤ 150 行**（仅 cron 配置 + 1 个回测触发脚本）。

## §一 目标

1. 写 1 个回测触发脚本（≤ 60 行）：调 `factor_ic.run_backtest()` 全量跑 3 年
2. 实跑 1 次，落 900 条到 `factor_ic_history` 表
3. 写 1 个简版 cron 调度配置（≤ 30 行）
4. 报告耗时 + 排名前 3 / 末 3 因子 ID

## §二 新增

- `backend/scripts/run_factor_ic_backtest.py`（≤ 60）单文件可执行
- `backend/scripts/migrate_factor_ic.py`（≤ 30）如未建则建表

## §三 实现要点

- **直接调** `from app.services.factor_ic import run_backtest`
- **跑批预算**：5000 股票 × 25 因子 × 36 月 ≤ 30 分钟
- **批量写入**：每 1000 条 commit 一次（防事务过大）
- **进度日志**：每跑完 1 月 print 1 行
- **不引入新库**（pandas + numpy 已有）

## §四 5 步执行

1. 检查 `factor_ic_history` 表是否存在（无则跑迁移脚本）
2. 写 `run_factor_ic_backtest.py`：调 service + 进度日志 + 批量 commit
3. **不**修改 cron 配置（已加在批 2 主体）
4. 实跑：`/d/self/.venv/Scripts/python.exe backend/scripts/run_factor_ic_backtest.py`
5. 验证落库：`SELECT COUNT(*), MIN(period), MAX(period) FROM factor_ic_history`

## §五 验证

- [ ] 表存在或迁移成功
- [ ] 跑完 3 年 36 月回测
- [ ] 落库 ≥ 800 条（25 因子 × 36 月）
- [ ] 耗时 ≤ 30 分钟
- [ ] 5 例 test_factor_ic.py 全过

## §六 grep 起点

```bash
grep -n "def run_backtest\|def calc_ic" backend/app/services/factor_ic.py
grep -n "FactorIcHistory\|factor_ic_history" backend/app/db/models.py
ls backend/scripts/ | grep -E "factor|migrate"
```

## §七 完成报告

```
① 改了 2 个文件（path:line）
② 表迁移 + 落库条数
③ 3 年回测耗时（分钟）
④ IC 排名前 3 / 末 3 因子 ID
⑤ 失效判定（deprecated_candidate）数量
⑥ 遗留风险
```

## §八 commit 提示词

```bash
cd /d/self && git add backend/scripts/run_factor_ic_backtest.py backend/scripts/migrate_factor_ic.py && git commit -m "[因子IC回测 批2 实跑] 36 月回测脚本 + 迁移

- run_factor_ic_backtest.py: 调 service 全量跑 3 年
- migrate_factor_ic.py: 建 factor_ic_history 表
- 实跑结果: 900 条落库 / 耗时 X 分钟
- IC 排名前 3: fXX fXX fXX / 末 3: fXX fXX fXX
- 失效判定: X 个因子标 deprecated_candidate"
```

## §九 启动

```bash
codex --approval-mode auto-edit --no-auto-commits --cd D:\self
```

开场白：
> "执行 `D:\self\因子IC实跑回测_批2_v4.md`（独立 50 行）。先 grep §六 3 个起点确认行号，禁止 read 全文。完成报告按 §七 6 项 + §八 commit。"

**异常熔断**：重新连接 ≥ 2/5 / 30 分钟无进展 / 引入新库 / 改动 > 150 行 / 总耗时 > 45 分钟。
