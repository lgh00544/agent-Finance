# 关系持仓 × 个股分析 5 批次合一 · Claude Code 执行指令

> **生成者**：WorkBuddy（sir 委派）
> **执行者**：Claude Code（D:\self 项目根目录）
> **决策人**：sir
> **依赖方案**：`D:\self\关系持仓_个股分析_优化方案.md`（**必读先于本文件**）
> **原则**：仅含需求+规则+约束，不含实际代码；Agent 解耦 / 代码-提示双层 / 缺失数据兜底 / auto-merge 永不碰交易规则。

---

## 〇、5 批次总览

| 批次 | 模块 | 核心动作 | 工时 | 依赖 | 优先级 |
|---|---|---|---|---|---|
| **F** | 组合↔个股联动链路 | PortfolioSentinel 多缓存键 + Monitor/Review 读组合告警 | 0.5 天 | 无 | 🔴 P0 |
| **D** | 派发期自动判定 | 新增 `distribution_phase.py`（6 维）→ 注入 Monitor/Sell/Score | 1.5 天 | 无 | 🔴 P0 |
| **E** | 游资数据真接入 | 复核 `dragon_tiger_source` + K189 对倒代码化 + 注入 4 Agent | 2 天 | 无 | 🟡 P1 |
| **G** | K 红线代码化 | 新增 `red_line_check.py`（C1/C2/C3/K139/K226/K189 事实层） | 1.5 天 | E（wash_trade_suspect）| 🟡 P1 |
| **H** | 复盘反哺选股 | `track_verify` 追加 portfolio/cycle attribution + Score 历史胜率 | 1.5 天 | D（distribution_phase） | 🟢 P2 |

**总工时**：~7 天 | **执行顺序**：**F → D → E → G → H**（F 依赖最少，优先解组合哨兵断点；G 必须在 E 后；H 必须在 D 后）

---

## 一、目标

### 做什么（5 件）
1. 让**组合哨兵**真正影响个股判断（MonitorAgent / ReviewAgent collect 段读取 PortfolioSentinel 告警）
2. 让**派发期**成为可计算的事实，不是 LLM 凭印象（6 维量化 → 注入 3 Agent）
3. 让**游资维度**从"prompt 原则"升级为"事实+代码"（K189 对倒 + 龙虎榜数据真接入 4 Agent）
4. 让 **K 红线**从"知识库文档"升级为"自动校验"（C1/C2/C3 + K139 SOP + K226 + K189）
5. 让**复盘反哺选股**（portfolio_attribution + cycle_attribution 注入 ScoreAgent）

### 不做什么（4 件）
- **不动** `agent_call` / `push_alert_node` 主体（LLM 决策路径不变，只变 collect 段喂的事实）
- **不动** 交易规则表 / 研判标准表（auto-merge 永不碰）
- **不动** Streamlit 前端（按 2026-08-20 已固化规则，所有展示层统一在 `web/src/`）
- **不引入** 新数据库（事实层全部走 SQLite + JSON 缓存，结构化字段直接进 AgentState）

---

## 二、架构约束（5 条铁律）

| # | 铁律 | 含义 |
|---|---|---|
| 1 | **Agent 解耦** | 5 Agent（Discover/Score/Position/Monitor/Sell/Review）之间通过 AgentState 共享事实，不互相调用 |
| 2 | **代码-提示双层** | 代码算阈值/事实（如 `distribution_score=0.78`），LLM 做综合判断 + 自然语言解释 |
| 3 | **缺失数据兜底** | 每个 service 函数必须返回 `{"data": {...}, "missing_data": [...]}`——**绝不编造数值**（K223 事实为先）|
| 4 | **auto-merge 永不碰交易规则** | 所有阈值（C1=60%/C2=30%/C3=0.92 等）都是**参考权重非死条件**，必须保留 LLM 一票否决权 |
| 5 | **前端归属** | 模块 D/E/G/H 的展示层统一 React 新版（`web/src/`），Streamlit 不动 |

