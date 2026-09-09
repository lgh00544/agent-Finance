# 系统能力地图与 Agent 协作治理：批 7 Codex 执行提示词

## 任务

你在 `D:\self` 项目中执行批 7：**已有专业服务工具化**。

目标：把系统里已经存在的专业分析服务包装成 ReAct 只读工具，让 Agent 按需调用，不再依赖一次性把所有专业上下文塞进 prompt。

参见：

- `D:\self\系统能力地图与Agent协作治理_方案.md` §7 批 7：已有专业服务工具化
- `D:\self\Memory治理与记忆防污染_提单.md` §5、§7、§9

引用文档只作参考，以本提示词为准。

## 当前代码事实

1. ReAct 工具在 `backend/app/agents/agentic_tools.py`，结构是 `TOOLS` schema + `TOOL_FUNCS` 函数表。
2. `agentic_call()` 在 `backend/app/agents/common.py` 里调用 `select_tools(tools_allowlist)`。
3. `score.py`、`sell.py`、`monitor.py` 已有 `tools_allowlist`。
4. 批 6 已治理 DB 私有知识；本批不要改知识注入。

## 必须先定位

只读锚点附近，不整读大文件：

```powershell
rg -n "def agentic_call|select_tools|TOOLS =|TOOL_FUNCS|_AGENTIC_TOOL_NOTE|tools_allowlist|def compute_distribution_phase|def compute_capital_view|def get_capital_stats|def get_factor_calibration|def judge_regime|def get_sector_regime_forecast|def aggregate_for_stock|def build_hot_money_context|def build_plans|portfolio_sentinel:last_risk" backend/app backend/tests
```

重点文件：

1. `backend/app/agents/agentic_tools.py`
2. `backend/app/agents/common.py`
3. `backend/app/agents/score.py`
4. `backend/app/agents/sell.py`
5. `backend/app/agents/monitor.py`
6. 相关服务：`sector_regime.py`、`track_verify.py`、`distribution_phase.py`、`capital_view.py`、`hot_money.py`、`take_profit.py`、`portfolio_sentinel.py`

## 新增工具

在 `agentic_tools.py` 增加 6 个只读工具，并同步注册到 `TOOLS` 和 `TOOL_FUNCS`：

1. `get_sector_regime(trade_date: str = "")`
   - 读已有板块结构预测。
   - 优先 `repo.get_sector_regime_forecast(date)`。
   - 不要调用 `sector_regime.judge_regime()`，因为它会落库。
2. `get_factor_calibration(period: str = "t5")`
   - 调用 `track_verify.get_factor_calibration(period)`。
   - 返回紧凑文本；空数据返回 `{"text": "", "note": "no_data"}`。
3. `get_distribution_phase(code: str, trade_date: str = "")`
   - 调用 `distribution_phase.compute_distribution_phase(code, date)`。
   - 该服务只写缓存可接受；不得新增 DB 写入。
4. `get_capital_view(code: str, trade_date: str = "")`
   - 只读已有资本视图快照。
   - 优先读 cache 或 `repo.get_capital_stats(code, date)`。
   - 不要直接调用 `compute_capital_view()`，因为它会落 4 张表。
5. `get_position_risk(code: str = "")`
   - 读取组合/持仓风险快照。
   - 优先读 `portfolio_sentinel:last_risk` cache；可调用 `take_profit.build_plans(trace=False, check_alerts=False)` 后按 code 过滤。
   - 不允许触发告警、留痕或交易动作。
6. `get_hot_money_context(code: str, stock_name: str = "", trade_date: str = "")`
   - 返回游资上下文。
   - 如果复用 `hot_money.aggregate_for_stock()` 会写 trace，必须先给它加向后兼容参数 `trace: bool = True`，工具调用传 `trace=False`。
   - 不改游资判断逻辑。

所有工具要求：

