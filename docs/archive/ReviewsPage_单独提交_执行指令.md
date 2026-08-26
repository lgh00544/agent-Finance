# ReviewsPage 单独提交

## 目标

把 `web/src/pages/ReviewsPage.tsx` 的工作区改动打成单条 commit 推送。

## 执行命令

```bash
cd /d/self
git add web/src/pages/ReviewsPage.tsx
git commit -m "feat(reviews): 详情抽屉加驳回 + AI 自动决策可见链路（banner + Drawer + 三按钮）"
git push
```

## 红线

1. 仅含 `web/src/pages/ReviewsPage.tsx` 一个文件
2. 不混入其它改动（候选池/Overview/Alerts/游资都已 HEAD）
3. 不删 untracked 方案 .md
4. commit message 简洁说明两件事：① 驳回按钮 ② AI 自动决策可见

## 验收清单

- [ ] commit 单文件，仅 ReviewsPage.tsx
- [ ] git push 成功
- [ ] 远程 HEAD 与本地一致
- [ ] 工作区剩 untracked 方案 .md（无需处理）
