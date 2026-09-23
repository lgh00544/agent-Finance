# 因子 IC 月度回测 · 批 2 方案 + 提示词 v1（自包含）

> **执行者**：Codex CLI（gpt5.5 MAX）或 Claude Code
> **依赖**：批 1（25 因子已注册）— 已落 `backend/app/factors/` + `factor_registry.py`
> **项目**：`D:\self`（A 股决策 Agent 系统，sir 自用单人项目）
> **协作铁律**（执行必守）：Agent 解耦 / 数据缺失不编造（K227）/ 人工终审 / 改动 ≤ 400 行

## 0. 元信息

### 0.1 项目背景（codex 新对话必读）
- 后端 FastAPI + SQLite/TiDB + 8 LangGraph Agent（Discover/Score/Position/Monitor/Sell/Review/MarketCondition/MarketIntel）+ DeepSeek LLM
- 批 1 已落 25 因子（动量 5 + 催化 3 + 估值 4 + 资金 5 + 质量 4 + 主线 4）于 `backend/app/factors/`
- 因子注册：`@factor_registry.register` 装饰器 + `list_active()` / `get(fid)` 3 函数
- 因子数据接口：`DataAdapter` 在 `backend/app/factors/data_adapter.py`，含 `kline_rows / financial_rows / fund_rows / news_rows / sector_rows / find / number / quantile`

### 0.2 本任务"为什么"
- **现状**：25 因子写完但**没人验证哪个真预测股价**
- **目标**：每月 1 号 cron 跑 3 年回测 → 算 IC/IR/胜率 → 写 `factor_ic_history` 表
- **价值**：批 1 因子只是"看着合理"，批 2 让系统**用历史数据证明它们真的管用**——发现 IC<0.02 的无效因子即可砍
- **不做**：动态调权（批 3+）、新因子发现（批 4）、前端 IC 报告页（批 5）

## 1. 架构

### 1.1 数据流

```
cron 每月 1 号 02:00 触发 run_factor_ic_backtest
  ↓
取过去 36 个月交易日历（DAGGER 月末对齐）
  ↓
对每月 1 天的"当日" 截面：
  - 调 25 因子（via factor_registry.list_active）
  - 对每只 A 股（约 5000 只，sql 拉 stock_basic）跑 DataAdapter → 25 因子值
  - 拿当日 close / 未来 20 日 close → 算 20 日 forward_return
  - 算每个因子的 IC = spearman_corr(因子值, 20日 forward_return)
  - 算 IR = IC.mean() / IC.std()（按月滚动）
  - 算胜率 = IC > 0 的月份占比
  ↓
写 factor_ic_history 表（factor_id / period / ic / ir / hit_rate / sample_size / 状态）
  ↓
更新 factor_status：IC 连续 3 月 < 0.02 → 标 'deprecated' 候选
  ↓
前端调 GET /api/factor-ic-history 展示
```

### 1.2 新增对象

| 类型 | 路径 | 行数 |
|---|---|---|
| Service | `backend/app/services/factor_ic.py` 新建 | ≤ 120 |
| 调度 | `backend/app/scheduler/jobs.py` 加 1 个 cron | +5 |
| 模型 | `backend/app/db/models.py` 加 `FactorIcHistory` | +30 |
| 迁移 | `backend/scripts/migrate_factor_ic.py` 新建 | ≤ 30 |
| API | `backend/app/api/routes.py` 加 `GET /api/factor-ic-history` | +40 |
| 测试 | `backend/tests/test_factor_ic.py` 新建 | ≤ 80（5 例） |
| 报告页 | `web/src/pages/FactorIcPage.tsx` 新建 | ≤ 100 |
| 路由 | `web/src/components/layout/SideMenu.tsx` +1 项 | +2 |
| API 客户端 | `web/src/api/factors.ts` 新建 | ≤ 30 |
| **合计** | | **≤ 437** |

### 1.3 解耦铁律
- **不动** 25 因子函数（只调用）
- **不动** factor_registry 注册逻辑
- **不动** Score Agent / LangGraph 节点
- **不动** LLM Schema
- **不引新库**（只用 scipy.stats.spearmanr + pandas + numpy，已有）
- **不写前端以外的内容**（IC 报告页是只读）

## 2. 字段与阈值

### 2.1 FactorIcHistory 模型
```python
class FactorIcHistory(Base):
    __tablename__ = "factor_ic_history"
    id: int  # pk
    factor_id: str           # "f01_ma20_deviate"
    factor_name: str         # 中文冗余
    category: str            # 大类
    period: str              # "2024-01"（YYYY-MM）
    ic: float                # 当月 IC（spearman 系数，-1~1）
    ir: float                # 滚动 3 月 IR（=IC.mean/IC.std）
    hit_rate: float          # 0-1，IC>0 月份占比
    sample_size: int         # 当月因子计算成功的股票数
    abs_ic: float            # |IC|，用于排序
    rank_in_category: int    # 同大类内 IC 排名 1-N
    status: str              # "active" / "deprecated_candidate"
    created_at: datetime
```

### 2.2 关键阈值（**不可改**）
- **回测窗口**：36 个月（3 年）
- **forward_return**：20 个交易日
- **IC 计算**：spearman 相关系数（rank-based）
- **IR 窗口**：滚动 3 月
- **失效判定**：IC 连续 3 月 < 0.02 标 deprecated_candidate
- **样本阈值**：< 100 样本的月不纳入 IR 统计
- **跑批时间**：≤ 30 分钟（5000 股 × 25 因子 × 36 月）