---

## 三、规则（按模块）

### 模块 F · 组合联动链路

| 项 | 规则 |
|---|---|
| **触发** | PortfolioSentinel 检测到组合层告警（行业集中度 > 60% / 组合回撤 > 8% / 系统性风险） |
| **缓存键** | `portfolio_sentinel:{trade_date}:{portfolio_id}` —— **必须多键隔离**，否则同 trade_date 不同组合互相污染 |
| **Monitor 注入** | collect 段追加 `portfolio_alert_level` / `concentration_warning` / `sector_exposure_pct` 3 字段 |
| **Review 注入** | collect 段追加 `portfolio_attribution`（组合 P&L 中该股的贡献度）|
| **回撤分解** | 组合回撤分解为"系统性（市场 β）"+"特异性（个股 α）"——返回 dict 形如 `{"system": -0.03, "alpha": -0.05}` |

### 模块 D · 派发期自动判定

| 项 | 规则 |
|---|---|
| **6 维评分** | ①高位滞涨时间（≥20日 缩量高位）②空间高度（距 60 日低点 ≥ 80%）③量价背离（量增价不涨 / 量平价跌）④主力净流出持续（≥5日）⑤顶部形态（双顶/头肩顶/跌破颈线）⑥政策/行业利空（外部输入）|
| **输出** | `distribution_score: float [0, 1]` + `distribution_phase: "early"|"mid"|"late"|"none"` + `missing_data: list[str]` |
| **注入范围** | MonitorAgent（高 → 触发提前告警）+ SellAgent（高 → 缩短止盈/止损阈值）+ ScoreAgent（中 → 评分上限 -10） |
| **缺失数据** | 任一维度缺数据时该维度权重按 0 计，**不补零也不补均值**；`distribution_phase="unknown"` 时 LLM 自主判断 |

### 模块 E · 游资数据真接入

| 项 | 规则 |
|---|---|
| **数据源** | 先复核 `backend/app/services/dragon_tiger_source.py` 是否已实现；若未实现则本次用 akshare 龙虎榜接口补全（`ak.stock_lhb_detail_em` / `ak.stock_lhb_jgmx_em`）|
| **K189 对倒** | 同一营业部同日同股买卖 ≥ 2 次 + 净买卖额偏差 < 5% → 标记 `wash_trade_suspect: bool` |
| **一线/二线** | 营业部近 30 日上榜次数 + 净买入额分位 → 标注"一线/二线/观察" |
| **注入范围** | ScoreAgent（评分上限 +5/0/-5）+ MonitorAgent（游资离场 → 告警）+ SellAgent（游资大幅净卖出 → 强制复核）+ PositionAgent（建仓时若已有同游资持仓 → 提示集中度） |
| **缺失数据** | 龙虎榜数据按日发布，无数据的日期 `dragon_tiger_data: null`，不强行估算 |

### 模块 G · K 红线代码化

| 项 | 规则 |
|---|---|
| **C1（行业集中度）** | 任一行业持仓占比 > 60% → `red_line_c1: "violated"` |
| **C2（组合回撤）** | 组合当日回撤 > 30% 年化（单日 -1.5% / 5日 -7% / 20日 -15%）→ `red_line_c2: "violated"` |
| **C3（系统性风险）** | 沪深 300 同期回撤 > 0.92 倍组合回撤 → `red_line_c3: "violated"`（说明下跌全怪市场）|
| **K139 SOP** | 个股跌破 20 日均线且成交额 < 5 日均量 50% → `k139_sop: "triggered"` |
| **K226 止损** | 个股从持仓高点回撤 > 15% → `k226_stop_loss: "triggered"` |
| **K189 对倒** | 复用模块 E 的 `wash_trade_suspect: true` → `k189_wash_trade: "violated"` |
| **输出** | `red_lines: {"c1": "ok/violated", "c2": ..., "k139_sop": ..., "k226_stop_loss": ..., "k189_wash_trade": ...}` |
| **注入范围** | MonitorAgent（任一 violated → 强制告警 + 推送）+ SellAgent（C2/C3 → 立即复核）+ ReviewAgent（写入复盘报告） |

