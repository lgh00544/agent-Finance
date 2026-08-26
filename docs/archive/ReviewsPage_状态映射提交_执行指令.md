# ReviewsPage 状态映射修复单独提交

## 目标

把 `web/src/pages/ReviewsPage.tsx` 的 SUG_STATUS 补 adopted 改动打包成单条 commit 推送。

## 执行命令

```bash
cd /d/self
git add web/src/pages/ReviewsPage.tsx
git commit -m "fix(reviews): 建议状态映射补 adopted 标签 — 与 approved 同色，避免英文 fallback"
git push
```

## 红线

1. 仅含 web/src/pages/ReviewsPage.tsx 一个文件
2. 不混入其它改动
3. commit message 简洁说明

## 验收清单

- [ ] commit 单文件，仅 ReviewsPage.tsx
- [ ] git push 成功
- [ ] 远程 HEAD 与本地一致