### 2.3 因子计算复用
- **必须复用** 批 1 的 `factor_registry.list_active()` + `DataAdapter`
- **不允许** 自己写新的因子计算逻辑
- 数据源：复用 `app.datasource.get_datasource()`

## 3. 实施参考（grep 起点）

执行时**先 grep 关键标识**（禁止通读）：
```bash
grep -n "list_active\|register" backend/app/services/factor_registry.py
grep -n "DataAdapter\|fetch_daily_kline\|fetch_financial" backend/app/factors/data_adapter.py
grep -n "add_job\|cron\|scheduler" backend/app/scheduler/jobs.py
grep -n "FactorIcHistory\|Base\|model" backend/app/db/models.py | head -10
grep -n "stock_basic\|list_stocks" backend/app/db/repo.py | head -5
```

| 现有 | 复用 |
|---|---|
| `factor_registry.list_active()` | 25 因子枚举 |
| `DataAdapter(source=..., code=...)` | 因子计算 |
| `app.datasource.get_datasource()` | 行情数据源 |
| `backend/app/scheduler/jobs.py` cron 模式 | 新加 1 项 |
| `backend/app/api/routes.py` GET 端点模式 | 新加 1 端点 |
| `web/src/pages/MarketIntelPage.tsx` 表格 + 状态色 | IC 报告页样式参考 |

## 4. 7 步执行顺序

1. **建 model**（30 min）：`FactorIcHistory` ORM + 迁移脚本
2. **建 service**（2 h）：`factor_ic.py` 含 `run_backtest()` / `calc_ic()` / `calc_ir()` / `judge_status()` 4 函数
3. **加 cron**（15 min）：`jobs.py` 加 `run_factor_ic_backtest_job` 每月 1 号 02:00 触发
4. **加 API**（30 min）：`GET /api/factor-ic-history?factor_id=&period=&limit=50`
5. **加测试**（1 h）：5 例（正常 IC / 全缺失 / 单因子缺失 / 样本不足 / 状态判定）
6. **前端 IC 页**（1 h）：表格 + 红黄绿 3 色 + 排名徽章
7. **实跑验证**（1 h）：手动触发 cron 跑 1 次全量 3 年回测，写库

## 5. 验证清单

- [ ] `factor_ic_history` 表迁移成功（`python migrate_factor_ic.py`）
- [ ] `run_backtest()` 跑完 3 年回测 ≤ 30 分钟
- [ ] 25 因子 × 36 月 = 900 条记录落库
- [ ] 失效判定：IC 连续 3 月 < 0.02 标 `deprecated_candidate` 正确
- [ ] `GET /api/factor-ic-history` 返回合法 JSON
- [ ] 前端 FactorIcPage 展示 25 因子最近 12 月 IC 趋势 + 排名
- [ ] 5 例单测全过
- [ ] 不动 25 因子函数（git diff 仅新文件 + jobs.py +5 + routes.py +40）

## 6. 红线

1. **不增第 7 大类**（K227）
2. **不删 6 大类**
3. **不编造数据**（缺数据返 None + reason，**不**插默认值）
4. **不动 25 因子函数**（只调用，不重写）
5. **不改 factor_registry** 注册逻辑
6. **不引新库**（只用 scipy.stats.spearmanr + pandas + numpy）
7. **不动 LangGraph**（`graphs.py:20-32`）
8. **不动 LLM Schema**（不增不改 prompt）
9. **不写大段注释**（docstring ≤ 3 行）
10. **代码侧最小改动**：≤ 437 行（5 例单测含内），超出停下报告 sir

## 7. Claude/Codex 端省 token 6 铁律

1. **不复读提示词已固化信息**——6 段 + Schema + 阈值齐备
2. **不写超出提示词范围的代码**——只动 §1.2 列的文件
3. **不写大段注释**——docstring ≤ 3 行
4. **复用** `factor_registry.list_active()` + `DataAdapter` + `get_datasource()`（**禁止重写**）
5. **测试 5 例** 不多写（正常/全缺失/单缺失/样本不足/状态判定）
6. **完成报告 ≤ 10 行**：①改了什么 ②测试结果 ③30 因子全跑耗时 ④遗留

## 8. grep 起点（执行必先跑）

```bash
grep -n "list_active\|register" backend/app/services/factor_registry.py
grep -n "DataAdapter\|fetch_daily_kline" backend/app/factors/data_adapter.py
grep -n "add_job\|cron" backend/app/scheduler/jobs.py
grep -n "class.*Base\|class.*Factor" backend/app/db/models.py | head -5
ls backend/scripts/ | grep migrate
```

## 9. 完成报告格式

```
① 改了什么（文件清单 path:line，含 9 个新文件 + 2 改动）
② 测试结果（5 例 passed/failed）
③ 25 因子全跑 3 年回测耗时（分钟）
④ 25 因子 IC 排名前 3 / 末 3（仅列 ID）
⑤ 失效判定：标 deprecated_candidate 的因子 ID 列表
⑥ 遗留风险
```

## 10. 启动

```bash
codex --approval-mode auto-edit --no-auto-commits --cd D:\self
```

新对话开场白：
> 执行 `D:\self\因子IC月度回测_批2_v1.md`（自包含）。先 grep §8 5 个起点确认行号，禁止 read 全文。完成报告按 §9 9 项格式。
