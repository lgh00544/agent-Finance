# D:\self 项目滚动归档（主题分类）

> **写于**：2026-08-20，整理自 2026-08-13 ~ 2026-08-20 daily logs
> **目的**：daily log 散落信息按主题压缩存档；项目使命/批次进度/红线等长期事实见 `PROJECT_STATE.md`
> **限制**：本文件作为机器快查索引，保留所有长期铁律；字符上限不再硬性约束 3000（旧规范已不适用，新规则加入后内容必要）。

## 协作模式（永久生效）

- sir 提需求 → Lark **直接出 Claude Code 提示词**（2026-08-19 起永久生效），仅需求+规则+约束，不含代码。**sir 不用每次都说"给我让 Claude Code 执行的提示词"**——这是默认。
- 唯一例外：涉及交易规则/研判标准/红线时，提示词内加"红线约束"段。
- 大型需求（5+ 批次/多模块联动）→ 先出方案文档（`D:\self\{主题}_方案.md`）→ 再出多批次执行指令（`D:\self\{主题}_{N}批次_Claude执行指令.md`）。
- 多批次执行指令结构：每批次包含 0 元信息 + 一目标 + 二架构约束 + 三规则 + 四实现参考 + 五执行顺序 + 六验证清单 + 七红线。批次按依赖排顺序。（2026-08-22 起默认按下方"省 token 铁律"精简版出）
- 审核任务交付（2026-08-17）：必须给"可复制给其他 agent 的总结段"，含 ①问题②操作③文件路径。
- 工程师交接（2026-08-17）：自然语言 5 要素——文件在哪/做什么/为什么/预期/思考。
- **🆕 精简提示词偏好（2026-08-27 sir 拍板）**：sir 说"给提示词"时 → **只给一段可复制文本**，讲清「①要执行的文件在哪（准确 path）+ ②需要注意什么（红线/约束/前提）」即可；**不要**再铺方案背景、表格、多段落解读。直接可丢给 Claude Code 执行。歧义 → 出了文件 + 一句话说明放哪。

### 🔴 前端默认改新版 React，不动 Streamlit（2026-08-20 sir 拍板，永久生效）

所有"页面/交互/组件/UI 文案/排序/筛选/徽章/Tab"修改 → **默认只改 `web/src/`**。Streamlit（`streamlit/pages/`）只在三种情况动：①后端 API 变更导致旧版报错阻塞使用 ②sir 显式点名 ③React 侧功能尚未迁移（查工单列表）。歧义 → 先问 sir，不擅自决定。

**不受此规则影响**：后端/数据/Agent/交易规则/研判标准——只动后端，两端都消费。

**已固化**：4400% 修复、复盘徽章排序、TaskDrawer 升级等按 React 新版出。Streamlit 同名指令保留可回滚，优先级**永远低于** React 版。

### 🆕 任务看板 UI 范式（2026-08-31 sir 拍板，永久生效）

**背景**：sir 在 RuleChangesPage 提出"任务看板方式"（泳道图，分阶段流转），认可为可复用的 UI 范式。后续所有"有明确流转阶段"的页面 → Lark **主动按此范式评估**是否可优化，并在出提示词前明确告知 sir。

**适用场景（3 项之一命中即推荐）**：
1. 业务有"待处理 → 处理中 → 已完成 / 驳回后回审"等 **≥3 个明确流转阶段**
2. 表格列里有 **多列表示状态/阶段**（如 AI 审核状态、采纳/驳回、回滚/重新审核）
3. 用户需"一眼看到多少条卡在哪个阶段"（流转感 > 明细查询感）

**5 列看板 + Drawer 抽屉 + 顶部筛选 标准配方**：
| 元素 | 规格 |
|---|---|
| 看板布局 | `Row + Col flex:1` 5 列（待审 / 审中 / 人工审 / 通过 / 驳回待重审）—— 列数依业务调整 |
| 列头 | 列名 + 该列卡片计数 |
| 卡片内容 | 标题 + 归属 Tag + 类型 Tag + 状态徽章 + 时间 + 关键操作按钮 |
| 拖拽 | `@dnd-kit/core` + `@dnd-kit/sortable`；**拖动必须 modal.confirm 二次确认**（防误拖） |
| 状态变更 | 拖到目标列 → 调对应 API（rejectSuggestion / reAuditSuggestion / reReviewSuggestion / rollbackRuleChange）|
| 顶部筛选 | `Input.Search`（关键词）+ `Select`（多维度下拉：Agent/类型/时间）|
| 详情 | 点击卡片 → 右侧 `Drawer` 720px，3 段（原信息 / AI 审核 / 元信息）|
| 操作按钮 | 重新审核（绿色）/ 回滚（红色，带原因）/ 查看完整（开抽屉）|
| API 复用 | 优先复用 `@/api/audit` `reAuditSuggestion` / `@/api/suggestions` `rejectSuggestion` 等已有接口；**禁止**为同一动作新加后端路由 |
| 改动预算 | ≤ 250 行；超过 → 拆 2 批 |

