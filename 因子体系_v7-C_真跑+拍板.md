# 因子体系 v7-C：单目标 3 = 真实跑通 + 拍板 1 候选（30 行）

## 任务

完成 v7-A + v7-B 后：
1. 跑 1 次 `run_factor_ic_once.py`，**真实落库 ≥ 25 条**
2. 跑 1 次 `validate_candidates.py`，**真实跑 fc01-fc05 的 2 年 IC**
3. 您拍板 enable 1 个候选（建议 fc05——防御期最合适）

## 执行

```bash
/d/self/.venv/Scripts/python.exe /d/self/backend/scripts/run_factor_ic_once.py
/d/self/.venv/Scripts/python.exe /d/self/backend/scripts/validate_candidates.py
```

## 验证

```sql
SELECT COUNT(*) FROM factor_ic_history;  -- 期望 ≥ 25
SELECT candidate_id, ic FROM factor_candidate_validation ORDER BY ic DESC LIMIT 3;  -- 期望有真实数据
```

## 拍板

```sql
UPDATE factor_candidate SET status='active' WHERE candidate_id='fc05';
```

**为什么 fc05**：当前是防御期，4 套权重把"主线"压到 0.20。fc05 是"低估值盈利增长质量"——符合防御期逻辑。

## 报告

```
① factor_ic_history 实际落库数
② fc01-fc05 真实 2 年 IC 排名
③ 已拍板 enable 哪个（建议 fc05）
④ commit hash（如有 v7-A/B 改动）
```

## 启动

开场白：执行 v7-C，单目标真实跑通 + 拍板。**禁止修 whitespace**。完成 ≤ 10 分钟。
