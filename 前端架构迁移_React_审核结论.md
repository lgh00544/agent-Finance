# 前端 React 迁移方案 · 审核结论

> 审核人：WorkBuddy（SeniorDeveloper）｜ 日期：2026-08-17
> 审核对象：`D:\self\前端架构迁移_React_总方案.md` + `D:\self\前端架构迁移_React_审核任务书.md`
> 审核方式：全部结论基于实际代码核对（api_client.py 全量 AST 提取 / 后端 routes.py 全量 AST 提取 / git 实测 / 启动脚本实测），非文档推演

---

## 〇、总体结论：**GO WITH CHANGES**

迁移方向正确（Streamlit 脚本重跑模型确实是架构天花板，React SPA 是正解），技术栈主流不重、阶段划分合理、git 回滚思路正确。但有 **5 个 P0 必须修改**（其中 2 个是方案自相矛盾、2 个是 API 清单遗漏/错误、1 个是 git 策略漏洞）+ 若干 P1。改完即可执行。

---

## 一、分项审核表

### A. API 完整性与正确性 —— **发现 2 处遗漏 + 2 处描述错误**

**已核实的正面事实：**
- `streamlit/api_client.py` 实测 **83 个函数**（4 个内部 helper `_get/_post/_put` + 79 个对外接口函数）
- 后端 `routes.py` 实测 **85 条路由**，用 AST 全量提取后与 api_client 逐条对照：**api_client 封装的后端路由 0 遗漏、0 路径偏差** ✅
- 抽查 12 个接口（candidates / candidate_tradeable / track_verify_list / track_verify_stats / hot_money_flows / chat_history / agent_suggestions / rule_changes 等）参数名、默认值、过滤语义与后端一致 ✅
- **无鉴权 / 无 SSE / 无 WebSocket / 无 cursor 分页**（全部 limit 参数式），axios 基础封装可全覆盖 ✅
- **页面无绕过 api_client 的直接 requests 调用**（全项目 0 处）✅
- 4 个关键路由全部存在：`/jobs/discover/run`（routes.py:259）、`/candidate/concentration`（:452）、`/stocks/names`（:483）、`/holdings/take-profit-plan`（:1043）✅

**P0-A1 · 总方案 §五 接口清单漏 2 个函数：**
| 遗漏函数 | 实际路径 | 谁在用 |
|---|---|---|
| `run_discover` | POST /api/jobs/discover/run | 候选池/系统概览页"立即运行 Discover"按钮 |
| `stock_names` | GET /api/stocks/names | 候选池/评分报告等代码→名称映射 |

（Phase 1 提示词第五步 candidates.ts 里**有** stockNames，但 system.ts 漏了 run_discover——两个文档各漏一半，合并看仍漏 run_discover。）

**P0-A2 · Phase 1 提示词错误：**
- "chat.ts（agent-chat 全部 **8** 个）"→ 实际 **9 个**：agents / history / batch-ask / batch-adjust-apply / batch-adjust-rollback / ask / rules / learn / learn-confirm
- "超时 60s（POST 任务类 600s）"→ 实际是 **GET/PUT 60s、所有 POST 600s**（api_client.py:13/19/25），另 **ocr_holding 180s**（:233）、**chat_learn 60s**（:488）走独立 requests 超时——TS client.ts 需按此分层设置

**P0-A3 · 行为面陷阱（最容易"函数都转了但交互不对"的点）：**
页面**大量操作不走对应 API 函数，而是走 `submit_task` 任务队列**。实测 7 个 kind：
```
position ×5（建仓计划生成）  daily_pipeline ×3（每日流水线）
sell_decision ×2（卖出）      market_intel ×2（研判刷新）
score ×1                     portfolio_sentinel ×1
monitor_all ×1
```
例：`api_client.sell_decision()` 函数**无任何页面直接消费**（4_持仓监控.py:303/663 都是 `api.submit_task("sell_decision", {"holding_id": hid})`）——React 端若只按函数清单转写，会把卖出做成"直接 POST sell-decision"而不是"提交任务 + 轮询进度"，**交互行为就变了**。TS 端必须复刻：**提交任务 → 轮询 `/api/tasks/{id}` → 完成后刷新页面数据**这条链路，而不是裸调接口。
同理 `trigger_score / create_plan / run_discover` 需确认页面用法（系统概览/评分报告页点按钮走任务队列或直调并存，转写时以页面实际行为为准，见修订版提示词要求）。

