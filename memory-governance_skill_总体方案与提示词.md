# memory-governance skill 总体方案与提示词

## 1. 需求背景

现有《Memory 治理与记忆防污染提单》的核心问题，不是“如何给某个系统新增 memory 表”，而是一个更底层、更通用的系统治理问题：

长期运行的智能系统会不断积累历史上下文、用户偏好、任务经验、失败教训、阶段判断和自动摘要。如果这些内容没有边界、来源、时效、置信度、可见范围和晋升机制，记忆会从“辅助上下文”逐渐变成“隐性规则”，最终污染判断。

因此，需要将该提单抽象成一套可插拔的 Memory Governance 标准体系，用于任何涉及长期记忆、经验沉淀、上下文召回、RAG、Agent 协作或规则晋升的系统。

该 skill 的目标不是替某个系统实现记忆功能，而是提供一套治理标准，帮助设计、审查和改造 memory 相关能力，防止：

1. 历史记忆误召回。
2. 过期经验污染当前判断。
3. 临时反馈被错误固化为长期规则。
4. 某个用户、项目、Agent 或场景的局部经验污染其他范围。
5. 召回内容被模型当作强证据。
6. 敏感历史上下文被不必要地带入输出。
7. Memory、Knowledge、Rule 三者边界混乱。

一句话目标：

```text
提供一套可插拔的 Memory Governance 标准，使记忆始终保持为可审计的软上下文，不能静默变成事实、规则、权限或跨范围污染源。
```

## 2. Skill 定位

建议 skill 名称：

```text
memory-governance
```

建议 description：

```text
Design, review, or refactor memory systems so that long-term memory, retrieved context, user preferences, agent experience, and rule promotion remain scoped, auditable, time-aware, and unable to silently become facts, permissions, or hard rules.
```

中文定位：

```text
用于设计、审查或改造长期记忆、RAG 上下文、Agent 经验沉淀、用户偏好和规则晋升链路，防止记忆污染、规则漂移、跨范围泄漏和历史误导。
```

它应该是一个“记忆治理审查与设计 skill”，而不是“记忆数据库开发 skill”。

## 3. 适用范围

应触发该 skill 的场景：

1. 设计或审查长期记忆系统。
2. 设计或审查 Agent memory、user memory、project memory。
3. 设计或审查 RAG / context retrieval / memory search 链路。
4. 处理经验沉淀、失败案例、用户偏好、自动摘要。
5. 将历史经验晋升为知识库、方法论或规则。
6. 设计多 Agent、多用户、多项目之间的记忆隔离。
7. 排查记忆误召回、旧经验污染、规则漂移。
8. 审查敏感记忆是否可能泄露到输出层。

不应触发该 skill 的场景：

1. 普通代码修改。
2. 一次性总结。
3. 没有持久化上下文的普通问答。
4. 与 memory、RAG、长期偏好、经验沉淀、规则晋升无关的任务。
5. 单纯的业务知识整理，除非它涉及长期复用、召回或晋升。

## 4. 核心设计原则

### 4.1 三层边界

```text
Rule：确定性约束，必须审核，可回滚，用于底线行为。
Knowledge：相对稳定的知识、方法论、定义、案例库，可复用但需标注适用范围。
Memory：历史上下文、过程观察、偏好、经验摘要，只能作为软参考。
```

Memory 的定位：

```text
只提供参考，不覆盖硬规则；
只补充上下文，不替代实时数据；
只影响当次判断，不直接改变未来行为；
需要晋升为 Knowledge / Rule 时，必须走审核与验证。
```

### 4.2 反污染红线

1. Memory 不等于 Rule。
2. 历史不等于事实。
3. 偏好不等于授权。
4. 召回不等于证据。
5. 自动沉淀不等于长期有效。
6. 相似度命中不等于适用。
7. 跨 scope 召回默认禁止。
8. Sensitive memory 默认不进入输出层。
9. Memory 不得覆盖用户当前指令。
10. Memory 不得替代实时数据或外部事实核验。

### 4.3 基本治理原则

1. 规则确定性注入，记忆概率性召回。
2. 记忆默认隔离，只允许在 owner_scope、visibility_scope 或明确授权范围内召回。
3. 记忆必须带来源、类型、时效、置信度、场景标签。
4. 记忆召回后必须先过滤、排序，再进入 prompt。
5. 记忆晋升为知识或规则，必须走审核链。
6. 记忆不可用时降级执行，不阻断主链路。
7. 会影响未来行为的沉淀必须可审计、可回滚。

