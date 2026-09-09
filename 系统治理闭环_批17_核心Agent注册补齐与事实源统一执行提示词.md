# 批 17：核心 Agent 注册补齐与事实源统一

请在 `D:\self` 项目中执行本批任务。

## 一、当前基线

系统治理批次 1～16 已完成：

- System Map 静态能力地图
- Collaboration Matrix 与运行时协作检查
- Knowledge、Shadow、Memory、Curator 治理
- Audit Gate 与 RuleChange 隔离
- 治理健康度和数据库迁移状态
- System Map 注册完整性校验
- `/system-map` 前端能力、健康和完整性展示

批 16 的注册完整性校验发现两个真实漂移：

- `market_intel`：graph 中有执行入口，但未出现在 `registry.list_agents()`
- `portfolio_sentinel`：graph 中有执行入口，但未出现在 `registry.list_agents()`

这不是校验器误报。当前两个模块确实存在独立 graph builder、Agent node 和业务职责，但静态 System Map Agent 注册缺失。

## 二、本批目的

补齐两个已存在核心 Agent 的 System Map 注册，使以下事实来源一致：

- graph runtime
- Agent module
- Agent chat metadata（如果该 Agent确实支持用户对话）
- System Map registry
- Workflow
- Collaboration Matrix
- Chat handler / intent target
- 前端能力地图和健康页

本批解决的问题：

1. System Map 健康页长期显示注册错误。
2. 协作检查的 known nodes 与地图信息可能不一致。
3. Workflow 已引用 Agent，但 Agent 详情不存在。
4. 后续新增功能时无法区分“真实 Agent”与“只读系统节点”。

## 三、重要约束：先判断是否为正式 Agent

开始修改前，必须分别判断 `market_intel` 和 `portfolio_sentinel`：

- 是否具有独立职责
- 是否具有独立执行入口
- 是否具有独立输入/输出
- 是否有独立生命周期或任务触发方式
- 是否应该被用户直接提问
- 是否应该出现在 `AGENT_CHAT_META`
- 是否仅作为系统级后台 Agent / 参考节点

不要因为 graph 中有 node，就自动把它加入用户聊天 Agent 列表。

必须区分：

1. **System Map 注册**：记录系统存在的真实 Agent。
2. **Chat Agent 注册**：允许用户直接对话的 Agent。
3. **Workflow 入口**：可以被某个流程触发的 Agent。
4. **Collaboration 节点**：可以作为引用方或目标方的治理节点。

如果 `market_intel` 或 `portfolio_sentinel` 不是用户聊天 Agent：

- 可以补 System Map registry
- 可以保留 Workflow / Collaboration 的系统节点语义
- 不要强行加入 `AGENT_CHAT_META`
- 不要改变用户聊天路由

## 四、先检查真实代码

不要依赖 README。先用 `rg` 精准定位并读取：

- `backend/app/system_map/registry.py`
- `backend/app/system_map/integrity.py`
- `backend/app/system_map/health.py`
- `backend/app/system_map/collaboration.py`
- `backend/app/services/agent_chat.py`
- `backend/app/services/chat_handlers.py`
- `backend/app/graph/graphs.py`
- `backend/app/graph/router.py`
- `backend/app/agents/market_intel.py`
- `backend/app/agents/portfolio_sentinel.py`
- `backend/app/api/routes.py`
- `backend/tests/test_batch16_system_map_integrity.py`
- `backend/tests/test_system_map.py`
- `backend/tests/test_system_map_collaboration.py`
- `backend/tests/test_collaboration_runtime.py`

先列出当前事实：

- Agent 是否在 graph
- Agent 是否在 registry
- Agent 是否在 chat metadata
- Agent 是否有 handler
- Agent 是否被 Workflow 引用
- Agent 是否被 Collaboration 引用

## 五、推荐实现

### 1. 补齐 registry 元数据

在 `system_map.registry` 中补齐 `market_intel`、`portfolio_sentinel` 的 Agent 元数据。

元数据至少应真实描述：

- `agent_id`
- `name`
- `responsibility`
- `agent_type`
- `authority_level`
- `inputs_required`
- `inputs_optional`
- `outputs`
- `knowledge_scope`
- `can_reference`
- `can_call`
- `cannot_do`
- `human_gate_required`