**P0-A4 · multipart 上传两处：**
`ocr_holding`（:230，timeout 180s）与 `chat_learn`（:482，multipart + params + data 混用）都用 requests files=。Phase 1 只给 ocr 标了 multipart，**chat_learn 未标**，且其"params 带 agent + form data 带 description"的混用方式易在 axios 里写错。修订版已补。

### B. git 分支与回滚策略 —— **思路正确，但有 1 个 P0 漏洞 + 2 个 P1**

**已核实的正面事实：**
- 当前在 main 分支，`git tag -l` 为空 → **tag 命名 web-phase1~5 无冲突** ✅
- `.gitignore` 已覆盖 `.env`、`data/`、`*.db` ✅（敏感文件安全）
- 备份目录 `backup/` 已在 .gitignore ✅

**P0-B1 · "先把未提交改动提交干净" —— 这批改动疑似混有批次 4 代码，直接提交有污染风险：**
- 实测 `git status`：**64 个未提交文件**，其中 `backend/app/api/routes.py`、`db/repo.py`、`datasource/akshare_source.py`、`scheduler/jobs.py` 均为 M 状态，且存在 **5 个 `.bak.batch4` 备份文件**（routes.py.bak.batch4 / repo.py.bak.batch4 / akshare_source.py.bak.batch4 / jobs.py.bak.batch4 / 见 git status）
- 而 `/api/candidate/concentration` 路由**已存在于 routes.py:452**——这是**批次 4 的功能**（候选行业集中度），但项目记忆里批次 4 标注"审核优化版已交付、待 sir 执行"
- 结论：**main 上的未提交改动极可能已包含批次 4 的部分落地代码**（或批次 3 与 4 混合）。任务书说"把批次 1-3 改动提交"——如果照做，可能把**未验收的批次 4 代码混进 commit**。
- **必须修改**：第零步先执行 `git diff` 逐文件确认改动归属（哪些属于批次 2/3 已验证、哪些疑似批次 4 未验收），按批次+主题拆分 commit；**批次 4 代码若未验收，单独 commit 或暂不提交**，绝不允许与已验证改动混装。这比"分主题 commit"的要求更高一级。

**P0-B2 · 红线自相矛盾（后端零改动 vs Phase 5 挂载产物）：**
- 总方案 §六 红线 6："后端 / 数据库 / Agent 链路零改动"；但 §二 生产期写"`npm run build` → FastAPI 挂载 `web/dist` 为静态根路径"
- 实测 `backend/app/main.py`：**0 处 StaticFiles**，且允许改动与否未声明——Phase 5 必然要改 main.py（约 10 行）
- **必须修改**：红线 6 修订为——"**迁移期间（Phase 1-4）后端零改动；Phase 5 仅允许 main.py 增加静态挂载（含 SPA fallback），约 10 行，其余后端代码不动**"

**P1-B3 · `.workbuddy/memory/` 提交归属未定义：**
git status 显示 `2026-08-14.md` 已跟踪（M）、`2026-08-17.md`/`MEMORY.md` 未跟踪（??）。任务书说"前端/后端/文档各一个 commit"——memory 归哪类没说。建议：作为"文档"一并提交（含项目决策记录，利于后续 Claude Code 会话读取上下文），但需 sir 确认（MEMORY.md 若含敏感内容可不提交）。

