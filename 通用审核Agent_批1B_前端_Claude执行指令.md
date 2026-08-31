# 通用审核 Agent — 批 1B（前端展示）· Claude Code 执行指令

> 0 元信息：sir 出题 / Claude Code 执行 / sir 验收
> 前置：批 1A 已提交 `f6b653f`（audit_log 表 + agent_suggestion 3 audit 字段 + audit_pending 批处理 + 03:30 cron）
> 本批只做 React 前端展示，后端零改动

## 一、目标
1. OverviewPage 加「AI 审核待审」统计卡（红/绿/灰三态数字），点击跳 RuleChangesPage
2. RuleChangesPage 列表行加「AI 审核」列（三态徽章，hover 显示 audit 摘要）
3. api/audit.ts 封装 3 个消费函数

## 二、架构约束
- 仅改 `web/src/`：新建 `api/audit.ts` + 改 `pages/OverviewPage.tsx` / `pages/RuleChangesPage.tsx`；复用 `components/common/StatusBadge.tsx` 已有三态（pending/ok/err），不引新色值/新库
- **后端零改动**：批 1A 未加 `/audit-log` GET 端点 → `getAuditLog` 定义为前向接线（404 诚实降级 null），页面 hover 用行内 `audit_verdict/audit_round`（`/agent-suggestions` 已返回）
- 复用 `TopStatusBar.tsx:111-154` useQuery 模式：`staleTime: 60_000, refetchInterval: 60_000`
- 数据源：`/agent-suggestions`（含 audit 三字段，客户端聚合三态统计）

## 三、规则
- `getAuditStats()` → GET `/agent-suggestions` → 客户端聚合 `{pending, pass, fail, total}`（audit_verdict 空/`pending`→pending）
- `getAuditPending()` → GET `/agent-suggestions` → 过滤 `audit_verdict∈{空, pending}`
- `getAuditLog(target_type, target_id)` → GET `/audit-log?target_type=..&target_id=..`（try/catch 返 null，诚实降级不崩）
- OverviewPage 卡：三态数字 `pending>0` 红 / `pending==0` 绿 / 无数据灰 `—`；点击 `navigate('/rule-changes')`
- RuleChangesPage 列：`source_suggestion_id` → join 客户端建议表 → `audit_verdict` 徽章（pending 待审/pass 已过/fail 驳回）；无关联建议 → `—`；hover 显 `label · 第{round}轮`（dissent 摘要待后端 /audit-log 端点，不伪造）
- 全部用 `StatusBadge`（tone: pending/ok/err）与现有 antd `Tooltip`

## 四、执行顺序
1. 新建 `web/src/api/audit.ts`（3 函数 + AuditStat 接口）
2. `OverviewPage.tsx`：import `useNavigate` + `getAuditStats`；useQuery（60s staleTime+refetchInterval）；顶部加点击卡片
3. `RuleChangesPage.tsx`：import `agentSuggestions` + `StatusBadge` + `Tooltip`；加建议 join 查询；Table 加「AI 审核」列
4. `tsc -b` + `npm run build` 零错

## 五、验证清单
- [ ] `tsc -b` EXIT=0，`npm run build` ✓（web 无 vitest/jest 基建，测试走 tsc+类型安全）
- [ ] git diff 仅 `web/src/`，后端零改动
- [ ] 总改动 ≤150 行
- [ ] OverviewPage 卡三态：pending>0 红可点 / pending==0 绿 / 无数据灰
- [ ] RuleChangesPage 列：无关联 `—`、有关联徽章三态、hover 显 round

## 六、红线
1. **后端零改动**——`/audit-log` 端点不在本批，`getAuditLog` 降级 null，禁止新增后端路由
2. 只动 `web/src/` 下 api/audit.ts + OverviewPage + RuleChangesPage；≤150 行；不引新库
3. **诚实原则**：dissent_view 无后端来源，hover 只显 verdict/round，绝不出假内容
4. React 优先、Streamlit 不动
5. 省 token：grep 定位不 read 全量；docstring ≤3 行；报告 ≤10 行
