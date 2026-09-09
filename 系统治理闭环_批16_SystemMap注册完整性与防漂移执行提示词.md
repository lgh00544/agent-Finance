# 批 16：System Map 注册完整性与防漂移

请在 `D:\self` 项目中执行本批任务。

## 一、当前基线

系统治理批次 1～15 已完成：

- System Map 静态能力地图
- Collaboration Matrix 与运行时调用检查
- RuleChange Agent 隔离与 Audit Gate
- Knowledge 元数据与 Shadow
- Memory / Experience Curator
- 治理健康度与数据库迁移健康状态
- `/system-map` 前端能力与运行状态看板

当前系统地图主要来自静态注册和多个运行时来源：

- `AGENT_CHAT_META`
- `chat_handlers._HANDLERS`
- `chat_handlers._INTENT_TARGETS`
- `agentic_tools.TOOLS`
- `agentic_tools.TOOL_FUNCS`
- `system_map.registry._WORKFLOWS`
- `system_map.collaboration._COLLABORATION_RULES`
- FastAPI 路由
- Agent 模块和提示词文件

风险是：以后新增 Agent、Workflow、工具或入口时，只改了一处，其他地方没有登记，导致：

- System Map 看不到真实能力
- Chat Router 找不到目标
- 协作矩阵引用未知 Agent
- 工具 schema 与函数注册不一致
- Workflow steps 与实际执行入口不一致
- 健康页显示正常但地图已失真

## 二、本批目的

新增一个只读的“System Map 注册完整性校验”能力，解决治理地图长期漂移问题。

完成后能够发现并展示：

- 未注册的 Agent
- 注册但没有实际 handler 的 Agent
- Workflow 引用了未知 Agent
- 协作矩阵引用了未知节点
- `TOOLS` 有 schema 但 `TOOL_FUNCS` 缺函数
- `TOOL_FUNCS` 有函数但没有 schema
- Intent target 缺失或指向未知 Agent
- 关键入口之间的登记不一致

本批只检测和展示，不自动修复，不自动补注册，不改变任何业务执行。

## 三、先检查真实代码

不要依赖 README。先使用 `rg` 定位并精准读取：

- `backend/app/system_map/registry.py`
- `backend/app/system_map/collaboration.py`
- `backend/app/system_map/health.py`
- `backend/app/services/chat_handlers.py`
- `backend/app/agents/agentic_tools.py`
- `backend/app/services/agent_chat.py`
- `backend/app/api/routes.py`
- `web/src/pages/SystemMapPage.tsx`
- `web/src/api/systemMap.ts`
- `web/src/types/index.ts`
- 现有 System Map、健康度、协作运行时测试

先列出“事实来源”和“展示注册来源”，不要先设计新注册中心。

必须确认：

1. 哪些 Agent 是真实可执行入口。
2. 哪些 Agent 只是静态能力节点。
3. 哪些 handler 是用户入口，哪些是内部 Agent 调用。
4. 工具 schema 与 `TOOL_FUNCS` 的真实键集合。
5. Workflow steps 是否要求每一步都能在 handler 或 Agent registry 中找到。
6. 协作矩阵中的 `chat_entry`、`feishu_gateway`、`portfolio_sentinel` 等节点是否属于合法系统节点。
7. 是否存在兼容别名、旧 intent 或非 Agent service，避免误报。

不要把普通 service、数据库表、前端页面误报为 Agent。

## 四、推荐实现

### 1. 新增只读完整性校验模块

优先新增：

- `backend/app/system_map/integrity.py`

模块只做静态读取和比较，不执行 Agent，不调用外部数据源，不写数据库。

可以提供类似：

- `check_system_map_integrity()`
- `get_registration_integrity()`

返回至少包括：

- `status`: `healthy` / `attention` / `error` / `unknown`
- `checked_at`
- `summary`
- `issues`
- `sources`

每条 issue 至少包含：

- `kind`
- `severity`
- `source`
- `item`
- `message`
- `expected`
- `actual`

建议 issue 类型：

- `agent_missing_registry`
- `agent_missing_handler`
- `workflow_unknown_step`
- `workflow_unknown_entry_agent`
- `collaboration_unknown_node`
- `tool_schema_without_function`
- `tool_function_without_schema`
- `intent_unknown_target`

