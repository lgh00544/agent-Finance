# 系统能力地图与 Agent 协作治理 · 批 1 Codex 执行提示词

你在 `D:\self` 项目中执行本批任务。

## 任务目标

实现“系统能力地图最小闭环”：只读暴露现有 Agent / Tool / Workflow 注册信息，不改变任何业务判断、不改变任何 Agent 输出、不改变 prompt 注入逻辑。

详细设计参见 `系统能力地图与Agent协作治理_方案.md`：

- §2 当前代码承载点
- §3 最小可落地形态
- §7 批 1：系统地图最小闭环
- §8 Codex 执行兼容要求
- §9 批 1 推荐执行指令骨架

## 执行纪律

1. 先用 `rg -n` 定位目标符号，只读目标行附近，不整读大文件。
2. 本批只做批 1，不做协作矩阵、不做规则注入隔离、不做知识库元数据、不做 ReAct 工具新增。
3. 不修改现有 Agent 输出 schema。
4. 不修改 `common.py` 的 prompt 注入顺序和逻辑。
5. 不修改现有任务执行逻辑。
6. 不引入网络依赖。
7. 测试只跑本批新增/相关测试，不跑全量回归。

## 先定位

请先定位以下符号，只读附近代码：

```powershell
rg -n "AGENT_CHAT_META|_TASK_KINDS|TOOLS =|TOOL_FUNCS|include_router|APIRouter" backend/app
```

重点确认：

1. `backend/app/services/agent_chat.py` 中 `AGENT_CHAT_META` 的结构。
2. `backend/app/agents/agentic_tools.py` 中 `TOOLS` / `TOOL_FUNCS` 的结构。
3. `backend/app/api/routes.py` 中 `_TASK_KINDS` 和路由注册方式。
4. 是否直接 import `_TASK_KINDS` 会产生循环依赖；若有风险，批 1 先手写 workflow 最小注册。

## 建议改动

### 1. 新增 system_map 模块

新增目录/文件：

```text
backend/app/system_map/__init__.py
backend/app/system_map/registry.py
```

`registry.py` 提供只读函数：

```text
list_agents()
get_agent(agent_id)
list_tools()
list_workflows()
get_system_map_summary()
```

第一版数据来源：

1. Agent：优先复用 `AGENT_CHAT_META`，补充 `agent_type`、`authority_level`、`cannot_do` 等默认字段。
2. Tool：读取 `agentic_tools.TOOLS`，只暴露 name / description / parameters / tool_type=readonly_data。
3. Workflow：若抽取 `_TASK_KINDS` 有循环风险，则先手写关键 workflow 最小注册：
   - daily_pipeline
   - score
   - position
   - sell_decision
   - monitor_all
   - market_intel
   - portfolio_sentinel
   - knowledge_import
   - chat_ask

要求：

1. 注册信息必须是普通 dict/list，可 JSON 序列化。
2. 不允许 registry 调用真实 Agent 或真实任务。
3. 不允许 registry 写库。
4. 未知 agent 返回 `None` 或空结果，由 API 层转 404。

### 2. 新增只读 API

在现有 API 路由体系中新增只读端点：

```text
GET /system-map
GET /system-map/agents
GET /system-map/agents/{agent_id}
GET /system-map/tools
GET /system-map/workflows
```

返回内容：

1. `/system-map` 返回 summary：agents_count / tools_count / workflows_count / agents / workflows。
2. `/agents` 返回 Agent 列表。
3. `/agents/{agent_id}` 未命中返回 404。
4. `/tools` 返回工具列表。
5. `/workflows` 返回 workflow 列表。

### 3. 新增测试

新增测试文件：

```text
backend/tests/test_system_map.py
```

测试至少覆盖：

1. `list_agents()` 包含 discover / score / monitor / sell / review。
2. `list_tools()` 包含 get_quote / get_daily_kline / search_knowledge。
3. `list_workflows()` 包含 score / sell_decision / market_intel。
4. API `/system-map/agents/score` 返回 score 信息。
5. API `/system-map/agents/not_exists` 返回 404。

## 验收命令

只跑本批测试：

```powershell
pytest backend/tests/test_system_map.py
```

若 API 测试依赖项目现有 test client fixture，复用现有测试写法；不要为本批引入大型测试框架。

## 红线核对

完成后逐条核对并在汇报中给结论：

1. 未改任何交易/评分/卖出/监控业务判断。
2. 未改任何 prompt 注入逻辑。
3. 未新增写库路径。
4. 未开放任何下单/撤单/券商接口。
5. 未把 system map 当作方法论知识库。

## 停手条件

遇到以下情况停止并报告：

1. 需要大幅移动 `_TASK_KINDS` 或重构 routes 才能避免循环依赖。
2. 需要改现有 Agent 输出 schema。
3. 需要改 `common.py` 注入逻辑。
4. 需要引入外部依赖。
5. 测试需要跑全量回归才能判断。

## 最终汇报格式

只汇报：

```text
改动文件+行号：
- ...

测试：
- pytest backend/tests/test_system_map.py：passed X / failed Y

红线核对：
- 未改业务判断：是/否
- 未改 prompt 注入：是/否
- 未新增写库路径：是/否
- 未开放交易接口：是/否
- System Map 未混入方法论：是/否

遗留/下一批：
- ...
```
