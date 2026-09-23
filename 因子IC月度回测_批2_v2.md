# 因子 IC 月度回测 · 批 2 提示词 v2（codex 自包含 + 带 commit + 修测试）

> **执行者**：Codex CLI（gpt5.5 MAX）或 Claude Code
> **前置条件**：批 1 25 因子已落 `D:\self\backend\app/factors/`
> **项目**：`D:\self`（A 股决策 Agent 系统，sir 自用单人项目）

## 0. 元信息

### 0.1 项目背景
- 后端 FastAPI + SQLite/TiDB + 8 LangGraph Agent（Discover/Score/Position/Monitor/Sell/Review/MarketCondition/MarketIntel）+ DeepSeek LLM
- 批 1 已落 25 因子于 `backend/app/factors/`，注册器 `factor_registry.py`
- 因子接口：`DataAdapter(source=..., code=...)` 含 `kline_rows / financial_rows / fund_rows / news_rows / sector_rows / find / number / quantile`
- 25 因子清单：动量 5 (f01-f05) + 催化 3 (f06-f08) + 估值 4 (f09-f12) + 资金 5 (f13-f17) + 质量 4 (f18-f21) + 主线 4 (f22-f25)

### 0.2 协作铁律
- Agent 解耦 / 数据缺失不编造（K227）/ 人工终审 / 改动 ≤ 400 行
- 不动 LangGraph（`graphs.py:20-32`）/ 不动 LLM Schema / 不引新库
- 批 1 遗留 2 测试 bug：**本批顺带修**（f05 fixture + test_single_missing）

### 0.3 本任务"为什么"
- 批 1 25 因子**写完但没人验证哪个真预测股价**
- 批 2 目标：每月 1 号 cron 跑 3 年回测 → 算 IC/IR/胜率 → 写 `factor_ic_history` 表
- 价值：用历史数据证明 25 因子谁真管用，发现 IC<0.02 的砍掉

## 1. 目标

**Part A（批 2 主体）**：因子 IC 月度回测系统
**Part B（顺带修批 1 遗留）**：修 2 个测试 bug

## 2. 架构

### 2.1 Part A 新增对象

| 类型 | 路径 | 行数 |
|---|---|---|
| Service | `backend/app/services/factor_ic.py` 新建 | ≤ 120 |
| 调度 | `backend/app/scheduler/jobs.py` +1 cron | +5 |
| 模型 | `backend/app/db/models.py` +`FactorIcHistory` | +30 |
| 迁移 | `backend/scripts/migrate_factor_ic.py` 新建 | ≤ 30 |
| API | `backend/app/api/routes.py` +1 端点 | +40 |
| 测试 | `backend/tests/test_factor_ic.py` 新建 | ≤ 80（5 例） |
| 报告页 | `web/src/pages/FactorIcPage.tsx` 新建 | ≤ 100 |
| 路由 | `web/src/components/layout/SideMenu.tsx` +1 | +2 |
| API 客户端 | `web/src/api/factors.ts` 新建 | ≤ 30 |
| **Part A 合计** | | **≤ 437** |

### 2.2 Part B 修 2 测试
- `backend/tests/test_score_factors.py:35` test_all_25_factors_normal 失败：f05 wyckoff_phase 期望 value is not None 但 mock 缺 `wyckoff_phase` 字段
  - 修法：`_adapter()` fixture 加 `extra={"wyckoff_phase": "吸筹"}`
- `backend/tests/test_score_factors.py:64` test_single_missing_has_explicit_reason 失败：f13 期望 value=None 但 fund_flow=5 时算出 0.05
  - 修法：测试期望改对——传 `fund_flow=[]` 时 f13 才返 None；当前传 `{"main_net_inflow": 5}` 时算法把 5 当作金额，需要传 `{"main_net_inflow": 0}` 或空列表

### 2.3 数据流

```
cron 每月 1 号 02:00 触发 run_factor_ic_backtest_job
  ↓
取过去 36 个月交易日历
  ↓
对每月月末 1 天的"当日" 截面：
  - 拉 5000 股票 list（via repo.list_all_stocks）
  - 每只跑 DataAdapter(source=datasource, code=...) 调 25 因子
  - 拿当日 close / 未来 20 日 close → 算 20 日 forward_return
  - 算每个因子的 IC = spearman_corr(因子值, 20日 forward_return)
  - 算 IR = IC.mean() / IC.std()（滚动 3 月）
  - 算胜率 = IC > 0 月份占比
  ↓
写 factor_ic_history 表
  ↓
IC 连续 3 月 < 0.02 标 deprecated_candidate
  ↓
GET /api/factor-ic-history 展示
```

