# 关系持仓批次 F · 组合↔个股联动链路 · Claude Code 执行指令

> **生成者**：Lark（WorkBuddy）
> **执行者**：Claude Code（D:\self 项目根）
> **决策人**：sir
> **依赖方案**：`D:\self\关系持仓_个股分析_优化方案.md` §三 模块 0（关系持仓联动）+ 批次 1/2 已有指令
> **执行起点**：§四 步骤 1
> **原则**：6 段精简版（省 token 铁律 2026-08-22 生效）

---

## 一、目标

把 **PortfolioSentinel → MonitorAgent → ReviewAgent** 的单向只读链路打通，让组合级告警真正影响个股判断。

### 做什么（4 件）
1. `portfolio_sentinel.py` 缓存键改为多键隔离（按 portfolio_id 隔离）
2. 新增 `compute_drawdown_decomposition()` 函数：组合回撤分解为系统 β + 特异性 α
3. `monitor_prompt.py` 的 `collect` 段追加 3 字段：组合告警等级 / 集中度预警 / 行业敞口
4. `review_prompt.py` 的 `collect` 段追加 `portfolio_attribution` 字段读取

### 不做什么（3 件）
- 不动 `monitor_prompt.py` 的 `agent_call` / `push_alert_node`（LLM 决策路径不变）
- 不动交易规则表 / 研判标准表
- 不改 Streamlit（前端归属 React，2026-08-20 已固化规则）

---

## 二、架构约束（4 条）

| # | 约束 | 含义 |
|---|---|---|
| 1 | **Agent 解耦** | MonitorAgent 只读 PortfolioSentinel 输出，不互相调用；通过 AgentState 共享 |
| 2 | **代码-提示双层** | 代码算阈值/事实（如 `concentration_warning="行业集中度 65% > 60% 阈值"`），LLM 做综合判断 + 自然语言解释 |
| 3 | **缺失数据兜底** | service 函数返回 `{"data": {...}, "missing_data": [...]}`——不补零/不补均值（K223 事实为先）|
| 4 | **缓存键隔离** | `portfolio_sentinel:{trade_date}:{portfolio_id}` 必须多键；否则同 trade_date 不同组合互相污染 |

---

## 三、规则（字段 + 阈值 + 触发条件）

### 字段：3 + 1 注入

| Agent | 字段 | 类型 | 含义 | 触发 |
|---|---|---|---|---|
| Monitor | `portfolio_alert_level` | `"green"\|"yellow"\|"red"` | 组合级告警等级 | PortfolioSentinel 检测到告警时 |
| Monitor | `concentration_warning` | `str\|null` | 集中度预警文案 | 行业集中度 > 60% |
| Monitor | `sector_exposure_pct` | `float [0,1]` | 行业敞口占比 | 同上 |
| Review | `portfolio_attribution` | `{"contrib_pct": float, "alpha": float, "drawdown_contrib": float}` | 组合 P&L 中该股贡献度 | 复盘时 |

### 阈值（参考权重，非死条件）

- C1 行业集中度：**60%**
- 组合当日回撤：-1.5% / 5 日 -7% / 20 日 -15%（任一触发）
- 系统性回撤占比：**0.92**（C3 红线）

### 缺失数据兜底

- 任一字段无数据 → 该字段填 `null` + `missing_data` 数组追加 `"<field_name>"`
- LLM 端看到 `null` 不报错，自主判断

### Schema（统一返回格式）

```
{
  "portfolio_alert": {
    "portfolio_alert_level": "yellow",
    "concentration_warning": "行业集中度 65% > 60% 阈值",
    "sector_exposure_pct": 0.65,
    "drawdown_decomp": {"system": -0.03, "alpha": -0.05}
  },
  "missing_data": []
}
```

---

## 四、执行顺序（6 步）

### 步骤 1 · 读已有代码（必做，不动手）

- `D:\self\backend\app\services\portfolio_sentinel.py`（现状摸底）
- `D:\self\agent_prompts\portfolio_sentinel_prompt.py`（采集段位置）
- `D:\self\agent_prompts\monitor_prompt.py` 的 `collect` 段
- `D:\self\agent_prompts\review_prompt.py` 的 `collect` 段
- 复用 `D:\self\批次1_移动止盈与组合哨兵_执行指令.md` §五 步骤 1-7 的 collect 段注入模板
- 复用 `D:\self\批次2_减仓比例与组合联动_执行指令.md` 的 portfolio_risk_context 注入点

### 步骤 2 · 改 `portfolio_sentinel.py` 缓存键

定位当前 `SimpleCache().get_or_set(...)` 调用点，缓存键改为：

```python
# 原（单键，污染）
f"portfolio_sentinel:{trade_date}"

# 新（多键，隔离）
f"portfolio_sentinel:{trade_date}:{portfolio_id}"
```

所有 `get_or_set` / `set` / `get` 调用点同步更新。

### 步骤 3 · 新增 `compute_drawdown_decomposition()`

函数签名：

```
compute_drawdown_decomposition(portfolio_id: str, trade_date: str) -> dict
返回：{"system": float, "alpha": float, "missing_data": list[str]}
```

实现参考（**不改实现，按现有风格**）：
- 系统 β：`沪深 300 同窗口回撤`（数据源 akshare `ak.stock_zh_index_daily("sh000300")`）
- 特异性 α：`组合回撤 - 系统 β × 组合 β 系数`
- 缺失数据：沪深 300 取不到 → `missing_data: ["index_data"]`

### 步骤 4 · 改 `monitor_prompt.py` collect 段

