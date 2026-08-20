# 关系持仓 + 个股分析 · 5 批次 Claude Code 执行指令

> 生成：Lark（2026-08-20）
> 上游方案：`D:\self\关系持仓_个股分析_优化方案.md`
> 决策人：sir 拍板
> 原则：只描述需求与规则，实现方式由 Claude Code 按项目现有风格统一处理

---

## 总览：批次依赖与优先级

```
D 派发期判定 ──┐
              ├──→ H 复盘反哺（依赖 D 的 distribution_phase）
E 游资真接入 ──┤
              ├──→ G K 红线代码化（依赖 E 的 wash_trade_suspect）
F 组合联动链路（独立，可最先做）
```

| 批次 | 内容 | 核心新文件 | Agent 改动 | 前端改动 | 预估工时 |
|---|---|---|---|---|---|
| F | 组合联动链路 | 0 | 3 Agent collect 段 | — | 0.5 天 |
| D | 派发期自动判定 | `distribution_phase.py` | 3 Agent collect 段 | — | 1.5 天 |
| E | 游资数据真接入 | `capital_view.py` | 4 Agent collect 段 | — | 2 天 |
| G | K 红线代码化 | `red_line_check.py` | 3 Agent collect 段 | React 徽章 | 1.5 天 |
| H | 复盘反哺选股 | 追加 2 函数 | Review/Score collect 段 | React 复盘页 | 1.5 天 |

---

# 批次 F：组合级 ↔ 个股级 联动链路打通 · 执行指令

> 生成：Lark（2026-08-20）
> 执行：Claude Code
> 决策人：sir 拍板
> 原则：只描述需求与规则，实现方式由 Claude Code 按项目现有风格统一处理

---

## 一、目标

本批次把 PortfolioSentinel 组合级产出**单向穿透**到 MonitorAgent 和 ReviewAgent，让组合结论回流到个股状态标签 + 复盘归因。

**要做的事**：
- PortfolioSentinel 节点末尾多缓存 3 个键（last_full / last_sector_alerts / last_concentration_alert）
- MonitorAgent collect 段追加读组合级告警（板块退潮 + 集中度）
- ReviewAgent collect 段追加读组合级 + 贡献度计算
- 缓存键规范注释化

**不做什么**：
- **不改 PortfolioSentinel 判断逻辑**（仅追加 `cache.set` 暴露已算好的结果）
- **不改 PortfolioSentinel schema / prompt / 节点流程**
- **不改 SellAgent**（批次 2 已完成，本次零动）
- **不改 PortfolioSentinel 与其他 Agent 的反向调用**（单向只读）

---

## 二、架构约束

### 现有对象提升

| 对象 | 改什么 | 不改什么 |
|------|--------|---------|
| `portfolio_sentinel.py` | 节点末尾追加 3 行 `cache.set`（last_full / last_sector_alerts / last_concentration_alert）| agent_call 逻辑零改、schema 零改、prompt 零改、节点流程零改 |
| `monitor.py` | `collect_quote` 末尾追加读 `cache.get("portfolio_sentinel:last_sector_alerts")` + 注入 `【组合级预警】` 段 | schema 不改、图结构不改、节点流程不改、prompt 不改 |
| `review.py` | `collect_review_input` 末尾追加读 `cache.get("portfolio_sentinel:last_risk")` + 计算"组合级贡献"（每只持仓对当日组合盈亏的贡献度 = 单票盈亏 / 组合总盈亏 × 100%）| 同上 |
| `cache.py` | 注释化所有 `portfolio_sentinel:*` 键（TTL / 写入方 / 读取方）| 实现不动 |

### 不新建对象

本批次零新建。

### 解耦铁律（最重要）

- **单向只读链路**：MonitorAgent / ReviewAgent 读 PortfolioSentinel 缓存，**绝不反向调用** PortfolioSentinel 的图/节点/router
- **PortfolioSentinel 判断逻辑零改动**：只允许在节点末尾追加 1-3 行 `cache.set`
- SellAgent 读 PortfolioSentinel 是批次 2 已完成，本次**不动**
- 不改其他 Agent（Discover/Score/Position/MarketIntel 零改动，除 ReviewAgent 的 collect 段追加）

---

## 三、规则

### PortfolioSentinel 缓存键规范

| 键名 | 内容 | TTL | 写入方 | 读取方 |
|------|------|-----|--------|--------|
| `portfolio_sentinel:last_full` | 完整 result（含 4 维全部输出）| 1800s | PortfolioSentinel 节点末尾 | （备用，未来可能用）|
| `portfolio_sentinel:last_risk` | `portfolio_risk` 段（已有，批次 2）| 1800s | 同上 | SellAgent（批次 2）|
| `portfolio_sentinel:last_sector_alerts` | `sector_alerts` 列表 | 1800s | 本次新增 | MonitorAgent（本次）|
| `portfolio_sentinel:last_concentration_alert` | `concentration_alert` 布尔 | 1800s | 本次新增 | MonitorAgent（本次）|

**纪律**：
- 缓存写入用 `cache.set(key, value, 1800)` 格式，TTL 与巡检频率同节奏
- 缓存读取用 `try/except` 包裹，缺失时降级为"组合数据不可用"
- 不写缓存逻辑进 PortfolioSentinel 的 schema / prompt / 节点判断

### MonitorAgent 注入规则

- 读取 `cache.get("portfolio_sentinel:last_sector_alerts")` 返回列表
- 若当前持仓股 code 出现在 `sector_alerts` 中 → 在 `quote_data` 段追加：
  ```
  【组合级预警】该股所属板块 {sector} 触发板块退潮（量比 {volume_ratio}，alert_level {level}）
  ```
- 读取 `cache.get("portfolio_sentinel:last_concentration_alert")` 返回布尔
- 若 `True` 且同板块持仓 ≥ 2 只 → 追加：
  ```
  【组合级预警】同板块持仓集中度超 40%，建议减仓优先考虑同板块标的
  ```
