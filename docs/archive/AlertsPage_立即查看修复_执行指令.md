# AlertsPage 「立即查看」修复

## 目标

`D:\self\web\src\pages\AlertsPage.tsx` 单文件改：「立即查看」点击后在该卡片下展开当前告警的详情（消息/动作/信号/推送/时间），而不是跳到完整日志 Table。

## 改动点

| 位置 | 改动 | 备注 |
|---|---|---|
| L32 useState 区 | 新增 `const [openId, setOpenId] = useState<number \| null>(null)` | 记录当前展开的告警 id |
| L88 按钮 onClick | 改 `onClick={() => setOpenId(openId === a.id ? null : a.id)}` | 切换展开/折叠 |
| L79-91 卡片网格 | 在每个告警卡下方新增条件渲染的详情面板（grid 列内 sub-grid） | 仅在 openId === a.id 时渲染 |

## 详情面板展示字段（AlertInfo 已有）

| 字段 | 展示 |
|---|---|
| message | 完整文本（不再省略） |
| action | 有则展示 |
| signal | JSON.stringify 展示（缩进 2） |
| pushed | ✓ 已推送 / — 未推送 |
| source | 来源（监控/手工） |
| created_at | 完整时间（不截断） |

## 红线

1. 不动后端 / API 层 / 类型定义
2. 不引入新依赖（不用 Drawer / Modal，用普通 div 展开即可）
3. 不破坏第三段「完整告警日志」Card 与 logOpen state
4. 资金告警关键字过滤逻辑保持不变
5. 0 条资金告警时整段不渲染（不变）
6. 详情面板只在「资金告警」卡片内展开，不影响中部任务状态、底部完整日志
7. 默认折叠（点开后才展开详情），不要默认全展开
8. 不弹 toast / modal

## 验收清单

- [ ] tsc --noEmit 0 error
- [ ] oxlint src/pages/AlertsPage.tsx 0 error
- [ ] 点「立即查看」按钮，该卡片下方出现详情面板（消息/动作/信号/推送/来源/完整时间 6 项）
- [ ] 再次点同一按钮，详情面板折叠
- [ ] 多个资金告警卡之间互不影响（点 A 展开不影响 B）
- [ ] 详情面板不遮挡「🟡 后台任务状态」和「🟢 完整告警日志」布局