**首个落地**：RuleChangesPage 规则变更记录（2026-08-31 开工，待验收）。

**Lark 工作流**：sir 提任意页面需求时，Lark **先判断是否符合 3 项命中之一**：
- 命中 → 提示词里明确写"建议采用任务看板范式"，并把范式核心要点（5 列 + 抽屉 + 拖拽 + 顶部筛选）作为约束列出来
- 不命中 → 按既有表格/卡片/列表形式正常出

**例外的例外**：纯数据查询/明细浏览类页面（无流转感）→ 维持表格，不强推看板。

### 🔴 自文件提示词默认写到项目中（2026-08-21 13:23 sir 拍板，14:29 二次强调，永久生效）

Lark 给出的所有"提示词 / 方案 / 执行指令 / 审核结论"类自文件，**默认全部写到项目根 `D:\self\`**，与代码同库同版本控制。命名规范 `{主题}_{版本/工单号}_{文档类型}.md`。

- **不再**默认写到 `C:\Users\57388\Desktop\提示词\`（仅可作可选镜像或历史归档）
- **必须**写到 `D:\self\` 的文件类型：执行指令 / 方案 / 审核结论 / 工单 / 应急修复指令 / 风险清单
- 写完用 `Write` 落盘 + `Bash ls` 验证 + 在回复中给文件路径 + 必要时 `present_files`
- 桌面提示词目录保留为可选镜像（执行端/Claude Code 工作流需要时由执行端自行同步）；**Lark 主交付物必须先落到 `D:\self\`**
- 歧义（"这个算不算自文件提示词"）→ 算的，包括方案、决策点列表、风险清单、Bug 复盘、给工程师的评审提示词
- **例外**：sir 显式说"写到桌面" / "写到别处" → 听 sir 的，但 Lark 主输出仍同时落到 `D:\self\`

**主从关系（避免版本漂移）**：
- `D:\self\` 是**主**，desktop `C:\Users\57388\Desktop\提示词\` 是**历史镜像**
- 已发现 desktop 残留 5 份历史镜像（`AIMedDRA编码_第1批次` / `AI改造_*` / `Discover前瞻子Agent_Claude执行指令` / `经验沉淀急救_Claude执行指令`）——其中 `Discover前瞻子Agent_Claude执行指令` 已 in-place 改了 5 处，desktop 那份**已过期**
- 处理原则：**in-place 改完项目内文件后**，如发现 desktop 有同名旧版，**追加一段顶部 banner**「已过期，请查 `D:\self\XXX.md` 主版」即可，**不删除**（sir 拍板"历史归档保留"）
- 未来 Lark 出新提示词前**先 ls `D:\self\`** 看是否已有同主题文件 → 有则 in-place 改，无则新建

### 🔴 提示词省 token 铁律（2026-08-22 凌晨 sir 拍板，永久生效）

**背景**：sir 反馈近期 token 消耗过大，主因之一是提示词内容冗余 / Claude Code 重复读已固化信息。

| # | 手段 | 怎么省 |
|---|---|---|
| 1 | **引用替代复述** | 上游方案/批次指令已写过的内容，**用 `参见 D:\self\XXX_方案.md §X` 一句话引用**，不重抄 |
| 2 | **精简 8 段 → 6 段** | 单批次提示词合并为：0 元信息 + 一目标 + 二架构约束 + 三规则 + 四执行顺序 + 五红线；砍掉独立的"四实现参考"段（改为 §三 段内 1-2 行文件引用） |
| 3 | **删套话和元说明** | 不写"以下是提示词 / 请仔细阅读"等开场白，直接干货 |
| 4 | **代码块禁入** | 不写 Python/TS/SQL 代码片段——一律"参考 `xxx.py:line` 已有的 `yyy()` 函数"；Schema 用伪代码或 JSON 示例 |
| 5 | **表格列数 ≤ 4** | 字段说明用「字段：含义」一行表达 |
| 6 | **方案 vs 提示词分工** | 详细背景/权衡/Schema 沉淀到 `D:\self\{主题}_方案.md`；提示词只放"做什么 + 规则 + 执行顺序 + 红线" |
| 7 | **同主题复用** | 已有 `批次1/2_XXX_执行指令.md` 不再重抄，写"复用 §五步骤 1-7 的 collect 段注入模板" |
| 8 | **目标长度** | 简单 ≤ 80 行 / 中等 ≤ 150 行 / 复杂 ≤ 250 行 / 多批次合一 ≤ 400 行 |

**硬约束（不能省）**：§五红线、字段/阈值/触发条件、准确 `path:line` 引用——这 3 项是 Claude Code 唯一准绳，错一个就会越界或返工。

**已应用**：`D:\self\关系持仓_个股分析_5批次合一_Claude执行指令.md` 350 行（达标）。**下次出提示词前自检**：能砍的段、能省的字、能引用的文件先看，**不要重复写**。

### 🔴 Claude Code 端也省 token（2026-08-24 sir 拍板，永久生效）

**背景**：之前只约束了"提示词 → Claude Code"输入端省 token，没约束"Claude Code → 写代码"输出端。sir 指出输出端同样要省——Claude Code 复读已固化信息、写大段注释、顺手改其他文件、测试多写都是浪费。

每份提示词 §五 红线末尾追加 6 条 Claude Code 端省 token 约束 + 代码侧最小改动铁律：

| # | 手段 | 怎么做 |
|---|---|---|
| 1 | **不复读提示词已固化信息** | 6 段 + Schema + 阈值已在本文件齐备，禁止再次 read 全文（只 grep 关键标识确认行号）|
| 2 | **不写超出提示词范围的代码** | 提示词列了改哪几个文件就只动那几个，禁止顺手改其他文件 |
| 3 | **不写大段注释** | 函数 docstring ≤ 3 行，函数体内不写 `# 注释`（除关键 trade-off）|
| 4 | **复用已有函数** | 已有实现的函数直接调用，禁止重写 |
| 5 | **测试用例不超规定数量** | 提示词列了 N 个就只写 N 个，禁止多写"以防万一" |
| 6 | **报告精简** | 执行完毕报告 ≤ 10 行：①改了什么 ②测试结果 ③遗留风险 |