## 3. 字段与阈值

### 3.1 FactorIcHistory 模型
```python
class FactorIcHistory(Base):
    __tablename__ = "factor_ic_history"
    id: int  # pk
    factor_id: str           # "f01_ma20_deviate"
    factor_name: str         # 中文冗余
    category: str            # 大类
    period: str              # "2024-01"（YYYY-MM）
    ic: float                # spearman -1~1
    ir: float                # 滚动 3 月 IR
    hit_rate: float          # 0-1
    sample_size: int         # 当月成功股票数
    abs_ic: float            # |IC|
    rank_in_category: int    # 同大类排名 1-N
    status: str              # "active" / "deprecated_candidate"
    created_at: datetime
```

### 3.2 关键阈值（**不可改**）
- **回测窗口**：36 个月
- **forward_return**：20 交易日
- **IC 算法**：spearman（scipy.stats.spearmanr）
- **IR 窗口**：滚动 3 月
- **失效判定**：IC 连续 3 月 < 0.02 → deprecated_candidate
- **样本阈值**：< 100 样本的月不入 IR
- **跑批时间**：≤ 30 分钟（5000 × 25 × 36）

### 3.3 因子计算复用
- **必须复用** `factor_registry.list_active()` + `DataAdapter`
- **不允许** 自己写新因子逻辑
- 数据源：复用 `app.datasource.get_datasource()`

## 4. 实施参考（grep 起点）

```bash
grep -n "list_active\|register" backend/app/services/factor_registry.py
grep -n "DataAdapter\|fetch_daily_kline" backend/app/factors/data_adapter.py
grep -n "add_job\|cron" backend/app/scheduler/jobs.py
grep -n "class.*Base\|class.*Factor" backend/app/db/models.py | head -5
grep -n "list_all_stocks\|stock_basic" backend/app/db/repo.py | head -5
ls backend/scripts/ | grep migrate
```

| 现有 | 复用 |
|---|---|
| `factor_registry.list_active()` | 25 因子枚举 |
| `DataAdapter(source=..., code=...)` | 因子计算 |
| `app.datasource.get_datasource()` | 行情源 |
| `jobs.py` cron 模式 | 新加 1 项 |
| `routes.py` GET 端点模式 | 新加 1 端点 |
| `web/src/pages/MarketIntelPage.tsx` | 表格 + 状态色样式 |

## 5. 8 步执行顺序

### Part B（先修，5 分钟）
1. **修 f05 fixture**（2 min）：`_adapter()` 加 `extra={"wyckoff_phase": "吸筹"}` 字段
2. **修 f13 测试**（3 min）：test_single_missing 改传 `fund_flow=[]` 或调整断言

### Part A（主体，1-2 天）
3. **建 model**（30 min）：`FactorIcHistory` ORM + 迁移脚本
4. **建 service**（2 h）：`factor_ic.py` 含 `run_backtest()` / `calc_ic()` / `calc_ir()` / `judge_status()` 4 函数
5. **加 cron**（15 min）：`run_factor_ic_backtest_job` 每月 1 号 02:00
6. **加 API**（30 min）：`GET /api/factor-ic-history?factor_id=&period=&limit=50`
7. **加测试**（1 h）：5 例（正常 IC / 全缺失 / 单因子缺失 / 样本不足 / 状态判定）
8. **前端 IC 页**（1 h）：表格 + 红黄绿 3 色 + 排名徽章 + SideMenu

## 6. 验证清单

### Part A
- [ ] `factor_ic_history` 表迁移成功
- [ ] `run_backtest()` 跑完 3 年 ≤ 30 分钟
- [ ] 25 因子 × 36 月 = 900 条记录落库
- [ ] 失效判定正确
- [ ] `GET /api/factor-ic-history` 返回合法 JSON
- [ ] 前端 FactorIcPage 展示
- [ ] 5 例单测全过