- **不写 LLM 怎么解读**：由 LLM 自由解读
- 缓存缺失时**不报错**，正常返回 hold + info 级常规跟踪

### ReviewAgent 注入规则

- 读取 `cache.get("portfolio_sentinel:last_risk")` 返回 dict
- 复盘顶部展示条新增："今日组合 {total_pnl_pct}%，最大贡献者 {top_contributor} ({pct}%)"
- 贡献度计算：`contribution_pct = 单票盈亏 / 组合总盈亏 × 100%`
- 顶部展示条数据缺失时 → 标注"组合数据不可用"，不影响个股级复盘
- **不写 LLM 怎么归因**：由 LLM 自由解读

### 缓存读取异常处理

所有读 cache 的代码用 `try/except` 包裹 + 返回值判 None，缺失时统一降级为"组合数据不可用"字符串，不影响 Agent 正常运行。

### 红线约束

- **不改 PortfolioSentinel 判断逻辑**（仅追加 `cache.set` 暴露已算好的结果）
- **不改 PortfolioSentinel schema / prompt / 节点流程**
- **不改 .env**、不改 SellAgent
- **单向只读**：MonitorAgent / ReviewAgent 不反向调用 PortfolioSentinel
- **auto-merge 永不碰 PortfolioSentinel 的判断逻辑**

---

## 四、实现参考

请遵循项目现有代码风格和模式：

- **cache 写入**：参照 `portfolio_sentinel.py` 节点末尾 `cache.set("portfolio_sentinel:last_risk", ...)` 的写法（批次 2 已落地）
- **Agent collect 段追加**：参照 `monitor.py` / `sell.py` 现有 collect 段的字段组织方式
- **缓存键注释**：参照 `cache.py` 现有的 key 命名规范
- **缺失数据兜底**：参照 `holding_view.py` 行情失败的"字段为 None + 前端显示 —"模式
- **try/except 包裹**：参照 `holding_view.py:53` `except Exception as exc: logger.warning(...)` 模式

---

## 五、执行顺序

1. 备份涉及文件
2. `portfolio_sentinel.py` 节点末尾追加 3 行 `cache.set`（last_full / last_sector_alerts / last_concentration_alert）
3. `cache.py` 加键规范注释
4. `monitor.py` collect_quote 末尾追加读 sector_alerts + concentration_alert + 注入 prompt 输入
5. `review.py` collect_review_input 末尾追加读 last_risk + 贡献度计算 + 注入 prompt 输入
6. 单测 `backend/tests/test_portfolio_link.py`
7. 验证

---

## 六、验证清单

- [ ] `portfolio_sentinel.py` 节点末尾 `cache.set` 调用 ≥ 3 个键
- [ ] `cache.py` 注释列出所有 `portfolio_sentinel:*` 键
- [ ] `monitor.py` collect 段包含「组合级预警」（grep 验证）
- [ ] `review.py` collect 段包含「组合级贡献」（grep 验证）
- [ ] 缓存缺失时不报错，正常返回常规跟踪
- [ ] 单元测试 `test_portfolio_link.py` 覆盖 3 缓存键 + 缺失降级
- [ ] 全量 pytest 通过
- [ ] 输出一份联动样本（MonitorAgent 实际 prompt 包含【组合级预警】段 + ReviewAgent 包含【组合级贡献】段）

---

## 七、红线

1. **不改 PortfolioSentinel 判断逻辑 / schema / prompt / 节点流程**
2. **不改 .env**、不改 SellAgent
3. **单向只读**：MonitorAgent / ReviewAgent 不反向调用 PortfolioSentinel
4. **缓存缺失不报错**，降级为"组合数据不可用"
5. **改前备份，改后验证**
6. **遇阻塞先停下回报**

---

*Lark 制定。sir 拍板：Agent 解耦，只描述需求与规则，实现交给 Claude Code 按项目风格统一处理。*

---

# 批次 D：派发期自动判定 · 执行指令

> 生成：Lark（2026-08-20）
> 执行：Claude Code
> 决策人：sir 拍板
> 原则：只描述需求与规则，实现方式由 Claude Code 按项目现有风格统一处理

---

## 一、目标

本批次把 K47/K175/K185 派发期判定从「人肉看 K 线 + prompt 原则」升级为**代码层可注入的事实字段**。

**要做的事**：
- 新增派发期判定服务，按 K175 派发期 6 维（时间/空间/量价/主力/形态/政策）计算每只标的的派发期 0-5 阶段
- 注入 MonitorAgent / SellAgent / ScoreAgent 的 collect 段（仅追加，不动判断逻辑）
- 定时任务每日 15:30 跑一遍持仓+候选
- 单独查询接口 + 缓存机制

**不做什么**：
- 不改任何 Agent 的判断逻辑（agent_call / push_alert_node）
- 不改 LLM 研判 prompt（不写"看到派发期 X 就如何如何"，由 LLM 自由解读）
- 不改任何前端页面（徽章展示统一在批次 H 或后续 React 批次）

---

## 二、架构约束

### 新建对象

| 对象 | 说明 |
|------|------|
| `backend/app/services/distribution_phase.py` | 派发期判定主服务（参照 `holding_view.py` 纯计算风格） |
| `backend/app/db/models.py` 追加 | `distribution_phase_log` 表（trade_date/stock_code/phase/six_dim/missing_data/created_at） |
| `backend/app/db/repo.py` 追加 | `insert_phase_log` / `get_latest_phase` / `get_latest_phases_batch` |
| `backend/app/api/routes.py` 追加 | `GET /api/distribution_phase/{stock_code}` 单点查询 + `POST /api/distribution_phase/{code}/recompute` 手动重算 |

### 现有对象提升

