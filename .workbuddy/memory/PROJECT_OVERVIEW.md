# D:\self 项目总览（一次性总览 · 2026-08-20 整理）

> **目的**：把分散在 6 份日志里的"项目是什么 / 现在到哪 / 接下去做什么"压缩成一份可读全档，避免后续会话反复翻日志。
> **读法**：从 §1 读到 §4 即可恢复项目全貌；§5 是索引表（按主题/按文件路径）；§6 是项目铁律；§7 是工作约束。
> **维护**：每次新增/完成批次，只更新 §2 批次表、§3 计划表，不要重写整份；详细日志在 `2026-08-XX.md` 里。

---

## §1. 项目是什么（核心身份）

**项目**：A 股全生命周期交易决策 Agent 系统
**路径**：`D:\self\`（Streamlit + FastAPI 主体；React SPA 迁移在 `D:\self\web/`）
**栈**：Python 3.14 (后端 + LLM) + Streamlit 1.60 (老前端 8501) + React 18 + Vite + TS + Antd 6 (新前端 5173 dev / 8000 dist) + SQLite (本地 dev.db) + TiDB (云端) + LangGraph + DeepSeek 双模型（flash/chat）
**作者**：sir (lgh00544)，项目 lead/director
**当前 AI 角色**：SeniorDeveloper，承担 ClaudeCode 执行指令的预审核 + 优化 + 落地追踪

**核心架构**：8 业务 Agent + 2 辅助 Agent，全部 LangGraph 串联，**单数据源 + 人工 fail-closed 红线**

| Agent | 职责 | 关键产出 |
|---|---|---|
| Discover | 每日潜力挖掘 | `stock_candidate` 表（trade_date+code 唯一） |
| Score | 六因子评分 | `stock_score` 表 + A/B/C 评级（权威单一，不兜底） |
| Position | 分批建仓方案 | `position_plan` 表（3-4 档 + 资金配比 + 止损止盈） |
| Monitor | 盘中监控 | `monitor_alert` 表（每 3 分钟，exit/reduce/hold+severity） |
| Sell | 卖出决策 | `sell_decision` 表（sell/partial/hold + reduce_ratio） |
| Review | 复盘沉淀 | `trade_review` + `agent_suggestion`（**人工审核后才生效**） |
| MarketCondition | 市况评分 | 5 维 0-10 → 总分 50 → 决定候选池规模上限 |
| MarketIntel | 市场研判底座 | 8 层方法论注入到全部 Agent |
| TrackVerify | 候选 T+N 验证 | `candidate_track_verify` 胜率统计 + 异常检测 |
| PortfolioSentinel | 组合哨兵 | 4 维风控（板块退潮/时间止损/回撤/集中度），10 分钟巡检 |

**终极目标**（sir 2026-08-14 拍板）：

> **全智能化托管——从选股，到实际建仓，以及买入后全生命周期的持仓计划监控；每个节点都可以人工控制。sir 可以完全信任并执行。**

**衡量标准**：sir 每天打开系统，能直接信任系统给出的每个结论并照着执行，不需要再自己算一遍或心怀疑虑。

---

## §2. 批次进度（已完成 + 进行中 + 待办）

### ✅ 已完成（含本会话内或近期落地的批次）

| # | 批次 | 完成日 | 累计测试 | 关键产出 |
|---|---|---|---|---|
| 1 | 移动止盈 + PortfolioSentinel | 2026-08-14 | 19 | take_profit.trailing_stop + 4 维哨兵 |
| 2 | SellAgent reduce_ratio + 组合联动 | 2026-08-17 | 483 | reduce_ratio 0-1 校验 + 100 股取整 |
| 3 | 选股反馈闭环 + 候选表现摘要 | 2026-08-17 | 541 | common.py 注入位 5.5 + 统计卡 |
| 4 | 盘前快筛 + 候选关联度 + 市况切换 | 2026-08-17 | 557 | pre_market_screen + concentration + shift_detect |
| - | MarketIntel 深度化 v3 | 2026-08-17 | 567 | 4 字段（main_structure/box_view/volume_character/stock_verification） |
| 5 | 准确率闭环增强（A/B/C 全档倒挂 + 市况方向命中率） | 2026-08-18 | 580 | rating_inversion 改两两对比 + next_day_index_pct |
| 评 A | 六因子透明评分（ScoreAgent 重构） | 2026-08-18 | 593 | 6 因子 0-10 + potential_flag 代码层推导 + v4 缓存前缀 |
| 评 B | 因子卡展示层（前端） | 2026-08-18 | 577 (非 AppTest) | factor_cards 3×2 网格 + 潜力横幅 + 交叉验证卡 |
| 评 C | 因子回测校准闭环 | 2026-08-18 | - | factor_scores 列 + compute_factor_correlation + get_factor_calibration 注入 |
| - | 模型体系优化 A-D | 2026-08-19 | 588+1 | A 经验沉淀 Worker 可配 provider / B 规则兜底 / C Score 两段式 / D llm_stats 单价 |
| - | 首屏性能优化（4 文件） | 2026-08-19 | 550+1 | client.ts 15s timeout / TopStatusBar retry:0 / market_view 10s 硬超时 / main.py 异步预热 |
| - | candidates 页 `.map is not a function` 修复 | 2026-08-19 | - | `/candidates/dates` 返回裸数组 |
| - | 板块数据稳定性优化 | 2026-08-19 | 634+22 | sector_snapshot 5min 落库 + 首页只读 DB + akshare 断路器 |
| - | 今日行动清单 | 2026-08-19 | 599+3 | 三区（A 可建仓 / B 持仓关注 / C 市况速览） |
| - | 选股效果验证：排序 + 徽章 | 2026-08-19/20 | - | 4 下拉（评级+状态+日期+排序）+ `badge-ok/info/mute` |
| - | TaskDrawer 升级 | 2026-08-20 | - | 取消按钮 + Alert 失败 + Progress 伪进度 |
| - | 候选池首页胜率防呆 | 2026-08-20 | - | _tv_stats 归一化 clamp [0,100]（应对 4400% 假值） |

### 🔄 进行中（v2 工单序列 + 候选人首页修复）

| 编号 | 内容 | 状态 | 备注 |
|---|---|---|---|
| 工单 6 | 全局后台任务面板 | ✅ 完成 | TaskDrawer 8 kind 覆盖 |
| 工单 7 | OverviewPage Dashboard 主体 | 📋 待做 | v1 缩水中账户条已 OK，Dashboard 卡片待补 |
| 工单 8 | HotMoneyPage 补全 | 📋 待做 | 已部分，差 Tab 内容增强 |
| 工单 9 | ReviewsPage 补全 | 📋 待做 | **缩水最严重**，旧 1409 → 新 214 行 |
| **工单 10** | **ProfilePage 新建** | **📋 待做** | **整页漏掉，104 行全新**；审核文档已出 `D:\self\ProfilePage_工单10_审核文档.md` |
| 工单 11 | AgentChatPage 补全 | 📋 待做 | chat_learn/chat_rule/chat_learn_confirm 待补 |
| 工单 12 | MarketIntelPage 深度化模块 | 📋 待做 | volume_signal/operative_meaning/三维验证 |
| - | 选股效果验证页"4400% 假胜率"根因 | ⚠️ 运行时待确认 | 仓库代码正确，疑似运行进程旧版；建议重启 streamlit |

### 🔴 待验证（已落地，需运行时人工确认）

| 验证项 | 触发条件 | 失败应对 |
|---|---|---|
| 批次 4 9:25 竞价数据 | 首日 9:25 人工核对 ulist 返回是否为撮合数据 | 若为昨收 → 切 9:31 开盘异动版 |
| 批次 5 8 条历史行回填 | 应用启动后手动 `fill_market_condition_next_day()` | 离线如实跳过 |
| 评级重做 A LLM 输出六因子 | 手动触发评分 | 失败 → 检查 prompt + 缓存 v4 命中情况 |
| 评级重做 B 因子卡渲染 | 评分报告页 Tab 切换 | 旧数据走 DataFrame 降级，不报错 |
| React 13 页全部实装（Phase 1-5）| sir 浏览器逐页验收 | 7_个人交易偏好 / 复盘全 Tab 仍待补 |
| MarketIntel 3 数据源外网 | 实盘调用 | 离线时降级结构已就绪 |
| MarketIntel prompt 方法论注入 | sir 在别处研究后注入 | 4 字段带 default_factory，注入前不崩 |
| TaskDrawer UI 8/8 | sir 浏览器验收 §4.1 | 已补完，0 残留 |
| 候选池首页 4400% 消失 | 重启 streamlit + 浏览器验证 | 若仍存在 → 检查运行进程版本 |
| 选股效果验证 排序/徽章 | 重启 streamlit + 浏览器验证 | 备份 `.bak.badge_sort` 在 24:00 已建 |

---

## §3. 当前规划（未来 1-2 周）

### 优先级 1：v2 工单序列恢复（React 缩水补完）

**目标**：把 Phase 1-5 之后发现的 React 缩水页面补回到与 Streamlit 等效（甚至更优）。

**v2 启动顺序**（sir 8/20 拍板）：
1. **工单 10** ProfilePage（整页漏掉，104 行全新）→ 审核文档已就绪
2. **工单 9** ReviewsPage（缩水最严重，1409 → 214 行）→ 跟踪验证 + 建议 + 统计 三大模块待补
3. **工单 7** OverviewPage Dashboard 主体
4. **工单 8** HotMoneyPage
5. 工单 11/12 待 v2 节奏明确

### 优先级 2：候选池首页"4400%"根因排查

- 仓库代码实测：`_group_stats` 返回 `win_rate=44.0`（百分制），`render.selection_stat_cards` 正确显示 44.0%
- 但 sir 在浏览器看到 4400% → **强烈指向运行进程是旧代码**
- 行动建议：① 重启 streamlit + 后端 ② 强制刷新（Ctrl+Shift+R）③ 若仍存在，杀进程清缓存
- 防呆已加：`_tv_stats` 归一化 clamp [0,100]

### 优先级 3：经验沉淀闭环 + 选股表现摘要展示层

- 后端已实装（A-G 7 子模块 + SQLite+FTS5 + Worker + 人工审核 + 回滚）
- 前端 5 模块 UI 优化（M1 队列 / M2 Digest / M3 详情 / M4 浏览器 / M5 设置）分批落地
- 与工单 7/9 联调

### 优先级 4：评级重做闭环巩固

- A 评分模型 / B 展示层 / C 回测校准 均已落地
- 待观察：① 校准建议是否触发 ② 6 因子历史回填 ③ T+10 样本积累（当前 0 样本，30+ 后下中期结论）

### 暂停 / 不做

- ❌ Streamlit 8501 退役（待 sir 拍板）
- ❌ Vue3 试点（已移交其他 Agent）
- ❌ 非计划内优化（sir 偏好阶段内不打断）

---

## §4. 关键事实（备查不变量）

### 模型路由（structured.py ModelLevel）

- **DEEP** = `deepseek-chat`：Discover 3 处全 DEEP / Score / Position / Sell / Review / MarketIntel / agent_chat 3 处
- **LIGHT** = `deepseek-v4-flash`：Monitor 巡检 / Sentinel 告警 / 经验沉淀 Worker
- 机制：json_object + 温度 0.3 + pydantic 校验 + 重试 3 次 + LIGHT 3 次失败降 DEEP + 按模型独立统计
- 关键事实：discover 初筛 DEEP 是 24 连败后的实测决策（50k tokens 长输入 flash 必空响应）**不可降级**

### Embedding

- `bge-m3`（SiliconFlow 云端默认）→ 降级 `bge-small-zh-v1.5`（本地）
- payload 写 `emb_model` 字段按模型过滤，防维度不一致

### 视觉 OCR

- `MiniMax-M3`（云端优先）→ 降级 PaddleOCR（本地）
- 只做识别，不参与研判

### 业务字段不变量

- `stock_score.grade`（A/B/C）**权威单一，不兜底**
- `take_profit_plan.status`（"持有观察"/"接近止损"/"减仓预警"/"接近止盈"）直接判定今天是否需关注
- `candidate_tradeable.is_tradeable/label`（"可建仓"/"建议关注"/"观察"）唯一来源
- `monitor_alert.severity`（"info"/"warn"/"err"）驱动前端色调

### 调度时间表

| 时间 | 任务 | 备注 |
|---|---|---|
| 9:25 | pre_market_screen | 竞价数据（首日人工验证） |
| 16:00 | track_verify_job | 候选 T+N 验证（追加 factor_scores 回填） |
| 16:10 | market_condition_job | 市况评分 |
| 16:20 | market_intel_job | 市场研判 |
| 15:30 | market_accuracy_job | 市况方向命中率回填 |
| 02:00 | experience_worker | 经验沉淀（+30min 探针） |
| 10 分钟 | portfolio_sentinel_job | 组合哨兵 |

### 测试基线

- 全量非 AppTest：**577-634 passed**（按完成批次递增）
- AppTest 22 failed：**环境性**（3.7GB 内存 + 8 python 进程），非代码回归
- 本地无 pytest：Claude Code 独立环境，本机不直接跑

---

## §5. 索引表

### 5.1 关键文件路径

| 类别 | 路径 | 用途 |
|---|---|---|
| 后端入口 | `backend/app/main.py` | FastAPI lifespan + 异步预热 |
| 业务核心 | `backend/app/agents/*.py` | 8 业务 Agent |
| 数据网关 | `backend/app/db/repo.py` | 统一数据访问（**铁律：所有 SQL 走这里**） |
| 路由 | `backend/app/api/routes.py` | 85+ 端点 |
| 调度 | `backend/app/scheduler/jobs.py` | 19 个 APScheduler 任务 |
| Prompt 调教 | `backend/app/agents/agent_prompts/*.py` | 全部 LLM prompt 集中 |
| LLM 路由 | `backend/app/llm/structured.py` | DEEP/LIGHT 双模型 + 校验 |
| Streamlit 旧前端 | `streamlit/pages/*.py` | 13 页面（8501 端口） |
| 共享组件 | `streamlit/render.py` | 复用函数 + CSS |
| React 新前端 | `web/src/pages/*.tsx` | 13 页面（5173 dev / 8000 dist） |
| 状态管理 | `web/src/store/*.ts` | Zustand（2-3 store 收敛） |
| 任务管理 | `web/src/hooks/useTaskSubmit.ts` | 提交 + 2s 轮询 |
| 数据库 | `data/dev.db` | SQLite 本地 + TiDB 云端 |

### 5.2 本会话核心交付物（按文件路径索引）

| 文件 | 用途 |
|---|---|
| `D:\self\今日行动清单_执行指令.md` | 系统概览页新增三区行动清单（原版，4 P0 已修正） |
| `D:\self\今日行动清单_执行指令_修正版.md` | 修正版 v2 |
| `D:\self\今日行动清单_执行指令_审核结论.md` | 审核结论（4 P0 + 3 P1） |
| `D:\self\选股效果验证_排序加徽章_执行指令.md` | 复盘页追踪列表加排序 + 可建仓徽章（仅 1 文件） |
| `D:\self\TaskDrawer升级_执行指令.md` | TaskDrawer 取消/Alert/Progress 增强 |
| `D:\self\候选池首页胜率防呆_执行指令.md` | `_tv_stats` 归一化 clamp [0,100] |
| `D:\self\板块数据稳定性优化_执行指令_v2.md` | sector_snapshot 5min 落库 + 首页只读 |
| `D:\self\模型体系优化_执行指令.md` | A-D 四项模型体系优化 |
| `D:\self\首屏性能优化_执行指令_审核优化版.md` | client.ts 15s + market_view 10s + 异步预热 |
| `D:\self\ProfilePage_工单10_审核文档.md` | v2 工单 10 工程师审核文档（**已就绪待投**） |
| `D:\self\backend\tests\test_action_brief.py` | 11 条今日行动清单单元测试 |
| `D:\self\streamlit\pages\6_交易复盘.py.bak.badge_sort` | 选股效果验证改动备份 |

### 5.3 按主题索引（找内容用）

| 想了解什么 | 看哪份日志 |
|---|---|
| 批次 1-4 详情 | `2026-08-13.md`、`2026-08-14.md`、`2026-08-17.md` |
| 评级重做 A/B/C 详情 | `2026-08-18.md` |
| 选股准确率验证 + 倒挂检测起源 | `2026-08-18.md` §"选股准确率验证" |
| React 迁移 Phase 1-5 | `2026-08-17.md` + `2026-08-18.md` 末尾 |
| 性能优化 + 黑屏根因 | `2026-08-18.md` 末尾 |
| 板块数据稳定性 | `2026-08-19.md` §"板块数据稳定性优化" |
| 今日行动清单 | `2026-08-19.md` §"今日行动清单" + 末尾"执行卡循环修复" |
| TaskDrawer 升级 | `2026-08-20.md` §"TaskDrawer 升级抽验" |
| 选股效果验证 3 问题 | `2026-08-19.md` §"选股胜率 4400% + 列表不可排序 + 级别标识缺失" |
| v2 工单序列 | `2026-08-20.md` §"第二版本工单序列" |
| 工单 10 审核文档 | `D:\self\ProfilePage_工单10_审核文档.md` |

---

## §6. 项目铁律（不可违反）

### 工程铁律

1. **Agent 之间必须解耦**——禁止超载既有 Agent（如需新功能，优先新建）
2. **执行提示仅含需求、不含代码**——确保 Claude Code 风格一致
3. **auto-merge 永不修改交易规则/研判标准**——全部改动可经 review_log 回滚
4. **统一走 repo.py 网关**——禁止 SQL 散落业务代码
5. **缓存键必须按模型独立**——防止不同 embedding 维度混用
6. **本地算力受限场景走异步队列 + 定时 Worker**——不阻塞实时任务

### 设计哲学（sir 2026-08-14 拍板）

**专业性 × 交互友好 × 操作合理**——三位一体，缺一不可：
- **专业性**：逻辑严谨、可追溯、不造假
- **交互友好**：操作人看得懂、不用心算、门槛低
- **操作合理**：输出直接可执行，符合实际交易规则（如 A 股 100 股整数倍）

设计准则：
- LLM 输出"艺术判断"（如比例/方向），代码层负责换算为"可执行事实"（如股数/价格）
- 展示层永远给操作人最终可执行的数字，不给需要二次计算的中间值
- 边界情况自动处理（100 股取整、持仓为 0 跳过、数据缺失降级）
- 每个节点都有人工控制入口（可信任、可 override、不强制自动执行）
- 宁可少做不要做废——功能不成熟时不展示，不给操作人制造噪音

### 协作铁律

- **审核交付格式**（sir 强制）：最终回复必须给一段可直接复制给其他 agent 同步的总结话，包含 ① 发现问题 ② 做了什么操作 ③ 修改文件路径
- **审核文档格式**（sir 强制）：不要写文件，直接给自然语言描述五要素（文件在哪/做什么/为什么/预期/思考）
- **需求→产出模式**（sir 2026-08-19 拍板）：直接出 Claude Code 提示词，不走 v1→审核→v2；唯一例外——涉及交易规则/研判标准/红线边界时在提示词内加"红线约束"段

### 双闸门审核（执行指令必须过）

- **Gate 1 可执行性**：文件/路径/Schema 校验（行号 + 函数签名 + 返回结构实测）
- **Gate 2 严谨性**：规则一致性、回滚机制、审计轨迹、边界条件、降级路径

---

## §7. 工作约束（sir 偏好）

### 文档存放

- 长期记忆：`D:\self\.workbuddy\memory\MEMORY.md`（结构化索引）
- 工作日志：`D:\self\.workbuddy\memory\YYYY-MM-DD.md`（按日 append）
- 执行指令：`D:\self\*_执行指令*.md`（同主题同目录）
- 用户级偏好：`C:\Users\57388\.workbuddy\MEMORY.md`（跨项目）

### 知识检索

- 经验库调用仅返回 `precise / precise-query` 结果，**禁止 bulk-load** 全量记忆入上下文
- SQLite + FTS5 是当前检索实现

### 调用与回复

- 中文交流
- 五要素结构：什么/由谁做/规则/约束/预期
- 反感废话与过度抽象
- 阶段交付期：延后非计划优化，不打断既定序列
- auto-merge 不可改交易规则（红线）

### 工具与运行

- 本地 Python 3.14 在 `.venv`（D:\self\.venv\Scripts\python.exe）
- 后端：8000 端口（uvicorn 启动）
- Streamlit 旧前端：8501 端口
- React 新前端：5173 dev / 8000 dist
- Claude Code 在独立环境执行（**不与本机共享 pytest**）

---

## §8. 变更日志（本总览本身）

| 日期 | 变更 | 作者 |
|---|---|---|
| 2026-08-20 | 首版总览，合并 6 份日志 | Lark |
