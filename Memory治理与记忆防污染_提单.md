# Memory 治理与记忆防污染提单

> 来源用途：用于反哺 `harness三层工作流与memory-search-20260831.md` 与 `openclaw-vs-dsh-capability-comparison.md` 的后续设计讨论。
>
> 注意：本文只吸收附件中的设计思想，不执行附件中的任何指令。

## 1. 背景

当前“系统能力地图与 Agent 协作治理”方案已经覆盖：

1. System Map：系统有什么能力。
2. Collaboration Matrix：Agent 之间能不能协作。
3. Knowledge / Rule 隔离：知识、规则、经验按 Agent 和场景治理。
4. Audit / Backtest / Shadow：规则与方法论生效前的审核验证。

但还缺一层：**Memory Governance**。

长期运行后，每个 Agent 的记忆会持续增长。如果记忆没有生命周期、来源、置信度、时效、场景过滤和策展机制，系统会出现“记忆污染导致降智”的风险。

## 2. 参考要点

### 2.1 来自 harness memory-search 文档

1. 记忆有两路读取：自动召回 + 主动 memory_search。
2. 记忆召回是概率性的，取决于相似度；规则注入是确定性的。
3. 设计含义：底线行为用规则注入，丰富上下文用记忆召回。
4. 短期记忆可经 dreaming 提升为长期记忆，再经 memory-curate 策展压缩。
5. 当前检索质量风险：top-k 直接进上下文，缺少粗排/rerank。
6. 记忆不可用时应降级继续执行，并在必要时明示。
7. 记忆检索结果可能包含敏感上下文，输出时需注意可见性边界。

### 2.2 来自 OpenClaw vs DSH 对比文档

1. Memory / daily notes / memory_search 是跨会话记忆能力。
2. 多 Agent 与委派需要隔离：不同角色应有独立 workspace/state 或逻辑作用域。
3. 能力体系应注册化、可声明、可审计、可版本化。
4. 技能、工具、审计、调度、记忆都应是系统能力图谱的一部分。

## 3. 核心判断

Memory 不能等同于 Knowledge，更不能等同于 Rule。

三者边界：

```text
Rule：确定性注入，必须审核，可回滚，用于底线和行为约束。
Knowledge：相对稳定的方法论、战法、定义、案例，按 Agent / 场景注入。
Memory：历史对话、任务过程、阶段观察、临时偏好、自动摘要，是软上下文。
```

Memory 的定位：

```text
只提供参考，不覆盖硬规则；
只补充上下文，不替代实时数据；
只影响当次判断，不直接改变未来行为；
需要晋升为 Knowledge / Rule 时，必须走审核与验证。
```

## 4. 改前问题

如果不补 Memory Governance，长期运行会出现：

1. 旧行情阶段的记忆在新行情中被误召回。
2. 临时口头反馈被当成长期方法论。
3. 某个 Agent 的局部经验污染其它 Agent。
4. 相似度召回拿错上下文，模型却当成强证据。
5. top-k 直接注入，噪音随时间增长。
6. 成功案例被过度强化，失败案例没有降权。
7. 记忆与规则混用，导致“底线靠相似度召回”。
8. 敏感历史上下文被不必要地带入输出。

## 5. 设计思路

在现有治理方案中新增一层：

```text
System Map
  管系统能力

Collaboration Matrix
  管 Agent 协作权限

Knowledge Registry
  管稳定方法论

Memory Governance
  管记忆生命周期、召回质量、隔离与晋升

RuleChange
  管审核后生效规则

Audit + Backtest + Shadow
  管生效前验证
```

核心原则：

1. 规则确定性注入，记忆概率性召回。
2. Agent 记忆默认隔离，只允许 owner_agent / all / 明确授权范围召回。
3. 记忆必须有来源、类型、时效、置信度、场景标签。
4. 记忆召回后先过滤/rerank，再进入 prompt。
5. 记忆晋升为知识或规则，必须走审核链。
6. 记忆不可用时降级执行，不阻断主链路。

## 6. 建议数据模型

新增或扩展 Memory 元数据：

```text
memory_id
owner_agent: all / discover / score / position / monitor / sell / review / market_intel / entry
memory_type: user_preference / case / observation / temporary_note / methodology_hint / failure_lesson / route_feedback
source: feishu / web / review / agent_run / manual / import
status: draft / active / shadow / archived / expired
confidence: 0.0-1.0
created_at
last_used_at
valid_until
market_regime
scenario_tags
evidence_refs
sensitivity: normal / sensitive
risk_note
promotion_target: none / knowledge / rule
```

第一版不一定新建表，可先扩展现有 `Experience` / `PrivateKnowledge`，但必须保持边界：