| 对象 | 改什么 | 不改什么 |
|------|--------|---------|
| `monitor.py` | `collect_quote` 末尾追加读 `cache.get("distribution_phase:{code}")`，写入 `quote_data` 段 | schema 不改、图结构不改、节点流程不改 |
| `sell.py` | `collect_sell_input` 末尾追加 `distribution_phase_context` 段 | 同上 |
| `score.py` | `collect_score_input` 末尾追加 `distribution_phase_context` 段（不单独占一维） | 同上 |
| `jobs.py` | 新增 15:30 定时任务（交易日判断 + 异常不抛断） | 现有任务不动 |
| `cache.py` | 追加注释列出 `distribution_phase:*` 键规范 | 实现不动 |

### 解耦铁律

- 派发期判定服务**零耦合**所有 Agent：只通过 `cache` 暴露结果，Agent 在 collect 段读
- 不动任何 Agent 节点流程（仅 collect 段追加 1 段）
- 不改 prompt（由 LLM 自由解读派发期字段）
- 不改 .env、不改其他 Agent

---

## 三、规则

### 派发期 5 阶段 + 拉升期 0 阶段

| 阶段 | label | 触发条件（参考权重非死条件） |
|---|---|---|
| 0 | 拉升期 | 5 日累计涨幅 > 10% 或 距 52 周高 < 5% |
| 1 | 初期 | 缩量阴跌（量比 < 0.9 + 阴线）|
| 2 | 砸盘期 | 放量下杀（量比 > 1.5 + 跌幅 > 5%）|
| 3 | 反弹期 | 缩量反弹（量比 < 0.9 + 阳线）|
| 4 | 末跌期 | 连续 3 日阴线 + 跌幅累计 > 8% |
| 5 | 触底期 | Spring 反弹机会（K185：长下影 + 放量 + 站稳 5 日线）|

### 派发期 6 维输入字段（K175）

每维单独算分，组合判定 phase：

1. **时间维度**：5 日累计涨跌幅 / 20 日累计涨跌幅
2. **空间维度**：距 52 周高 / 距 52 周低
3. **量价维度**：量价背离（价涨量缩 / 价跌量放）/ 量价配合
4. **主力维度**：5 日主力净流入趋势（数据源缺失时标 `null`，不编造）
5. **形态维度**：近 10 日 K 线反转形态计数（吞没/十字星/锤头/上吊）
6. **政策维度**：近 30 日政策事件数（数据源缺失时标 `null`，不编造）

### 输出 schema

```json
{
  "stock_code": "601138",
  "trade_date": "2026-08-20",
  "phase": 0,
  "phase_label": "拉升期",
  "confidence": "高",
  "six_dim": {
    "time": {"5d_pct": 18.79, "20d_pct": 25.3, "signal": "超买"},
    "space": {"pct_to_52w_high": 1.5, "pct_to_52w_low": 45.2, "signal": "近高"},
    "volume_price": {...},
    "capital": {...},
    "pattern": {...},
    "policy": {...}
  },
  "missing_data": [],
  "reason": "时间维度 5 日 +18.79% > 10% + 距 52 周高 1.5% < 5% = 拉升期 0 阶段"
}
```

**纪律**：
- 任何维度数据缺失 → 该维 `signal: "数据不足"` + 全局 `missing_data: [...]`
- `confidence` 随缺失维度数自动降级（0 缺=高, 1-2 缺=中, ≥3 缺=低）
- `phase_label` 在 `confidence: "低"` 时加 `?` 后缀（如"拉升期?"）
- `reason` 用自然语言写判定依据（K223 事实为先），不只输出 phase 数字
- **数据缺失 ≠ 派发期 0**：必须是 0 才是 0，缺失时 `phase: null`

### 缓存与定时

- 缓存键：`distribution_phase:{stock_code}`，TTL 24h
- 定时任务：每日 15:30 跑一遍 `holding` + `candidate` 表的所有 code
- 落库：每次判定都写 `distribution_phase_log`（历史可查）
- 手动触发：`POST /api/distribution_phase/{code}/recompute` 强制重算并刷新缓存

### 红线约束

- **派发期判定 = 参考权重非死条件**（K22 工具不是枷锁）：LLM 可根据其他因素推翻
- **不写死"派发期 X 必须如何如何"**：prompt 不改，由 LLM 自由解读
- **不修改 K47/K175/K185 红线文本**：所有阈值是参考权重，存放在代码常量里（不写进 prompt）

---

## 四、实现参考

请遵循项目现有代码风格和模式：

- **派发期服务**：参照 `backend/app/services/holding_view.py` 的纯计算风格（不落库不研判，返回 dict 即可）
- **数据库表**：参照 `backend/app/db/models.py` 现有表结构 + `repo.py` 的 CRUD 模式
- **Agent collect 段追加**：参照 `monitor.py` / `sell.py` / `score.py` 现有 collect 段的字段组织方式（dict 拼装后注入 prompt）
- **缓存使用**：参照 `cache.set("portfolio_sentinel:last_risk", ..., 1800)` 的键名/TTL 规范
- **定时任务**：参照 `jobs.py` 现有 monitor / portfolio_sentinel 定时任务的写法（交易日判断 + 异常不抛断 + log 记录）
- **缺失数据兜底**：参照 `holding_view.py` 行情失败的"字段为 None + 前端显示 —"模式
- **派发期阶段定义**：参照 `base_file/持仓与盈亏计划_完整知识库_v1.0_2026-08-06.md` §9（K47 派发期 5 阶段）+ §10（K175 派发期 6 维）+ §9.3（K185 Spring 反弹）

---

## 五、执行顺序

1. 备份涉及文件
2. `models.py` 加 `distribution_phase_log` 表
3. `repo.py` 加 `insert_phase_log` / `get_latest_phase` / `get_latest_phases_batch`
4. 新建 `services/distribution_phase.py`（纯计算，输入 K 线/板块/主力，输出 phase + six_dim + missing_data）
5. `cache.py` 加键规范注释
6. `monitor.py` / `sell.py` / `score.py` collect 段各追加 1 段（读 cache，注入 prompt 输入）
7. `jobs.py` 加 15:30 定时任务
8. `routes.py` 加 `GET /api/distribution_phase/{code}` + `POST /api/distribution_phase/{code}/recompute`
9. 单测 `backend/tests/test_distribution_phase.py`
10. 验证