**P1-B4 · 启动脚本已失效，威胁"Streamlit 全程并行可用"承诺：**
- 实测 `run_dev.bat` 第 18-19 行：`set PY=D:\space\self\self\.venv\Scripts\python.exe` —— **`D:\space\self\self` 不存在**（当前项目在 `D:\self\`），脚本一运行即报 `[ERROR] venv python not found` 退出
- `.venv` 实际在 `D:\self\.venv\Scripts\python.exe`，`backend/scripts/dev_run.py` 存在
- 不影响 React 迁移本身，但"Streamlit 全程可用"依赖可用的启动入口 → 列为 Phase 0 前置修复项（改两个路径变量即可）

**P1-B5 · .gitignore 需补临时文件规则：**
13 个 `.bak.batch*` + `.bak_*` + `_pytest_b4.log` 均为未跟踪状态。任务书已要求"加进 .gitignore"✅，落实为具体写法：追加 `*.bak*`、`*_b?.log`（注意不要误伤 `base_file/` 等正常目录）。

### C. 技术栈选型 —— **结论：合理，不重。Zustand 保留、收敛边界**

- 全栈 7 件套（Vite5/React18/TS/AntD5/TanStack Query/Zustand/ECharts）是数据密集型后台的标准配置，对单人 + AI 维护是**主流而非负担**；不引入 Next/Redux/Tailwind 的判断正确 ✅
- **Zustand 精简评估（实测数据）**：全项目 `st.session_state` 使用 **159 处**，分布 12 页（6_交易复盘 36、4_持仓监控 34、1_候选池 34、2_评分报告 19、10_Agent对话 17、0_系统概览 9……），且存在**跨页面联动需求**（候选池选中股票 → 评分报告/建仓计划共享选中上下文）。React Query 只解决服务端状态，客户端 UI 态（选中/展开/表单草稿）必须另有载体。
  - **建议：Zustand 保留，但收敛边界**——只建 2-3 个全局 store（AppShell 折叠态、全局选中股票、审核/两步确认弹窗态），页面内部状态一律 useState/useReducer。砍掉 Zustand 换 Context 会写出多层 Provider 嵌套，对 AI 维护反而更差。
- npm：实测 node 22.22.2 / npm 10.9.7 可用，Vite5 要求 Node ≥18 ✅

### D. 并行运行与切换安全 —— **发现 1 个 P1（生产托管确实没写清）**

**P1-D1 · 生产构建产物托管细节缺失（任务书自己点出的问题，坐实）：**
总方案只写"FastAPI 挂载 web/dist 为静态根路径"，缺 4 个关键细节：
1. **SPA fallback**：React Router 子路由（如 `/holdings`）直接刷新/直达时，FastAPI 需把非 `/api` 路径 fallback 到 index.html——否则 404
2. **挂载顺序**：`/api` 路由必须在 StaticFiles 之前注册（FastAPI 匹配顺序），或 StaticFiles 用 `html=True` 挂根路径
3. **Vite base**：dev 代理（5173）与生产挂载（8000）下 base 建议固定 `/`，不引入子路径复杂度
4. **启动脚本**：Phase 5 后 `run_dev.bat` 的 Streamlit 启动行替换为"React build + uvicorn"或 dev 双进程
→ 修订版提示词已给出 main.py 挂载段的参考写法（含 fallback 中间件）。

**P2-D2 · 双前端并发写风险**：单人操作场景实际风险低，且后端无写锁概念。建议迁移期约定"写操作只用 React 端、Streamlit 只读核对"，无需代码改动。

### E. 硬红线与验收标准 —— **结论：红线需修订（见 P0-B2），验收清单基本完备**

- 验收自查 8 条覆盖了 git / dev 启动 / 代理 / 路由 / 折叠 / build / 对照表 / 交付报告，质量高 ✅
- 补充 2 条：① `npm run build` 后加 `vite preview` 冒烟（注意 dev 代理在 preview 下不生效，API 会 500——验收第 6 条应注明"仅验证外壳，API 走代理验证"）；② 增加"Node ≥18 版本检查"前置项
- 涨红跌绿、状态色映射与现有 `render.py` 的 `--up/--down` 语义核对过，一致 ✅

### F. 工作量与顺序 —— **结论：5 阶段合理，Phase 1 偏大建议拆分，经验沉淀顺序可优化**

- Phase 1 范围（工程 + 外壳 + 79 接口 TS 化 + 6 个共享组件）对单次 Claude Code 会话偏大，**建议拆为 1a（工程/主题/外壳/路由占位）+ 1b（API 客户端全量 + 共享组件）**，各自独立验收
- **经验沉淀放 Phase 5 的顺序问题**：sir 迁移 React 的核心理由就是"经验沉淀审核需要状态化交互（两步确认/批量过目/可回滚）"，但方案把它排到最后——若后端经验沉淀闭环（A-E）已落地，建议 **Phase 3 结束后插入经验沉淀页**（此时核心页面已迁完，React 即可承载审核交互），不必等 5 阶段全完。这是可选的顺序优化，不阻塞。
- 13_经验沉淀在导航映射里标 P1/Phase 5，与 Phase 2-4 的 P0/P1/P2 优先级体系并行，逻辑自洽 ✅

---

## 二、必须修改项清单（执行前必改）

| 编号 | 级别 | 内容 | 出处 |
|---|---|---|---|
| M1 | P0 | 总方案 §五 补 `run_discover`、`stock_names` 2 个接口 | 方案 §五 |
| M2 | P0 | Phase 1 提示词修正：chat 9 个（非 8）、timeout 分层（GET/PUT 60s / POST 600s / ocr 180s / learn 60s）、chat_learn 补 multipart | 任务书第二部分 |
| M3 | P0 | git 第零步加"逐文件 git diff 厘清批次归属"——64 个未提交文件疑似混有批次 4 代码（concentration 路由已在），未验收代码不得与已验证改动混装提交 | 任务书第二部分 |
| M4 | P0 | 红线 6 修订为"迁移期后端零改动；Phase 5 仅允许 main.py 静态挂载（含 SPA fallback）约 10 行" | 方案 §六 |
| M5 | P0 | run_dev.bat 路径修复（D:\space\self\self → D:\self），否则 Streamlit 并行可用承诺落空 | 方案 §〇 |
| M6 | P1 | 生产托管 4 细节补齐：SPA fallback / 挂载顺序 / Vite base / 启动脚本（修订版已给写法） | 方案 §二 |
| M7 | P1 | Phase 1 拆 1a/1b 两步，各自验收 | 方案 §四 |
| M8 | P1 | `.workbuddy/memory/` 提交归属明确化（建议随"文档"提交，需 sir 确认） | 任务书第二部分 |
| M9 | P1 | .gitignore 追加 `*.bak*`、`*_b?.log` | 任务书第二部分 |
| M10 | P2 | Zustand 保留但收敛为 2-3 个全局 store | 方案 §一 |
| M11 | P2 | 迁移期双前端写操作约定（只用 React 写、Streamlit 只读） | 方案 §六 |
| M12 | P2 | 经验沉淀页评估提前到 Phase 3 后插入（不阻塞） | 方案 §三 |

---

## 三、修订版 Phase 1 提示词（M1-M9 已合入，可直接执行）

```
你是资深 React 前端工程师，负责为本项目（A 股智能托管系统，D:\self）搭建全新的 React SPA 前端，
替代现有 Streamlit（并行运行期两者共存）。本阶段只做工程搭建 + 应用外壳 + API 客户端，页面用占位组件。

