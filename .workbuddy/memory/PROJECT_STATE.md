# D:\self 项目总览（Master Doc）

> **维护者**：Lark（云雀）· WorkBuddy SeniorDeveloper
> **建立时间**：2026-08-20
> **目的**：替代 7 天 daily log 散落状态，给 sir 提供一份**随时可查、结构化、可外部分享**的项目真相源。
> **存储位置**：① 本地 `D:\self\.workbuddy\memory\PROJECT_STATE.md`（git tracked）② 资料库同名副本（在线跨设备访问）

---

## 1. 🎯 项目使命与衡量标准

### 终极目标（sir 2026-08-14 拍板）

> **全智能化托管——从选股，到实际建仓，以及买入后全生命周期的持仓计划监控；每个节点都可以人工控制。sir 可以完全信任并执行。**

### 衡量标准

sir 每天打开系统，能**直接信任**系统给出的每个结论并照着执行，**不需要再自己算一遍或心怀疑虑**。

### 系统对应环节

| 环节 | 系统承载 | 人工控制点 |
|---|---|---|
| 选股 | DiscoverAgent 每日挖掘 → 候选池 | 候选可筛选/批量对话调整 |
| 建仓 | ScoreAgent 评级 → PositionAgent 分批方案 | 人工确认后实际执行建仓 |
| 买入后全生命周期监控 | MonitorAgent 盘中监控 + PortfolioSentinel 组合哨兵 + SellAgent 卖出决策 | 人工确认卖出/加减仓 |
| 复盘沉淀 | ReviewAgent 复盘 + agent_suggestions | 人工审核采纳后生效 |

---

## 2. 🏛️ 系统架构

### 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Streamlit（8501，**主**）+ React SPA（5173，过渡期并行） |
| 后端 | FastAPI（8000），Uvicorn |
| LLM | DeepSeek 双模型路由：DEEP=deepseek-chat / LIGHT=deepseek-v4-flash（structured.py:32） |
| Embedding | bge-m3（SiliconFlow 云端）→ 降级 bge-small-zh-v1.5（本地） |
| OCR | MiniMax-M3（云端）→ 降级 PaddleOCR（本地） |
| 数据源 | akshare（主）→ mairui（补）→ 自有 fallback（datasource/fallback.py） |
| 行情 | akshare/eastmoney + 新浪降级；hot_sectors 已稳定化（2026-08-19 落地） |
| 持久化 | TiDB 云端主库 + SQLite 本地冷备（sync_manager） |
| 任务调度 | scheduler/jobs.py（19 个 job 已注册，2026-08-19 末态） |
| 缓存 | cache.SimpleCache()（in-process，跨模块单例） |
| 断路器 | datasource/breaker.py，5min 窗口 |

### 8 业务 Agent + 2 辅助 Agent

| Agent | 职责 | 模型 |
|---|---|---|
| Discover | 每日潜力股挖掘：硬过滤 → LLM 初选 → 新闻核实 → LLM 终选 | DEEP×3 |
| Score | 五维打分 A/B/C（基本30/技术25/资金15/舆情15/行业15），**权威评级** | DEEP |
| Position | 分批建仓 3-4 档，总仓≤60%/单票≤30%，仅 B+ 可生成 | DEEP |
| Monitor | 盘中监控，每 3 分钟，输出 exit/reduce/hold + severity | LIGHT |
| Sell | 卖出决策 sell/partial/hold + 置信度 | DEEP |
| Review | 卖出复盘归因 + 教训 + 偏好回流 + agent_suggestions | DEEP |
| MarketCondition | 市况评分 0-50，决定候选池规模上限 | DEEP |
| MarketIntel | 5 维度研判：阶段定性/核心矛盾/风险偏好切换/量能信号/次日盯盘点 | DEEP |
| TrackVerify | 候选池 T+N 验证（统计胜率，不主动决策） | 纯统计 |
| BatchChat | 候选池批量对话（只读分析+调整留痕） | LIGHT |