---

## 六、验证清单

- [ ] `services/distribution_phase.py` 6 维计算函数齐全
- [ ] `distribution_phase_log` 表结构 + repo CRUD 通过
- [ ] `GET /api/distribution_phase/{code}` 返回完整 6 维原始值 + phase + confidence + missing_data
- [ ] `monitor.py` / `sell.py` / `score.py` collect 段各追加 1 段（grep 验证）
- [ ] 持仓表所有 code 跑通派发期判定，结果落库 + 缓存
- [ ] 数据缺失时 `missing_data` 字段非空，phase 为 null
- [ ] 15:30 定时任务正常执行（交易日判断 + 异常不抛断）
- [ ] 缓存 TTL 24h 生效
- [ ] 单元测试 `test_distribution_phase.py` 覆盖 6 维计算 + 缺失数据兜底
- [ ] 全量 pytest 通过
- [ ] 输出一份派发期判定样本（6 维原始值 + phase + reason + missing_data）

---

## 七、红线

1. **不改任何 Agent 节点流程**（仅 collect 段追加 1 段）
2. **不改任何 LLM prompt**（不写"看到派发期 X 就如何如何"）
3. **不改 .env**、不改其他 Agent
4. **不修改 K47/K175/K185 红线文本**（阈值在代码常量里）
5. **数据缺失必标 `missing_data`，不编造**
6. **派发期判定 = 参考权重非死条件**（K22 工具不是枷锁）
7. **改前备份，改后验证**
8. **遇阻塞先停下回报**

---

*Lark 制定。sir 拍板：Agent 解耦，只描述需求与规则，实现交给 Claude Code 按项目风格统一处理。*

---

# 批次 E：游资数据真接入 · 执行指令

> 生成：Lark（2026-08-20）
> 执行：Claude Code
> 决策人：sir 拍板
> 原则：只描述需求与规则，实现方式由 Claude Code 按项目现有风格统一处理

---

## 一、目标

本批次把"游资维度"从 prompt 概念升级为**有数据源 + 有落库 + 有注入**的事实层。

**要做的事**：
- 复核 `dragon_tiger_source` / `capital_actor` / `dragon_tiger` / `capital_flow` / `capital_stats` 五张表/数据源是否落地
- 缺失则补全（参照 `base_file/游资维度嵌入需求规格_2026-08-09.md`）
- 新增 `capital_view.py` 服务（参照 `holding_view.py` 风格，纯计算不研判）
- K189 ⑥ 游资对倒识别代码化（纯代码判定，不交给 LLM）
- 注入 DiscoverAgent / ScoreAgent / MonitorAgent / SellAgent 的 collect 段

**不做什么**：
- 不改 Agent 节点流程（仅 collect 段追加 1 段）
- 不改 LLM 研判 prompt（不写"游资撤离就如何如何"，由 LLM 自由解读）
- 不动前端 React 版（徽章展示统一后续批次）
- 不绑死席位映射（未知营业部 → LLM 研判占位）

---

## 二、架构约束

### 复核与补全

| 对象 | 复核什么 | 缺则补什么 |
|------|---------|------------|
| `backend/app/datasource/dragon_tiger_source.py` | 龙虎榜抓取（东财 lhb / 上交所 / 深交所）| 参照 `akshare_source.py` 风格新建 + 兜底降级（多源 or 失败）|
| `backend/app/db/models.py` 四表 | `capital_actor` / `dragon_tiger` / `capital_flow` / `capital_stats` | 缺则补，参照需求规格 §1 |
| `backend/app/db/repo.py` CRUD | 四表读写函数 | 缺则补 |

### 新建对象

| 对象 | 说明 |
|------|------|
| `backend/app/services/capital_view.py` | 游资视图服务（输入 code + 时间范围，输出 recent_actors / coordination / stats_30d / theme_resonance / wash_trade_suspect / missing_data）|

### 现有对象提升

| 对象 | 改什么 | 不改什么 |
|------|--------|---------|
| `discover.py` | `collect_candidates` 末尾追加 `capital_flow` 段（题材共振加分）| schema 不改、图结构不改 |
| `score.py` | `collect_score_input` 末尾追加 `capital_view` 摘要到"资金/游资"维度 | 同上 |
| `monitor.py` | `collect_quote` 末尾追加 `capital_view` 摘要（持仓被游资关注/撤离）| 同上 |
| `sell.py` | `collect_sell_input` 末尾追加 `capital_view` 摘要（游资撤离信号）| 同上 |
| `cache.py` | 追加 `capital_view:*` 键规范注释 | 实现不动 |
| `jobs.py` | T+1 16:30 拉龙虎榜 + 聚合游资操作 + 统计胜率 | 现有任务不动 |

### 解耦铁律

- 游资视图服务**零耦合**所有 Agent：只通过 `cache` + DB 暴露结果
- 不绑死席位映射（未知营业部 → LLM 研判占位）
- K189 对倒识别 = 纯代码判定，不交给 LLM
- 跟买 ≠ 必胜（K225 诚实）：prompt 不变，事实层更厚

---

## 三、规则

### 游资视图输出 schema

```json
{
  "stock_code": "601138",
  "as_of": "2026-08-20",
  "recent_actors": [
    {"name": "赵老哥", "tier": "一线", "net_buy": 1.2e8, "days_active": 3}
  ],
  "coordination": "多游资同买",
  "stats_30d": {"胜率": 65.0, "盈亏比": 2.1, "平均持仓天数": 5},
  "theme_resonance": true,
  "wash_trade_suspect": false,
  "missing_data": []
}
```

**纪律**：
- 30 日内无数据 → `recent_actors: []` + `coordination: "数据不足"`，**不**写成"无动作"
- 未知营业部 → 标 `name: "未知"`，由 LLM 后续研判
- 胜率统计至少 10 笔交易才有意义，< 10 笔 → `stats_30d: null` + `missing_data: ["交易笔数不足"]`

