# 工作区统一收尾提交

## 目标

把工作区待提交的改动打包成 2 条 commit 推送。

## 改动点

| # | 范围 | commit |
|---|---|---|
| 1 | `_tmp_*` / `_dbg_*` / `_verify_*` 共 8 个临时调试脚本删除 + `.workbuddy/memory/2026-08-24.md` | `chore(cleanup): 清掉临时调试脚本 + memory 日志同步` |
| 2 | `web/src/pages/AlertsPage.tsx` 三段式重构 | `feat(alerts): 重点分层 — 资金告警置顶 / 任务状态卡 / 完整日志折叠` |

## 执行命令

```bash
cd /d/self

# Commit 1: cleanup
git add _tmp_capital_view_verify.py _tmp_db_inspect.py _tmp_debug_cache.py \
        backend/tests/_dbg_force.py backend/tests/_dbg_force2.py \
        backend/tests/_verify_capital_fix.py backend/tests/_verify_capital_fix2.py \
        backend/tests/_verify_capital_fix3.py \
        .workbuddy/memory/2026-08-24.md
git commit -m "chore(cleanup): 清掉临时调试脚本 + memory 日志同步"

# Commit 2: alerts
git add web/src/pages/AlertsPage.tsx
git commit -m "feat(alerts): 重点分层 — 资金告警置顶 / 任务状态卡 / 完整日志折叠"

git push
```

## 红线

1. **不删任何业务代码**：只删 `_tmp_*` / `_dbg_*` / `_verify_*` 前缀的临时脚本
2. **不动 backend/app/** 下任何业务模块
3. **不动 frontend/、streamlit/** 下文件
4. **不动 types/index.ts、api/** 下文件
5. **不动 CandidatesPage.tsx**（批次 4 已在 HEAD commit 77e2be3，无改动）
6. **不合并两条 commit**（按 feature/cleanup 分开）

## 验收清单

- [ ] commit 1 成功，文件清单：8 个 _tmp/_dbg/_verify 删除 + memory 日志
- [ ] commit 2 成功，仅含 web/src/pages/AlertsPage.tsx
- [ ] git push 成功，远程 HEAD 与本地一致
- [ ] git status 工作区只剩 untracked 方案 .md（不需要提交）
- [ ] 业务代码（backend/app/、web/src/、frontend/、streamlit/）零改动
