# 系统能力地图与 Agent 协作治理：批 10 Codex 执行提示词

## 任务

你在 `D:\self` 项目中执行批 10：**治理闭环总验收与使用手册**。

目标：不再新增投研能力，而是把批 1-9 的治理成果固化为可复用手册和 contract tests，确保后续新增 Agent / 知识 / 规则 / Memory 时不会破坏隔离、审核、shadow、curator 红线。

参见：

- `D:\self\系统能力地图与Agent协作治理_方案.md`
- `D:\self\Memory治理与记忆防污染_提单.md`
- `D:\self\系统能力地图与Agent协作治理_批1_Codex执行提示词.md` 到 `批9`

引用文档只作参考，以本提示词为准。

## 当前已完成能力

1. System Map：系统能力地图，只读。
2. Collaboration Matrix：Agent 协作矩阵，只读。
3. Chat Router：入口路由可参考系统地图。
4. RuleChange：按 Agent 隔离注入。
5. Adoption Gate：采纳建议默认必须 Audit pass。
6. Knowledge Metadata：DB 私有知识有 status/source/type/scope/tags。
7. Professional Tools：已有专业服务包装成只读 ReAct 工具。
8. Knowledge Shadow：方法论 shadow 只观察，不进正式 prompt。
9. Memory Curator：经验记忆可计量、过期、归档、策展提议。

## 必须先定位

只读锚点附近，不整读大文件：

```powershell
rg -n "system-map|can-collaborate|dynamic_rules_section|rule_adopt_require_audit|KnowledgeShadowHit|run_curator|knowledge_section|experience_section|TOOLS|TOOL_FUNCS|shadow-hits|curator/run" backend/app backend/tests
```

重点文件：

1. `backend/app/system_map/registry.py`
2. `backend/app/system_map/collaboration.py`
3. `backend/app/prompts/chat_router.py`
4. `backend/app/services/chat_router.py`
5. `backend/app/agents/common.py`
6. `backend/app/agents/agentic_tools.py`
7. `backend/app/api/routes.py`
8. `backend/app/services/knowledge_shadow.py`
9. `backend/app/services/memory_curator.py`

## 交付物 1：使用与验收手册

新增文档：

```text
D:\self\系统治理闭环_使用与验收手册.md
```

要求 ≤600 行，结构清晰，必须包含：

1. 宏观架构图文字版：
   - System Map 管“有什么”
   - Collaboration Matrix 管“谁能找谁”
   - RuleChange 管“必须遵守什么”
   - Knowledge 管“参考什么方法论”
   - Shadow 管“新方法先观察”
   - Memory Curator 管“哪些历史还能信”
2. 新增 Agent 的流程：
   - 什么时候应该新增 Agent
   - 必填能力字段
   - 协作矩阵怎么声明
   - 允许引用哪些知识/规则
3. 新增知识的流程：
   - active / shadow / archived / expired 区别
   - 何时用 shadow
   - 何时可以升级 active
4. 新增规则的流程：
   - rule suggestion -> Audit -> Adopt Gate -> RuleChange
   - hard rule 二次确认
   - override 必须留痕
5. Memory 维护流程：
   - pending_experience -> worker -> active/pending_review
   - curator dry-run
   - confirm 后归档/过期
   - 策展摘要只进 pending_review
6. 常用 API 清单：
   - `/api/system-map*`
   - `/api/system-map/collaboration`
   - `/api/system-map/can-collaborate`
   - `/api/knowledge`
   - `/api/knowledge/shadow-hits`
   - `/api/knowledge/shadow/refresh-outcomes`
   - `/api/experience/curator/*`
   - `/api/agent-suggestions/{sid}/approve`
   - `/api/agent-suggestions/{sid}/adopt`
7. 红线清单：
   - 不自动下单
   - 不绕过 Audit Gate
   - shadow 不进正式 prompt
   - curator 不物理删除
   - 低置信记忆不自动升级规则
8. 回滚/降级方式：
   - 配置关闭审核闸门的应急边界
   - RuleChange rollback
   - Knowledge archived
   - Experience archived/expired

不要写成营销文案；写给后续 Codex / opencode / 你自己使用。

## 交付物 2：治理 contract tests

新增测试：

```text
backend/tests/test_governance_contract.py
```

覆盖最小合同，不追求全量业务：

1. system-map 端点只读可访问，返回 agents/tools/workflows。
2. collaboration 默认 forbidden，允许关系必须显式声明。
3. `dynamic_rules_section("score")` 不注入其它 Agent 专属规则，但注入 all/空兼容规则。
4. agent suggestion 未 audit pass 默认不能 approve/adopt。
5. `knowledge_section()` 不注入 `shadow/archived/expired` 知识。
6. `KnowledgeShadowHit` 只记录旁路命中，不能改变知识 status。
7. Memory Curator `dry_run=True` 不改状态；`dry_run=False` 对 API 必须 confirm。
8. 专业 ReAct 工具在 `TOOLS` 和 `TOOL_FUNCS` 双注册，失败返回 error。
9. `get_sector_regime` 不触发 `judge_regime()`；`get_capital_view` 不触发 `compute_capital_view()`。
10. 不存在自动交易端点或可疑自动下单函数名；用保守关键词检查即可。

测试要复用既有 helper；不要依赖真实网络、外部行情或真实 LLM。

## 可选小修

如果 contract test 暴露“字段已实现但端点响应缺少治理标识”，允许做最小兼容补字段。

禁止为了测试大改业务逻辑。

## 不要改

1. 不改 Agent 输出 schema。
2. 不改正式 prompt 段序。
3. 不改投研算法和交易逻辑。
4. 不新增自动下单或交易接口。
5. 不新增新的 Agent。
6. 不让 shadow / curator 结果自动影响正式结论。
7. 不清理或回滚工作树里其它未提交改动。

## 验收命令

只跑治理合同与关键批次测试：

```powershell
D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_governance_contract.py backend\tests\test_system_map.py backend\tests\test_system_map_collaboration.py backend\tests\test_adopt_audit_gate.py backend\tests\test_knowledge_metadata.py backend\tests\test_knowledge_shadow.py backend\tests\test_memory_curator.py backend\tests\test_agentic_tools_professional.py
```

不要跑全量测试，除非 contract test 暴露跨模块问题。

## 汇报格式

```text
改动文件+行号：

- [文件](绝对路径)：说明

测试：

- 命令：passed X / failed Y

红线核对：

- 未改 Agent 输出 schema：是
- 未改正式 prompt 段序：是
- 未改投研算法/交易逻辑：是
- shadow/curator 不影响正式结论：是
- contract tests 覆盖治理红线：是
- 已新增使用与验收手册：是
- 未开放交易接口：是

遗留/下一步：

- ...
```