### K189 ⑥ 游资对倒识别（纯代码）

- 同一标的近 5 个交易日：若同一营业部出现在买入 + 卖出两侧 → `wash_trade_suspect: true`
- 阈值：单次金额 ≥ 1000 万
- 标的级聚合：若该标的多日多次触发 → 标 `wash_trade_suspect: true`
- **不交给 LLM**：LLM 只负责解读对倒对操作的影响

### 注入点规范

- DiscoverAgent 注入到候选池评分（题材共振加分）
- ScoreAgent 注入到"资金/游资"维度（事实层加厚）
- MonitorAgent 输出"持仓被游资关注" / "持仓被游资撤离"信号（事实 + LLM 解读）
- SellAgent 注入"游资大幅净卖 + K189 出货验证"事实（LLM 决定是否减仓）

### 红线约束

- **游资跟买 ≠ 必胜**（K225 诚实）：prompt 不变，只加事实
- **K226 9 主体判定**仍是判断派发期派发嫌疑的核心，游资只是其中 1 个主体
- **K189 ⑥ 对倒 → 警惕**（不作为单点清仓依据）
- **K227 字段误读**：累计涨幅≠估值 / 瞬时≠全口径 / 单源≠多源 → 游资数据要标 source
- **不硬绑席位映射**：未知营业部由 LLM 研判占位

---

## 四、实现参考

请遵循项目现有代码风格和模式：

- **数据源**：参照 `backend/app/datasource/akshare_source.py` + `datasource/base.py` + `fallback.py` 模式
- **数据库表**：参照 `backend/app/db/models.py` 现有 SQLAlchemy 表 + `repo.py` CRUD 模式
- **游资视图服务**：参照 `backend/app/services/holding_view.py` 纯计算风格
- **K189 ⑥ 对倒识别**：参照 `游资大佬追踪体系_2026-08-08.md` §四（4 大对倒信号） + §七（K189 实战应用 5 步）
- **需求规格**：参照 `base_file/游资维度嵌入需求规格_2026-08-09.md` 全文（5 节）
- **游资体系方法论**：参照 `base_file/游资大佬追踪体系_2026-08-08.md` 全文
- **Agent collect 段追加**：参照 `monitor.py` / `sell.py` / `score.py` / `discover.py` 现有 collect 段的字段组织方式
- **缺失数据兜底**：参照 `holding_view.py` 行情失败的"字段为 None + 前端显示 —"模式

---

## 五、执行顺序

1. 备份涉及文件
2. 复核 `dragon_tiger_source` / 四张表 / repo CRUD（输出状态报告）
3. 缺则补全（数据源 + models + repo）
4. 新建 `services/capital_view.py`（recent_actors / coordination / stats_30d / wash_trade_suspect / missing_data）
5. `cache.py` 加键规范注释
6. `discover.py` / `score.py` / `monitor.py` / `sell.py` collect 段各追加 1 段
7. `jobs.py` 加 T+1 16:30 拉龙虎榜 + 聚合 + 胜率统计
8. 单测 `backend/tests/test_capital_view.py`
9. 验证

---

## 六、验证清单

- [ ] 复核结果：数据源 + 四表 + repo CRUD 状态报告
- [ ] `services/capital_view.py` 五字段齐全
- [ ] `GET /api/capital_view/{code}` 返回完整数据，缺数据字段全列
- [ ] 四个 Agent collect 段各追加 1 段（grep 验证）
- [ ] K189 ⑥ 对倒识别纯代码判定（不依赖 LLM）
- [ ] T+1 16:30 定时任务正常执行
- [ ] 30 日内无数据时 `coordination: "数据不足"`，不伪造"无动作"
- [ ] 未知营业部 → `name: "未知"`，不绑死席位
- [ ] 单元测试 `test_capital_view.py` 覆盖 5 字段 + 缺失数据兜底 + 对倒识别
- [ ] 全量 pytest 通过
- [ ] 输出一份游资视图样本（5 字段 + missing_data）

---

## 七、红线

1. **不改任何 Agent 节点流程**（仅 collect 段追加 1 段）
2. **不改任何 LLM prompt**（不写"游资撤离就如何如何"）
3. **不绑死席位映射**（未知营业部 → LLM 研判占位）
4. **跟买 ≠ 必胜**（K225 诚实）：prompt 不变，事实层更厚
5. **K189 ⑥ 对倒 → 警惕**（不作为单点清仓依据）
6. **不改 .env**、不改其他 Agent
7. **数据缺失必标 `missing_data`，不编造**
8. **改前备份，改后验证**
9. **遇阻塞先停下回报**

---

*Lark 制定。sir 拍板：Agent 解耦，只描述需求与规则，实现交给 Claude Code 按项目风格统一处理。*

---

# 批次 G：K 红线代码化（持仓知识库 v1.0 落地）· 执行指令

> 生成：Lark（2026-08-20）
> 执行：Claude Code
> 决策人：sir 拍板
> 原则：只描述需求与规则，实现方式由 Claude Code 按项目现有风格统一处理

---

## 一、目标

本批次把 C1/C2/C3/C4 + K139 SOP + K189 对倒 + K226 9 主体判定**从 prompt 原则升级为代码可注入的事实字段**，让 LLM 基于事实判断而不是凭印象。

**要做的事**：
- 新增 `red_line_check.py` 服务（纯计算，输入持仓+当前价+主力数据，输出 C1/C2/C3/K139 SOP/K226/K189 事实）
- 注入 MonitorAgent / SellAgent / PositionAgent 的 collect 段
- 单独查询接口
- React 版前端徽章（按 2026-08-20 sir 拍板的 React 优先规则）

**不做什么**：
- **不改 C1=60% / C2=30% / C3=0.92 / C4 等阈值**（L0 红线）
- **不改 K139 SOP / K189 / K226 红线文本**（存放在代码常量里，不写进 prompt）
- **不动任何 Agent 的判断逻辑**（仅 collect 段追加）
- **不动 Streamlit 前端**（按 React 优先规则）