### 2. 误报控制

必须建立明确的合法节点集合：

- 真实 Agent
- 系统入口节点
- 只读治理节点
- 已确认的兼容别名

不要简单把所有字符串集合直接做全量相等比较。

对无法确认的关系显示 `unknown` 或低严重度 attention，不要强行判 error。

如果某个 Agent 的实际入口无法可靠发现：

- 明确列为 `unknown`
- 在 issue 中说明缺少事实来源
- 不凭文件名猜测执行能力

### 3. 健康接口接入

优先复用现有：

- `GET /api/system-map/health`

可以新增模块：

- `registration_integrity`

或者在现有健康返回中增加完整性字段。

要求：

- 仍然只读
- 健康查询不执行任务、不写库、不执行 DDL
- 单个来源读取失败时返回模块级 error/unknown
- 不把“没有发现问题”与“无法检查”混淆

### 4. 前端展示

在现有 `/system-map` → `运行状态` 或能力地图中增加完整性展示。

展示：

- 注册完整性状态
- 检查时间
- 来源数量
- issue 数量
- 严重级别
- 问题来源与具体对象
- 预期与实际差异

必须明确文案：

- “未发现登记不一致”
- “发现需要处理的问题”
- “当前无法确认”

不能添加：

- 自动注册按钮
- 自动修复按钮
- Agent 启用/禁用按钮
- 修改协作矩阵按钮
- 修改 Workflow 按钮
- 工具执行按钮
- 交易或下单按钮

## 五、治理边界

必须保持：

- System Map 只读。
- 完整性校验只观察，不自动修复。
- Collaboration Matrix 默认 forbidden。
- 运行时协作拒绝语义不变。
- RuleChange 仍经过 Audit Gate。
- Knowledge active/shadow/archived/expired 语义不变。
- Shadow 不进入正式 prompt 或 scoring。
- Memory / Experience 不升级为硬规则。
- Curator 不物理删除。
- ReAct 工具仍只读，失败返回 error。
- 不新增业务写库路径。
- 不开放自动交易、下单、撤单接口。
- 不改变 Agent 输出 schema。
- 不改变 prompt 注入逻辑。
- 不改变数据库迁移语义。

## 六、测试要求

只新增或修改本批直接相关测试，至少覆盖：

1. 健康注册状态在所有来源一致时为 healthy。
2. Agent 只有 registry 没有真实 handler 时能被发现。
3. Workflow 引用未知 Agent 时能被发现。
4. Collaboration Matrix 引用未知节点时能被发现或按约定标记 unknown。
5. `TOOLS` 缺少 `TOOL_FUNCS` 时能被发现。
6. `TOOL_FUNCS` 缺少 schema 时能被发现。
7. Intent target 指向未知 Agent 时能被发现。
8. 兼容别名和系统入口节点不会误报。
9. 单一来源读取失败不会让整个检查伪装 healthy。
10. 健康接口和完整性校验不执行 DDL、任务、写库或交易。
11. 前端空数据、error、unknown、issue 列表可正常展示。
12. 前端没有任何自动修复或业务写操作入口。

如果项目没有前端测试框架：

- 至少运行 `npm run build`
- 至少运行 `npm run lint`
- 运行本批新增后端测试
- 运行 System Map 与治理健康相关回归
- 不要引入大型测试体系

## 七、实施前说明

开始修改前先说明：

- 各事实来源分别是什么
- 哪些不一致可以确定为 error
- 哪些只能标记 unknown
- 如何避免把 service/alias 误报为 Agent
- 为什么复用现有 health 与 System Map，而不是新建独立治理系统
- 每项新增/调整的目的、风险、缓解方式和预期效果

如果当前注册信息不足以可靠判断某项关系，宁可显示 unknown，也不要凭猜测自动扩展注册表。

## 八、完成后汇报

完成后只汇报：

- 改动文件 + 行号
- 测试 passed / failed
- 发现的真实登记不一致
- healthy/attention/error/unknown 各态验证
- `/system-map` 展示入口
- 红线逐条核对
- 是否存在未提交改动

不要自动提交 Git。