定位 `collect` 函数（参考 `monitor_prompt.py` 已有的 collect 段位置），追加 3 字段读取：

```python
# 伪代码示意，实际按 monitor_prompt.py 已有 collect 段风格
portfolio_alert = fetch_portfolio_alert(portfolio_id, trade_date)  # 来自 portfolio_sentinel
context["portfolio_alert_level"] = portfolio_alert["portfolio_alert_level"]
context["concentration_warning"] = portfolio_alert["concentration_warning"]
context["sector_exposure_pct"] = portfolio_alert["sector_exposure_pct"]
context["missing_data"] += portfolio_alert["missing_data"]
```

### 步骤 5 · 改 `review_prompt.py` collect 段

定位 `collect` 函数，追加 1 字段读取：

```python
portfolio_attribution = compute_portfolio_attribution(trade_id, trade_date)
context["portfolio_attribution"] = portfolio_attribution["data"]
context["missing_data"] += portfolio_attribution["missing_data"]
```

`compute_portfolio_attribution()` 在 `portfolio_sentinel.py` 同文件新增，参考 `track_verify.py` 已有 attribution 函数风格。

### 步骤 6 · 测试 + 验证

新增 `tests/test_portfolio_sentinel_v2.py`，覆盖 3 个用例：

| # | 测试名 | 验证点 |
|---|---|---|
| 1 | `test_multi_portfolio_cache_isolation` | 同 trade_date 不同 portfolio_id 缓存互不污染 |
| 2 | `test_drawdown_decomposition_missing_index` | 沪深 300 取不到时 `system=0, alpha=组合回撤, missing_data=["index_data"]` |
| 3 | `test_collect_segment_injects_3_fields` | mock portfolio_alert 后 Monitor collect 段能正确读出 3 字段 |

跑测试：

```
pytest tests/test_portfolio_sentinel_v2.py -v
pytest tests/ -v  # 全量回归
mypy backend/app/services/portfolio_sentinel.py
```

预期：`tests/test_portfolio_sentinel_v2.py` 3 passed，全量回归不引入新失败，mypy 零错。

### 收尾

提交（**不 push**，等 sir review）：

```
git add -A
git commit -m "[批次F] 组合↔个股联动链路落地：缓存多键隔离 + drawdown 分解 + Monitor/Review collect 段注入"
```

完成后报告：①改了哪些文件 ②测试结果 ③遗留风险。

---

## 五、红线（5 条必守 + 2 条省 token 硬约束）

| # | 红线 | 含义 |
|---|---|---|
| 1 | **不动 agent_call / push_alert_node** | 5 Agent 改造只动 collect 段，LLM 决策路径不变 |
| 2 | **auto-merge 永不碰交易规则** | C1=60% 等阈值是参考权重非死条件，必须保留 LLM 一票否决权 |
| 3 | **不编造数值** | 缺失数据时返回 `missing_data`，**不补零/不补均值/不强行估算** |
| 4 | **不动 Streamlit** | 展示层按 2026-08-20 已固化规则统一在 `web/src/`，本次不涉及前端 |
| 5 | **不引入新数据库** | 事实层走 SQLite + SimpleCache + AgentState，不引 PG/Mongo/Redis |
| 6 | **Claude Code 端也省 token（2026-08-24 sir 拍板）** | 见下方 §五.1 |
| 7 | **代码侧最小改动 + 复用已有函数** | 见下方 §五.2 |

### 五.1 Claude Code 端省 token 6 条（sir 2026-08-24 拍板）

| # | 手段 | 怎么做 |
|---|---|---|
| 1 | **不复读提示词已固化信息** | 6 段 + Schema + 阈值已在本文件齐备，**禁止**再次 read `关系持仓_个股分析_优化方案.md` / `批次1_*.md` 全文核对（只 grep 关键标识确认行号）|
| 2 | **不写超出提示词范围的代码** | 本次只动 5 个文件：`portfolio_sentinel.py` / `portfolio_sentinel.py`（同文件新增 `compute_drawdown_decomposition`） / `monitor_prompt.py` / `review_prompt.py` / 新测试。**禁止**顺手改其他文件 |
| 3 | **不写大段注释** | 函数 docstring ≤ 3 行，函数体内不写 `# 注释`（除关键 trade-off） |
| 4 | **复用已有函数** | `fetch_portfolio_alert` / `compute_portfolio_attribution` 如有已有实现**直接调用**，禁止重写 |
| 5 | **测试用例 ≤ 3 个** | 已规定 3 用例（多键隔离 / drawdown 分解缺失数据 / collect 段字段注入），**禁止**多写 |
| 6 | **报告精简** | 执行完毕报告 ≤ 10 行：①改了什么（5 文件清单）②测试结果（3 passed / 全量 N passed）③遗留风险（如有） |

### 五.2 代码侧最小改动铁律

- 改动行数预算：≤ 80 行（不含新增 `compute_drawdown_decomposition` 函数体）
- `compute_drawdown_decomposition` 函数体 ≤ 30 行（参考 `track_verify.py` 已有函数）
- 任何超出预算的改动 → **停下报告 sir**，不要自行决定加功能


---

## 六、沟通节点

- **每个步骤完成后** → 输出 ①改了哪些文件 ②测试结果 ③遗留风险
- **遇到方案决策点**（字段含义不清晰 / 阈值有歧义）→ **先停下问 sir**，不要自行决定
- **遇到红线触碰**（必须改 agent_call / 必须改交易规则表 / 必须引新库）→ **立即停下报告**
- **批次 F 完成后** → 停下来报告 sir，等验收再进批次 D（派发期自动判定）