---

## 二、架构约束

### 新建对象

| 对象 | 说明 |
|------|------|
| `backend/app/services/red_line_check.py` | 红线扫描主服务（参照 `holding_view.py` 纯计算风格）|
| `backend/app/api/routes.py` 追加 | `GET /api/red_line_check` 持仓红线扫描接口 |

### 现有对象提升

| 对象 | 改什么 | 不改什么 |
|------|--------|---------|
| `monitor.py` | `collect_quote` 末尾追加读 `red_line_check` + 注入【红线扫描】段 | schema 不改、图结构不改、prompt 不改 |
| `sell.py` | `collect_sell_input` 末尾追加读 `red_line_check` + 注入【K139 SOP 触发判定】段 | 同上 |
| `position.py` | `collect_position_input` 末尾追加读 `red_line_check` + 注入 C1/C2 软上限 + K192 吸筹末期策略 | 同上 |
| `cache.py` | 追加 `red_line_check:*` 键规范注释 | 实现不动 |

### 解耦铁律

- 红线扫描服务**零耦合**所有 Agent：只通过 `cache` + API 暴露结果
- **不改任何 Agent 节点流程**（仅 collect 段追加 1 段）
- **不改任何 LLM prompt**（不写"看到 C3 触发就如何如何"，由 LLM 自由解读）
- **不改 .env**、不改其他 Agent

---

## 三、规则

### 红线扫描输出 schema（每个持仓一行）

```json
{
  "stock_code": "601138",
  "as_of": "2026-08-20",
  "c1_cap_pct": 17.6,
  "c1_alert": false,
  "c2_alert": false,
  "c3_stop_loss": 59.00,
  "c3_alert": false,
  "c4_high_break": true,
  "pnl_pct": 1.86,
  "k139_sop": {
    "trailing_stop": 65.17,
    "stage": "持有观察",
    "next_action": "持有观察"
  },
  "k226_subject_count": 0,
  "k226_alert_level": "无",
  "k189_wash_suspect": false,
  "missing_data": []
}
```

**纪律**：
- 所有数值字段 null 显式标 null，前端显示"—"，**不**伪造 0
- C1/C2/C3 阈值不写死到 prompt 文本，仅在代码常量里
- K139 SOP 计算结果仅作参考，最终由 LLM 综合判断 + 人工执行
- K226 主体数据缺失时 `subject_count: null` + `alert_level: "数据不足"`

### K139 SOP 阶段判定（参考权重非死条件）

| 当前价 vs 成本 | 阶段 | next_action |
|---|---|---|
| 跌破 C3（成本 × 0.92）| 跌破 C3 | 立即清仓（不犹豫）|
| 移动止盈线以下 | 持有观察 | 持有观察 |
| 移动止盈线 ~ +5% | 持有观察 | 持有观察 |
| +5% 触发（成本 × 1.05）| +5% 减仓 | 减仓 1/3 ~ 1/2 锁利 |
| +10% 触发（成本 × 1.10）| +10% 减仓 | 减仓 1/3 锁利 |
| 突破 52 周高 | 突破 | 警惕 + 评估是否继续持有 |

**移动止盈线** = 成本 + (现价 - 成本) × 0.5（K183 移动止盈法）

### 注入点规范

- MonitorAgent：每持仓在 `quote_data` 段追加 `【红线扫描】{red_line_check 摘要}`
- SellAgent：每持仓在 `quote_pack` 段追加 `【K139 SOP 触发判定】{k139_sop}`
- PositionAgent：建仓前在 `position_input` 段追加 C1/C2 软上限 + K192 吸筹末期策略

### 前端徽章（React 新版优先）

- 当前持仓表格右侧每行加 4 个小徽章：C1/C2/C3/K139（绿/黄/红/灰四态）
- 鼠标悬停显示触发条件（如"C3 止损 59.00，距 -0.5%"）
- 颜色规范：绿=正常 / 黄=接近阈值（±20%）/ 红=已触发 / 灰=数据不足
- **不在 Streamlit 版做**（按 2026-08-20 sir 拍板的 React 优先规则）

### 红线约束

- **不改 C1=60% / C2=30% / C3=0.92 / C4 阈值**（L0 红线，写在代码常量里）
- **不改 K139 SOP / K189 / K226 红线文本**
- **K139 SOP = 参考权重非死条件**（K22 工具不是枷锁）：LLM 可调整
- **数字缺失 → 字段 null**，不默认 0
- **前端徽章只在 React 新版做**，Streamlit 不动
- **auto-merge 永不碰阈值**

---

## 四、实现参考

请遵循项目现有代码风格和模式：

- **红线扫描服务**：参照 `backend/app/services/holding_view.py` 的纯计算风格（不落库不研判，返回 dict 即可）
- **Agent collect 段追加**：参照 `monitor.py` / `sell.py` / `position.py` 现有 collect 段的字段组织方式
- **K139 SOP 阶段定义**：参照 `base_file/持仓与盈亏计划_完整知识库_v1.0_2026-08-06.md` §3（K139 SOP 持盈不持亏）+ §4（关键风控位）
- **K226 9 主体判定**：参照 `base_file/游资维度嵌入需求规格_2026-08-09.md` §3.1 + `base_file/游资大佬追踪体系_2026-08-08.md` §七
- **K189 对倒识别**：依赖批次 E 的 `capital_view.wash_trade_suspect` 字段
- **C 档红线**：参照 `base_file/持仓与盈亏计划_完整知识库_v1.0_2026-08-06.md` §二（C1/C2/C3/C4）
- **K183 移动止盈法**：参照 §3.3 K139 SOP + §3.3 K183
- **缺失数据兜底**：参照 `holding_view.py` 行情失败的"字段为 None + 前端显示 —"模式
- **React 徽章**：参照 `web/src/components/Badge.tsx`（如有）的徽章样式

---

## 五、执行顺序

