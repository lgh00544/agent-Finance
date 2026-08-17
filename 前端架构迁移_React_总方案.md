# 前端架构迁移总方案：Streamlit → React SPA

> 决策人：sir　|　2026-08-17　|　执行：Claude Code
> 结论：全量迁移 React，Streamlit 并行运行期间逐步退役。

---

## 〇、决策背景

Streamlit 的脚本重跑模型（每次交互全页 rerun + 状态清零）与交易系统的状态化交互需求根本冲突：
点任何按钮 → 全页黑屏重载 → 表单/滚动/展开状态全部丢失 → 高频操作不可用。

React SPA 从模型上消除此问题：组件级更新、状态常驻、无全页刷新。

---

## 一、技术栈选型

| 层 | 选型 | 理由 |
|---|---|---|
| 构建 | Vite 5 | 秒级 HMR，Claude Code 熟悉 |
| 框架 | React 18 + TypeScript | 生态最大，类型安全 |
| UI 库 | Ant Design 5（暗色主题） | 数据密集型企业后台标准件：表格/表单/布局全内置，中文生态 |
| 服务端状态 | TanStack Query v5 | 缓存/自动刷新/mutation/loading 全托管，替代手写轮询 |
| 客户端状态 | Zustand | 轻量，选中项/展开态/表单临时态 |
| 路由 | React Router v6 | 标准 |
| 图表 | ECharts（echarts-for-react） | 金融图表，中文生态 |
| HTTP | Axios | 与现有 api_client.py 风格一致 |

**不引入**：Next.js（本地系统不需要 SSR）、Redux（Zustand 够）、Tailwind（AntD 自带设计系统）。

---

## 二、项目结构

```
D:\self\
├── backend\          # FastAPI（零改动）
├── streamlit\        # Streamlit（并行运行，逐页退役）
└── web\              # ★ 新建 React 工程
    ├── src\
    │   ├── api\      # TS 版 api_client（60+ 接口）
    │   ├── components\  # 共享组件
    │   │   ├── layout\     # AppShell / Sidebar / TopStatusBar
    │   │   └── common\     # StatCard / StatusBadge / EmptyState / ErrorCard / ConfidenceBar / StockLabel
    │   ├── pages\    # 12 个页面（对齐现有导航）
    │   ├── stores\   # Zustand
    │   ├── hooks\    # 通用 hooks（usePolling 等）
    │   ├── types\    # TS 类型（对齐后端 schema）
    │   └── utils\
    ├── vite.config.ts   # proxy /api → localhost:8000
    └── package.json
```

**开发期端口**：React 5173（Vite dev）→ proxy → FastAPI 8000。Streamlit 8501 继续可用。
**生产期**：`npm run build` → FastAPI 挂载 `web/dist` 为静态根路径。

---

## 三、导航映射（12 页）

| 分组 | 页面 | 迁移优先级 | 批次 |
|---|---|---|---|
| 持仓风控 | **4 持仓监控**（操作最密集，Streamlit 最痛点） | P0 | Phase 2 |
| 选股决策 | **1 每日候选池**（详情展开+操作前置） | P0 | Phase 2 |
| 选股决策 | **3 建仓计划**（表单向导） | P0 | Phase 2 |
| 选股决策 | **2 评分报告**（详情 Tab） | P1 | Phase 2 |
| 系统概览 | 0 系统概览（看板聚合） | P1 | Phase 3 |
| 系统概览 | 12 市场研判 | P1 | Phase 3 |
| 持仓风控 | 8 告警日志 | P2 | Phase 3 |
| 策略沉淀 | 6 交易复盘（黑盒规范保留） | P2 | Phase 4 |
| 策略沉淀 | 5 游资追踪 | P2 | Phase 4 |
| 策略沉淀 | 10 Agent 对话（看板/线性双视图） | P2 | Phase 4 |
| 策略沉淀 | 9 交易知识库 / 11 规则变更记录 | P3 | Phase 4 |
| 新增 | 13 经验沉淀（新功能直接 React 开发，不走 Streamlit） | P1 | Phase 5 |

