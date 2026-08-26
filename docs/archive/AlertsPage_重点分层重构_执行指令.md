# AlertsPage 重点分层重构

## 目标

`D:\self\web\src\pages\AlertsPage.tsx` 单文件改：把"sir 第一眼关心的"三类信息分层置顶，告别揉成一团表格。

## 改动点

| 位置 | 改动 | 备注 |
|---|---|---|
| L4-6 import | 新增 `import { useTaskSubmit, tasksStore } from '@/store/tasksStore'`（按项目已有写法）+ `import { useQuery }` 已有 | 用于读任务列表 |
| 现有 alerts useQuery 保留 | 不动 | 完整告警数据源 |
| 新增 useQuery | `useTasks` / `useLatestTaskByModule` 等已有 hooks 取后台任务进度 | 仅复用、不新写 |
| return 内重排 | 顶部 → 中部 → 底部三段式 | 见下表 |

## 三段式布局

| 段 | 内容 | 数据源 | 视觉 |
|---|---|---|---|
| **🔴 资金告警**（置顶，最高优先级） | 过滤 `severity==='critical' && message/action 含 钱/止损/止盈/减仓/跌停/涨停/盈利 关键字` 的告警，截前 5 条 | alerts useQuery | 红色边框 Card，每条卡片化显示：股票 + 严重 Tag + 消息 + 时间 + "立即查看"按钮 |
| **🟡 后台任务状态** | 取 tasksStore 中 running/failed 的任务（agent 名 / 进度条 / 状态 / 耗时 / 失败原因） | tasksStore（已有） | 黄色边框 Card，失败红色高亮；空态"暂无运行中任务" |
| **🟢 完整告警日志** | 原 Table（含筛选 + 分页），可折叠 | alerts useQuery | 默认折叠，需点 "展开完整日志"按钮 |

## 红线

1. 不动后端 / API 层 / 类型定义
2. 不引入新依赖（用 antd Card / Tag / Progress / Collapse）
3. alerts useQuery 保留原行为，不删
4. 资金告警的关键字过滤只在前端做（client-side filter），**不动后端**
5. tasksStore 已有数据就复用，**不新建接口**
6. 资金告警卡片 0 条时整段不渲染（不显示空卡）
7. 任务状态卡片 0 任务时显示"暂无运行中任务"占位
8. 完整日志折叠默认状态 = collapsed
9. 不弹 toast / modal（除非点击"立即查看"跳转）
10. 不动 SideMenu / AppShell

## 验收清单

- [ ] tsc --noEmit 0 error
- [ ] oxlint src/pages/AlertsPage.tsx 0 error
- [ ] 页面顶部出现红色"资金告警"卡，含止损/止盈/跌停等关键字的告警置顶
- [ ] 中部出现黄色"后台任务状态"卡，running 任务显示进度条 + 耗时，failed 任务红色高亮
- [ ] 底部"完整告警日志"默认折叠，点击展开看到原 Table
- [ ] 三段颜色清晰不混（红/黄/默认）
- [ ] 移动端窄屏仍可读（grid auto-fill 适配）
- [ ] 资金告警 0 条 / 任务 0 条 时不显示空白卡