【第零步：git 分支与回滚保障（最先执行，失败即停）】
1. 检查 git 状态（git status / git branch --show-current / git tag -l）。
2. 【关键】当前 main 分支有 64 个未提交文件。先执行 git diff 逐文件确认改动归属：
   - 批次 2/3 已验证的前端优化与后端改动 → 分主题 commit（前端批次优化 / 后端改动 / 文档各一个 commit，
     不许混装）
   - 疑似批次 4 的代码（routes.py 中的 /api/candidate/concentration、repo.py/akshare_source.py/
     jobs.py 的改动）→ 若未验收，单独 commit 或暂不提交，绝不允许与已验证改动混装
   - .workbuddy/memory/ 随"文档"commit（若 sir 确认无敏感内容）；.bak.* 备份与 *_b?.log 临时文件
     不提交，追加进 .gitignore（*.bak*、*_b?.log）
3. 从 main 切出并切换到新分支 feat/web-react：此后全部 React 工作只在该分支进行，绝不切换回 main 改东西。
4. 本阶段完成且验收通过后：git tag web-phase1，并合回 main（merge --no-ff 保留分支轨迹）。
5. 回滚约定：任何阶段出问题，git checkout main 即回到纯 Streamlit 状态；阶段内回退用 git reset 到
   本阶段起点 commit。把该约定写进交付报告。