**代码侧最小改动铁律**：改动行数预算简单 ≤ 50 / 中等 ≤ 80 / 复杂 ≤ 150 行；超出 → 停下报告 sir。

**已应用**：`D:\self\关系持仓_批次F_Claude执行指令.md` §五.1 + §五.2（共 14 行新增约束）。

## 关系持仓 × 个股分析 5 批次（2026-08-24 全收口）

| 批次 | commit | 主题 | 关键文件 |
|---|---|---|---|
| F | e552bb3 | 组合↔个股联动 | portfolio_sentinel 多键 + drawdown + Monitor/Review 注入 |
| D | f35dc53 | 派发期自动判定（后半段）| distribution_phase.py + DistributionPhaseLog + 3 Agent + cron 15:30 |
| E | 待工程师 | 游资数据真接入 | capital_view.py 363 行 + K189 + 4 Agent 注入（后端已测，前端 5 补丁未 Apply）|
| G | 1f006e9 | K 红线代码化 | red_line_check.py 178 行 + 3 Agent 注入 + React HoldingsPage 4 徽章 |
| H | d9044d5 | 复盘反哺选股 | track_verify 追加 2 函数 + 2 端点 + Review/Score 注入 + React ReviewsPage「组合复盘」Tab |

**5 批次共同铁律**（sir 决策底线，永久生效）：
- Agent 解耦：只动 collect 段，不动 agent_call / push_alert_node
- 代码-提示双层：代码算事实（K189 对倒 / 派发期 phase / C1-C3 阈值 / 历史胜率加分），LLM 做综合判断
- 缺数据 → null + missing_data 明列（K223 事实为先）
- L0 阈值（C1=60%/C2=30%/C3=0.92）永不修改，参考权重非死条件，LLM 一票否决权保留
- React 新版优先，Streamlit 不动（2026-08-20 已固化规则）
- 不引新库：SimpleCache + 已有 SQLite 表 + agent 已有 collect 段