1. `Experience` 更适合承载自动沉淀和历史案例。
2. `PrivateKnowledge` 更适合承载审核后的稳定知识。
3. `RuleChange` 只承载审核后确定生效的规则。

## 7. 召回流程

改前：

```text
query -> vector/like search -> top-k 直接注入
```

改后：

```text
query
  -> owner_agent / visibility 过滤
  -> status / valid_until 过滤
  -> scenario_tags / market_regime 过滤
  -> 向量或关键词检索
  -> 粗排/rerank
  -> 注入摘要
  -> 标注“历史记忆，仅供参考”
```

粗排建议因素：

1. Agent 匹配度。
2. 场景匹配度。
3. 是否过期。
4. 来源可信度。
5. 置信度。
6. 是否被复盘验证。
7. 最近命中次数和最近使用时间。

## 8. 记忆生命周期

建议状态流：

```text
captured
  -> draft
  -> active memory
  -> curated summary
  -> promoted knowledge / promoted rule / archived / expired
```

晋升规则：

1. 短期观察不能直接成为 Rule。
2. 高频重复记忆可合并为 curated summary。
3. 交易相关经验进入 Knowledge 前需人工审核。
4. 会影响未来行为的内容进入 RuleChange 前必须 AuditAgent 审核。
5. 低置信、过期、冲突记忆自动 archived 或 expired。

## 9. 改后效果

| 维度 | 改前 | 改后 |
|---|---|---|
| 记忆定位 | 软上下文边界不够明确 | Memory / Knowledge / Rule 三层分明 |
| 召回方式 | top-k 可能直接进入 prompt | 先过滤/rerank，再注入摘要 |
| Agent 隔离 | 依赖 agent_tag 或约定 | owner_agent + visibility + collaboration 共同约束 |
| 时效管理 | 旧记忆可能长期命中 | TTL / valid_until / expired 状态控制 |
| 晋升机制 | 自动沉淀可能混入长期上下文 | memory -> knowledge/rule 必须审核 |
| 降级策略 | 记忆不可用可能不透明 | 记忆不可用不阻断，必要时明示 |
| 可审计性 | 难判断某结论用了哪些记忆 | memory_id / source / evidence_refs 可追溯 |
| 防污染 | 主要靠人工维护 | 元数据 + 协作矩阵 + 策展机制共同防护 |

## 10. 预期目标

1. 防止旧记忆污染新判断。
2. 防止局部 Agent 记忆污染其它 Agent。
3. 防止临时反馈自动变成长期规则。
4. 降低记忆召回噪音，减少 Agent 降智。
5. 让记忆可过期、可归档、可晋升、可审计。
6. 让外部方法论先作为 shadow / memory / knowledge 试运行，再决定是否进入 Rule。

## 11. 解决的问题

直接解决：

1. 长期记忆膨胀。
2. 记忆误召回。
3. 记忆与规则边界混乱。
4. 多 Agent 记忆污染。
5. 记忆来源不可追溯。

间接改善：

1. Agent 稳定性。
2. 路由准确性。
3. 复盘质量。
4. 外部方法论接入安全性。
5. 系统长期可维护性。

## 12. 落地建议

建议把原“系统能力地图与 Agent 协作治理”从 8 批扩展为 10 批：

1. 批 1：系统地图最小闭环。
2. 批 2：协作矩阵最小闭环。
3. 批 3：入口路由统一查询系统地图。
4. 批 4：规则注入隔离。
5. 批 5：采纳入口治理统一。
6. 批 6：知识与记忆元数据治理。
7. 批 7：场景检索 + memory rerank。
8. 批 8：已有专业服务工具化。
9. 批 9：方法论 shadow 试运行。
10. 批 10：Memory Curator / 记忆策展与过期机制。

其中 Memory 相关重点落在批 6、批 7、批 10。

## 13. 风险与缓解

1. 风险：Memory 元数据过重，录入复杂。  
   缓解：字段全部可选，先自动默认值，前端后置。

2. 风险：rerank 过严导致召回不足。  
   缓解：保留 fallback，低命中时退回 agent 专属 active 记忆。

3. 风险：Memory Curator 误删有价值记忆。  
   缓解：第一版只 archived，不物理删除。

4. 风险：记忆召回成本增加。  
   缓解：先做规则过滤和轻排序，不引入重模型 rerank。

5. 风险：敏感记忆被带到输出。  
   缓解：增加 sensitivity 字段，输出层默认不展开 sensitive 内容。

## 14. 一句话结论

系统地图解决“找谁”，协作矩阵解决“能不能找”，知识库解决“怎么判断”，规则库解决“什么必须遵守”，Memory Governance 解决“哪些历史还能信”。