## 5. 建议 Skill 结构

```text
memory-governance/
  SKILL.md
  references/
    principles.md
    memory-schema.md
    retrieval-pipeline.md
    promotion-audit.md
    review-checklist.md
```

### 5.1 SKILL.md

只放入口判断和最小红线，避免 skill 自身变成上下文污染源。

应包含：

1. 什么时候使用该 skill。
2. 什么时候不要使用该 skill。
3. Memory / Knowledge / Rule 的最短边界定义。
4. 反污染红线。
5. 根据任务类型读取 references 的路由。

建议限制：

```text
SKILL.md 不超过 120 行。
详细说明、schema、流程、清单全部放入 references。
```

### 5.2 references/principles.md

放通用治理原则：

1. Memory / Knowledge / Rule 三层边界。
2. Memory 只能作为 soft context。
3. 记忆与事实、授权、规则的区别。
4. scope、freshness、confidence、sensitivity 的基本含义。
5. 常见污染类型和防护原则。

### 5.3 references/memory-schema.md

放通用 metadata schema：

```text
memory_id
owner_scope
visibility_scope
memory_type
source
status
confidence
created_at
last_used_at
valid_until
context_tags
evidence_refs
sensitivity
risk_note
promotion_target
```

字段原则：

1. 字段可按系统复杂度裁剪。
2. 不要求第一版全部强制录入。
3. 但 source、scope、status、confidence、freshness、sensitivity 必须有默认策略。
4. 没有 metadata 的记忆不得直接作为高置信上下文注入。

### 5.4 references/retrieval-pipeline.md

放召回过滤与排序流程：

```text
query
  -> scope filter
  -> status filter
  -> freshness filter
  -> sensitivity filter
  -> confidence/source scoring
  -> scene rerank
  -> inject as "historical memory, reference only"
```

排序因素：

1. scope 匹配度。
2. 场景匹配度。
3. 是否过期。
4. 来源可信度。
5. 置信度。
6. 是否被复盘验证。
7. 最近命中次数。
8. 最近使用时间。
9. 与当前用户指令是否冲突。
10. 与当前事实数据是否冲突。

### 5.5 references/promotion-audit.md

放记忆生命周期和晋升审核：

```text
captured
  -> draft
  -> active memory
  -> curated summary
  -> knowledge candidate
  -> reviewed knowledge

captured
  -> draft
  -> rule candidate
  -> audit
  -> approved rule
```

晋升原则：

1. 短期观察不能直接成为 Rule。
2. 高频重复记忆可合并为 curated summary。
3. 失败案例与成功案例都要保留适用条件。
4. 会影响未来行为的内容进入 Rule 前必须审核。
5. 低置信、过期、冲突记忆应 archived 或 expired。
6. 第一版只归档，不物理删除。
7. 所有晋升必须保留 evidence_refs 和 rollback 路径。

### 5.6 references/review-checklist.md

放审查清单：

1. 是否区分 Memory / Knowledge / Rule。
2. 是否存在 Memory 覆盖 Rule 的路径。
3. 是否存在旧记忆长期有效的问题。
4. 是否存在跨用户、跨项目、跨 Agent 召回污染。
5. 是否记录 source、confidence、valid_until。
6. 是否对 sensitive memory 做输出层保护。
7. 是否对召回结果做过滤和 rerank。
8. 是否明确 memory unavailable 的降级策略。
9. 是否有记忆晋升审核链。
10. 是否有 archived / expired / rollback 机制。

## 6. 标准输出形态

当该 skill 被用于设计任务时，输出应包括：

1. 需求背景。
2. 污染风险列表。
3. Memory / Knowledge / Rule 边界。
4. metadata schema。
5. retrieval pipeline。
6. lifecycle。
7. promotion audit。
8. sensitivity / visibility 规则。
9. review checklist。
10. 最小落地建议。

当该 skill 被用于审查任务时，输出应包括：

1. 发现的问题，按严重度排序。
2. 触发的反污染红线。
3. 受影响的记忆链路。
4. 建议修正方案。
5. 必要测试或验证项。

## 7. 全套执行提示词

### 提示词 1：抽象需求背景

