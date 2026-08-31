# 通用审核 Agent — 批 1 最小闭环（Claude Code 执行指令）

> 0 元信息：sir 出题 / Claude Code 执行 / sir 验收
> 路线：通用审核Agent_方案.md §3-§7（已过审）
> 任务：audit_log 表 + agent_suggestion 审核字段 + AuditAgent + 凌晨批量审核入口 + 漏扫补跑（仅 agent_suggestion 1 个 target）

---

## 一、目标

做 1 个最小闭环：**只覆盖 agent_suggestion**（review 输出的策略建议）这一类待审点，跑通：

1. AuditAgent 批量扫描待审建议 → 辩证审核 → audit_log 落库
2. 失败 → 自动触发 review.rethink → 重审 1 轮
3. 原 `agent_suggestion` 表加 `audit_verdict` 字段，审核状态靠 DB 留痕
4. 提供可手动/定时调用的 `audit_pending` 批处理入口；默认设计为每天凌晨低峰期执行，启用后的漏审下次按状态补跑

**不做的**：pending_experience / rule_change / review_result 三类（批 2 扩）；审计中心独立页（批 2）；React 概览卡/列表列（批 1B）；实时逐条触发审核；Streamlit 改动（永久规则：默认 React 优先）。

## 二、架构约束

| 对象 | 处理 |
|---|---|
| 新表 | `audit_log`（id/target_type/target_id/round/verdict/confidence/support_view/dissent_view/boundary_cases/evidence_refs/audit_model/reasoning/duration_ms/created_at）|
| 原表加字段 | `agent_suggestion` 加 `audit_verdict(String(8), default=pending)` / `audit_round(Int, default=0)` / `last_audit_id(Int, nullable=True)` |
| 新 Agent | `backend/app/agents/audit.py`（collect_audit + llm_audit + llm_re_audit 3 个函数） |
| 新 prompt | `agent_prompts/audit_prompt.py`（SYSTEM_PROMPT + build_user_prompt） |
| 批处理入口 | `backend/app/agents/audit.py` 提供 `run_pending_audits(cutoff_id, last_scanned_id, limit=50)`；`backend/app/api/routes.py` 在 `_TASK_KINDS` 增加 `audit_pending`（复用现有任务提交入口） |
| 执行时机 | 不改 `review.py` 实时触发；每天凌晨低峰期或手动任务触发时，按 DB 状态扫描待审/漏审记录 |
| 前端 | 批 1A 不做；只保证 DB 字段和 audit_log 可供批 1B 展示 |

**解耦铁律**：
- AuditAgent 只注入 collect 段，不动 agent_call / push_alert_node
- 产出时只落 `audit_verdict=pending`；审核执行由 `audit_pending` 批处理扫描，不阻塞 review 落库
- audit 读原表只读不写（仅写 audit_log + 原表 3 个 audit 字段）

**已有模式复用**：
- 异步 task → 参考 `backend/app/api/routes.py:62-90` 的 `_TASK_KINDS` 注册 + `task_queue.submit(kind, label, fn, params)` 模式
- FastAPI 路由 → 参考 `routes.py:817-846`（`/reviews/{rid}/adopt|reject`）的写法

## 三、规则（硬约束，按这条改）

### 3.1 audit_log 表
- `target_type` 枚举：`agent_suggestion / pending_experience / rule_change / review_result`（批 1 只用第一个）
- `verdict` 枚举：`pending / pass / fail`
- `round` 1=首审，2=重审（**不超 2**）
- `dissent_view` 强制非空，≥50 字，**必含 1 个具体反例/场景**（如"亨通惨案根因 1"）
- `evidence_refs` 用 `SafeJSON` 存 list[str]，至少 1 条，格式 "K223" 或 "knowledge_id=42" 或 "rule_change#15"
- 索引：`(target_type, target_id)` / `verdict` / `created_at`

### 3.2 辩证 schema（`AuditOutput`）
```
verdict: pass/fail
confidence: 0-100
support_view: ≥30 字
dissent_view: ≥50 字 + 必含具体反例
boundary_cases: ≥30 字
evidence_refs: list[str] 至少 1 条
one_line_summary: ≤40 字
```