1. 只读业务状态，不写 profile、rule_change、agent_suggestion、交易表。
2. 允许读数据源、读缓存、写短期 cache；不允许告警/留痕/审核/交易副作用。
3. 返回 JSON 可序列化，复用 `_safe()`。
4. 异常必须由 `_wrap()` 转为 `{"error": ...}`，不中断主链路。
5. 大结果必须截断，只给摘要字段，避免工具输出撑爆 prompt。

## 更新工具说明

更新 `_AGENTIC_TOOL_NOTE`，补充新增工具名称和使用边界：

1. 数据充分时不要空转调工具。
2. 新工具仅用于核验或补充缺失维度。
3. 工具返回 error/no_data 时应降级，不得编造。

## Agent allowlist

只在已有 agentic 分支里调整 allowlist：

1. `score.py`
   - 增加：`get_sector_regime`、`get_factor_calibration`、`get_distribution_phase`、`get_capital_view`、`get_hot_money_context`
   - 保留原工具。
2. `sell.py`
   - 增加：`get_position_risk`、`get_distribution_phase`、`get_capital_view`、`get_hot_money_context`
   - 不加 `get_financial`，除非原来已有。
3. `monitor.py`
   - 高危复核增加：`get_position_risk`、`get_distribution_phase`、`get_capital_view`、`get_hot_money_context`
   - 保持 `max_rounds=4`，不要放大成本。

不要让 `select_tools(None)` 变成默认开放全部新工具给所有 Agent。若当前 `None=全量` 行为保留，必须确保实际调用方都显式 allowlist；测试要锁住关键 Agent 的 allowlist。

## 可选系统地图同步

`system_map.registry.list_tools()` 如果是读取 `agentic_tools.TOOLS`，新增工具会自动出现。若测试需要，可补充一条系统地图工具列表测试。

## 不要改

1. 不改 Agent 输出 schema。
2. 不改批 6 知识元数据、知识注入和 `knowledge_section()`。
3. 不改规则采纳审核闸门。
4. 不新增自动下单或交易接口。
5. 不新增新的投研算法；只包装已有服务。
6. 不让工具调用触发业务落库、告警、审核或交易动作。

## 测试要求

新增或扩展最小测试，推荐新增：

```text
backend/tests/test_agentic_tools_professional.py
```

覆盖：

1. `TOOLS` 和 `TOOL_FUNCS` 同时包含 6 个新增工具。
2. `select_tools(["get_sector_regime"])` 只返回白名单工具。
3. 每个新增工具成功路径返回 JSON 可序列化对象。
4. 服务异常时工具返回 `error`，不中断。
5. `get_sector_regime` 不调用 `judge_regime()`。
6. `get_capital_view` 不调用 `compute_capital_view()`。
7. `get_hot_money_context` 调用聚合时传 `trace=False`，或等价证明不写 trace。
8. `get_position_risk` 调用 `build_plans(trace=False, check_alerts=False)` 或只读 cache。
9. `score/sell/monitor` 的 allowlist 含预期新工具，且 monitor 仍 `max_rounds=4`。
10. `system_map` 工具列表能看到新增工具。

测试中优先 monkeypatch 服务函数，不访问真实网络和外部数据源。

## 验收命令

只跑相关测试：

```powershell
D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_agentic_tools_professional.py backend\tests\test_system_map.py backend\tests\test_score_refactor.py backend\tests\test_distribution_phase.py backend\tests\test_capital_view.py backend\tests\test_hot_money_inject.py
```

如果只改了 agentic 工具和 allowlist，失败时先收窄到新测试定位，不要全量回归。

## 汇报格式

```text
改动文件+行号：

- [文件](绝对路径)：说明

测试：

- 命令：passed X / failed Y

红线核对：

- 未改 Agent 输出 schema：是
- 未改知识注入与知识元数据：是
- 未改采纳审核闸门：是
- 新工具只包装已有服务：是
- 工具失败降级 error：是
- 工具调用不触发业务落库/告警/审核/交易：是
- 未开放交易接口：是

遗留/下一批：

- ...
```

