# 关系持仓批次 E · 游资数据真接入 · DSH 工程指令

> 方案：`D:\self\关系持仓_个股分析_优化方案.md` §三模块2

## 一、目标

游资维度从「prompt 原则」升级为「代码可注入事实层」：K189 对倒纯代码判定 + 4 Agent collect 段注入 + 持仓黄/红/灰徽章。

## 二、范围（DSH 出 diff，工程师跑测试+commit）

| # | 改动 | 文件 |
|---|---|---|
| 1 | 复核 `datasource/dragon_tiger_source.py` 是否存在，缺则新建（akshare 拉龙虎榜落 `dragon_tiger` 表）| `backend/app/datasource/dragon_tiger_source.py`（可能新建）|
| 2 | 复核 `db/models.py` 四表（`capital_actor / dragon_tiger / capital_flow / capital_stats`）缺哪个补哪个，仿 `sector_snapshot` 风格 | `backend/app/db/models.py` `backend/app/db/init.sql` `backend/app/db/session.py` `backend/app/db/repo.py` |
| 3 | 新建 `compute_capital_view(symbol, trade_date)` 主服务 | `backend/app/services/capital_view.py`（新建）|
| 4 | 注入 4 Agent collect 段 | `backend/app/agents/{discover,score,monitor,sell}.py` |
| 5 | 路由 + 缓存击穿 | `backend/app/api/routes.py` |
| 6 | 前端三维表 + 徽章 | `streamlit/pages/5_游资追踪.py` + `web/src/`（React 同步）|
| 7 | 测试 + commit | `backend/tests/test_capital_view.py`（新建）+ git |

## 三、规则

**K189 对倒**（纯代码）：同标的近 5 日，同营业部同出现在买+卖两侧 + 单次金额 ≥ 1000 万 → `wash_suspect: True`。

**Schema**：
```
{"recent_actors":[{name,tier,net_buy,days_active}],
 "coordination":"多游资同买|单家动作|无显著动作|数据不足",
 "wash_suspect":false,
 "stats_30d":{胜率,盈亏比,平均持仓天数},
 "theme_resonance":true,
 "source":"sse_only",
 "missing_data":[]}
```

**30 日无数据**→`recent_actors:[]`, `coordination:"数据不足"`，**绝不写"无动作"`**。

**注入点**（4 Agent 各 1 字段 `capital_view_context`）：Discover 在 `capital_flow` 段后；Score 在「资金/游资」维度（加分项仿 D 派发期减分项）；Monitor 在 D 派发期字段后追加；Sell 在 `portfolio_risk_context` 后追加（D 派发期后）。

**缓存**：`SimpleCache().get_or_set(key=f"capital_view:{trade_date}:{symbol}", ttl=86400)`。

**徽章**：被游资关注→黄；被游资撤离+触发对倒→红；无数据→灰。

## 四、红线（4 条）

1. **不动 `agent_call` / `push_alert_node`**——只动 collect 段
2. **不碰 `_TR` 交易规则表**
3. **不写「无数据=无动作」**（K227 诚实）
4. **不硬绑席位映射**——未知营业部→LLM 研判占位

## 五、DSH 操作流程

按编号顺序让 DSH 一次出全部 diff，工程师逐条 Apply。每 Apply 一条 → 工程师跑下面验证 → 通过再进下一条。

| 阶段 | DSH 出 | 工程师做 |
|---|---|---|
| 1 | 数据源 + 四表 diff（含 `_ensure_*_table()` + `_upsert_*` 入 repo）| `python -c "from app.db.session import init_db; init_db()"` 看表建成功 |
| 2 | `services/capital_view.py` 新建 | `python -c "from app.services.capital_view import compute_capital_view; print(compute_capital_view('600519','2026-08-24'))"` 调通 |
| 3 | 4 Agent collect 注入 diff | `grep "capital_view_context" backend/app/agents/{discover,score,monitor,sell}.py` 各 1 行 |
| 4 | routes + ?force=true 击穿 | `curl http://localhost:8000/api/capital_view/600519?force=true` |
| 5 | Streamlit + React 前端 diff | 浏览器看徽章三色态 |
| 6 | `tests/test_capital_view.py` ≤ 5 用例 | `pytest backend/tests/test_capital_view.py -v && pytest backend/tests/ -v` |
| 7 | — | 全部绿后 commit（不 push）：`git add -A && git commit -m "[批次E] 游资数据真接入：dragon_tiger_source + 4表 + capital_view + K189对倒 + 4 Agent 注入 + 前端徽章"` |

## 六、测试用例（≤ 5）

1. `test_wash_trade_suspect_true` — 同标的近 5 日同席位买+卖 ≥ 1000 万 → `wash_suspect: True`
2. `test_no_data_writes_insufficient` — 30 日无数据 → `coordination: "数据不足"`（不写「无动作」）
3. `test_recent_actors_fields_complete` — `recent_actors` 字段齐全（name/tier/net_buy/days_active）
4. `test_4_agents_collect_injects` — 4 Agent collect 段可读出 `capital_view_context`
5. `test_force_cache_bypass` — `?force=true` 跳缓存

## 七、风格

- 仿 `holding_view.py` 纯计算风格
- 仿 `sector_snapshot.py` SimpleCache + 24h TTL
- 仿 `distribution_phase.py` 6 维 → 1 维主入口的写法
- 函数 docstring ≤ 3 行；不写大段注释
- 复用已有函数：`holding_view.py / distribution_phase.py / _ensure_sector_snapshot_table` 直接调，不重写

## 八、沟通

DSH 出 diff 后，工程师在右侧文件树核对 Apply；任何红线触碰立即停下报 sir。批次 E 完成后停等验收，再进批次 G（K 红线代码化，依赖 E 的 wash_suspect）。