1. 备份涉及文件
2. 新建 `services/red_line_check.py`（C1/C2/C3/C4/K139/K226/K189 字段计算）
3. `cache.py` 加键规范注释
4. `monitor.py` / `sell.py` / `position.py` collect 段各追加 1 段
5. `routes.py` 加 `GET /api/red_line_check` 接口
6. 前端 `web/src/pages/HoldingsPage.tsx` 加 4 个小徽章（颜色 + 悬停提示）
7. 单测 `backend/tests/test_red_line_check.py`
8. 验证

---

## 六、验证清单

- [ ] `services/red_line_check.py` 全字段计算（10 个字段齐全）
- [ ] `GET /api/red_line_check` 返回所有持仓红线扫描结果
- [ ] 三个 Agent collect 段各追加 1 段（grep 验证）
- [ ] C1/C2/C3 阈值与知识库 v1.0 §二完全一致（60% / 30% / 0.92）
- [ ] K139 SOP 阶段计算正确（移动止盈 / +5% / +10% / 跌破 C3）
- [ ] K189 对倒嫌疑字段从批次 E 的 `capital_view.wash_trade_suspect` 读取
- [ ] 数字缺失 → 字段 null，前端显示"—"
- [ ] 单元测试 `test_red_line_check.py` 覆盖 10 字段 + 缺失数据兜底
- [ ] 全量 pytest 通过
- [ ] React 版徽章颜色与字段值一一对应
- [ ] 输出一份红线扫描样本（10 字段全 + missing_data）

---

## 七、红线

1. **不改 C1/C2/C3/C4 阈值**（L0 红线，写在代码常量里）
2. **不改 K139 SOP / K189 / K226 红线文本**
3. **不改任何 Agent 节点流程**（仅 collect 段追加 1 段）
4. **不改任何 LLM prompt**（不写"看到 C3 触发就如何如何"）
5. **不改 .env**、不改其他 Agent
6. **数字缺失 → null**，不默认 0
7. **前端徽章只在 React 版做**，Streamlit 不动
8. **改前备份，改后验证**
9. **遇阻塞先停下回报**

---

*Lark 制定。sir 拍板：Agent 解耦，只描述需求与规则，实现交给 Claude Code 按项目风格统一处理。*

---

# 批次 H：复盘反哺选股（组合级 + 个股级对比）· 执行指令

> 生成：Lark（2026-08-20）
> 执行：Claude Code
> 决策人：sir 拍板
> 原则：只描述需求与规则，实现方式由 Claude Code 按项目现有风格统一处理

---

## 一、目标

本批次把复盘从"胜率统计"升级为"组合级曲线 + 各持仓贡献度 + 跨期复利"三维分析，回流到 ScoreAgent 的"历史胜率"维度。

**要做的事**：
- `track_verify.py` 追加 2 个新函数（不动现有函数）：`build_portfolio_attribution` + `build_stock_cycle_attribution`
- ReviewAgent collect 段追加读组合级 + 贡献度
- ScoreAgent 加"历史胜率"加分规则（不破坏 5 维结构，作为加分项）
- React 复盘页增强：组合曲线 + 瀑布图 + 周期复利表

**不做什么**：
- **不改 track_verify 现有函数**（仅追加新函数）
- **不改 ReviewAgent / ScoreAgent 节点流程**（仅 collect 段追加）
- **不改 5 维评分结构**（历史胜率作为加分项，不单独占一维）
- **不动 Streamlit 复盘页**（按 React 优先规则，与 v2 工单 9 衔接）

---

## 二、架构约束

### 现有对象提升

| 对象 | 改什么 | 不改什么 |
|------|--------|---------|
| `track_verify.py` | 追加 2 个新函数（`build_portfolio_attribution` + `build_stock_cycle_attribution`）| 现有所有函数不动、签名不动、单测不动 |
| `review.py` | `collect_review_input` 末尾追加读组合级 + 贡献度计算 | schema 不改、图结构不改、prompt 不改 |
| `score.py` | `collect_score_input` 末尾追加读历史胜率 + 加分规则（不单独占一维，作为"资金/游资"维度加分项）| 同上 |
| `cache.py` | 追加 `track_verify:portfolio:*` / `track_verify:cycle:*` 键规范注释 | 实现不动 |

### 不新建对象

本批次零新建。

### 解耦铁律

- track_verify 现有函数**零改动**（仅追加 2 个新函数 + 单测）
- 贡献度计算口径**写死到代码 + 注释 + 单测**，不依赖 LLM
- ReviewAgent / ScoreAgent 仅 collect 段追加 1 段，节点流程不动
- 不改 .env、不改其他 Agent

---

## 三、规则

### `build_portfolio_attribution(period_days: int)` 输出 schema

```json
{
  "period_days": 30,
  "as_of": "2026-08-20",
  "portfolio_curve": [
    {"date": "2026-07-22", "total_pnl_pct": 0.0},
    {"date": "2026-07-23", "total_pnl_pct": -0.5},
    {"date": "2026-08-20", "total_pnl_pct": 5.2}
  ],
  "contributors": [
    {"stock_code": "601138", "stock_name": "工业富联", "contribution_pct": 35.0, "pnl_amount": 1050.00, "holding_days": 15},
    {"stock_code": "601012", "stock_name": "隆基绿能", "contribution_pct": 65.0, "pnl_amount": 1950.00, "holding_days": 18}
  ],
  "drag_analysis": "最大贡献者 隆基绿能 (65.0%)；最大拖累者 无",
  "missing_data": []
}
```

**计算口径**：
- 每日组合盈亏 = Σ(单票 pnl) / 总成本
- 贡献度 = 单票盈亏 / 组合总盈亏 × 100%
- 仅统计 `status="holding"` + `status="closed"` 的持仓
- `period_days` 默认 30，可配置 7/30/90/365

**纪律**：
- 数据缺失时 `missing_data` 列出，不伪造曲线
- 持仓无历史 → `contributors: []` + `drag_analysis: "无持仓数据"`
- 组合总盈亏为 0 → `contribution_pct: 0.0`（不除零）