### 模块 H · 复盘反哺选股

| 项 | 规则 |
|---|---|
| **portfolio_attribution** | 复盘时计算该笔交易对组合 P&L 的贡献：`{"contrib_pct": 0.12, "alpha": 0.08, "drawdown_contrib": -0.03}` |
| **cycle_attribution** | 复盘时按生命周期阶段（建仓/持仓/止盈/止损）拆分收益贡献 |
| **ScoreAgent 加权** | 候选股历史相似特征胜率 > 60% → 评分 +5；30-60% → 0；< 30% → -5 |
| **最小样本** | 相似特征样本数 < 5 → **不加权**（避免小样本噪声）|
| **依赖** | 模块 D 的 `distribution_phase` 字段必须在 ScoreAgent 评分前可读 |

---

## 四、实现参考（项目现有风格 + 参照文件）

### 4.1 必读文件（按依赖顺序）

| 类别 | 路径 | 用途 |
|---|---|---|
| **方案文档** | `D:\self\关系持仓_个股分析_优化方案.md` | 5 模块细节 + 决策点 + 协同点 |
| **知识库** | `D:\self\base_file\持仓与盈亏计划_完整知识库_v1.0_2026-08-06.md` | 派发期/K 红线/组合联动口径 |
| **知识库** | `D:\self\base_file\游资维度嵌入需求规格_2026-08-09.md` | 游资维度接入规范 |
| **已有 Prompt** | `D:\self\agent_prompts\portfolio_sentinel_prompt.py` | 组合哨兵 prompt（批次 F 改造对象）|
| **已有 Prompt** | `D:\self\agent_prompts\monitor_prompt.py` | 监控 agent（批次 D/G 注入对象）|
| **已有 Prompt** | `D:\self\agent_prompts\sell_prompt.py` | 卖出 agent（批次 D/G 注入对象）|
| **已有 Prompt** | `D:\self\agent_prompts\score_prompt.py` | 评分 agent（批次 D/E/H 注入对象）|
| **已有 Prompt** | `D:\self\agent_prompts\position_prompt.py` | 建仓 agent（批次 E 注入对象）|
| **已有 Prompt** | `D:\self\agent_prompts\review_prompt.py` | 复盘 agent（批次 F/H 注入对象）|
| **已有 Service** | `D:\self\backend\app\services\holding_view.py` | 持仓视角（批次 D/E/G 复用）|
| **已有 Service** | `D:\self\backend\app\services\portfolio_sentinel.py` | 组合哨兵（批次 F 改造对象）|
| **批次 1/2** | `D:\self\批次1_移动止盈与组合哨兵_执行指令.md` / `批次2_减仓比例与组合联动_执行指令.md` | 批次 F 直接复用其 collect 段模板 |

### 4.2 风格规范（必须遵守）

1. **collect 段追加**：每个 Agent 改造只动 `collect` 函数内的字段注入，**不动** `agent_call` / `push_alert_node`
2. **service 函数返回格式**：所有新 service 必须返回 `{"data": {...}, "missing_data": [...]}`，参考 `holding_view.py` 现有风格
3. **日志规范**：每个 service 入口打 `logger.info(f"[{module}] start: {params}")`，异常打 `logger.exception`
4. **测试覆盖**：每个新 service 必须有 ≥ 3 个单测（正常 / 缺失数据 / 边界值）
5. **前端展示**（如适用）：React 新版统一在 `web/src/components/`，按 2026-08-20 已固化规则不动 Streamlit

### 4.3 数据 Schema（统一规范）