### 3.3 SYSTEM_PROMPT 硬约束（写进 prompt）
1. 强制正反辩论：列出支持意见 + 强制找 1 条反对意见（不论你是否认同）
2. 反对意见必须含具体场景/反例（**禁止"可能存在风险"等空话**）
3. 至少 1 条边界场景（什么情况下结论会失效）
4. 至少 1 条基础库引用（K 编号 / 私有知识 ID / 反例库）
5. 找不到反对意见 → **强制 fail**，写明「我没找到具体反方，但请 sir 复核」
6. round=2 重审时追加：「历史 fail 原因：<dissent_view>，请明确回应每条反对」

### 3.4 执行时机与补漏
- `review.py` 不实时触发 audit；review 只负责正常产出并落库，新增字段保持默认 `audit_verdict=pending`
- 新增 `run_pending_audits(cutoff_id, last_scanned_id, limit=50)`：只扫描 `agent_suggestion.id > max(cutoff_id, last_scanned_id) AND (audit_verdict='pending' OR last_audit_id IS NULL OR (audit_verdict='fail' AND audit_round < 2))`
- `cutoff_id` 是启用边界：批 1 执行前记录当前 `max(agent_suggestion.id)`，避免历史存量被自动审核；只有 sir 明确要求补历史才允许传 `cutoff_id=0`
- `last_scanned_id` 是增量游标：用现有 `experience_config` 存 `audit_cursor.last_id`，每轮跑完更新到本轮最大 `agent_suggestion.id`；失败中断不越过未处理 id
- 新增任务类型 `audit_pending`：复用现有 `_TASK_KINDS` + `task_queue.submit` 模式，可手动触发；`scheduler/jobs.py` 挂每天 03:30 cron
- 扫描必须幂等：同一条记录最多审到 round=2；已 pass 或 round=2 fail 的记录不再自动重审
- 不新增 scheduler 依赖；复用现有 `scheduler.add_job(..., "cron")` 模式

### 3.5 失败重审
- audit round=1 verdict=fail → 自动调用 `llm_rethink_suggestion(agent_suggestion.review_id, audit_log.dissent_view)` 走 review 已有链路
- review rethink 完成后 → 对同一 review_id 下新写入的待审建议重新跑 audit round=2；扫描端按新增 id + 游标捞取，禁止新建无限链路
- round=2 仍 fail → 标 `agent_suggestion.audit_verdict=fail`，**不再自动 rethink**，原表正常呈 sir
- 最多 2 轮防止无限循环

### 3.6 旁路开关
- 暂不实现 `/audit/{aid}/confirm-fail`（批 4 再做）
- 批 1 应急方案：sir 改 `agent_suggestion.audit_verdict='pass'` 直接 SQL 标绿

### 3.7 缓存键
`audit:{target_type}:{target_id}:round{1|2}` → 走 `agent_call(agent="audit", model_level=DEEP, ttl=86400)` 既有 SimpleCache
- **不**用 `call_llm_cached` 直调，统一走 `agent_call` 复用全局基线/HARD_RULES/偏好

## 四、执行顺序

1. `backend/app/db/init.sql` 追加 `audit_log` 表 + 3 索引（参考已有 `ai_reasoning_trace` 表写法）
2. `backend/app/db/models.py` 追加 `AuditLog` 类 + `AgentSuggestion` 加 3 字段
3. `agent_prompts/audit_prompt.py` 新建（SYSTEM_PROMPT + build_user_prompt + build_re_audit_user_prompt）
4. `backend/app/agents/audit.py` 新建（collect_audit / llm_audit / llm_re_audit 3 函数）
5. `backend/app/agents/schemas.py` 追加 `AuditOutput`（pydantic）
6. `backend/app/db/repo.py` 追加 `insert_audit_log` / `get_audit_log` / `update_audit_log_verdict` / `update_agent_suggestion_audit` / `list_agent_suggestions_for_audit`，游标读写复用现有 `get_config/set_config`
7. `backend/app/agents/audit.py` 追加 `run_pending_audits(cutoff_id, last_scanned_id, limit=50)`：按启用边界 + 游标 + 状态扫描 pending/漏审/未完成二审
8. `backend/app/api/routes.py` 在 `_TASK_KINDS` 注册 `"audit_pending"`（复用现有任务提交入口，不新增 `/audit/*` 展示 API）
9. `backend/app/scheduler/jobs.py` 增加 `audit_pending_job` + `scheduler.add_job(audit_pending_job, "cron", hour=3, minute=30)`，参考 `experience_worker_job`
10. `backend/tests/test_audit.py` 新建（≥4 个：collect 注入 / 辩证 schema / pending 扫描补漏 / round=2 仍 fail 不再 rethink）