### 协作铁律

1. **代码/LLM 强分离**：数据采集/硬过滤/数学计算/存储/缓存/调度/告警走代码；一切主观研判走 LLM
2. **评级权威单一化**：score.grade 是 A/B/C 来源，不兜底
3. **人工审核红线**：agent_suggestions 必须人工审核采纳
4. **事实为先不编造**：研判必须基于已落库事实
5. **调教集中在 `agent_prompts/` + 偏好档案 + 知识库**，代码侧只调接口不调 prompt

### 关键路径

- 后端：`backend/app/agents/`、`db/repo.py`、`api/routes.py`、`graph/graphs.py`、`datasource/akshare_source.py`
- 前端：`streamlit/pages/*.py`（13 页）+ `app.py` / `web/src/pages/*.tsx`（13 页）
- 知识库：`agent_prompts/`（global_base_prompt + knowledge/*.md + *_prompt.py）
- 同步：`sync_manager.py`（check/init/backup/restore），TiDB ↔ SQLite

---

## 3. 👤 sir 的设计哲学（永久生效）

**"专业性 × 交互友好 × 操作合理"三位一体**

| 维度 | 准则 |
|---|---|
| 专业性 | 逻辑严谨、可追溯、不造假 |
| 交互友好 | 操作人看得懂、不用心算、门槛低 |
| 操作合理 | 输出直接可执行，符合实际交易规则（如 A 股 100 股整数倍） |

**反面教材**：批次 2 初版设计 reduce_ratio 只显示 "33%"——实操中谁知道 33% 是多少股？是否满足 100 股整数倍？设计高大上但用不起来等于零。

**设计准则（所有后续执行指令必须遵循）**：

- LLM 输出"艺术判断"（比例/方向）→ 代码层换算为"可执行事实"（股数/价格）
- 展示层永远给**最终可执行的数字**，不给需要二次计算的中间值
- 边界情况自动处理（100 股取整、持仓为 0 跳过、数据缺失降级）
- 每个节点都有人工控制入口（可信任、可 override、不强制自动执行）
- 宁可少做不要做废——功能不成熟时不展示，不给操作人制造噪音

---

## 4. 🤝 协作模式（永久生效）

### 需求→产出流程（2026-08-19 拍板）

```
sir 提需求
  ↓
Lark 直接输出 Claude Code 提示词（仅需求+规则+约束，不含代码）
  ↓
Claude Code 按项目风格统一实现
  ↓
sir 验证
```

**唯一例外**：涉及**交易规则 / 研判标准 / 红线边界**时，在提示词内加一段"红线约束"标注，**不单独出审核文档**（除非 sir 明确要求）。

### 审核任务交付格式（2026-08-17 起永久生效）

完成后最终回复给**一段可直接复制给其他 agent 同步的总结**，一段话内包含：
1. 发现了什么问题
2. 做了什么操作
3. 修改后的文件在哪里（绝对路径）

### 交接工程师审核的固定格式（2026-08-17 起永久生效）

直接给一段自然语言描述，必须包含：
1. 文件在哪里（路径）
2. 文件是做什么的
3. 为什么这么做、原因是什么
4. 预期结果是什么
5. 方案背后的思考

---

## 5. ✅ 已完成批次（2026-08-13 → 2026-08-20）

| 批次 | 内容 | 状态 | 测试基线 |
|------|------|------|----------|
| **批次 1** | 移动止盈 + PortfolioSentinel | ✅ | 19/19 |
| **批次 2** | SellAgent reduce_ratio + 组合联动 | ✅ | 483 passed |
| **批次 3** | 选股反馈闭环 + 候选池表现摘要 | ✅ | 541 passed |
| **批次 4** | 盘前快筛 + 候选关联度 + 市况切换 | ✅ | 557 passed |
| **MarketIntel 深度化** | 8 层研判方法论注入 | ✅ | 567 passed |
| **批次 5** | 评级倒挂全档 + 市况方向命中率 | ✅ | 580 passed |
| **评级重做 A** | 六因子透明评分体系 | ✅ | 593 passed |
| **评级重做 B** | 因子卡展示层可视化 | ✅ | 577 non-AppTest passed |
| **评级重做 C** | 因子回测校准闭环 | ✅ | 已落地 |
| **板块数据稳定性优化** | sector_snapshot 表 + 5min 落库 + 断路器 + hot_sectors 改读 DB | ✅ | 634 passed |
| **TaskDrawer 升级** | 取消按钮 + Alert 强化 + 伪进度条 | ✅ | 8/8 抽验通过 |
| **6_交易复盘排序+徽章** | 4 下拉 + A→B→C 排序 + 可建仓徽章 | ✅ | 19 grep hits |

### 关键模型决策（2026-08-18 落地）

- **LIGHT 模型 = deepseek-v4-flash**（Monitor/Sentinel/Worker），3 次失败自动降级 DEEP
- **DEEP 模型 = deepseek-chat**（Discover/Score/Position/Sell/Review/MarketIntel + agent_chat）
- **统计独立**：按模型分离 light_stats / deep_stats 监控成本与命中率
- ⚠️ **代码陷阱**：`structured.py:32` 注释"LIGHT=Discover 初筛"是历史遗留——**实测 Discover 3 处全部 DEEP**，改代码勿被注释误导

### 选股准确率验证（2026-08-18）

时间窗 8/5~8/17，40 候选：
- T+3 胜率 **64.0%**（25 样本）/ +1.1% / 盈亏比 1.99 → 短期有效
- T+5 胜率 **50.0%**（14 样本）/ +0.66% / 盈亏比 1.38 → 退化为硬币
- T+10：0 样本，暂不可评

**核心发现**：评级 A/B/C 与实际涨跌几乎脱钩——T+3 B 档 69.2% vs C 档 63.6% 几乎一样；T+5 C 档(100%/+5.27%) 远好于 B 档(22.2%/-1.9%)。**已通过批次 5 扩展倒挂检测为全档位两两对比**。

---

## 6. 🚧 进行中（2026-08-20）

### v2 工单序列（React SPA 补完基线）

13 Streamlit 页 vs 13 React 页盘点：v1 已完成工单 1-6（账户条/候选池/评分/计划/持仓），v2 恢复缩水页：

| 工单 | 内容 | 缺口 | 优先级 |
|---|---|---|---|
| **10** | **ProfilePage 新建**（漏掉整页 104 行） | 后端 4 端点已建、api/profile.ts 4 函数齐、类型已定义，**仅缺页面** | 🔴 最高 |
| **9** | ReviewsPage 补全 | 缩水最严重（1409→214），旧版 6 模板 + Suggestions 待补 | 🔴 |
| **7** | OverviewPage Dashboard 主体卡片 | 工单 1 已 OK 账户条，主体待补 | 🟡 |
| **8** | HotMoneyPage 补全 | 150→394 差距：Profiles/胜率迭代/Agent 建议 | 🟡 |
| **11** | AgentChatPage 补全 | 165→321 差距：chat_learn/chat_rule | 🟢 |
| **12** | MarketIntelPage 深度化 | 180→215 差距：箱位/主线三分类/三维验证/催化传导链 | 🟢 |

**当前执行中**：工单 10 ProfilePage Claude Code 提示词已出（含 4 处 P0 待修正——`@/types/trade` 路径错、`putProfile` body 结构、`useEffect` 死循环、`ReloadOutlined` 未用）

### 待验证项（需运行时人工核验）

- 批次 4 盘前快筛 9:25 竞价数据核验
- MarketIntel 三数据源外网返回结构
- MarketIntel prompt 方法论（由 sir 另研）
- 批次 5 评级倒挂 8 条历史行回填验证
- 评级重做 A 六因子 LLM 输出确认
- 板块数据稳定性优化明早 9:00 scheduler 首跑确认
- TaskDrawer 升级 UI 视觉确认（取消按钮/Alert/Progress）
- 6_交易复盘 排序+徽章 UI 视觉确认
- 4400% 胜率问题：sir 在候选池首页仍见 4400%，已出防呆提示词（候选池首页 win_rate clamp [0,100]）

---

## 7. 📋 接下来规划

### 短期（本周）

1. **工单 10 ProfilePage** 完成 → 收尾 v1→v2 第一刀
2. **工单 9 ReviewsPage** 补完（缩水最严重）→ 复盘/选股闭环体验彻底对齐
3. **4400% 防呆落地**（重启 streamlit 后浏览器实测）
4. **v1→v2 进度盘点**：每完成一个工单更新 v1 已完成 vs v2 仍缺的对比

### 中期（本月）

5. **工单 7/8** Dashboard + 游资追踪 → Dashboard 主体回到 Streamlit v1 体验
6. **工单 11/12** AgentChat + MarketIntel 深度化
7. **市场研判方法论由 sir 注入**（MarketIntel prompt 是 v1 唯一未做的关键注入）
8. **T+10 准确率验证**：等 30+ 样本下中期结论

### 长期

9. **前端 A/B 档**：性能优化 + Vue3 试点（已移交其他 Agent，不在本链路跟踪）
10. **Streamlit → React 全量迁移**：v2 完成后逐步退役 Streamlit
11. **5 因子 → N 因子持续校准**：评分模型迭代
12. **市况方向命中率量化**：基于 T+1 沪深 300 回填，量化 MarketIntel 准确性

---

## 8. 👥 关键人物

| 角色 | 身份 | 职责 |
|---|---|---|
| **sir** | 项目 owner / lead（git lgh00544） | 需求拍板、最终验收、红线把关 |
| **Lark（云雀）** | WorkBuddy AI 助手（SeniorDeveloper） | 需求理解 + Claude Code 提示词 + 审核 |
| **Claude Code** | 执行 agent | 按项目风格统一实现代码 |
| **工程师 Agent** | 接力实施 | 接收审核后提示词，跑 Claude Code 落地 |
| **Reviewer**（其他 Agent） | 跨链路审查 | 工单 1-6 的前端 A/B 档移交方 |

---

## 9. 📁 关键资产路径

### 后端（FastAPI）

```
backend/app/
├── agents/                # 8 业务 + 2 辅助 Agent
├── api/routes.py          # 全部 REST 端点（含 profile 4 端点 L785/791/800/809）
├── db/
│   ├── models.py          # SQLAlchemy 模型
│   ├── repo.py            # 唯一数据网关
│   ├── init.sql           # MySQL DDL（最新 sector_snapshot 表已加）
│   └── session.py         # DB 连接 + 迁移
├── scheduler/jobs.py      # 19 个定时任务
├── services/              # market_view/candidate_tradeable/track_verify 等
├── datasource/            # akshare/mairui/fallback/breaker/http_client
├── cache.py               # SimpleCache 模块级单例
├── graph/                 # LangGraph 流程
└── main.py                # FastAPI 入口（含 /web 静态挂载）
```

### 前端

```
streamlit/                # 13 页（主，8501）
├── app.py
├── render.py              # 公共组件库（stat_cards/selection_stat_cards/fold_module）
├── api_client.py          # 后端 REST 薄封装
└── pages/0~13_*.py        # 中文文件名 13 页

web/                      # React SPA（过渡，5173）
├── src/
│   ├── App.tsx            # 路由（13 + 1 兜底）
│   ├── components/layout/ # AppShell/SideMenu/TopStatusBar/TaskDrawer
│   ├── pages/             # 13 个 React 页
│   ├── api/               # client.ts + 各 page API 封装
│   ├── store/             # tasksStore.ts 等
│   ├── types/index.ts     # 全局类型（TradeProfile L294 / KnowledgeItem / HotMoneyProfile 等）
│   └── hooks/             # useTaskSubmit 等
├── dist/                  # 构建产物（dev server 用 HMR）
└── package.json
```

### 知识与方法论

```
agent_prompts/            # 全部 LLM 调教集中点
├── global_base_prompt    # 全局基调
├── *_prompt.py           # 各 Agent 提示
└── knowledge/*.md        # 知识库（交易知识/板块等）

base_file/                # 静态素材（持仓/游资/方法论）
sync_manager.py           # TiDB ↔ SQLite 同步
```

### 本项目文档

```
D:\self\
├── .workbuddy/memory/    # 本会话长期记忆
│   ├── PROJECT_STATE.md  # ← 本文档
│   ├── MEMORY.md         # 滚动归档（按主题）
│   └── 2026-08-*.md      # 每日工作日志
├── *执行指令_*.md         # 各批次 Claude Code 提示词
├── *审核结论*.md          # 审核交付物
├── *_报告*.md             # 验证报告（如准确率报告）
└── ProfilePage_工单10_*.md  # 工单审核文档
```

---

## 10. ⚠️ 红线与陷阱（永久生效）

### 交易规则红线（auto-merge 永远不动）

- DiscoverAgent / ScoreAgent / SellAgent / PositionAgent 的判定逻辑
- agent_prompts/*.py 中的具体规则阈值
- candidate_tradeable.py::tradeable_view / ensure_tradeable
- 所有"研判标准表"（@property 标记为标准的字段）
- review_log / agent_suggestions 的人工采纳流程

### 代码陷阱（高发错点）

1. **`structured.py:32` 注释错误**：说"LIGHT=Discover 初筛"，实测全 DEEP——读代码看实测，不读注释
2. **`fetch_industry_spot` 缺 kind 参数**：未走断路器（已修，2026-08-19 加 kind="snapshot"）
3. **`tradeable_view().ensure_if_missing()`** 会在 dashboard 聚合时触发 ~900 次 DB 查询——首页聚合**禁止调 tradeable_view**，改用 `repo.list_candidate_tradeable(trade_date, limit=50)`
4. **win_rate 口径混乱**：`track_verify._group_stats` 返回 0-100 百分制；`_calc_stats` 返回 0-1 小数（line 95）——**展示层必须显式归一化**，否则会出 4400%
5. **`repo.list_candidate_tradeable` 返回字段**：实际是 `tier/price_zone/label/block_reason`（不是 `grade/reason/potential_flag`）
6. **`@/types/trade` 不存在**：类型在 `web/src/types/index.ts`（索引签名接口）
7. **akshare 反爬严**：高频调用会被 IP 限流，定时任务间隔 ≥5 分钟（板块数据稳定性优化后）
8. **100 股整数倍**：A 股所有股数计算必须用 `round_down_to_lot()` 兜底
9. **stale 数据兜底**：板块行情 ≥30 分钟未更新前端必须标"陈旧"，不可空着
10. **LLM 二次确认**：agent_suggestions 的 adopt() 涉及硬规则必须 confirm=True 二次确认

### 测试环境陷阱

- **AppTest 22 failed** 是**内存压力环境性超时**（与代码无关，不要追代码）
- **tsc --noEmit EXIT=0 零错不一定代表代码到位**——未使用 import/函数 tsc 不报警（见 TaskDrawer 升级首轮漏改）
- **必须 `grep -n <关键标识> 文件 | wc -l`** 实际核对落地数（不要只看 Claude Code 回报）

---

## 11. 📞 快速恢复上下文

Lark 读到本段可立即恢复 sir 当前位置与下一步：

```
当前：v2 工单 10 ProfilePage（Claude Code 提示词已出，4 处 P0 待修正）
下一步：等 sir 把修正后提示词交给工程师 → 落地 → 浏览器实测
然后：工单 9 ReviewsPage（缩水最严重）
```

下次新会话开始时：先读本文件，再读 `MEMORY.md`（滚动归档），再读最近 1-2 个 daily log，即可恢复完整上下文。