```python
# 模块 D 输出（distribution_phase）
{
    "distribution_score": 0.78,          # float [0, 1]
    "distribution_phase": "mid",         # early / mid / late / none / unknown
    "contributing_dims": ["time", "volume_price"],  # 哪几维贡献了分数
    "missing_data": ["policy_news"]      # 缺失维度
}

# 模块 F 输出（portfolio_alert）
{
    "portfolio_alert_level": "yellow",  # green / yellow / red
    "concentration_warning": "行业集中度 65% > 60% 阈值",
    "sector_exposure_pct": 0.65,
    "drawdown_decomp": {"system": -0.03, "alpha": -0.05}
}

# 模块 E 输出（dragon_tiger_summary）
{
    "top_seats": [{"name": "东方证券绍兴解放南路", "tier": "一线", "net_buy": 12000000}],
    "wash_trade_suspect": False,
    "missing_data": []
}

# 模块 G 输出（red_lines）
{
    "c1": "ok", "c2": "violated", "c3": "ok",
    "k139_sop": "ok", "k226_stop_loss": "triggered", "k189_wash_trade": "ok"
}
```

---

## 五、执行顺序（5 批次串行）

### 5.1 批次 F · 组合联动链路（0.5 天）

1. 读 `agent_prompts/portfolio_sentinel_prompt.py` 和 `backend/app/services/portfolio_sentinel.py` 全文
2. 修改 `portfolio_sentinel.py` 缓存键为 `portfolio_sentinel:{trade_date}:{portfolio_id}` 多键隔离
3. 在 `portfolio_sentinel.py` 新增 `compute_drawdown_decomposition(portfolio_id, trade_date) -> {"system": float, "alpha": float}` 函数（参考 PortfolioSentinel 已有风险计算）
4. 修改 `monitor_prompt.py` 的 `collect` 段：追加 `portfolio_alert_level` / `concentration_warning` / `sector_exposure_pct` 3 字段读取
5. 修改 `review_prompt.py` 的 `collect` 段：追加 `portfolio_attribution` 字段读取
6. 新增 3 个单测到 `tests/test_portfolio_sentinel.py`（多组合隔离 / 缺失数据 / 回撤分解边界）
7. 跑 `pytest tests/test_portfolio_sentinel.py -v` 全绿
8. 跑 `mypy backend/app/services/portfolio_sentinel.py` 零错

### 5.2 批次 D · 派发期自动判定（1.5 天）

1. 新建 `backend/app/services/distribution_phase.py`，定义 6 维计算函数（`time_dimension` / `space_dimension` / `volume_price_dimension` / `capital_flow_dimension` / `pattern_dimension` / `policy_dimension`）
2. 主入口 `compute_distribution_phase(symbol, trade_date) -> {"distribution_score": float, "distribution_phase": str, "contributing_dims": list, "missing_data": list}`
3. 在 `monitor_prompt.py` collect 段注入 3 字段（`distribution_score` / `distribution_phase` / `contributing_dims`）
4. 在 `sell_prompt.py` collect 段注入 3 字段（同上）
5. 在 `score_prompt.py` collect 段注入 3 字段，并加规则"phase=mid/late → 评分上限 -10"
6. 新增 8 个单测到 `tests/test_distribution_phase.py`（每维 1 个 + 主入口 2 个：高分/低分/缺失数据）
7. 跑 `pytest tests/test_distribution_phase.py -v` 全绿

### 5.3 批次 E · 游资数据真接入（2 天）

1. 复核 `backend/app/services/dragon_tiger_source.py`：若已实现则复用并修复；若未实现则新建
2. 新建 `backend/app/services/dragon_tiger_source.py`：
   - `fetch_dragon_tiger_detail(trade_date) -> list[dict]`（用 akshare `ak.stock_lhb_detail_em`）
   - `classify_seat_tier(seat_name, lookback_days=30) -> "一线"|"二线"|"观察"`（按近 30 日上榜次数 + 净买入额分位）
   - `detect_wash_trade(trade_date, symbol) -> bool`（K189：同营业部同日同股买卖 ≥ 2 次 + 净买卖偏差 < 5%）