### Part B
- [ ] test_all_25_factors_normal[f05] 改为 pass
- [ ] test_single_missing_has_explicit_reason 改为 pass
- [ ] pytest test_score_factors.py → 32 passed
- [ ] pytest test_factor_ic.py → 5 passed

## 7. 红线

1. **不增第 7 大类**（K227）
2. **不删 6 大类**
3. **不编造数据**
4. **不动 25 因子函数**（只调用，不重写）
5. **不改 factor_registry** 注册逻辑
6. **不引新库**（只用 scipy.stats.spearmanr + pandas + numpy）
7. **不动 LangGraph**（`graphs.py:20-32`）
8. **不动 LLM Schema**
9. **不写大段注释**（docstring ≤ 3 行）
10. **代码侧最小改动**：Part A ≤ 437 + Part B ≤ 20 = 合计 ≤ 457，超出停下报告 sir

## 8. Claude/Codex 端省 token 6 铁律

1. **不复读已固化信息**
2. **只动 §2 列的文件**
3. **docstring ≤ 3 行**
4. **复用** `factor_registry` + `DataAdapter` + `get_datasource()`（**禁止重写**）
5. **Part B 测试 2 例** + **Part A 测试 5 例** = 7 例不多写
6. **完成报告 ≤ 10 行**

## 9. grep 起点（执行必先跑）

```bash
grep -n "list_active\|register" backend/app/services/factor_registry.py
grep -n "DataAdapter\|fetch_daily_kline" backend/app/factors/data_adapter.py
grep -n "add_job\|cron" backend/app/scheduler/jobs.py
grep -n "class.*Base\|class.*Factor" backend/app/db/models.py | head -5
ls backend/scripts/ | grep migrate
```

## 10. commit 提示词（**完成 Part B 后立即 commit**）

```bash
cd /d/self
git add backend/tests/test_score_factors.py
git commit -m "[因子细分化 批1 测试修复] f05 fixture 补 wyckoff_phase 字段 + f13 缺失测试期望改对

- test_all_25_factors_normal[f05]: _adapter() 加 extra.wyckoff_phase 字段
- test_single_missing_has_explicit_reason: f13 传 fund_flow=[] 触发 None 路径
- pytest 32 passed / 0 failed
"
```

## 11. commit 提示词（**完成 Part A 后立即 commit**）

```bash
cd /d/self
git add backend/app/services/factor_ic.py \
        backend/app/scheduler/jobs.py \
        backend/app/db/models.py \
        backend/scripts/migrate_factor_ic.py \
        backend/app/api/routes.py \
        backend/tests/test_factor_ic.py \
        web/src/pages/FactorIcPage.tsx \
        web/src/components/layout/SideMenu.tsx \
        web/src/api/factors.ts
git commit -m "[因子IC回测 批2] 月度 cron + IC/IR/胜率 + 失效判定

- factor_ic.py: 36 月回测 + spearman IC + 滚动 3 月 IR + 失效判定
- cron 每月 1 号 02:00 run_factor_ic_backtest_job
- FactorIcHistory ORM + 迁移 + 900 条/3 年落库
- GET /api/factor-ic-history?factor_id=&period=&limit=50
- 失效: IC 连续 3 月 < 0.02 → deprecated_candidate
- 前端 FactorIcPage 表格 + 红黄绿 + 排名
- 5 例单测全过

阶段 1 基建期批 2（人主导）→ 批 3 自迭代框架
"
```

## 12. 完成报告格式（**按 2 个 commit 顺序回报**）

```
=== Commit 1（Part B 修测试）===
① 改了 test_score_factors.py:35,64
② pytest 32 passed
③ 遗留: 0

=== Commit 2（Part A 批 2 主体）===
① 改了什么（9 文件 path:line）
② 5 例单测 passed
③ 25 因子 × 3 年回测耗时（分钟）
④ IC 排名前 3 / 末 3（仅列 ID）
⑤ 失效判定列表（标 deprecated_candidate 的因子 ID）
⑥ 遗留风险
```

## 13. 启动

```bash
codex --approval-mode auto-edit --no-auto-commits --cd D:\self
```

新对话开场白：
> 执行 `D:\self\因子IC月度回测_批2_v2.md`（自包含 + 含 2 个 commit 指令）。先 grep §9 5 个起点确认行号，禁止 read 全文。完成报告按 §12 双段格式。
