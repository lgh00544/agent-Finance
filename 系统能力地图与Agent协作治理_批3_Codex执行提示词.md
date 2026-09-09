# 系统能力地图与 Agent 协作治理 · 批 3 Codex 执行提示词

你在 `D:\self` 项目中执行本批任务。

## 前置状态

批 1/2 已完成并验证：

- 批 1：`system_map.registry` + `/api/system-map*` 只读端点。
- 批 2：`system_map.collaboration` + `/api/system-map/collaboration`、`allowed-targets`、`can-collaborate`。
- 验证命令：`D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_system_map.py backend\tests\test_system_map_collaboration.py`：12 passed。

## 任务目标

让入口路由开始“读取系统地图和协作矩阵”，用于决定目标 Agent / workflow / permission_note。

本批只做入口路由认知增强，不改变任何业务 Agent 行为，不强制拦截现有业务链路。

详细设计参见 `系统能力地图与Agent协作治理_方案.md`：

- §6 执行链路
- §7 批 3：入口路由统一查询系统地图
- §8 Codex 执行兼容要求

## 执行纪律

1. 先用 `rg -n` 定位目标符号，只读附近代码。
2. 本批优先改 `chat_router`，飞书只通过现有 `route_and_execute` 自然受益。
3. 不改 `chat_handlers.dispatch()` 的业务执行分支，除非只传递新增只读 hint/meta 且不改变行为。
4. 不改任何 Agent 输出 schema。
5. 不改 `common.py` prompt 注入逻辑。
6. 不改 `rule_change` 注入逻辑。
7. 不新增写库路径。
8. 不引入网络依赖。
9. 只跑本批相关测试。

## 先定位

```powershell
rg -n "def route|def route_and_execute|_route_regex|RouteIntent|SYSTEM_PROMPT|user_prompt|dispatch\\(" backend/app/services backend/app/prompts backend/tests
rg -n "get_system_map_summary|can_collaborate|list_allowed_targets" backend/app/system_map
```

重点确认：

1. `backend/app/services/chat_router.py` 的 `route()` 返回结构。
2. `backend/app/prompts/chat_router.py` 的 `RouteIntent` schema。
3. `backend/app/services/chat_handlers.py` 的 `dispatch()` 参数是否只能接收现有 intent/params/hint。
4. 现有飞书测试写法，避免破坏 teach/remember 流程。

## 建议改动

### 1. 路由 schema 增强

在 `backend/app/prompts/chat_router.py` 中兼容扩展 `RouteIntent`：

```text
target_agent: str = ""
workflow_id: str = ""
permission_note: str = ""
```

要求：

1. 字段必须有默认值，兼容旧响应。
2. 不改变现有 `intent`、`params`、`hint` 的语义。
3. prompt 中加入压缩说明：路由应优先参考系统地图，不认识的能力 fail-closed 或走 chat/help。

### 2. chat_router 注入系统地图摘要

在 `backend/app/services/chat_router.py` 中：

1. 从 `app.system_map.registry` 读取 `get_system_map_summary()`。
2. 从 `app.system_map.collaboration` 读取 `can_collaborate()`。
3. 构造短文本 `system_map_hint`，注入 LLM 路由 user prompt 或 system prompt。
4. 保留关键词快速路径 `_route_regex`，不增加 token 成本。

要求：

1. 地图读取失败时降级为空，不影响原路由。
2. 不在路由阶段调用真实业务 Agent。
3. 不把完整系统地图长 JSON 塞进 prompt，只给压缩摘要。

### 3. 权限说明只做标注

当 LLM 路由返回 `target_agent` / `workflow_id` 时：

1. 用 `can_collaborate("chat_entry", target_agent, "call")` 做只读检查。
2. 将结果写入 `permission_note` 或合并到 `hint`。
3. 本批不阻断现有 dispatch；若 forbidden，只在 hint 中标注“未注册协作关系，已按兼容路径处理”。

说明：

1. 批 3 是认知增强，不做强制拦截。
2. 强制拦截留到后续治理批次。

### 4. 飞书入口兼容

`feishu_bridge` 通过 `route_and_execute()` 调用 `chat_router`，本批不要直接改飞书长连接逻辑。

如果必须改 `chat_handlers.dispatch()`：

1. 只能保持参数兼容。
2. 不能改变已有 intent 的执行结果。
3. 不能影响 teach / remember / forget / draft。

### 5. 测试

新增或扩展测试：

```text
backend/tests/test_chat_router_system_map.py
```

至少覆盖：

1. `RouteIntent` 兼容旧 JSON：没有 target_agent/workflow_id/permission_note 也可解析。
2. 系统地图摘要读取失败时，`route()` 仍可返回原有 intent。
3. 对“分析 600519”路由仍为 score，且可带 target_agent=score 或 hint 中含权限说明。
4. 对未知能力请求不应抛异常，应走 chat/help/unknown 兼容路径。
5. `route_and_execute()` 对现有简单命令不破坏。

如测试需要 mock LLM，复用现有 chat_router 测试风格；不要真实调用外部 LLM。

## 验收命令

只跑批 1/2/3 相关测试和现有飞书路由保护测试：

```powershell
D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_system_map.py backend\tests\test_system_map_collaboration.py backend\tests\test_chat_router_system_map.py backend\tests\test_feishu_teach.py
```

若 `test_feishu_teach.py` 与本批无关但失败，先确认是否由本批改动导致；不要跑全量测试。

## 红线核对

完成后逐条核对并在汇报中给结论：

1. 未改任何交易/评分/卖出/监控业务判断。
2. 未改任何 Agent 输出 schema。
3. 未改 prompt 注入逻辑。
4. 未改 rule_change 注入逻辑。
5. 未新增写库路径。
6. 本批只读查询 system map / collaboration，不做业务强制拦截。
7. 未开放任何下单/撤单/券商接口。

## 停手条件

遇到以下情况停止并报告：

1. 需要重构 `chat_handlers.dispatch()` 才能完成。
2. 需要改飞书长连接收发逻辑。
3. 需要改业务 Agent 输出 schema。
4. 需要改 `common.py` 注入逻辑。
5. 需要真实调用外部 LLM 才能测试。
6. 需要新增数据库表或写库逻辑。

## 最终汇报格式

只汇报：

```text
改动文件+行号：
- ...

测试：
- D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_system_map.py backend\tests\test_system_map_collaboration.py backend\tests\test_chat_router_system_map.py backend\tests\test_feishu_teach.py：passed X / failed Y

红线核对：
- 未改业务判断：是/否
- 未改 Agent 输出 schema：是/否
- 未改 prompt 注入：是/否
- 未改 rule_change 注入：是/否
- 未新增写库路径：是/否
- 只读查询不拦截：是/否
- 未开放交易接口：是/否

遗留/下一批：
- ...
```
