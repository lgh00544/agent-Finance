# 批次 G' · 板块标签 + 下一个风口预测 · Claude Code 执行指令

## §0 元信息
生成者：WorkBuddy。执行者：Claude Code / DSH。范围：仅 G'，不动 H'。
原则：见 `D:\self\AGENTS.md`（省 token + 最小改动）。
依赖：D' 板块前瞻已落地（sector_forward_view.py 已有 _score 返回 continuation_prob / exhaustion_risk / chase_risk / switch_candidate），**禁止重算这 4 个数**。

## §一 目标
在 D' 已算的 4 个硬指标基础上派生 5 色板块标签 + 新增"下一个风口"预测表，落库 + scheduler 15:50 job。
不做：Agent 注入（H' 范围）/ 前端（H' 范围）/ LangGraph 主图节点（红线 1）/ agent_call（红线 2）/ sector_snapshot 热路径（红线 3）。

## §二 架构约束
- 新文件：`backend/app/services/sector_next_hot.py`（≤ 100 行，docstring ≤ 3 行）
- 改 `backend/app/services/sector_forward_view.py`：`_score()` 末尾追加 `sector_tag` 派生（≤ 20 行新增）
- 改 `backend/app/db/init.sql` 末尾追加 2 张 DDL：`ALTER TABLE sector_forward_forecast ADD COLUMN sector_tag ...` + `CREATE TABLE sector_next_hot ...`
- 改 `backend/app/db/models.py`：SectorForwardForecast 加 `sector_tag` 字段；SectorDailyRankLog 后追加 `SectorNextHot` ORM
- 改 `backend/app/db/repo.py`：追加 `upsert_sector_next_hot(rows: list[dict])` + `list_sector_next_hot_by_date(date, limit=5)`
- 改 `backend/app/scheduler/jobs.py`：注册 `sector_next_hot_job`，cron `mon-fri 15:50`，紧跟 sector_forward 15:45
- 复用：`sector_forward_view._score()` 返回的 4 指标 / `repo.list_sector_daily_by_date(date)` / `repo.upsert_sector_forward_forecast()` 已有 upsert 风格
- 解耦：不改 LangGraph / 不改 discover.py / score.py / position.py / market_intel.py（H' 才动 Agent 注入）

## §三 规则

### 3.1 5 色板块标签派生（sector_tag 单选）
- `one_day_fly` 一日游：chase_risk >= 0.6 AND top10_freq_10d < 0.3 AND streak < 2
- `low_buy` 短线低吸：exhaustion_risk < 0.4 AND continuation_prob >= 0.5 AND box_position_60d < 0.6
- `fade_warn` 警惕退潮：exhaustion_risk >= 0.6
- `mainline_seed` 主线雏形：switch_candidate == True AND continuation_prob >= 0.5 AND streak >= 2
- `accelerate_warn` 高潮追高：regime_stage == "accelerate" AND chase_risk >= 0.5
- 多个触发 → 优先级：mainline_seed > fade_warn > accelerate_warn > low_buy > one_day_fly
- 都不满足 → `none`

注意：以上条件涉及的 4 个数必须从 D' `_score()` 返回的 dict 取，**禁止重算**。

### 3.2 sector_next_hot 表
```sql
CREATE TABLE IF NOT EXISTS sector_next_hot (
    id INT PRIMARY KEY AUTO_INCREMENT,
    trade_date VARCHAR(10) NOT NULL,
    sector_name VARCHAR(64) NOT NULL,
    rank_no INT NOT NULL,
    hot_score FLOAT NOT NULL,
    expected_horizon_days INT NOT NULL,
    confidence FLOAT NOT NULL,
    trigger_evidence JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_snh_date_name (trade_date, sector_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE sector_forward_forecast ADD COLUMN sector_tag VARCHAR(16) NOT NULL DEFAULT 'none';
```

### 3.3 hot_score 公式（仅基于 D' 已有数据）
```
hot_score = 0.40 * (1 if switch_candidate else 0)
          + 0.30 * top10_freq_10d
          + 0.20 * continuation_prob
          + 0.10 * (1 - current_rank_no / 80)
```
clamp 到 [0, 1]。

### 3.4 expected_horizon_days 公式（硬规则加成）
起始 1，触发任一加 / 减：
- switch_candidate = 1：+2
- top10_freq_10d >= 0.7：+2；0.5~0.7：+1
- 当前 rank_no 11~30：+0；31~50：-1；>50：-2
- regime=mainline 且当前不在 top10：+1
- regime=rotation/chaos：-1
- clamp 到 [1, 5]

