# 前端 React 迁移：工程师审核任务书 + 更新版 Phase 1（含 git 回滚策略）

> 本文档两部分：
> - 第一部分：给工程师 Agent 的**审核提示词**（可直接复制，先跑这个）
> - 第二部分：**更新版 Phase 1 提示词**（新增 git 分支策略，供工程师一并审核；审核通过后才执行）

---

## 第一部分：工程师审核提示词（现在就复制这段）

```
你是本项目（A 股智能托管系统，D:\self，Streamlit 前端 + FastAPI 后端）的资深全栈工程师，
现在角色是「技术审核人」。有一项重大架构变更即将执行：前端从 Streamlit 全量迁移到 React SPA。
执行前需要你做一次完整的技术审核，输出 GO / NO-GO 结论。

【审核对象（先通读全部三份材料）】
1. D:\self\前端架构迁移_React_总方案.md —— 迁移总方案（技术栈/结构/5 阶段计划/API 接口面/交互红线）
2. D:\self\前端架构迁移_React_审核任务书.md 第二部分 —— 更新版 Phase 1 提示词（本次待执行的第一个阶段，含 git 分支策略）
3. 实际代码对照（审核必须基于真实代码，不能只看文档）：
   - D:\self\streamlit\api_client.py（API 接口源清单，60+ 函数）
   - D:\self\streamlit\app.py（导航结构）
   - D:\self\backend\app\main.py（CORS 与静态资源挂载）
   - git 仓库状态：当前在 main 分支，存在一批未提交改动（批次1-3 前端优化 + 后端若干文件）

【审核清单（逐项给出 结论/风险/修改建议）】

A. API 完整性与正确性（最重要）
- 总方案中的 API 接口清单是否与 api_client.py 实际函数一一对应？有无遗漏/多余/路径偏差？
- 逐个抽查至少 10 个接口：HTTP 方法、路径、参数名、返回字段与后端 routes.py 是否一致？
- 有无需要鉴权/长超时/分页/SSE/WebSocket 的特殊接口？Phase 1 的 axios 封装是否覆盖这些场景？

B. git 分支与回滚策略（本次新增，重点审）
- 策略：执行者在动手前必须：
  1) 先把 main 上当前未提交的批次1-3 改动提交（分主题 commit，不许混提交）；
  2) 从 main 切出 feat/web-react 分支，全部 React 工作只在该分支进行；
  3) 每个 Phase 完成并验收通过后打 tag（web-phase1 ~ web-phase5）+ 合回 main；
  4) 回滚 = git checkout main 或回退到对应 tag，Streamlit 全程在 main 可用。
- 审查点：该策略是否有漏洞？未提交改动先提交是否合理（会不会把不该提交的东西提交进去，需要先看 git status 全量判断）？
  tag 命名是否会与现有 tag 冲突（先 git tag -l 确认）？并行期 Streamlit 与 React 双前端并存是否有运维风险（端口/启动脚本/文档）？

C. 技术栈选型
- Vite5 + React18 + TS + AntD5 + TanStack Query + Zustand + ECharts：对单人 + Claude Code 维护的现实约束是否过重？
  有无更简的等价替代（如去掉 Zustand 只用 React Query + Context）？给出保留/精简建议。
- npm 作为唯一包管理器在 Windows 环境的可行性。

D. 并行运行与切换安全
- Vite dev 代理 '/api' → 8000 与生产构建（相对路径/base 配置、静态托管方式）是否在方案中说清楚了？
  生产环境 React 构建产物由谁托管（FastAPI 静态挂载？独立静态服务器？）——方案没写清就指出来。
- 迁移期数据一致性：两个前端同时操作同一后端（如同时改持仓）是否有并发风险？

E. 硬红线与验收标准
- 红线清单（后端零改动、涨红跌绿、Streamlit 不动、API 一一对应）是否完备、可验证？
- Phase 1 验收自查清单是否有漏项（如：TypeScript 编译、构建产物体积、Node 版本要求）？

F. 工作量与顺序
- 5 阶段划分是否合理？Phase 1 范围（工程搭建+外壳+60+ 接口 TS 化）是否过大需要拆分？
- 经验沉淀模块推迟到 Phase 5 直接 React 开发的决策是否可行（后端 A-E 是否被阻塞）？

【输出格式】
1. 总体结论：GO / NO-GO / GO WITH CHANGES（附一句话理由）
2. 分项审核表：A-F 每项 → 结论 / 发现的问题（引用具体文件与行号）/ 修改建议
3. 必须修改项清单（执行前必须改的，标注 P0/P1）
4. 可选优化项清单（不阻塞执行）
5. 对第二部分 Phase 1 提示词的修订版：如审核发现 P0 问题，直接给出修订后的提示词全文；无 P0 则原样确认。

【硬约束】
- 你只审核、不执行：不创建/修改任何文件，不动 git。
- 所有结论必须基于实际代码核对，禁止只凭文档下结论。
- 发现与文档描述不符的代码事实，逐条列出（文档 vs 实际）。
```