【背景与总方案】
先通读 D:\self\前端架构迁移_React_总方案.md——这是本迁移的完整方案。严格按它执行；如与实际代码冲突，
以实际代码为准并在报告中标注。注意方案 §五 接口清单已勘误（补 run_discover、stock_names 两个接口）。

【第一步：自主探索，动手前必须完成】
1. 通读 D:\self\streamlit\api_client.py——全部 83 个函数（含 4 个内部 helper），这是 TS 版 API 客户端的
   完整源清单，逐个转写，一个不能漏。函数清单与路径对照以本提示词附录的勘误表为准。
2. 通读 D:\self\streamlit\app.py——st.navigation 的 4 组 12 页导航结构（系统概览/选股决策/持仓风控/
   策略沉淀），React 侧边栏按此复刻。7_个人交易偏好.py 未在导航注册，跳过不迁。
3. 通读 D:\self\streamlit\render.py 的 _GLOBAL_THEME_CSS（文件前部）——现有暗色主题的 CSS 变量
   （--bg/--text/--up/--down/--warn 等）与整体视觉风格，React 主题要延续这套视觉。
4. 抽看 D:\self\streamlit\pages\0_系统概览.py 顶部 30 行——看 top_status_bar 的信息结构
   （指数行情/系统状态/时间），React 顶部状态栏按此复刻。
5. 确认 D:\self\backend\app\main.py 已开 CORS（allow_origins=["*"]），无需后端改动。
6. 【行为面】逐一确认每个操作按钮在页面里的真实调用方式：直接调 API 函数 vs 走 submit_task 任务队列
   （已知：sell_decision/position/daily_pipeline/market_intel/score/portfolio_sentinel/monitor_all
   走任务队列）——TS 端必须复刻"提交任务 → 轮询 /api/tasks/{id} → 完成后刷新"链路，不能裸调接口。

【第二步：工程初始化】
1. 在 D:\self\web\ 创建 Vite 5 + React 18 + TypeScript 工程（npm create vite@latest web -- --template react-ts）。
   统一 npm。Node 版本要求 ≥18（本机 22 满足）。
2. 安装依赖：antd @ant-design/icons @tanstack/react-query zustand axios react-router-dom
   dayjs echarts echarts-for-react
3. vite.config.ts 配置 dev 代理：'/api' → 'http://localhost:8000'（changeOrigin: true）。
4. tsconfig.json 开启严格模式与路径别名 "@/*" → "src/*"。

【第三步：暗色主题与全局样式】
1. main.tsx 用 ConfigProvider + theme.darkAlgorithm 包裹 App；中文 locale（zh_CN）。
2. src/index.css 定义 CSS 变量，对齐 Streamlit 版视觉：深色背景（#0f1117 级）、涨红跌绿（中国股市惯例：
   --up 红 / --down 绿）、琥珀警示色。全局字体、滚动条样式暗色化。
3. token 定制（ConfigProvider theme.token）：colorPrimary 延续现系统主色、borderRadius 适中、字号基准 14px。