**5 批次收口未完成**：
- 批次 E 工程师需 Apply 5 处前端补丁 + 跑全量 pytest + commit
- 批次 E 既有 2 失败（test_capital_view.py 设计缺陷 + routes.cache 模块属性）待归账
- 工作区 18 个 `.bak` 残留 + 4 个 `_tmp_*` 临时文件待清理

## 设计哲学（sir 拍板）

- LLM 输出"艺术判断" → 代码层换算"可执行事实"（100 股整数倍、股数、金额）
- 展示层永远给最终可执行数字，不给中间值
- 边界自动处理、每个节点有人工控制入口
- 功能不成熟不展示，不制造噪音

## 高频陷阱（执行/审核必查）

1. `structured.py:32` 注释"LIGHT=Discover 初筛"是**错的**，Discover 3 处全 DEEP
2. `fetch_industry_spot` 需传 `kind="snapshot"` 才走断路器
3. dashboard 聚合**禁止**调 `tradeable_view()`（ensure_if_missing 触发 900 次 DB 查询），用 `repo.list_candidate_tradeable(trade_date, limit=50)`
4. `repo.list_candidate_tradeable` 字段是 `tier/price_zone/label/block_reason`（**不是** `grade/reason/potential_flag`）
4a. 复盘追踪列表缺徽章/排序：Streamlit `D:\self\选股效果验证_排序加徽章_执行指令.md` + React `D:\self\React复盘页徽章排序_执行指令.md`（均未执行）
4b. **React 候选池页默认拉全表 bug**（2026-08-20）：`CandidatesPage.tsx:480` 的 `date` state 始终 undefined，`<Select value={date ?? dates?.[0]}>` 是非受控显示，queryFn 实际传 undefined → repo 拉全表 39 条。**修复模板**：`useEffect(() => { if (!date && dates?.length) setDate(dates[0]) }, [dates, date])` + `enabled: !!date`。指令：`D:\self\React候选池页默认仅最近一次生成_执行指令.md`
4c. **同 trade_date 下所有候选共用同批生成时间**（毫秒级差），"最近一次生成结果"=trade_date 最大的那一天全部候选
5. `TradeProfile` 在 `web/src/types/index.ts:294`（**不是** `types/trade.ts`——该文件不存在）
6. win_rate 口径：`track_verify._group_stats` 0-100 百分制；`_calc_stats` 0-1 小数——展示层必须显式归一化（防 4400%）。**React 新前端 `CandidatesPage.tsx:572` 和 `ReviewsPage.tsx:132` 曾误把百分制再乘 100，已出修复指令 `D:\self\React前端胜率展示修复_执行指令.md`**
7. `WebFetch` 失效时用 `request` 直调 akshare：market_hours.snapshot_allowed() 是交易日闸门
8. `useEffect` 替代写法是死循环——不要在 render 阶段直接 `form.setFieldsValue`
9. tsc EXIT=0 零错不代表落地——未使用 import/函数 tsc 不报警，必须 `grep 关键标识 | wc -l` 核对
10. AppTest 22 failed 是**环境性内存压力**，与代码无关

## 关键术语映射

- "批次" = 一次完整开发周期（Claude Code 提示词 + 实施 + 验收）
- "工单" = React SPA 补全的 v1→v2 子任务（工单 1-6 已完成，工单 7-12 进行中）
- "auto-merge" = GitLab 自动合入的 PR——**永不**改交易规则/研判标准表
- "review_log" = 所有规则改动的可回滚审计

## 调试快速路径

- 数据不显示 → `curl /api/<endpoint>` 直验后端；浏览器 vs 后端分离判定
- LLM 异常 → 先 `light_stats` / `deep_stats` 看命中率，3 次失败自动降级
- 任务调度 → `job_status()` 接口看 `last_*` 时间戳
- 行情缺失 → `sector_snapshot.updated_at` + `sector_refresh_job` cron 日志
- 经验沉淀全链路空 → 先查 `pending_experience.status` + `experience COUNT(*)` + `worker_run.last_*`；168 done 但 experience 0 行 = LLM `worth=False` 全被丢（EXTRACT_SYSTEM 宁缺毋滥 + 摘要过薄）
