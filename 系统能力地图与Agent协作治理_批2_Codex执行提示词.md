# 系统能力地图与 Agent 协作治理 · 批 2 Codex 执行提示词

你在 `D:\self` 项目中执行本批任务。

## 前置状态

批 1 已完成并通过：

- 新增 `backend/app/system_map/registry.py`
- 新增 `/api/system-map*` 只读端点
- `D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_system_map.py`：5 passed

本批只做“协作矩阵最小闭环”，不接入业务强制拦截。

## 任务目标

建立只读 Agent 协作矩阵，让系统能查询：

1. 某个 Agent 可以调用谁。
2. 某个 Agent 可以引用谁。
3. 某个 Agent 是否可以提出规则变更。
4. 哪些协作关系需要审核。
5. 未注册关系默认 forbidden。

详细设计参见 `系统能力地图与Agent协作治理_方案.md`：

- §4 协作矩阵
- §7 批 2：协作矩阵最小闭环
- §8 Codex 执行兼容要求

## 执行纪律

1. 先用 `rg -n` 定位批 1 文件和 API，不整读大文件。
2. 本批只新增/扩展 system_map 的只读协作矩阵。
3. 不修改任何 Agent 输出。
4. 不修改 `common.py` 注入逻辑。
5. 不修改 `rule_change` 注入逻辑。
6. 不修改飞书、chat_router、任务执行逻辑。
7. 不新增写库路径。
8. 不引入网络依赖。
9. 只跑本批相关测试。

## 先定位

请先定位以下符号，只读附近代码：

```powershell
rg -n "list_agents|get_agent|list_tools|list_workflows|get_system_map_summary|system-map" backend/app/system_map backend/app/api/routes.py backend/tests
```

重点确认：

1. `backend/app/system_map/registry.py` 的现有函数风格。
2. `/api/system-map*` 端点所在位置。
3. `backend/tests/test_system_map.py` 的 test client 写法。

## 建议改动

### 1. 新增协作矩阵模块

优先在现有 system_map 包内新增：

```text
backend/app/system_map/collaboration.py
```

若批 1 已把相关结构都集中在 `registry.py`，也可以放在 `registry.py`，但推荐单独文件，避免 registry 变臃肿。

提供只读函数：

```text
list_collaboration_rules()
can_collaborate(requester_agent, target_agent, relation)
list_allowed_targets(agent_id)
```

返回结构必须 JSON 可序列化。

### 2. 协作关系字段

每条规则建议字段：

```text
requester_agent
target_agent
relation: call / reference / summarize / propose_change / forbidden
allowed: true / false
max_depth
conflict_policy
audit_required
reason
```

默认策略：

1. 未注册关系默认 forbidden。
2. Agent 不允许调用自己。
3. `entry_orchestrator` 类型可 call 业务 Agent，但不能直接让变更生效。
4. `review` 可 `propose_change` 到业务 Agent，但 `audit_required=true`。
5. `audit` 可审核建议，但不能修改规则。
6. `score` 可 reference `discover` / `market_intel`，但不能无条件覆盖自己的评分。
7. `sell` / `monitor` 可 reference `market_intel` / `portfolio_sentinel` / 风险类能力。

### 3. 最小矩阵内容

第一版至少覆盖：

```text
feishu_gateway -> discover / score / position / monitor / sell / review / market_intel: call allowed
chat_entry -> discover / score / position / monitor / sell / review / market_intel: call allowed
score -> discover: reference allowed
score -> market_intel: reference allowed
score -> portfolio_sentinel: reference allowed
sell -> monitor: reference allowed
sell -> market_intel: reference allowed
sell -> portfolio_sentinel: reference allowed
monitor -> portfolio_sentinel: reference allowed
review -> discover / score / position / monitor / sell: propose_change allowed, audit_required=true
audit -> agent_suggestion: reference allowed
```

说明：

1. 如果批 1 没有注册 `feishu_gateway` / `chat_entry`，本批可先在矩阵里作为虚拟入口 agent_id 使用，不强制新增 AgentDefinition。
2. `agent_suggestion` 不是 Agent 时，可作为 target_kind 或 resource 处理；不要为它强行新增业务 Agent。

### 4. 新增只读 API

在现有 API 路由中新增：

```text
GET /system-map/collaboration
GET /system-map/agents/{agent_id}/allowed-targets
GET /system-map/can-collaborate?requester=&target=&relation=
```

要求：

1. `/collaboration` 返回完整矩阵。
2. `/agents/{agent_id}/allowed-targets` 返回该 Agent 可协作目标。
3. `/can-collaborate` 返回：
   - requester_agent
   - target_agent
   - relation
   - allowed
   - audit_required
   - conflict_policy
   - reason
4. 未注册关系返回 `allowed=false`，不要 500。

### 5. 新增测试

新增或扩展：

```text
backend/tests/test_system_map_collaboration.py
```

至少覆盖：

1. `can_collaborate("score", "discover", "reference")` 为 allowed。
2. `can_collaborate("score", "score", "call")` 为 forbidden。
3. `can_collaborate("review", "score", "propose_change")` 为 allowed 且 `audit_required=true`。
4. 未注册关系默认 forbidden。
5. API `/api/system-map/collaboration` 返回非空列表。
6. API `/api/system-map/agents/score/allowed-targets` 包含 discover 或 market_intel。
7. API `/api/system-map/can-collaborate?...` 对 allowed/forbidden 都能稳定返回。

## 验收命令

只跑批 1 + 批 2 相关测试：

```powershell
D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_system_map.py backend\tests\test_system_map_collaboration.py
```

不要跑全量测试。

## 红线核对

完成后逐条核对并在汇报中给结论：

1. 未改任何交易/评分/卖出/监控业务判断。
2. 未改任何 prompt 注入逻辑。
3. 未改 `rule_change` 注入逻辑。
4. 未新增写库路径。
5. 协作矩阵当前只读展示，不拦截业务链路。
6. 未开放任何下单/撤单/券商接口。

## 停手条件

遇到以下情况停止并报告：

1. 需要重构批 1 `registry.py` 才能完成。
2. 需要改现有 Agent 输出 schema。
3. 需要改 `common.py` 注入逻辑。
4. 需要接入 chat_router / 飞书真实路由。
5. 需要新增数据库表。
6. 需要引入外部依赖。

## 最终汇报格式

只汇报：

```text
改动文件+行号：
- ...

测试：
- D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_system_map.py backend\tests\test_system_map_collaboration.py：passed X / failed Y

红线核对：
- 未改业务判断：是/否
- 未改 prompt 注入：是/否
- 未改 rule_change 注入：是/否
- 未新增写库路径：是/否
- 协作矩阵只读不拦截：是/否
- 未开放交易接口：是/否

遗留/下一批：
- ...
```