## 五、验证清单

- [ ] `audit_log` 表在 init.sql 执行后建好，老数据不动
- [ ] 老 `agent_suggestion` 默认 `audit_verdict=pending`，不自动迁移/补审
- [ ] 手动触发 `audit_pending(cutoff_id=启用前max_id)` → 启用后新增 pending/last_audit_id=NULL 记录出现 `audit_log(round=1, target_id=sid)`，历史存量不被自动审核
- [ ] `experience_config.audit_cursor.last_id` 随成功扫描推进；失败中断不越过未处理 id
- [ ] 注入 dissent 强信号 → audit_log.verdict=fail → review rethink 触发 → round=2 audit_log 落库
- [ ] round=2 仍 fail → `agent_suggestion.audit_verdict=fail`，不再触发第 3 轮
- [ ] `pytest backend/tests/test_audit.py` 全过

## 六、红线（sir 决策底线，Claude Code 必读）

### 6.1 不破坏既有
- `agent_call` / `push_alert_node` / `task_queue` 核心调度**一字不动**；只允许在 `routes.py` 注册新任务类型、在 `scheduler/jobs.py` 挂 03:30 cron
- review_agent 的 `llm_rethink_suggestion` 函数**直接复用**，AuditAgent 只调它，不重写
- 老数据全部 `audit_verdict=pending` / `audit_round=0` / `last_audit_id=NULL`，不补不迁移

### 6.2 不引新依赖
- 不用新库（SimpleCache + 已有 SQLite + 已有 FTS5 + 已有 `agent_call` 足够）
- 不引新 LLM 客户端（统一 `agent_call(agent="audit", model_level=DEEP, ...)`）
- 不写新工具（audit 只读 `repo` + `agent_prompts/knowledge/*.md` 文件，不写新工具函数）

### 6.3 失败有据可查
- `audit_log.reasoning` 完整存 LLM 原始 JSON（sir 可看 AI 推理全文）
- `audit_log.duration_ms` 记录耗时（监控性能）
- dissent_view 留痕：批 1A 先保证 DB 可查；前端 hover 放到批 1B

### 6.4 业务红线
- **AuditAgent 不修改任何 agent_prompts / K 红线 / 阈值**（只审核）
- **不删原表记录**（audit fail 不删 suggestion，只标 `audit_verdict=fail`）
- **不污染原 LLM 缓存**（audit cache_key 必含 round；老 cache 不动）

### 6.5 Claude Code 端省 token 约束
1. **不复读本提示词**：6 段 + Schema + 阈值已齐备，禁止 read 全文（只 grep 关键标识）
2. **不写超出范围代码**：本批只动列出的文件；禁止顺手改其他文件
3. **不写大段注释**：函数 docstring ≤ 3 行，函数体内不写 `# 注释`（除关键 trade-off）
4. **复用已有函数**：audit 必调 `agent_call` / `repo.*` / 现有 `task_queue.submit` 路径，**禁止重写**
5. **测试不超过 13 个**：本提示词列 4 个 + 已有 3 个回归即可，禁止多写
6. **报告精简**：≤10 行：①改了什么（文件清单）②pytest 结果 ③遗留风险

### 6.6 代码侧最小改动铁律
- 本批总改动预算 ≤ 250 行（不算 init.sql 和测试）
- 超出 → 停下报告 sir，不自行加功能

---

## 附：参考文件 path:line 速查

| 内容 | 位置 |
|---|---|
| agent_call 签名 | `backend/app/agents/common.py:357-375` |
| AgentSuggestion 模型 | `backend/app/db/models.py:401-434` |
| review.py 建议落库位置（只读参考，不改实时触发） | `backend/app/agents/review.py:225-235` |
| llm_rethink_suggestion | `backend/app/agents/review.py:252-289` |
| task_queue submit 模式 | `backend/app/api/routes.py:62-90`（task 类型注册）/ `backend/app/services/task_queue.py:73` |
| 路由写法 | `backend/app/api/routes.py:817-846` |
| init.sql 风格 | `backend/app/db/init.sql:210-229`（ai_reasoning_trace） |
| ReviewAgent prompt 风格 | `agent_prompts/review_prompt.py`（SYSTEM_PROMPT 模板） |
| review_prompt 哲学 | `agent_prompts/knowledge/review.md`（辩证依据来源） |
