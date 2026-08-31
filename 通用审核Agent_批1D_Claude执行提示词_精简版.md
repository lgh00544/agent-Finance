通用审核 Agent 批 1D（紧急 UI 增强：原内容 + 完整审核意见全展示，Claude Code 执行提示词·精简版）

路线：方案 §3-§7 + 批 1A f6b653f + 批 1B 31ef0fb + 批 1C 42113f3 已提交
本任务：RuleChangesPage hover 弹层展示原 suggestion 全文 + audit_log 完整审核意见（无审核时显"未审核"提示）
后端：零改动（routes.py:994 端点 + repo.py:2060 函数已就位）

---

可直接复制给 Claude Code 的提示词：

执行通用审核 Agent 批 1D（紧急 UI 增强：原内容 + 完整审核意见全展示）。

【sir 实测反馈】截图显示：RuleChangesPage「AI 审核」列 hover 只显示 verdict/round，看不到原建议全文 + 审核意见完整内容。批 1B/1C 没满足"给我看审核意见"原需求。curl 实证：20 条全 pending，audit_log 0 行。

【前端必改 1】web/src/pages/RuleChangesPage.tsx「AI 审核」列 hover 弹层升级（≤60 行）：

- 当前：Tooltip 显示 label·第N轮
- 改为：Popover 展开 2 块（hover 触发，width=520，content 用 Descriptions 组件或简单 dl）
  - 块 1【原建议】rule_name + current_value + suggested_value + reason + evidence + problem_desc + rule_text(去重) + risk_note + status + reject_reason + created_at —— 从该行数据直接拿，列表 query 已含全部字段
  - 块 2【AI 审核】（仅 audit_log 非空时）verdict(pass/fail) + round + confidence + support_view + dissent_view + boundary_cases + evidence_refs(list 渲染) + audit_model + created_at + reasoning 前 300 字（折叠展开）
- 复用 antd Popover + Descriptions（已装）实现
- 块 2 数据源：useQuery(['audit-log', target_type, target_id], () => getAuditLogFull('agent_suggestion', sid), { enabled: !!sid, staleTime: 30_000 })
- 没有 audit_log 时块 2 显示「未审核 — 等待 03:30 cron 或手动 audit_pending(cutoff_id=0)」灰色提示
- 不要做 loading 闪烁（staleTime 30s 够长；初次 null 显示"未审核"占位，不显示 spinner）

【前端必改 2】web/src/api/audit.ts 已有 getAuditLog（第 39 行附近），检查并补强（≤10 行）：
- 如已存在 getAuditLog(target_type, target_id) 走 try/catch 降级 null → 改为去掉 catch 让 404 真实冒泡给 React Query error 状态
- 新增 getAuditLogFull（不降级版，React Query 用 enabled+isError 判"未审核"）：直接 await get<...>('/audit-log', { target_type, target_id })
- 失败 → 抛错（不返回 null），上层用 error 处理展示"未审核"

【硬约束】
1. 仅改 web/src/ 下 2 文件（api/audit.ts + pages/RuleChangesPage.tsx），**后端零改动**
2. 复用 antd 现有 Popover/Descriptions/Tooltip，不引新依赖
3. hover 弹层 width=520，长内容 scroll auto max-height=480，不破布局
4. 不动 RuleChangesPage 其它列、表格列宽、查询逻辑
5. 不写"加载中" spinner（staleTime 30s 内静默），用占位"未审核"
6. 总改动 ≤ 80 行（前端 60 + api 10 + 测试 10）
7. 测试 ≤ 1 个：snapshot 测 hover 内容结构
8. 报告 ≤ 10 行

【commit】
git add web/src/api/audit.ts web/src/pages/RuleChangesPage.tsx web/src/components/audit/RuleAuditPopover.tsx 2>/dev/null
git add web/src/api/audit.ts web/src/pages/RuleChangesPage.tsx
git commit -m "feat(audit-web): 通用审核Agent批1D——hover展示原内容+完整审核意见（无审核时显占位）"

【sir 上线后必做】
- 重启前端：cd web && npm run dev（5173）；如已运行 vite 已热更新
- 跑 audit_pending：curl -X POST http://localhost:8000/api/task/submit -H 'Content-Type: application/json' -d '{"kind":"audit_pending","params":{"cutoff_id":0,"limit":5}}' 先跑 5 条看效果
- 刷新 RuleChangesPage hover 验证：
  - 无审核记录 → 显"未审核"占位
  - 有审核记录 → 块 1 原内容 + 块 2 完整审核意见（dissent/support/boundary/evidence/reasoning 全部可见）
- 满意后再跑剩下 15 条：curl 同上但 limit=20

【附：参考 path:line 速查】
| 内容 | 位置 |
|---|---|
| /audit-log 端点 | backend/app/api/routes.py:994-1000 |
| get_latest_audit_log_by_target | backend/app/db/repo.py:2060-2075 |
| RuleChangesPage 当前 hover | web/src/pages/RuleChangesPage.tsx:80-92 |
| getAuditLog 当前实现 | web/src/api/audit.ts:39-51 |
| 现有 60s useQuery 模式 | web/src/components/layout/TopStatusBar.tsx:111-154 |
| antd Popover / Descriptions | antd 已装，import { Popover, Descriptions } from 'antd' |