3. 新建 `backend/app/services/dragon_tiger_summary.py` 聚合函数 `summarize_dragon_tiger(symbol, trade_date) -> dict`
4. 在 `score_prompt.py` collect 段注入 + `tier` 加权规则
5. 在 `monitor_prompt.py` collect 段注入 `dragon_tiger_summary` 字段 + 游资离场告警规则
6. 在 `sell_prompt.py` collect 段注入 + 强制复核规则
7. 在 `position_prompt.py` collect 段注入 + 同游资集中度提示
8. 新增 6 个单测到 `tests/test_dragon_tiger.py`（数据获取 mock / 营业部分类 / 对倒检测 / 缺失数据）
9. 跑全测

### 5.4 批次 G · K 红线代码化（1.5 天）

1. 新建 `backend/app/services/red_line_check.py`：
   - `check_c1_concentration(portfolio_id) -> "ok"|"violated"`
   - `check_c2_portfolio_drawdown(portfolio_id, trade_date) -> "ok"|"violated"`
   - `check_c3_systematic_risk(portfolio_id, trade_date) -> "ok"|"violated"`
   - `check_k139_sop(symbol, trade_date) -> "ok"|"triggered"`
   - `check_k226_stop_loss(symbol, trade_date) -> "ok"|"triggered"`
   - `check_k189_wash_trade(symbol, trade_date) -> "ok"|"violated"`（**复用模块 E 的 `wash_trade_suspect` 字段**）
   - 主入口 `check_all_red_lines(portfolio_id, symbol, trade_date) -> dict`
2. 在 `monitor_prompt.py` collect 段注入 `red_lines` 字段 + 任一 violated → 强制告警 + 推送
3. 在 `sell_prompt.py` collect 段注入 + C2/C3 → 立即复核规则
4. 在 `review_prompt.py` collect 段注入 + 写入复盘报告规则
5. 新增 8 个单测到 `tests/test_red_line_check.py`（每个红线 1 个 + 主入口 2 个）
6. 跑全测

### 5.5 批次 H · 复盘反哺选股（1.5 天）

1. 修改 `backend/app/services/track_verify.py`：
   - 新增 `compute_portfolio_attribution(trade_id, trade_date) -> {"contrib_pct": float, "alpha": float, "drawdown_contrib": float}`
   - 新增 `compute_cycle_attribution(trade_id, trade_date) -> dict`（按 建仓/持仓/止盈/止损 阶段拆分）
2. 在 `score_prompt.py` collect 段注入 `historical_win_rate_for_features` 字段 + 相似特征胜率加权规则（样本 < 5 不加权）
3. 新增 5 个单测到 `tests/test_track_verify.py`（port attribution / cycle attribution / 相似特征匹配 / 样本不足跳过）
4. 跑全测

### 5.6 总体收尾（每个批次都要做）

- 提交：`git add -A && git commit -m "[F/D/E/G/H] <模块名> 落地"`（**不 push**，等 sir review）
- **批次 F 完成后**单独提交流程：sir 验收通过才进批次 D

---

## 六、验证清单（每批次完成后 [ ] 勾选）

### 批次 F
- [ ] `portfolio_sentinel.py` 缓存键已改为多键隔离
- [ ] `compute_drawdown_decomposition` 函数已实现 + 单测
- [ ] `monitor_prompt.py` collect 段已注入 3 字段
- [ ] `review_prompt.py` collect 段已注入 `portfolio_attribution`
- [ ] `pytest tests/test_portfolio_sentinel.py -v` 全绿
- [ ] `mypy backend/app/services/portfolio_sentinel.py` 零错
- [ ] git commit 已提交（未 push）

### 批次 D
- [ ] `distribution_phase.py` 已新建，6 维计算函数齐全
- [ ] `compute_distribution_phase` 主入口返回符合 schema
- [ ] `monitor_prompt.py` / `sell_prompt.py` / `score_prompt.py` collect 段已注入
- [ ] `pytest tests/test_distribution_phase.py -v` 全绿
- [ ] 缺失数据场景：`missing_data` 正确返回，LLM 端不报错
- [ ] git commit 已提交

