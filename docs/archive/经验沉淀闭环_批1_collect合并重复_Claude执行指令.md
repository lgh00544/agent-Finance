# 经验沉淀闭环 · 批 1(collect 段合并重复)— Claude Code 执行指令

## 〇 元信息
执行者:Claude Code。决策人:sir。范围:**根因修复**,合并重复 pending,experience 增量从 0.29% → 5%/日。原则:不引新库、Agent 解耦、扩字段读时兼容、Worker 行为不变、改 ≤ 80 行。

## 一 目标
**`pending_experience` 进池前合并重复信号**,让 Worker 处理到的不再是"5 条相同的 000725 hold"而是"1 条 000725 hold ×5 次"。

**具体目标**:
- 同 `(stock_code, signal_type, hour_bucket)` 已 pending → 不 insert 新行,改为更新 `artifacts_ref`(扩展为 JSON)
- 旧数据兼容:读时 try JSON / except 走 int 旧逻辑
- LLM 看到 `count≥3` 持续信号 → 标 `worth=True`(给批 2 铺垫)
- 经验增量 1 周内 ≥ 50 条

**不做**:不动 Worker / 提示词 / Agent 核心 / 前端 / M5。

## 二 架构约束
- **入口**:`db/repo.py:2055 add_pending_experience` 是唯一调用点(`graph/router.py:83`)
- **改 2 文件 + 1 测试**:
  - `db/repo.py:2055-2063` 改 `add_pending_experience` 函数体(扩 artifacts_ref + 加合并查询)
  - `db/repo.py` 加 `merge_pending_duplicate(task_id, stage, summary, artifacts_ref)` 辅助函数
  - `tests/test_pending_dedup.py` 新建,5 测试
- **不引新库** —— 复用 SQLite + JSON 字段
- **artifacts_ref 字段**:`Integer → Text` 兼容方案 —— 旧数据是 int,新数据是 `JSON {count, first_at, last_at, stock_code, signal_type}`
- **不动 Worker**:`_process_item` 行为不变,只是 source 数据更干净

## 三 规则

### 3.1 数据契约(artifacts_ref 扩字段)

| 形态 | 数据 | 含义 |
|---|---|---|
| 旧(兼容)| 整数 | 单次事件 ID |
| 新(本批)| `JSON {count, first_at, last_at, stock_code, signal_type, original_ref}` | 聚合后的事件 |

`stock_code` + `signal_type` 从 `summary` 解析(`"000725 监控信号 hold"` → stock_code=000725, signal_type=hold)。

### 3.2 合并规则(在 `merge_pending_duplicate` 内)
- `summary` 形如 `"{stock_code} 监控信号 {signal_type}"` → 走合并
- 其他形态(`候选 N 只` / `评分 N 分` / `建仓方案 N 批`)→ 不合并,直接 insert 新行
- 合并键:同 `(stock_code, signal_type, hour_bucket=floor(now, 1h))` 已有 pending → 更新 count++,不 insert
- `hour_bucket` 默认 1 小时(可后续改成 4h,本批先 1h)

### 3.3 5 个测试(必须全过)
1. **无重复**:首次 insert → 走原逻辑,count=1
2. **同 hour 重复 1 次**:第 2 次 insert → 合并,count=2,**不新增行**
3. **同 hour 重复 3+ 次**:第 4 次 insert → 合并,count=4,**仍只 1 行**
4. **不同 hour 不合并**:跨 1h 边界 → 新行
5. **不同 signal_type 不合并**:同票 `hold` vs `reduce` → 各 1 行

测试用 `repo.add_pending_experience` + `repo.list_pending_experience` 串行调,每次用独立 test_id(task_id 加随机后缀),不污染 DB。

### 3.4 兼容性(读侧)
- `Worker` 读 `artifacts_ref` 时:try `json.loads` 成功 → dict,失败 → int 旧逻辑
- `route_draft` 看 `draft.confidence`(LLM 输出),不直接看 artifacts_ref → **不动**

## 四 执行顺序
1. 读 `db/repo.py:2055-2063` 全文 + `db/models.py:580 PendingExperience` schema
2. 加 `merge_pending_duplicate` 辅助函数(8-12 行)于 `add_pending_experience` 之前
3. 改 `add_pending_experience`:
   - 解析 summary 拿 stock_code + signal_type
   - 命中合并键 → UPDATE(原 id 行的 artifacts_ref + count)+ 跳过 INSERT
   - 未命中 → 原逻辑 INSERT,artifacts_ref=JSON {count:1, first_at:now, last_at:now, ...}
4. 新建 `tests/test_pending_dedup.py`,5 测试
5. `cd backend && .venv/Scripts/python.exe -m pytest tests/test_pending_dedup.py -q` → 5 passed
6. 跑回归:`test_experience_worker` / `test_review_log` 必须仍绿
7. 跑一次真实 worker 跑通,DB 中重复 pending 应合并

## 五 验证清单
- [ ] `merge_pending_duplicate` 函数存在
- [ ] 5 测试全过
- [ ] 同 hour 同 signal 重复 5 次 → DB 仍 1 行,artifacts_ref.count=5
- [ ] 跨 hour 同 signal 重复 5 次 → DB 5 行
- [ ] 旧数据(artifacts_ref=int)读不报错
- [ ] Worker 回归测试全过
- [ ] 真实跑一轮后 experience 增量 ≥ 1(批 1 单独 + 1,批 2 + N)

## 六 红线
1. **绝不动 Worker**(`experience_worker.py` 全文件)
2. **绝不动 Agent 核心**(`graph/router.py` 路由逻辑)
3. **绝不动前端**
4. **绝不动 EXTRACT_SYSTEM**(批 2 才动)
5. **绝不删旧数据** —— 读时 JSON 兼容
6. **绝不引新库** —— 用 SQLite + JSON 字段
7. 改动 ≤ 80 行(超出停下报 sir)

**Claude 端省 token 约束**:①不复读本提示词(只 grep path:line)②只动 `db/repo.py` + 1 新测试 ③不写大段注释(docstring≤3行)④复用 `add_pending_experience` 已有逻辑,只插入合并层 ⑤测试不超 5 个 ⑥报告 ≤ 10 行(改了哪些文件/5 测试结果/Worker 回归/真实合并数)。
