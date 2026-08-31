通用审核 Agent 批 1B 修复版（routes 透出 + 前端联调，Claude Code 执行提示词·精简版）

路线：方案 §3-§7 + 批 1A f6b653f 已提交 + 批 1B 前端 3 文件已写（未 commit）
本任务：补 routes.py 透出 3 字段 + 分 2 次 commit + 真实 LLM 验证

---

可直接复制给 Claude Code 的提示词（17 行核心 + 3 行 commit 模板）：

执行通用审核 Agent 批 1B 修复版（routes 透出 + 前端联调，2 次 commit）。

【P0 修复】backend/app/api/routes.py:937-954 的 GET /agent-suggestions 端点没把批 1A 迁移的 3 列透出（audit_verdict / audit_round / last_audit_id），导致 web/src/api/audit.ts 客户端聚合拿不到 audit 状态，前端三态徽章 / OverviewPage「AI 审核待审」卡 100% 灰。

必改（routes.py:943 在 "suggestion_source": s.suggestion_source or "llm", 之后 + 在 "created_at": str(s.created_at) 之前插入 3 行）：
    "audit_verdict": getattr(s, "audit_verdict", None) or "",
    "audit_round": getattr(s, "audit_round", 0) or 0,
    "last_audit_id": getattr(s, "last_audit_id", None),
（getattr 兜底——老模型/未迁移库不崩；与批 1A session.py +3 列迁移对齐）

【commit 顺序 — 严禁混批】

# Commit 1：飞书批 2 串扰 6 文件（独立 commit，独立于本主题）
git add .env.example backend/app/core/config.py backend/app/scheduler/jobs.py backend/app/services/feishu_bridge.py backend/app/services/feishu_sender.py backend/tests/test_feishu_b4.py
git commit -m "feat(feishu): 飞书批2（具体子主题待你按实际改写）"

# Commit 2：批 1B 修复 4 文件（routes.py 透出 3 行 + 前端 3 文件 107 行）
git add backend/app/api/routes.py web/src/api/audit.ts web/src/pages/OverviewPage.tsx web/src/pages/RuleChangesPage.tsx
git commit -m "feat(audit-web): 通用审核Agent批1B——agent_suggestions接口透出audit 3字段 + 前端三态徽章（修复版）"

【硬约束】
1. routes.py 仅 1 处改 3 行（≤5 行总改动）；其余前端 3 文件一字不动（批 1B 已审过）
2. 严禁把批 1A f6b653f 已提交的 10 文件重复 add（git status 验证工作区干净只剩 9 个 untracked/modified）
3. getattr 兜底是必须的——sir 切流期间可能某些实例没跑 session.py +3 迁移，不崩
4. 字段顺序：放在 suggestion_source 后、created_at 前，保持响应体结构稳定
5. commit message 用 feat(audit-web): 前缀，匹配批 1A feat(audit): 风格
6. 不要顺手改 config.py / jobs.py / feishu_* —— 那些是飞书批 2 的范围
7. 报告 ≤ 10 行：① routes.py diff（必须含 3 行透出）② 2 个 commit hash ③ tsc -b EXIT=0 验证 ④ /api/agent-suggestions curl 抽查一行确认 audit_verdict 有值（或仍空=老数据未审核正常）

【上线后 sir 必做】（不在 Claude Code 范围）
- 重启后端（PID 23772 仍跑批 1A 旧代码）让 audit_pending + 03:30 cron 生效
- 手动触发 audit_pending(cutoff_id=0) 走真实 LLM 辩证，验证 audit_log 落库 + OverviewPage 数字实时刷新

---

核验项（sir 验收时逐条过）：
1. routes.py:943 后插入 3 行：git diff backend/app/api/routes.py 必须含 3 行 getattr(s, "audit_*", ...)
2. 2 次 commit 分离：git log --oneline -3 必须看到 2 个独立 commit，前缀分别是 feat(feishu): 和 feat(audit-web):
3. tsc EXIT=0：cd web && npx tsc -b 返回 0
4. 后端接口透出：curl /api/agent-suggestions 抽查一行确认 audit_verdict 字段存在（值可空=老数据未审）
5. 飞书批 2 6 文件独立：git log --stat feat(feishu) hash 仅含飞书 6 文件，无 audit-* 文件
