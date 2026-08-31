# 系统能力地图与 Agent 协作治理方案

> 目标：为现有 A 股全生命周期决策 Agent 系统建立一套“系统级能力地图 + Agent 协作规则 + 权限边界 + 治理闭环”，让任意入口或 Agent 在需要时知道该找谁、能调用什么、不能越过什么边界。
>
> 执行方式：本方案面向 Codex 分批执行。先落最小结构化地图和只读接口，再逐步接入路由、协作矩阵、知识/规则隔离和外部方法论。
>
> 红线：不自动下单；不绕过人工审核；不让入口 Agent 直接改规则；不把局部经验写入全局知识；不大改现有主链路。

## 1. 宏观定位

现有系统不是单个聊天助手，而是一个多 Agent 投研操作系统。系统需要一张结构化地图，让所有入口和 Agent 可以按规则发现能力。

核心对象：

```text
System Map        系统能力地图：系统有什么 Agent / Tool / Service / Workflow
Agent Registry   Agent 注册表：每个 Agent 的职责、输入、输出、边界
Capability Graph 能力图谱：能力之间如何组合
Collaboration Matrix 协作矩阵：谁能调用谁、引用谁、覆盖谁
Governance Layer 治理层：审核、回滚、验证、shadow、防污染
```

飞书入口只是一个示例。网页对话、API 调用、自动任务、未来任何入口，都应查询同一张系统地图。

## 2. 当前代码承载点

已存在能力，优先复用：

1. Agent 说明：`backend/app/services/agent_chat.py` 的 `AGENT_CHAT_META`。
2. 任务能力：`backend/app/api/routes.py` 的 `_TASK_KINDS`。
3. 工具能力：`backend/app/agents/agentic_tools.py` 的 `TOOLS` + `TOOL_FUNCS`。
4. 注入层：`backend/app/agents/common.py` 的 `build_agent_context()`、`dynamic_rules_section()`、`knowledge_section()`。
5. 知识库：`backend/app/db/models.py` 的 `PrivateKnowledge`。
6. 规则库：`backend/app/db/models.py` 的 `RuleChange`。
7. 审核：`AuditLog`、`agent_suggestion.audit_verdict`。
8. 经验：`Experience` / `PendingExperience`。

第一原则：先把这些分散信息统一注册和只读暴露，不重建一套平行系统。

## 3. 最小可落地形态

第一版只做三类注册，不做复杂知识图谱：

```text
AgentDefinition
ToolDefinition
WorkflowDefinition
```

### 3.1 AgentDefinition

字段建议：

```text
agent_id: discover / score / position / monitor / sell / review / audit / market_intel / portfolio_sentinel / feishu_gateway
name: 中文名
agent_type: research_decision / entry_orchestrator / governance / experience / market_context
responsibility: 核心职责
inputs_required: 必填输入
inputs_optional: 可选输入
outputs: 输出对象
can_call: 可调用 Agent / Workflow / Tool
can_reference: 可引用结论
cannot_do: 禁止事项
knowledge_scope: global / agent / scenario
authority_level: readonly / advisory / proposal / governance
human_gate_required: true / false
```

### 3.2 ToolDefinition

字段建议：

```text
tool_id
owner_module
tool_type: readonly_data / readonly_analysis / writer_with_gate
inputs
outputs
used_by
cache_policy
failure_policy
cannot_do
```

第一版只注册只读工具。任何写库工具必须标 `writer_with_gate`，不能给普通 Agent 直接调用。

### 3.3 WorkflowDefinition

字段建议：

```text
workflow_id
intent_examples
steps
required_inputs
optional_inputs
allowed_entry_agents
audit_required
human_confirm_required
final_responder
```

示例：

```text
workflow_id: holding_should_sell
intent_examples: 某持仓还能不能拿 / 要不要卖 / 风险大不大
steps: monitor -> sell -> market_intel_summary -> portfolio_sentinel_summary -> response_synthesizer
human_confirm_required: true
```

## 4. 协作矩阵

协作矩阵用于防污染和防降智。它不存方法论，只存权限与关系。

字段建议：

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

基础规则：

1. 入口 Agent 可调用业务 Agent，但只能汇总，不能覆盖业务 Agent 结论。
2. Score 可参考 Discover，但不能无条件继承 Discover 结论。
3. Sell / Monitor 可参考 PortfolioSentinel 和 MarketIntel，但不能突破硬规则。
4. Review 可评价所有业务 Agent，但只能生成建议，不能直接改规则。
5. Audit 可审核建议，但不能自己修改规则。
6. 任何 Agent 不得调用自己形成循环。
7. 默认 deny：未注册协作关系一律禁止。

## 5. 知识与规则隔离

系统地图不替代知识库。两者职责不同：

```text
System Map：谁能做什么，谁能找谁，权限是什么
Knowledge：怎么判断，什么方法论，什么经验
RuleChange：审核后生效的行为约束
```

隔离原则：

1. Global 知识只放全局原则、合规边界、硬性红线、基础定义。
2. Agent 专属知识只给对应 Agent 注入。
3. Scenario 知识按市场阶段、任务场景触发。
4. RuleChange 必须按 `target_agent` / `all` 精准注入。
5. 外部方法论先 shadow，不直接进入 global/all。