不要为了通过测试填写空泛占位文本。

元数据要反映真实边界：

- `market_intel` 是市场环境研判/参考，不是交易执行者。
- `portfolio_sentinel` 是组合级风险巡检/参考，不是自动交易者。
- 两者输出均为 advisory/reference，不能直接下单。

### 2. 统一 known nodes

评估 `integrity.py`、`collaboration.py` 和 `registry.py` 是否各自维护重复的节点白名单。

如果能小范围复用现有 registry，优先复用；不要新建第二个全局注册中心。

目标是：

- System Map 能发现两个 Agent
- `check_collaboration()` 能识别两个 Agent 为合法节点
- 完整性检查不再把它们报成 `agent_missing_registry`
- 未声明关系仍然默认 forbidden

不要因此扩大任何协作关系。补注册不等于自动允许调用。

### 3. Chat metadata 谨慎处理

只有确认两个 Agent 应支持用户直接对话时，才修改 `AGENT_CHAT_META`。

如果不应支持用户直接对话：

- 保持 Chat Router 现状
- 只在 System Map / Workflow / Collaboration 层登记
- 增加测试证明不会被误暴露为用户聊天目标

### 4. Workflow 和 handler 对齐

如果 Workflow 已经引用两个 Agent，确认它们的 `steps`、`allowed_entry_agents`、`final_responder` 与真实执行入口一致。

不要为了完整性测试修改 Workflow 业务语义。

如果存在 `market` 等兼容 intent alias：

- 保留旧 alias
- 显式记录 alias 映射
- 不重复创建一个新的用户入口

## 六、风险与缓解

实施前必须说明：

- 补注册可能让前端显示更多 Agent，是否会造成用户误解
- 把后台 Agent 加入 Chat metadata 可能扩大用户可访问面
- 统一 known nodes 可能放宽未知节点检查
- 误加协作规则可能造成 Agent 越权调用

缓解要求：

- 仅补事实元数据，不新增协作 allow 关系
- 仅在确认后扩展 Chat metadata
- unknown caller/target 仍默认拒绝
- 每个 Agent 的 `cannot_do` 保持交易红线
- 保留完整性测试锁定来源关系

## 七、测试要求

只新增或修改本批直接相关测试，至少覆盖：

1. `market_intel` 出现在 `registry.list_agents()`。
2. `portfolio_sentinel` 出现在 `registry.list_agents()`。
3. 两者元数据包含真实职责、输出和禁止事项。
4. 完整性检查不再产生这两个 `agent_missing_registry` 问题。
5. `check_collaboration()` 能识别两者为 known node。
6. 未声明的调用关系仍返回 `allowed=False`。
7. Workflow 引用与真实 Agent 注册一致。
8. 如果不支持用户聊天，Chat Router 不会误把它们暴露为普通聊天 Agent。
9. 不新增协作 allow 关系。
10. 不新增交易、写库、审核采纳或自动修复路径。

运行最小相关测试：

- 本批新增注册测试
- `test_batch16_system_map_integrity.py`
- `test_system_map.py`
- `test_system_map_collaboration.py`
- `test_collaboration_runtime.py`
- 必要的治理合同测试

不要默认跑全量测试。

## 八、治理红线

必须保持：

- System Map 仍只读。
- 补注册不等于开放协作。
- Collaboration Matrix 默认 forbidden。
- 运行时协作拒绝语义不变。
- RuleChange 仍走 Audit Gate。
- Knowledge active/shadow/archived/expired 语义不变。
- Shadow 不进入正式 prompt 或评分。
- Memory / Experience 不升级为硬规则。
- Curator 不物理删除。
- ReAct 工具仍只读。
- 不开放自动交易、下单、撤单接口。
- 不新增业务写库路径。
- 不改变 Agent 输出 schema。
- 不改变 prompt 注入逻辑。

## 九、完成后汇报

完成后只汇报：

- 改动文件 + 行号
- 测试 passed / failed
- 两个 Agent 是否纳入 Chat metadata，以及理由
- 完整性检查前后结果
- 是否新增任何协作 allow 关系
- 红线逐条核对
- 是否存在未提交改动

不要自动提交 Git。