### 3.5 候选筛选
1. 读 `sector_daily_snapshot` 当日 rank_no 在 11~80 的板块（top10 之外的活跃板块）
2. 逐个调 D' 的 `_score()` 拿 4 指标（**不要复制 _score 内部逻辑**）
3. 算 hot_score >= 0.5 入选
4. 取前 5，按 hot_score 降序
5. 落库 sector_next_hot（trade_date 同日删后插）

### 3.6 缺数据降级
- 板块无 D' 指标（D' 未跑）：hot_score=null, confidence=0.2, evidence 标 data_insufficient=true
- 候选数 < 5：照实输出，不补 0
- 全部数据缺失：当 trade_date 当日 sector_next_hot 为空，job 仍跑但不报错

### 3.7 sector_forward_forecast.sector_tag 落库
- _score() 返回 dict 加 `sector_tag` 键（按 §3.1 派生）
- `upsert_sector_forward_forecast` payload 加 sector_tag 字段（沿用 repo 现有 upsert 风格）
- 老数据 sector_tag='none'（DEFAULT 已设）

## §四 实现参考
- 风格沿用 `sector_forward_view.py`（pure code + repo + logger.warning）
- 调度风格见 `scheduler/jobs.py:684`（sector_forward_job）
- repo upsert 风格见 `repo.py:upsert_sector_forward_forecast`（同 trade_date 删后插）
- sector_tag 优先级判断可写在 _score() 末尾 5 行内，复用 if/elif 链

## §五 执行顺序
1. init.sql 末尾加 sector_next_hot CREATE + sector_forward_forecast ALTER
2. models.py SectorForwardForecast 加 sector_tag 字段；SectorDailyRankLog 后加 SectorNextHot ORM
3. repo.py 加 upsert_sector_next_hot + list_sector_next_hot_by_date
4. sector_forward_view.py _score() 末尾加 sector_tag 派生（≤20 行）；upsert 链路上加 sector_tag 字段
5. 新建 sector_next_hot.py：judge_next_hot(trade_date=None) -> dict，循环读 top11~80 板块算 hot_score 落库
6. scheduler/jobs.py 加 sector_next_hot_job，cron mon-fri 15:50
7. 写 tests/test_sector_next_hot.py，**只覆盖 4 场景**：
   - one_day_fly：构造 chase_risk=0.8 / top10_freq=0.2 / streak=1 → sector_tag='one_day_fly'
   - mainline_seed：构造 switch=True / continuation=0.7 / streak=3 → sector_tag='mainline_seed'
   - 风口候选筛选：构造 6 个 rank>10 板块，热度排序符合预期
   - expected_horizon_days：构造 switch=True + top10_freq=0.8 → expected >= 3
8. pytest backend/tests/test_sector_next_hot.py -q 全过
9. 顺手加 1 个回归 test_sector_forward_view 测 sector_tag 字段（沿用现有 test，不重写）
10. git add + git commit -m "feat(regime): batch G' 板块标签 + 下一个风口预测"（不 push）

## §六 验证清单
- [ ] init.sql 增量成功（含 ALTER 老库）
- [ ] ORM 导入无循环引用
- [ ] sector_forward_forecast.sector_tag 字段老数据默认 'none'
- [ ] sector_next_hot 表可读可写
- [ ] 4 测试全过 + 1 回归测试通过
- [ ] scheduler.get_jobs() 能看到 sector_next_hot_job
- [ ] 手工 judge_next_hot() 真实跑通
- [ ] git commit 完成，不 push

## §七 红线
1. 不新增 LangGraph 主图节点
2. 不动 agent_call
3. 不改 sector_snapshot 热路径
4. 不重算 D' 4 指标（continuation_prob / exhaustion_risk / chase_risk / switch_candidate 必须调 _score()）
5. 标签派生纯代码，LLM 不参与
6. 缺数据标 data_insufficient + confidence=0.2，不补 0
7. commit 不 push
8. 改动行数预算 ≤ 200（_score 增 20 + service 100 + job + ORM + repo + test 合计），超 → 报告 sir
9. Claude Code 端省 token：①不复读本指令已固化信息 ②禁止顺手改 _score() 已有 4 指标的逻辑（只追加 sector_tag 派生） ③禁止重写 _score() ④只动提示词列的文件 ⑤docstring ≤ 3 行 / 函数体内不写 # 注释 ⑥测试只写 5 个（4 + 1 回归），禁止多写 ⑦执行完毕报告 ≤ 10 行：改了什么文件 / 5 测试结果 / 遗留风险