注：7 个人交易偏好未在导航注册（已废弃或隐藏），迁移时确认后跳过。

---

## 四、迁移阶段

| 阶段 | 内容 | 交付物 |
|---|---|---|
| **Phase 1** | 工程搭建 + 暗色主题 + AppShell（侧边栏/顶部状态栏）+ TS 版 API 客户端 + 共享组件 | `web/` 可启动，导航可点（页面为占位） |
| **Phase 2** | 核心操作页 ×4（持仓监控/候选池/建仓计划/评分报告） | 高频操作全部可在 React 完成 |
| **Phase 3** | 看板页 ×3（系统概览/市场研判/告警日志） | 日常查看切到 React |
| **Phase 4** | 策略页 ×5（复盘/游资/Agent对话/知识库/规则变更） | 全部页面 React 化 |
| **Phase 5** | 经验沉淀（新功能直接 React）+ 构建产物挂载 + Streamlit 退役 | 单一入口 |

每阶段结束 sir 人工验收后再进下一阶段；期间 Streamlit 全程可用，随时可回退。

---

## 五、API 接口面（迁移零变动清单）

后端 **零改动**（CORS 已开）。前端需在 TS 中封装以下接口（源：streamlit/api_client.py）：

- 系统：/api/health　/api/system/status　/api/dashboard　/api/jobs/status　/api/llm/stats　/api/datasource/stats
- 任务：/api/tasks/submit　/api/tasks/recent　/api/tasks/{id}　/api/tasks/{id}/retry
- 行情：/api/market/indices　/api/market/indices/history　/api/market/hot-sectors　/api/market-condition
- 研判：/api/market_intel　/api/market_intel/dates
- 账户：/api/account/summary　/api/account/baseline
- 候选：/api/candidates　/api/candidates/dates　/api/candidates/tradeable　/api/candidate/concentration
- 留痕：/api/traces　/api/traces/{id}
- 评分：/api/scores　/api/score/{code}
- 建仓：/api/positions　/api/positions/plan
- 持仓：/api/holdings　/api/holdings/quotes　POST /api/holdings　/api/holdings/{id}/exit|add|cost|trades|monitor|sell-decision|sell-decisions　/api/holdings/take-profit-plan
- OCR：/api/ocr/status　/api/ocr/holding（multipart）
- 建议：/api/agent-suggestions　{id}/approve|adopt|reject
- 规则：/api/rule-changes　{id}/rollback
- 验证：/api/track/verify/list|dates|stats|run|suggest
- 告警：/api/alerts
- 复盘：/api/reviews　{id}/adopt|reject
- 偏好：/api/profile（GET/PUT/export/import）
- 游资：/api/hot-money/profiles|flows|traces|win-rate-iteration|tier/apply
- 对话：/api/agent-chat/agents|history|ask|rules|learn|learn/confirm|batch-ask|batch-adjust/apply|batch-adjust/{id}/rollback
- 知识：/api/knowledge（GET/POST/batch-import/{id}/delete）

---

## 六、交互红线（迁移过程全程有效）

1. **功能零丢失**：现有 12 页每个按钮/表单/入口在 React 中全部可达，行为一致。
2. **实时性不降级**：顶部状态栏轮询、行情刷新频率 ≥ 现状（React Query refetchInterval）。
3. **审核闸门不弱化**：高影响两步确认、回滚二次确认、驳回必填理由等交互原样复刻。
4. **黑盒规范保留**：交易复盘页只暴露结果与建议，算法细节收深层折叠。
5. **并行期可回退**：任何阶段 Streamlit 保持可用，直到 Phase 5 验收后才退役。
6. 后端 / 数据库 / Agent 链路零改动。

---

## 七、Claude Code 执行提示词索引

- Phase 1（工程搭建）：见会话提示词，或本文件附录 A
- Phase 2-5：每阶段开始时由 sir 索取，基于上一阶段交付物定制

*方案定稿后即启动 Phase 1。*
