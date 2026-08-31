通用审核 Agent 批 1C（GET /audit-log 端点 + hover 真摘要，Claude Code 执行提示词·精简版）

路线：方案 §3-§7 + 批 1A f6b653f + 批 1B 31ef0fb 已提交
本任务：补后端 GET /audit-log 端点 + 前端 getAuditLog 接线，hover 能看完整 dissent 摘要（≤40 行后端 + ≤10 行前端回填）

---

可直接复制给 Claude Code 的提示词：

执行通用审核 Agent 批 1C（补 GET /audit-log 端点 + 前端 hover 真摘要）。

【背景】批 1B 31ef0fb 提交后，`web/src/api/audit.ts:39-51` 的 `getAuditLog` 调用 /audit-log 端点返回 404，已 catch 降级 null，hover 暂用行内 verdict/round（不满足"给我看审核意见"原需求）。本批补后端 + 前端真接线。

【后端必改】backend/app/api/routes.py 加 1 个端点（参考已有 routes.py:937 风格）：
- 路径：GET /audit-log
- 入参：target_type: str (必填，agent_suggestion/pending_experience/rule_change/review_result) + target_id: int (必填)
- 行为：调 audit.py 的新函数 `get_latest_audit_log(target_type, target_id)` → repo.py 新增 `get_latest_audit_log_by_target(target_type, target_id)` → 返回最新一条 audit_log（按 created_at desc）或 404
- 响应：直接返回 audit_log 行 dict（含 dissent_view 完整字段、reasoning、evidence_refs、support_view、boundary_cases、audit_model、duration_ms、created_at）
- 位置：在 routes.py /agent-suggestions 端点（:937）附近插入新端点，复用现有 Pydantic 风格

【后端必加】backend/app/db/repo.py 新增 1 函数：
- 签名：`get_latest_audit_log_by_target(target_type: str, target_id: int) -> dict | None`
- SQL：`SELECT * FROM audit_log WHERE target_type=? AND target_id=? ORDER BY created_at DESC LIMIT 1`（索引已覆盖 (target_type, target_id)）
- 走 `backend/app/db/session.py` 已有 SessionLocal（与 init.sql 批 1A +3 迁移共用连接）

【前端回填】web/src/api/audit.ts:39-51 `getAuditLog` 已定义，仅去掉 try/catch 兜底返回 null（让 404 真实冒泡给 UI）：
- 改：直接 `return await get<...>('/audit-log', { target_type, target_id })`
- catch 改为 re-throw（让上层页面用 React Query 的 error 状态展示"未审核"）

【前端 UI】web/src/pages/RuleChangesPage.tsx hover 改造（≤10 行）：
- 把当前 hover 显示"label·第N轮"升级为"verdict + round + dissent_view 前 40 字"
- 已有 Tooltip 组件直接复用，把 title 改为 `[verdict] 第{round}轮: {dissent_view.slice(0, 40)}...`

【硬约束】
1. 总改动 ≤ 50 行（后端 30 + 前端 10 + UI 10）
2. 严禁动 audit.py 既有 collect_audit/llm_audit/llm_re_audit/run_pending_audits
3. 严禁动 audit_log 表结构（批 1A 已锁）
4. 复用 repo.py 现有 SELECT 模式（参考 `get_agent_suggestions` at repo.py 已有位置）
5. 端点必须 404 时返回 {"detail": "not found"} 让前端能判别（不要返回 null 数组）
6. 测试 ≤ 2 个：test_audit_log_get（端点 + 404 路径）+ test_get_latest_audit_log_by_target（repo 函数）
7. 报告 ≤ 10 行：① routes.py diff ② repo.py 新增函数 ③ 前端 2 文件 diff ④ pytest 结果 ⑤ curl 抽查一行

【commit 模板】
git add backend/app/api/routes.py backend/app/db/repo.py backend/tests/test_audit.py web/src/api/audit.ts web/src/pages/RuleChangesPage.tsx
git commit -m "feat(audit-api): 通用审核Agent批1C——GET /audit-log端点 + hover显示完整dissent摘要"

【上线后 sir 必做】
- 重启后端（已在 PID 31280 跑批 1A+1B+飞书批2；新端点需要再次重启或 reload）
- curl 抽查：GET /audit-log?target_type=agent_suggestion&target_id=1 → 200 含 dissent_view 完整字段
- 触发 audit_pending(cutoff_id=0) 走真 LLM 1 条 → curl 看 audit_log 落库 → 前端 hover 能看完整摘要