【第四步：应用外壳 AppShell】
1. src/components/layout/AppShell.tsx：左侧固定侧边栏（可折叠）+ 顶部状态栏 + 主内容区（Outlet）。
2. 侧边栏：AntD Menu，4 个分组 12 项，完全对齐 Streamlit 导航：
   系统概览组：系统概览(/)、市场研判(/market-intel)
   选股决策组：每日候选池(/candidates)、评分报告(/scores)、建仓计划(/plans)
   持仓风控组：持仓监控(/holdings)、游资追踪(/hot-money)、告警日志(/alerts)
   策略沉淀组：交易复盘(/reviews)、交易知识库(/knowledge)、Agent对话(/agent-chat)、规则变更记录(/rule-changes)
   每项带图标（AntD Icons 语义对应）+ 中文名；当前路由高亮；折叠态只显示图标。
3. 顶部状态栏（TopStatusBar.tsx）：
   左侧：三大指数（上证/深证/创业板，名称+点位+涨跌幅，涨红跌绿）——React Query 调 GET /api/market/indices，
   refetchInterval 30s；
   右侧：系统状态点（GET /api/health，绿=正常/红=异常）+ 北京时间（每秒更新）。
   接口失败时优雅降级（显示"—"），绝不白屏。
4. 路由配置：React Router v6，12 条路由全部注册，页面组件统一为占位组件 PagePlaceholder
  （显示页面名 + "Phase 2/3/4 实装"），确保导航点击即可切换且 URL 正确；刷新/直达子路由必须正确渲染
  （SPA fallback 在 dev 由 Vite historyApiFallback 保证）。

【第五步：TypeScript API 客户端】
1. src/api/client.ts：Axios 实例，baseURL '/api'（走 Vite 代理），超时分层：
   GET/PUT 60s、POST 600s、ocr 上传 180s、chat_learn 60s（后两个为独立实例或 per-request timeout）。
   响应拦截器统一错误处理（网络错误 → 抛出带中文提示的 Error，供 React Query onError 展示）。
2. src/api/ 目录按域分文件转写 api_client.py 的全部函数（一个不漏），每个函数配 TS 类型：
   - system.ts：health/systemStatus/dashboard/jobStatus/llmStats/datasourceStats/runDiscover
     （runDiscover = POST /api/jobs/discover/run，勿遗漏）
   - tasks.ts：submitTask/recentTasks/taskDetail/retryTask
   - market.ts：marketIndices/indexHistory/hotSectors/marketCondition/marketIntel/marketIntelDates
   - account.ts：accountSummary/saveAccountBaseline
   - candidates.ts：candidates/candidateDates/candidateTradeable/candidateConcentration/stockNames
   - traces.ts：traces/traceDetail
   - scores.ts：scores/triggerScore
   - positions.ts：plans/createPlan
   - holdings.ts：holdings/holdingQuotes/addHolding/exitHolding/holdingAdd/holdingCost/
     holdingTrades/monitorHolding/sellDecision/sellDecisions/takeProfitPlan
   - ocr.ts：ocrStatus/ocrHolding（multipart FormData，timeout 180s）
   - suggestions.ts：agentSuggestions/approveSuggestion/adoptSuggestion/rejectSuggestion/
     ruleChanges/rollbackRuleChange
   - track.ts：trackVerifyList/Dates/Stats/Run/Suggest
   - alerts.ts、reviews.ts、profile.ts（GET/PUT/export/import）、knowledge.ts
     （list/add/delete/batchImport）
   - hotMoney.ts：profiles/flows/traces/winrateIterate/tierApply
   - chat.ts：共 9 个——chatAgents/chatHistory/batchAsk/applyBatchAdjust/rollbackBatchAdjust/
     chatAsk/chatRule/chatLearn/chatLearnConfirm。chatLearn 为 multipart 上传：
     params 带 agent、form data 带 description（参照 api_client.py:482 的实现，timeout 60s）
3. src/types/ 定义核心数据类型（Holding/Candidate/Score/Plan/Trace/Review/Task/AgentSuggestion 等），
   字段对齐后端返回（参考 api_client.py 各函数 docstring 与 Streamlit 页面取用字段）。
