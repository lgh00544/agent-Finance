# ReviewsPage 详情抽屉加驳回 + AI 自动决策可见链路

## 目标

`D:\self\web\src\pages\ReviewsPage.tsx` 单文件改两件事：① 详情抽屉里"采纳"旁加"驳回"按钮；② 顶部 review 列表显示 AI 自动决策状态，支持点击查看/提意见/回滚。

## 改动点

| 位置 | 改动 | 备注 |
|---|---|---|
| L40-47 adopt 函数 | 平行加 reject 函数，调用 rejectSuggestion(r.id, '人工驳回') + 错误提示 | rejectSuggestion API 已存在 |
| L66 按钮 | 在「采纳建议并更新偏好档案」旁加「驳回」按钮（type="default" danger），点击调 reject | 共享 SUG_STATUS 标签映射 |
| L68 已有状态 | 加 `r.suggest_status === 'rejected' ? <Text type="secondary">已驳回</Text> : null` | 与已采纳文案并列 |
| L284 策略闭环 Table | 不动（已经有驳回按钮 L299） | 仅补详情抽屉 |

## AI 自动决策可见链路（新增）

| 改动点 | 内容 |
|---|---|
| reviews list 顶部 | 在「选中行详情」上方加一行 AI 自动决策 banner：显示"近 N 条 AI 自动执行 · 通过 X · 驳回 Y · 待审 Z" |
| 点击 banner | 展开 Drawer 列出所有 AI 自动决策记录（plan 自动通过 / 监控自动调仓 / 经验自动归档），每条带：时间 / 模块 / 操作 / 状态 |
| 每条记录操作 | 「查看详情」「提意见」「回滚」三按钮；前两个跳对应抽屉，最后一个调新加的 `rollbackAutoDecision` API |

> 注：如 `rollbackAutoDecision` API 不存在，本轮**只做可见性 + 提意见入口**，回滚按钮显示为 disabled + Tooltip「回滚功能开发中」。**红线约束：不引新接口、不动后端**。

## 红线

1. 不动后端 / API 层（rejectSuggestion 已存在，rollbackAutoDecision 不存在则禁用）
2. 不引入新依赖
3. 列表 / 表格 / ECharts 等其它组件不动
4. 不改后端 reject 接口参数（reason 传 '人工驳回' 字符串）
5. 驳回与采纳并列，不允许删掉采纳按钮
6. 不弹 toast / modal（除 modal.confirm 二次确认外）
7. AI 自动决策 banner：reviews 数据为空时不显示
8. 不改 api/suggestions.ts（rejectSuggestion 已导出）

## 验收清单

- [ ] tsc --noEmit 0 error
- [ ] oxlint src/pages/ReviewsPage.tsx 0 error
- [ ] 详情抽屉「采纳」旁出现「驳回」按钮
- [ ] 点驳回 → modal 二次确认 → 调 rejectSuggestion → 状态变「已驳回」
- [ ] reviews list 顶部出现 AI 自动决策 banner（含数量统计）
- [ ] banner 展开 Drawer 列出自动决策记录（时间/模块/操作/状态）
- [ ] 「查看详情」「提意见」「回滚」三按钮可见，回滚 disabled + Tooltip「开发中」
- [ ] 已有功能（采纳、策略闭环 Table、ECharts 组合归因）零回归