## 6. 执行链路

任意入口统一执行：

```text
输入
  -> Intent Parser
  -> System Map 查询
  -> Collaboration Matrix 权限校验
  -> Workflow Planner
  -> Agent / Tool / Service 调用
  -> Response Synthesizer
  -> Audit / Human Gate
  -> Trace 留痕
```

入口 Agent 的边界：

1. 可以理解意图。
2. 可以查询系统地图。
3. 可以调度授权 Agent / Workflow。
4. 可以汇总输出。
5. 可以把用户反馈转为待审建议。
6. 不可以直接修改规则。
7. 不可以替代业务 Agent 做最终研判。
8. 不可以绕过 AuditAgent。

## 7. 分批落地

### 批 1：系统地图最小闭环

目的：先建立只读系统地图，不改变任何业务判断。

改动范围：

1. 新增 `backend/app/system_map/registry.py`。
2. 从 `AGENT_CHAT_META`、`_TASK_KINDS`、`agentic_tools.TOOLS` 汇总只读注册信息。
3. 新增服务函数：
   - `list_agents()`
   - `get_agent(agent_id)`
   - `list_tools()`
   - `list_workflows()`
   - `get_system_map_summary()`
4. 新增只读 API：
   - `GET /system-map`
   - `GET /system-map/agents`
   - `GET /system-map/agents/{agent_id}`
   - `GET /system-map/tools`
   - `GET /system-map/workflows`

验收：

1. API 能列出现有主要 Agent。
2. API 能列出现有 ReAct tools。
3. 不修改任何 Agent 输出。
4. 不修改 prompt 注入逻辑。
5. 新增测试只覆盖 system_map。

风险：

1. 从 `_TASK_KINDS` import routes 可能引起循环依赖。

缓解：

1. 批 1 不直接 import routes 的私有变量；可先手写 workflow 最小注册，或把 task 元信息抽出到无副作用模块。

### 批 2：协作矩阵最小闭环

目的：把“谁能找谁”变成代码里的白名单。

改动范围：

1. 在 `backend/app/system_map/registry.py` 或新文件 `collaboration.py` 定义静态矩阵。
2. 新增：
   - `can_collaborate(requester, target, relation)`
   - `list_allowed_targets(agent_id)`
3. 新增 API：
   - `GET /system-map/collaboration`
   - `GET /system-map/agents/{agent_id}/allowed-targets`
4. 暂不强制接入业务调用，只读展示和测试。

验收：

1. 未注册关系默认 forbidden。
2. Feishu/entry 类 Agent 可 call 业务 Agent，但不能 propose_change 直接生效。
3. Review 可 propose_change，但必须 audit_required。
4. 单测覆盖 allowed / forbidden / audit_required。

风险：

1. 一开始矩阵不完整，若直接强制可能影响现有业务。

缓解：

1. 批 2 只读，不拦截业务；批 3 后再逐步接入。

### 批 3：入口路由统一查询系统地图

目的：让飞书、Agent 对话、未来入口不再各自硬编码系统能力。

改动范围：

1. 优先接 `backend/app/services/chat_router.py` 和飞书相关 handler。
2. 路由 prompt 或规则中注入 `get_system_map_summary()` 的压缩摘要。
3. 意图路由输出必须包含：
   - `intent`
   - `target_agent`
   - `workflow_id`
   - `required_params`
   - `permission_note`
4. 若目标 Agent 不在系统地图中，fail-closed。

验收：

1. “查持仓”仍走 holdings。
2. “分析 600519”仍走 score。
3. “要不要卖某持仓”能识别 sell/monitor 相关 workflow。
4. 未注册能力不被路由。

风险：

1. 路由 prompt 变长，轻量模型成本上升。

缓解：

1. 只注入压缩地图，不注入长说明；保留关键词快速路径。

### 批 4：规则注入隔离

目的：把原始设计中的 Agent 专属增量规则隔离落成机制。

改动范围：

1. 执行前盘点 active `rule_change.target_agent` 分布。
2. `dynamic_rules_section()` 改为 `dynamic_rules_section(agent: str)`。
3. `build_agent_context()` 改为传当前 agent。
4. 仅注入 `target_agent in (agent, all)`；空值第一版兼容为 all，但报告数量。
5. 补测试：discover/score/sell 规则隔离。

验收：

1. 输出存量 target_agent 分布。
2. 不同 Agent 只看到自己、all、兼容空值规则。
3. 若空值占比高，验收报告必须注明“兼容阶段，污染未完全消除”。

风险：

1. 存量空规则全按 all，实际收窄效果有限。

缓解：

1. 后续单独做存量规则归类批次。

### 批 5：采纳入口治理统一

目的：防止入口 Agent 或复盘建议绕过审核直接影响未来行为。

改动范围：