```text
你是一个系统治理架构师。请基于 D:\self\Memory治理与记忆防污染_提单.md，将其中面向特定系统的 Memory Governance 提单，抽象成一套通用 skill 的需求背景文档。

执行纪律：
1. 先用 rg -n "^#" 定位章节。
2. 只读取与背景、核心判断、改前问题、预期目标相关的章节附近内容，不整读大文件。
3. 不写落地实现，不写代码。
4. 输出一份 ≤600 行的《memory-governance_skill_需求背景.md》。

文档必须包含：
- 为什么需要 Memory Governance。
- Memory 污染会造成哪些系统性风险。
- Memory / Knowledge / Rule 的边界。
- 该 skill 的适用范围与不适用范围。
- 该 skill 要解决的通用问题，而不是某个具体系统的问题。

红线：
- 不把某个 Agent 名称、业务域名、交易场景写成通用规则。
- 不把临时经验、偏好、历史结论包装成硬规则。
- 不展开具体落地批次。
```

### 提示词 2：设计通用 skill 方案

```text
你是 Codex skill 设计专家。请基于《memory-governance_skill_需求背景.md》和 D:\self\Memory治理与记忆防污染_提单.md，设计一个可插拔的通用 skill：memory-governance。

执行纪律：
1. 先用 rg 定位 D:\self\Memory治理与记忆防污染_提单.md 中的核心判断、设计思路、数据模型、召回流程、生命周期、风险缓解章节。
2. 只读取相关章节附近内容。
3. 不创建 skill 文件，只输出方案文档。
4. 输出一份 ≤600 行的《memory-governance_skill_设计方案.md》。

方案必须包含：
- skill 名称、description 草案、触发条件。
- 不应触发该 skill 的场景。
- SKILL.md 应包含哪些最小规则。
- references/ 下应拆分哪些文档。
- Memory / Knowledge / Rule 三层边界。
- 通用 metadata schema。
- retrieval filtering / rerank 标准流程。
- promotion / audit / rollback 原则。
- sensitivity / visibility / scope 隔离规则。
- review checklist。
- 反污染红线。

设计要求：
- 这是跨系统标准，不是某个系统的实现方案。
- SKILL.md 必须短，细节进 references。
- 自动触发要谨慎，避免 skill 自身污染普通任务。
```

### 提示词 3：生成 skill 文件

```text
你是 Codex skill 创建者。请使用 skill-creator 规范，在合适的 Codex skills 目录下创建一个新 skill：memory-governance。

输入材料：
- D:\self\memory-governance_skill_需求背景.md
- D:\self\memory-governance_skill_设计方案.md
- D:\self\Memory治理与记忆防污染_提单.md

执行纪律：
1. 必须先读取 skill-creator 的 SKILL.md。
2. 不整读大文件；对提单只按章节定位读取必要片段。
3. 使用 apply_patch 创建或修改文件。
4. 不添加无用 README、空目录、占位示例。
5. 完成后运行 skill validator。
6. 只报告改动文件、验证结果、红线核对。

目标结构：
memory-governance/
  SKILL.md
  references/
    principles.md
    memory-schema.md
    retrieval-pipeline.md
    promotion-audit.md
    review-checklist.md

SKILL.md 要求：
- description 必须能精准触发：设计、审查、改造 memory / RAG / Agent 记忆 / 经验沉淀 / 规则晋升治理。
- 明确不适用于普通代码修改、一次性总结、无持久化上下文的普通任务。
- 只保留入口判断、核心红线、引用 references 的路由。
- 不超过 120 行。

references 要求：
- 每份文档聚焦单一主题。
- 不写特定业务 Agent 名称作为通用要求。
- 所有规则必须表述为跨系统标准。
- 明确 Memory 只能作为 soft context。
- 明确任何 Rule 晋升都需要审核和回滚路径。

验收红线：
- Memory 不等于 Rule。
- 历史不等于事实。
- 偏好不等于授权。
- 召回不等于证据。
- 自动沉淀不等于长期有效。
- 跨 scope 召回默认禁止。
- sensitive memory 默认不进入输出层。
```

## 8. 执行顺序建议

推荐分三步执行：

1. 先生成《memory-governance_skill_需求背景.md》。
2. 再生成《memory-governance_skill_设计方案.md》。
3. 最后创建真正的 `memory-governance` skill。

这样可以避免把某个具体系统的实现细节直接沉淀成通用规则，也能防止 skill 自身变成新的上下文污染源。