---

## 第二部分：更新版 Phase 1 提示词（含 git 分支策略，审核通过后执行）

```
你是资深 React 前端工程师，负责为本项目（A 股智能托管系统）搭建全新的 React SPA 前端，
替代现有 Streamlit（并行运行期两者共存）。本阶段只做工程搭建 + 应用外壳 + API 客户端，
页面用占位组件。

【第零步：git 分支与回滚保障（最先执行，失败即停）】
1. 检查 git 状态（git status / git branch --show-current / git tag -l）。
2. 当前 main 分支上存在未提交的批次1-3 改动：按主题分 commit 提交干净
  （前端批次优化、后端改动、文档各一个 commit；不许一个 commit 混装；.bak_* 备份文件
   与临时文件不提交，加进 .gitignore）。
3. 从 main 切出并切换到新分支 feat/web-react：此后全部 React 工作只在该分支进行，
   绝不切换回 main 改东西。
4. 本阶段完成且验收通过后：git tag web-phase1，并合回 main（merge --no-ff 保留分支轨迹）。
5. 回滚约定：任何阶段出问题，git checkout main 即回到纯 Streamlit 状态；
   阶段内回退用 git reset 到本阶段起点 commit。把该约定写进交付报告。

【背景与总方案】
先通读 D:\self\前端架构迁移_React_总方案.md——这是本迁移的完整方案（技术栈选型、项目结构、
导航映射、API 接口面、交互红线）。严格按它执行；如与实际代码冲突，以实际代码为准并在报告中标注。

【第一步：自主探索，动手前必须完成】
1. 通读 D:\self\streamlit\api_client.py——全部 60+ 个 API 封装函数，这是 TS 版 API 客户端的
   完整源清单，逐个转写，一个不能漏。
2. 通读 D:\self\streamlit\app.py——st.navigation 的 4 组 12 页导航结构，React 侧边栏按此复刻。
3. 通读 D:\self\streamlit\render.py 的 _GLOBAL_THEME_CSS（文件前部）——现有暗色主题的 CSS 变量
   （--bg/--text/--up/--down/--warn 等）与整体视觉风格，React 主题要延续这套视觉。
4. 抽看 D:\self\streamlit\pages\0_系统概览.py 顶部 30 行——看 top_status_bar 的信息结构
   （指数行情/系统状态/时间），React 顶部状态栏按此复刻。
5. 确认 D:\self\backend\app\main.py 已开 CORS（allow_origins=["*"]），无需后端改动。

【第二步：工程初始化】
1. 在 D:\self\web\ 创建 Vite 5 + React 18 + TypeScript 工程
  （npm create vite@latest web -- --template react-ts）。统一 npm，不用 pnpm/yarn。
2. 安装依赖：antd @ant-design/icons @tanstack/react-query zustand axios react-router-dom
   dayjs echarts echarts-for-react
3. vite.config.ts 配置 dev 代理：'/api' → 'http://localhost:8000'（changeOrigin: true）。
4. tsconfig.json 开启严格模式与路径别名 "@/*" → "src/*"。

【第三步：暗色主题与全局样式】
1. main.tsx 用 ConfigProvider + theme.darkAlgorithm 包裹 App；中文 locale（zh_CN）。
2. src/index.css 定义 CSS 变量，对齐 Streamlit 版视觉：深色背景（#0f1117 级）、
   涨红跌绿（中国股市惯例：--up 红 / --down 绿）、琥珀警示色。全局字体、滚动条样式暗色化。
3. token 定制（ConfigProvider theme.token）：colorPrimary 延续现系统主色、borderRadius 适中、
   字号基准 14px。

【第四步：应用外壳 AppShell】
1. src/components/layout/AppShell.tsx：左侧固定侧边栏（可折叠）+ 顶部状态栏 + 主内容区（Outlet）。
2. 侧边栏：AntD Menu，4 个分组 12 项，完全对齐 Streamlit 导航：
   系统概览组：系统概览(/)、市场研判(/market-intel)
   选股决策组：每日候选池(/candidates)、评分报告(/scores)、建仓计划(/plans)
   持仓风控组：持仓监控(/holdings)、游资追踪(/hot-money)、告警日志(/alerts)
   策略沉淀组：交易复盘(/reviews)、交易知识库(/knowledge)、Agent对话(/agent-chat)、
   规则变更记录(/rule-changes)
   每项带图标（AntD Icons 语义对应）+ 中文名；当前路由高亮；折叠态只显示图标。
3. 顶部状态栏（TopStatusBar.tsx）：
   左侧：三大指数（上证/深证/创业板，名称+点位+涨跌幅，涨红跌绿）——React Query 调
   GET /api/market/indices，refetchInterval 30s；
   右侧：系统状态点（GET /api/health，绿=正常/红=异常）+ 北京时间（每秒更新）。
   接口失败时优雅降级（显示"—"），绝不白屏。
4. 路由配置：React Router v6，12 条路由全部注册，页面组件统一为占位组件 PagePlaceholder
  （显示页面名 + "Phase 2/3/4 实装"），确保导航点击即可切换且 URL 正确。

【第五步：TypeScript API 客户端】
1. src/api/client.ts：Axios 实例，baseURL '/api'（走 Vite 代理），超时 60s（POST 任务类 600s），
   响应拦截器统一错误处理（网络错误 → 抛出带中文提示的 Error，供 React Query onError 展示）。
2. src/api/ 目录按域分文件转写 api_client.py 的全部函数（一个不漏），每个函数配 TS 类型：
   - system.ts：health/systemStatus/dashboard/jobStatus/llmStats/datasourceStats
   - tasks.ts：submitTask/recentTasks/taskDetail/retryTask
   - market.ts：marketIndices/indexHistory/hotSectors/marketCondition/marketIntel/marketIntelDates
   - account.ts：accountSummary/saveAccountBaseline
   - candidates.ts：candidates/candidateDates/candidateTradeable/candidateConcentration/stockNames
   - traces.ts：traces/traceDetail
   - scores.ts：scores/triggerScore
   - positions.ts：plans/createPlan
   - holdings.ts：holdings/holdingQuotes/addHolding/exitHolding/holdingAdd/holdingCost/
     holdingTrades/monitorHolding/sellDecision/sellDecisions/takeProfitPlan
   - ocr.ts：ocrStatus/ocrHolding（multipart 上传）
   - suggestions.ts：agentSuggestions/approveSuggestion/adoptSuggestion/rejectSuggestion/
     ruleChanges/rollbackRuleChange
   - track.ts：trackVerifyList/Dates/Stats/Run/Suggest
   - alerts.ts、reviews.ts、profile.ts、hotMoney.ts、chat.ts（agent-chat 全部 8 个）、knowledge.ts
3. src/types/ 定义核心数据类型（Holding/Candidate/Score/Plan/Trace/Review/Task/AgentSuggestion 等），
   字段对齐后端返回（参考 api_client.py 各函数 docstring 与 Streamlit 页面取用字段）。

【第六步：React Query 全局配置】
main.tsx 或 App.tsx：QueryClientProvider，默认 staleTime 30s、retry 1、refetchOnWindowFocus false。

【第七步：共享基础组件】
src/components/common/ 下实现（本阶段先做静态展示层，Phase 2 起使用）：
- StatCard：指标卡（标题+数值+副文，支持涨跌色）
- StatusBadge：状态标签（pending 灰/processing 蓝/done 绿/active 绿/rolled_back 灰 等映射）
- EmptyState：空态（图标+说明+可选操作）
- ErrorCard：错误卡（标题+详情+重试按钮，接收 React Query 的 error）
- ConfidenceBar：置信度进度条（≥0.85 绿/0.5-0.85 琥珀/<0.5 灰）
- StockLabel：股票标识（代码+名称，名称缺失显示"名称待补"）

【硬红线】
- 第零步 git 流程必须先走完，再动任何代码；全程只在 feat/web-react 分支提交。
- 只在 D:\self\web\ 新建代码文件；绝不改动 backend/、streamlit/、任何现有文件
  （.gitignore 追加除外）。
- 后端零改动；不引入方案外的依赖（不加 Tailwind/Redux/Next）。
- 所有 API 函数必须与 api_client.py 一一对应，路径、参数、方法零偏差。
- 涨红跌绿（中国股市惯例）贯穿所有颜色逻辑。
- npm 安装失败时报告，不要换包管理器。
- TypeScript strict 模式无 any 滥用（API 响应类型允许渐进完善，先 unknown/接口占位）。

【验收自查】
1. git log 展示：main 已清理干净 + feat/web-react 分支上本阶段 commit 记录。
2. cd D:\self\web && npm run dev —— http://localhost:5173 打开无报错。
3. 后端启动（uvicorn）时：顶部状态栏显示真实指数行情与系统状态（走代理无 CORS 报错）；
   后端关闭时优雅降级。
4. 侧边栏 4 组 12 项可点击切换，URL 正确变化，刷新后路由保持（含直接访问子路由）。
5. 侧边栏折叠/展开正常。
6. npm run build 成功，无 TS 类型错误（警告可容忍）。
7. src/api/ 函数清单与 api_client.py 逐一对数（在报告中列对照表）。
8. 输出交付报告：目录结构树、依赖清单、API 函数对照表（Python→TS）、与总方案的偏差项、
   git 分支与回滚说明、Phase 2 实装建议。
```

---

## 执行节奏

1. **现在**：把第一部分审核提示词贴给工程师 Agent 审核（只审不改）。
2. 工程师返回 GO（或修订版提示词）后：用**第二部分**（或工程师修订版）给执行 Agent 跑 Phase 1。
3. 之后每阶段：执行 → 验收 → 打 tag → 合 main。