### 批次 E
- [ ] `dragon_tiger_source.py` 已复核/新建
- [ ] `wash_trade_suspect` 检测函数已实现
- [ ] 4 Agent collect 段已注入
- [ ] `pytest tests/test_dragon_tiger.py -v` 全绿
- [ ] akshare 接口失败时 `missing_data: ["dragon_tiger_data"]` 正确返回
- [ ] git commit 已提交

### 批次 G
- [ ] `red_line_check.py` 已新建，6 个红线函数齐全
- [ ] K189 复用模块 E 的 `wash_trade_suspect`
- [ ] 3 Agent collect 段已注入
- [ ] `pytest tests/test_red_line_check.py -v` 全绿
- [ ] 任一红线 violated 时 Monitor 强制告警链路测试通过
- [ ] git commit 已提交

### 批次 H
- [ ] `track_verify.py` 已追加 2 个 attribution 函数
- [ ] `score_prompt.py` collect 段已注入历史胜率
- [ ] 样本 < 5 不加权逻辑已测试
- [ ] `pytest tests/test_track_verify.py -v` 全绿
- [ ] git commit 已提交

### 整体
- [ ] 5 批次全部完成后 `pytest tests/ -v` 全绿（567 + 新增 ≥ 30 测试）
- [ ] 所有 commit 已落本地仓库，**未 push**
- [ ] sir review 报告已生成：`D:\self\关系持仓_个股分析_5批次_执行报告.md`

---

## 七、红线（5 条必守）

| # | 红线 | 含义 |
|---|---|---|
| 1 | **不动 agent_call / push_alert_node** | 5 Agent 改造只动 collect 段，LLM 决策路径不变；新事实层通过 AgentState 注入，不改 prompt 主体逻辑 |
| 2 | **auto-merge 永不碰交易规则/研判标准** | 所有阈值（C1=60%/C2=30%/C3=0.92 等）都是**参考权重非死条件**，必须保留 LLM 一票否决权 |
| 3 | **不编造数值** | 缺失数据时返回 `missing_data` 字段，**不补零/不补均值/不强行估算**（K223 事实为先）|
| 4 | **不动 Streamlit** | 展示层统一 React 新版（`web/src/`），按 2026-08-20 已固化规则 |
| 5 | **不引入新数据库** | 事实层全部走 SQLite + JSON 缓存 + AgentState，不引 PG/Mongo/Redis |

---

## 八、Claude Code 执行前必读清单

1. **方案文档**：`D:\self\关系持仓_个股分析_优化方案.md`（5 模块细则 + 决策点）
2. **知识库 v1.0**：`D:\self\base_file\持仓与盈亏计划_完整知识库_v1.0_2026-08-06.md`（§9.2 派发期口径）
3. **游资需求规格**：`D:\self\base_file\游资维度嵌入需求规格_2026-08-09.md`
4. **批次 1/2 执行指令**：`D:\self\批次1_移动止盈与组合哨兵_执行指令.md` + `批次2_减仓比例与组合联动_执行指令.md`（批次 F 模板参照）
5. **Agent prompt 5 份**：`agent_prompts/{score,position,monitor,sell,review}_prompt.py`
6. **Service 3 份**：`backend/app/services/{holding_view,portfolio_sentinel}.py` + 即将新建的 3 个 service

**执行起点**：从 §5.1 批次 F 第 1 步开始，按依赖顺序串行执行；每个批次完成后**停下来报告 sir，等验收再进下一批次**。

**沟通节点**：
- 每个批次提交后 → 输出 ①改了哪些文件 ②测试结果 ③遗留风险
- 遇到方案决策点（§3 任何字段含义不清晰）→ **先停下问 sir，不要自行决定**
- 遇到红线触碰（必须改 agent_call / 必须改交易规则表）→ **立即停下报告**