### `build_stock_cycle_attribution(stock_code: str)` 输出 schema

```json
{
  "stock_code": "601138",
  "as_of": "2026-08-20",
  "total_cycles": 3,
  "total_pnl_amount": 1250.00,
  "avg_holding_days": 12.5,
  "win_cycles": 2,
  "loss_cycles": 1,
  "win_rate": 0.667,
  "best_cycle": {"entry_date": "2026-06-01", "exit_date": "2026-06-20", "pnl_pct": 8.5},
  "worst_cycle": {"entry_date": "2026-07-15", "exit_date": "2026-07-30", "pnl_pct": -3.2},
  "missing_data": []
}
```

**计算口径**：
- 同一 code 的所有 `status="closed"` 记录按 entry_date 配对为 cycle
- 每次"建仓 → 清仓"为一个完整 cycle
- win_rate 输出口径 = 0-1 小数（前端展示层显式 × 100，**绝不**再二次乘 100）
- avg_holding_days = Σ(cycle 持仓天数) / total_cycles

### ScoreAgent 历史胜率加分规则

- 读取 `build_stock_cycle_attribution(stock_code)` 结果
- 历史胜率 ≥ 60% → "资金/游资"维度追加 +5 分（封顶 100）
- 历史拖累率（最大拖累者）≥ 30% → "资金/游资"维度扣 -10 分（下限 0）
- 缺失历史 → 标"无历史数据"，不加分不扣分
- **不改变 5 维评分结构**（历史胜率作为加分项，不单独占一维）

### ReviewAgent 注入规则

- 复盘顶部展示条新增：`组合 {total_pnl_pct}%，最大贡献者 {top_contributor} ({pct}%)，最大拖累者 {top_drag} ({pct}%)`
- 每只历史持仓卡片显示"对组合贡献度"（正绿/负红）
- 同代码多次操作 → 折叠展示"周期复利"汇总（win_rate + best/worst cycle）
- 数据缺失时标注"组合数据不可用"，不影响个股级复盘

### 红线约束

- **不改 track_verify 现有函数**（仅追加 2 个新函数 + 新单测）
- **不改 5 维评分结构**（历史胜率作为加分项，不单独占一维）
- **win_rate 输出口径统一为 0-1 小数**（前端展示层显式 × 100，**绝不**再二次乘 100 —— 防止 4400% bug 复发）
- **不改 .env**、不改其他 Agent
- **auto-merge 永不碰口径常量**

---

## 四、实现参考

请遵循项目现有代码风格和模式：

- **新函数追加**：参照 `track_verify.py` 现有 `_group_stats` / `_calc_stats` 函数的纯计算风格
- **贡献度计算**：参照 `holding_view.py` 的 `build_account_summary` 汇总逻辑（双数据路径 + 缺失数据兜底）
- **Agent collect 段追加**：参照 `review.py` / `score.py` 现有 collect 段的字段组织方式
- **win_rate 口径**：参照 `track_verify._group_stats` 0-100 百分制 vs `_calc_stats` 0-1 小数 —— 本批次**统一 0-1 小数**，避免 4400% bug 复发
- **缓存使用**：参照 `cache.set("portfolio_sentinel:last_risk", ..., 1800)` 的键名/TTL 规范
- **React 复盘页**：参照 `web/src/pages/ReviewsPage.tsx` 现有 Tabs 结构 + `v2 工单 9`（ReviewsPage 补全 1409→214）后续 batch
- **缺失数据兜底**：参照 `holding_view.py` 行情失败的"字段为 None + 前端显示 —"模式

---

## 五、执行顺序

1. 备份涉及文件
2. `track_verify.py` 追加 `build_portfolio_attribution` + `build_stock_cycle_attribution` 两个新函数（**不动现有函数**）
3. `cache.py` 加键规范注释
4. `review.py` collect_review_input 末尾追加读组合级 + 贡献度
5. `score.py` collect_score_input 末尾追加读历史胜率 + 加分规则
6. 单测 `backend/tests/test_track_verify_attribution.py`（**新建**，不与现有 `test_track_verify.py` 冲突）
7. 验证

---

## 六、验证清单

- [ ] `build_portfolio_attribution` 输出完整曲线 + contributors + drag_analysis
- [ ] `build_stock_cycle_attribution` 输出完整 win_rate + best/worst cycle
- [ ] track_verify 现有所有函数签名 / 输出零改动
- [ ] 现有 `test_track_verify.py` 全量通过
- [ ] `review.py` collect 段包含「组合级贡献」（grep 验证）
- [ ] `score.py` collect 段包含「历史胜率」（grep 验证）
- [ ] win_rate 输出口径统一为 0-1 小数（前端展示层 × 100）
- [ ] 历史胜率 ≥ 60% → 资金维度追加 +5 分（单测验证）
- [ ] 历史拖累率 ≥ 30% → 资金维度扣 -10 分（单测验证）
- [ ] 缺失历史 → 标"无历史数据"，不加分不扣分
- [ ] 单元测试 `test_track_verify_attribution.py` 覆盖 2 个新函数 + 加分规则
- [ ] 全量 pytest 通过
- [ ] 输出一份组合归因样本（曲线 + contributors + drag_analysis）

---

## 七、红线

1. **不改 track_verify 现有函数**（仅追加 2 个新函数）
2. **不改 5 维评分结构**（历史胜率作为加分项，不单独占一维）
3. **不改任何 Agent 节点流程**（仅 collect 段追加 1 段）
4. **不改任何 LLM prompt**（不写"看到胜率高就如何如何"）
5. **win_rate 输出口径统一为 0-1 小数**（防止 4400% bug 复发）
6. **不改 .env**、不改其他 Agent
7. **改前备份，改后验证**
8. **遇阻塞先停下回报**

---

*Lark 制定。sir 拍板：Agent 解耦，只描述需求与规则，实现交给 Claude Code 按项目风格统一处理。*
