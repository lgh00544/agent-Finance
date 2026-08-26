# Scheduler 当日状态诊断 · 单步排查（Claude Code）

## 〇 元信息
执行者：Claude Code。决策人：sir。目的：5 分钟内搞清楚"今天 0 候选/0 评分"的根因 —— 是 scheduler 没起、cron 未触发，还是端点未生成？纯只读诊断，不动任何代码。

## 一 目标
回答 4 个问题：
1. scheduler 进程是否在线？
2. 已注册哪些 cron？最近一次触发时间？
3. 今日 0 候选/0 评分的根因（cron 没跑 / 跑了失败 / 跑了没数据）？
4. 龙虎榜/游资 16:30 cron 是否触发？游资 win_rate_5d 为何仍 0/7？

**不做**：不动代码 / 不修 cron / 不改模型 —— 仅诊断报告。

## 二 调研入口（按顺序）

### 入口 1：scheduler 进程状态
```bash
# 后端是否在跑
curl -s http://localhost:8000/api/scheduler/status 2>&1 | head -30
# 或
ps -ef | grep -iE "uvicorn|fastapi|scheduler" | grep -v grep
```

### 入口 2：已注册 cron 列表
- 读 `backend/app/scheduler/jobs.py` 全文 grep：
  - `scheduler.add_job(.*?id="(.*?)"` → 所有注册 ID
  - `cron` 触发时间表达式
- 关键 cron ID 应包含：`daily_discover` / `market_intel` / `dragon_tiger` / `hot_money_win_rate` / `experience_worker`

### 入口 3：worker_run / job_status 最近执行
```bash
cd backend && /d/self/.venv/Scripts/python.exe -c "
from app.db.session import SessionLocal
from app.db.models import WorkerRun, JobStatus
from sqlalchemy import select, func, desc
with SessionLocal() as db:
    for M in [WorkerRun, JobStatus]:
        print(f'=== {M.__name__} ===')
        for j_name in ['daily_discover','market_intel','dragon_tiger','hot_money_win_rate','experience_worker','score_loop']:
            rows = db.execute(select(M).where(M.job_name==j_name).order_by(desc(M.started_at)).limit(3)).all()
            for r in rows:
                print(f'  {j_name}: start={r.started_at} status={r.status} err={getattr(r,\"error\",\"\")[:50]}')
"
```

### 入口 4：今日实际产出查表
```bash
cd backend && /d/self/.venv/Scripts/python.exe -c "
from app.db.session import SessionLocal
from app.db.models import Candidate, StockScore, LhbOriginalFlow
from sqlalchemy import select, func
import datetime
with SessionLocal() as db:
    today = datetime.date.today().isoformat()
    print('today =', today)
    for M in [Candidate, StockScore, LhbOriginalFlow]:
        if hasattr(M,'trade_date'):
            n = db.execute(select(func.count()).select_from(M).where(M.trade_date==today)).scalar()
            print(f'  {M.__name__}.trade_date={today}: {n}')
"
```

## 三 报告格式（≤ 20 行）

Claude Code 完成后输出 markdown 表格：

| # | 问题 | 答案 | 证据（path:line 或 curl 输出） |
|---|---|---|---|
| 1 | scheduler 是否在线 | ✅/❌ | `/api/scheduler/status` 输出 |
| 2 | 已注册 cron 列表 | N 个 | `jobs.py:Lstart-Lend` |
| 3 | 今日 0 候选根因 | 一句话结论 | worker_run.status / error |
| 4 | 今日 0 评分根因 | 一句话结论 | 同上 |
| 5 | 龙虎榜今日新增 | N 行 | lhb_original_flow |
| 6 | 游资 win_rate_5d 0/7 原因 | 是否 iteration 真跑过 / 数据不够 / 函数报错 | collect_signals 干跑结果 |

末尾追加 1 行「结论 + 下一步建议」。

## 四 红线
1. **绝不修改任何文件**——纯只读
2. **绝不重启 scheduler / backend**
3. **绝不写新代码**
4. **绝不删任何记录**

## 五 Claude 端省 token 约束
①不复读本提示词（只 grep `path:line`）②每个入口输出 ≤ 5 行 ③报告 ≤ 20 行 ④失败信息原文贴出，不解释 ⑤发现根因后不写修复方案（留 sir 拍板）。
