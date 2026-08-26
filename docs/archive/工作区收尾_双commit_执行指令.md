# 工作区收尾（AlertsPage + 游资归一化）双 commit

## 目标

把工作区 6 个待提交文件拆成 **2 条独立 commit** 推送：① AlertsPage 单文件；② 游资归一化（后端 3 文件 + 测试 + memory）。

## 改动点

| Commit | 文件 | 类型 |
|---|---|---|
| 1 | `web/src/pages/AlertsPage.tsx` | feat(alerts) |
| 2 | `backend/app/db/repo.py` + `backend/app/services/hot_money_review.py` + `backend/app/scheduler/jobs.py` + `backend/tests/test_hot_money_signals_normalize.py` + `.workbuddy/memory/2026-08-25.md` | fix(hot-money): seat_name 归一化 |

## 执行命令

```bash
cd /d/self

# Commit 1: AlertsPage
git add web/src/pages/AlertsPage.tsx
git commit -m "feat(alerts): 重点分层 + 消息列结构化 — 资金告警置顶 / 任务状态卡 / 完整日志可折叠"

# Commit 2: 游资归一化 + memory
git add backend/app/db/repo.py \
        backend/app/services/hot_money_review.py \
        backend/app/scheduler/jobs.py \
        backend/tests/test_hot_money_signals_normalize.py \
        .workbuddy/memory/2026-08-25.md
git commit -m "fix(hot-money): seat_name 归一化 — repo.normalize_seat + collect_signals 适配 + scheduler cron 同步"

git push
```

## 红线

1. 两条 commit 严格分开（不混）
2. AlertsPage commit **只含 web/src/pages/AlertsPage.tsx 一个文件**
3. 游资归一化 commit **不含任何 frontend/web/src/Alert* 文件**
4. 不改任何其它文件
5. 不删 untracked 方案 .md（那些是历史方案，不入仓）

## 验收清单

- [ ] commit 1 单文件，仅 AlertsPage.tsx
- [ ] commit 2 含 5 个文件（3 后端 + 1 测试 + 1 memory），不含 AlertsPage.tsx
- [ ] git log 显示 2 条新 commit，message 与上面对应
- [ ] git push 成功
- [ ] 工作区剩 untracked 方案 .md（无需处理）