4. 【行为复刻】所有页面以"提交任务 + 轮询进度"方式调用的操作（sell_decision/position/daily_pipeline/
   market_intel/score/portfolio_sentinel/monitor_all），在 TS 层封装为 useTaskSubmit hook：
   submitTask(kind, params) → useQuery 轮询 /api/tasks/{id} → 完成回调。禁止把任务类操作裸调成
   同步接口。

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
- 只在 D:\self\web\ 新建代码文件；绝不改动 backend/、streamlit/、任何现有文件（.gitignore 追加除外）。
- 迁移期间（本阶段）后端零改动；生产静态挂载属 Phase 5 单独任务，本阶段不做。
- 不引入方案外的依赖（不加 Tailwind/Redux/Next）。
- 所有 API 函数必须与 api_client.py 一一对应，路径、参数、方法零偏差；任务队列类操作必须走
  useTaskSubmit 链路。
- 涨红跌绿（中国股市惯例）贯穿所有颜色逻辑。
- npm 安装失败时报告，不要换包管理器。
- TypeScript strict 模式无 any 滥用（API 响应类型允许渐进完善，先 unknown/接口占位）。

【验收自查】
1. git log 展示：main 已按批次/主题清理干净 + feat/web-react 分支上本阶段 commit 记录（无混装 commit）。
2. cd D:\self\web && npm run dev —— http://localhost:5173 打开无报错。
3. 后端启动（uvicorn）时：顶部状态栏显示真实指数行情与系统状态（走代理无 CORS 报错）；后端关闭时优雅降级。
4. 侧边栏 4 组 12 项可点击切换，URL 正确变化，刷新后路由保持（含直接访问子路由）。
5. 侧边栏折叠/展开正常。
6. npm run build 成功，无 TS 类型错误（警告可容忍）；用 vite preview 冒烟外壳渲染（API 走代理不生效属预期，
   不作为失败项）。
7. src/api/ 函数清单与 api_client.py 逐一对数（在报告中列对照表：83 个函数全覆盖，含 runDiscover/stockNames；
   chat 域 9 个）。
8. 输出交付报告：目录结构树、依赖清单、API 函数对照表（Python→TS）、任务队列行为复刻说明
   （7 个 kind 的处理方式）、与总方案的偏差项、git 分支与回滚说明、Phase 2 实装建议。
```

---

## 四、执行节奏建议

1. sir 拍板本审核结论（M1-M9 是否全部接受）
2. 用修订版 Phase 1 提示词执行（已合入 M1-M9）
3. 同时修复 run_dev.bat 路径（1 分钟，可并入 Phase 0 前置项）
4. 每阶段：执行 → 验收 → 打 tag → 合 main

---

## 附：关键代码事实索引（供复核）

| 事实 | 证据 |
|---|---|
| api_client 83 函数 / 79 对外 | `grep -c "^    def" streamlit/api_client.py` = 83 |
| 后端 85 路由 / 0 遗漏 | AST 提取 routes.py，与 api_client 全量对照 |
| timeout 分层 | api_client.py:13(GET 60) / :19(POST 600) / :25(PUT 60) / :233(ocr 180) / :488(learn 60) |
| 任务队列 7 kind | 页面 grep submit_task 汇总 |
| git 64 未提交文件 | `git status --short | wc -l` = 64 |
| concentration 路由已存在 | routes.py:452（批次 4 特征，记忆标注"待执行"） |
| run_dev.bat 路径失效 | run_dev.bat:18-19 指向不存在的 D:\space\self\self |
| main.py 无 StaticFiles | `grep -c "StaticFiles" backend/app/main.py` = 0 |
| CORS 已开 | main.py:37 allow_origins=["*"] |
| tag 无冲突 | `git tag -l` 为空 |
| .env / data 已忽略 | `git check-ignore .env data/dev.db` 命中 |