1. 配置新增 `RULE_ADOPT_REQUIRE_AUDIT=true`。
2. `approve_agent_suggestion()` 增加 profile 类审核门。
3. `adopt_agent_suggestion()` 增加 prompt/规则类审核门。
4. `adopt_review_suggestion()` 标为兼容旧入口；建议前端降权或要求确认。
5. override 必须记录 reason。

验收：

1. audit 未通过的 `agent_suggestion` 默认不能 approve/adopt。
2. audit pass 的建议可按原逻辑生效。
3. 规则类 hard 仍保留二次确认。
4. 旧 review adopt 不被静默扩大权限。

风险：

1. 旧建议没有 audit 状态导致流程变长。

缓解：

1. 旧建议允许人工 override，但必须留痕。

### 批 6：知识元数据与场景检索

目的：让通用知识、Agent 知识、场景知识、外部方法论可治理。

改动范围：

1. `PrivateKnowledge` 兼容新增字段：
   - `source_type`
   - `methodology_type`
   - `market_scope`
   - `scenario_tags`
   - `evidence_level`
   - `valid_from`
   - `valid_to`
   - `status`
   - `risk_note`
2. `vector_store.search_knowledge()` 支持 agent + tags/type/scope/status 轻过滤。
3. `common.knowledge_section()` 可传入 query/scenario，但第一版保持旧调用兼容。
4. 前端知识库页只做可选字段展示和录入。

验收：

1. 老知识正常显示、正常注入。
2. 新知识可按 Agent / 标签 / 类型筛选。
3. `status=archived` 不注入。
4. 不改变 ReAct `search_knowledge` 工具行为。

风险：

1. 字段多，录入复杂。

缓解：

1. 字段全部可选；默认 `source_type=manual`、`status=active`。

### 批 7：已有专业服务工具化

目的：让 Agent 按需调用已有专业服务，而不是一次性塞满 prompt。

改动范围：

1. 在 `agentic_tools.py` 增加只读 `_get_xxx` 实现。
2. 同步挂到 `TOOLS` schema 和 `TOOL_FUNCS`。
3. 按 Agent allowlist 裁剪。
4. 优先工具：
   - `get_sector_regime`
   - `get_factor_calibration`
   - `get_distribution_phase`
   - `get_capital_view`
   - `get_position_risk`
   - `get_hot_money_context`

验收：

1. Score ReAct 能调用板块结构、因子校准、派发期、资本视图。
2. Sell ReAct 能调用持仓风险、公告、派发期、游资上下文。
3. 工具失败返回 error，不中断主链。
4. 自动注入知识检索不在本批改变。

风险：

1. 工具过多导致空转和成本上升。

缓解：

1. 只在 DEEP 或高危复核节点开放；严格 allowlist；结果截断；失败降级。

### 批 8：方法论 shadow 试运行

目的：外部方法论先观察验证，再决定是否正式生效。

改动范围：

1. 知识/规则支持 `draft / shadow / active / archived` 状态。
2. 第一版只做知识类 shadow。
3. shadow 不注入正式主结论，只记录命中和模拟倾向。
4. 接入 T+N 验证统计。

验收：

1. shadow 不改变正式结果。
2. 可查看命中次数和后验表现。
3. 可升级 active 或 archived。

风险：

1. 留痕量增加，实现复杂。

缓解：

1. 只在 Discover/Score 开启；只记录短摘要。

## 8. Codex 执行兼容要求

每批执行提示词应满足：

1. 单批只做一个目标，不跨批。
2. 先 `rg -n` 定位函数/类/接口，再读目标行附近。
3. 不整读大文件。
4. 不改无关 UI 或样式。
5. 不跑全量测试，除非 sir 明确要求。
6. 每批新增或修改测试必须最小化。
7. 每批结束只报告：
   - 改动文件 + 行号
   - 测试 passed/failed
   - 红线核对
   - 未完成/下一批

## 9. 批 1 推荐执行指令骨架

```text
目标：实现“系统能力地图最小闭环”，只读暴露现有 Agent/Tool/Workflow，不改变任何业务判断。

先定位：
rg -n "AGENT_CHAT_META|TOOLS =|TOOL_FUNCS|_TASK_KINDS" backend/app

约束：
1. 不修改现有 Agent 输出。
2. 不修改 prompt 注入逻辑。
3. 不直接 import 会造成循环的 routes 私有对象；如有循环风险，先手写 workflow 最小注册。
4. 只新增 system_map 模块、只读 API、最小测试。

验收：
1. GET /system-map/agents 返回现有 Agent。
2. GET /system-map/tools 返回 ReAct tools。
3. GET /system-map/workflows 返回关键 workflow。
4. pytest 只跑新增 system_map 测试。
```

## 10. 成功标准

完成后，系统应具备：

1. 任意入口能查询系统有什么能力。
2. 任意 Agent 可按权限发现可协作对象。
3. 新 Agent / 新 Tool / 新 Workflow 上线必须注册。
4. 外部方法论不直接污染全局知识。
5. 会改变未来行为的建议必须审核、可回滚、可验证。

最终形态：

```text
Agent 不是靠 prompt 记忆系统
而是通过 System Map 理解系统
通过 Collaboration Matrix 协作系统
通过 Governance Layer 保护系统
```
