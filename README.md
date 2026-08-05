# A 股全生命周期决策 Agent 系统（单机自部署）

> ## ⚠️ 监管红线（必读）
>
> **本系统是纯研究辅助工具，所有交易必须由人工执行。**
> 系统只输出：候选池、评分报告、分批建仓方案、持仓预警、卖出决策参考、交易复盘。
> **本系统不存在任何下单/撤单/自动交易代码**，也不会与任何券商接口对接。
> 买卖决策、委托下单、资金划转全部由你本人手工完成——请永远保留最终决策权。
> 系统产生的任何 Agent 优化建议同样**必须经人工审核确认后才生效**，禁止自动、无监督修改任何策略与参数。

## 系统架构

六个 Agent（LangGraph 有向图编排，DeepSeek 结构化输出，各自独立隔离的提示词文件）：

```
DiscoverAgent  每日全市场潜力挖掘（市况评分 → 硬过滤 → LLM 初选 → 新闻核实 → 数据富化 → LLM 终选 → 落库）
ScoreAgent     单股 0-100 多维打分（基本面/技术/资金/舆情/行业景气）
PositionAgent  分批建仓方案（4 档区间 + 资金配比 + 止损止盈参考）
MonitorAgent   持仓监控预警（交易时段每 3 分钟，实时行情 60s 内缓存，飞书推送，LLM 信号研判）
SellAgent      卖出决策参考（聚合监控信号/建仓计划/最新行情 → 持有/减仓/清仓建议）
ReviewAgent    卖出复盘（盈亏归因 + 经验教训 + 筛选偏好回流 + 全链路优化建议）
```

**设计原则**：股票交易是概率博弈与市场艺术，不是可精确求解的科学。
- 代码只承担：刚性黑名单过滤（ST/退市/停牌/流动性，客观事实）、数据采集、指标**纯数学计算**、存储、缓存、调度、接口、告警推送。
- **所有主观研判**（趋势、估值、舆情、支撑压力、买卖时机、风险等级、评分、卖出决策）**全部交由 LLM 完成**，程序只输出原始素材。
- 交易规则与研判标准全部集中在项目根 `agent_prompts/` 独立文件，可直接改 Prompt 深度调教。

## 快速开始

### 方式一：本机开发模式（推荐先跑通）

需要 Python 3.11+（本项目在 3.14 验证通过）。

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt

# 2. 配置密钥（必填 DEEPSEEK_API_KEY，可选 SILICONFLOW_API_KEY / FEISHU_WEBHOOK_URL）
cp .env.example .env
#   编辑 .env 填写 DEEPSEEK_API_KEY

# 3. 跑测试（过滤/指标/LLM 解析/状态流转/DB/页面渲染全绿）
.venv/Scripts/python -m pytest backend/tests

# 4. 全链路冒烟测试（真实 akshare + 真实 DeepSeek）
.venv/Scripts/python backend/scripts/smoke_test.py

# 5. 启动后端 API + 定时任务
.venv/Scripts/python backend/scripts/dev_run.py

# 6. 启动 Streamlit 面板（另开终端）
.venv/Scripts/streamlit run streamlit/app.py
```

默认**全本地文件化存储**，无需任何外部服务：
- 业务数据 → SQLite 单文件 `data/dev.db`（迁移系统直接复制该目录即可）
- 私有知识向量库 → 本地文件模式 Qdrant `data/qdrant_storage/`
- LLM 结果缓存 → 进程内存（重启自动清空）

### 方式二：Docker 一键部署（两服务）

需要 Docker Desktop。backend + streamlit 两服务（存储同样走本地文件 + `./data` 数据卷）：

```bash
cp .env.example .env   # 填写密钥，保持默认本地存储开关即可
docker compose up -d --build
# 面板 http://localhost:8501   API http://localhost:8000
```

**可选外部服务模式**：如需 MySQL/Redis/Qdrant server，在 `.env` 中把
`DB_BACKEND=mysql`、`CACHE_BACKEND=redis`、`QDRANT_MODE=server` 并填写对应连接参数。
存储层已做抽象接口封装（`repo.py` / `cache.py` / `vector_store.py` 三网关），业务代码不直接接触 SQLite/Qdrant 原生调用，切换存储只需改配置。

## 使用流程

1. **工作日 16:10** 自动运行 DiscoverAgent + ScoreAgent，生成当日候选池与评分（也可面板手动触发）。
2. 在「评分报告」查看五维评分与风险清单 → 在「建仓计划」生成分批方案（纯建议）。
3. **人工执行建仓后**，在「持仓监控」录入持仓与成交明细（支持**券商持仓截图 OCR 自动识别**，见下方小贴士）。
4. 交易时段（9:30-11:30 / 13:00-15:00）每 3 分钟 MonitorAgent 自动研判（实时行情 60 秒内缓存，信号基于当次最新价计算），触发预警推送飞书（未配置则落库告警日志）；收盘后 15:00-15:30 做收盘数据校验；「持仓监控」页可随时点「立即刷新监控」全量手动触发。
5. 盘中可按需点击「生成卖出决策」，SellAgent 独立研判输出 持有/减仓/清仓 参考（**仅供参考，卖出必须人工执行**）。
6. **人工卖出后**在「持仓监控」记录卖出 → 自动触发 ReviewAgent 复盘：①盈亏归因与经验教训；②建议采纳后可一键写入「个人交易偏好」档案；③全链路 Agent 优化建议进入「待审核」区。
7. 偏好档案在「个人交易偏好」页可视化编辑、导入/导出，保存立即生效，并自动注入后续所有 Agent 的 LLM 调用。

## 每日候选池筛选机制

> 本节描述「每日候选池」从全市场 5000+ 只股票到最终落库的真实生成流程，与当前代码实现一一对应。
> 核心分工：**代码只做客观硬过滤与数据打包，所有主观选股判断全部由 LLM 完成**（DeepSeek 结构化输出）。

### 一、完整筛选流程（按执行顺序）

**第 0 步：任务触发（调度层）**

- 工作日（周一至周五）16:10 由 APScheduler 自动触发（`backend/app/scheduler/jobs.py` 的 `daily_discover_job`，北京时间 Asia/Shanghai；错过后 1 小时内补跑）；也可在 Streamlit 首页点击「手动触发每日挖掘」（`POST /api/jobs/discover/run`）。
- 运行前校验当日是否为交易日（akshare 交易日历，`_is_trading_day`；日历拉取失败时按工作日放行），并用任务锁防止与手动触发重叠。
- 触发后执行 `run_daily_pipeline`（`backend/app/graph/router.py`）：先跑完整 Discover 图，随后对落库的候选**自动执行 ScoreAgent 打分**——候选 ≥5 只自动切换**并行模式**（线程池并发打分，同一 prompt/schema 结果与串行一致，提速不降质），<5 只保持单 Agent 串行。

**第 1 步：全市场快照 + 停牌名单（数据采集层，代码硬规则）**

- 拉取全市场实时快照（东财接口优先，失败自动降级新浪，`backend/app/datasource/akshare_source.py` 的 `fetch_spot_universe`，600 秒缓存、超时/退避重试）。
- 拉取当日停牌名单（`fetch_suspended`；停牌表拉取失败不阻塞主流程）。

**第 2 步：刚性硬过滤 + 客观排序（`backend/app/agents/discover.py` 的 `apply_hard_filter`，纯函数）**

- 代码硬规则（客观事实，无博弈空间）：①名称含 `ST`/`退` 的股票剔除；②成交额低于阈值（默认 1 亿元）的剔除；③当日停牌名单内的剔除。
- 剩余股票**按成交额降序客观排序**，取前 300 只（默认 `discover_top_n`）组成「初筛表」——此排序是客观数据操作，不含任何主观判断。

**第 3 步：LLM 初选（研判层，`discover.py` 的 `llm_shortlist` 节点）**

- 将初筛表压缩为文本（13 列原始数值：代码/名称/现价/涨跌幅/成交额/量比/换手率/动态PE/PB/总市值/流通市值/60日涨跌幅/年初至今涨跌幅，见 `_TABLE_COLS`），并附大盘上下文（上证指数近 5 日 + 行业板块涨幅/跌幅前 5）。
- 调用 DeepSeek（system prompt 为 `agent_prompts/discover_prompt.py` 的 `SYSTEM_PROMPT`；json_object 结构化输出 + pydantic 校验，失败最多重试 3 次），按其中的选股标准从表中挑选波段潜力股，输出**候选理由 + 风险初判**，通常 5-15 只、宁缺毋滥（数量标准在 Prompt 中约定，非代码固定）。
- 初选结果按「当日」缓存 24 小时（同日重复运行不重复调用 LLM）。

**第 4 步：候选股新闻核实（数据采集层，`discover.py` 的 `enrich_news` 节点）**

- 对每只初选候选拉取最新公告新闻，存入 `news_article` 表并写入向量库索引；再对该股做语义检索取相关度最高的 5 条（`search_related`，top_k=5）作为研判素材；单只股票新闻失败不阻塞整体。

**第 5 步：LLM 最终确认 + 落库（研判层，`discover.py` 的 `llm_final` 节点）**

- 第二次调用 DeepSeek：把初选结果（13 列数据表）+ 每只候选的新闻标题摘要打包（`build_final_prompt`），由 LLM 剔除新闻中暴露明确利空的标的，输出最终候选清单。
- 按排名写入 `stock_candidate` 表（同一股票同日仅一条，重复运行覆盖更新）：候选理由、风险初判、当日行情快照全部落库。
- 随后 `run_daily_pipeline` 自动对每只候选依次执行 ScoreAgent（五维 0-100 打分 + A/B/C 分级）——**分级与评分属于 ScoreAgent 的输出**，在「评分报告」页查看，Discover 阶段不产生分级。

### 二、三层筛选明细

| 层级 | 环节 | 规则与默认值 | 修改位置 |
|---|---|---|---|
| 第一层：前置刚性过滤 | 名称 ST/退 剔除 | 名称含 `ST` 或 `退` 即剔除（代码硬规则，客观事实） | `apply_hard_filter`（不建议改） |
| | 流动性过滤 | 成交额 ≥ 1 亿元（默认） | `.env` 的 `MIN_AMOUNT`，重启后端 |
| | 停牌剔除 | 当日停牌名单内剔除（数据源自动） | 无需配置 |
| | 送入 LLM 的数量 | 按成交额降序取前 300 只（默认） | `.env` 的 `DISCOVER_TOP_N`，重启后端 |
| 第二层：量化初筛排序 | 排序规则 | 按成交额降序（客观数据排序，非主观打分） | `apply_hard_filter`（不建议改） |
| | 量化因子 | **无独立打分权重层**——量比/换手率/PE/PB/市值/60日涨跌幅等 13 列只作为原始数值随表交给 LLM 研判，代码不设权重、不设阈值 | 如需增删字段：`discover.py` 的 `_TABLE_COLS` |
| 第三层：LLM 深度研判 | 输入数据 | 初筛表 13 列数值 + 上证指数近 5 日 + 行业板块涨跌前 5 + 每只候选新闻标题摘要 | — |
| | 研判标准 | `agent_prompts/discover_prompt.py` 的 `SYSTEM_PROMPT`（量能/趋势/基本面/行业热度/风险控制五条），另叠加全局基线 `agent_prompts/global_base_prompt.md`（最先加载） | 直接编辑 Prompt 文本 |
| | 偏好与知识注入 | 自动注入「个人交易偏好」档案 + 按标签检索的私有知识库条目（top_k=5）+ `HARD_RULES` 硬性规则 | 见下方「可调教入口」 |
| | 输出数量 | 通常 5-15 只、宁缺毋滥（Prompt 约定，非代码固定） | 编辑 `SYSTEM_PROMPT` |
| | 分级标准 | **A/B/C 分级不在此阶段**——由 ScoreAgent 打分时输出（0-100 分 + 等级） | `agent_prompts/score_prompt.py` |

### 三、可调教入口汇总

| 想调什么 | 去哪里改 | 生效方式 |
|---|---|---|
| 最低成交额 / 送入 LLM 的股票数量 | `.env` 的 `MIN_AMOUNT` / `DISCOVER_TOP_N` | 重启后端 |
| 选股理念（量能/趋势/估值偏好、回避的形态、输出数量） | `agent_prompts/discover_prompt.py`（初选标准与新闻最终确认要求） | 重启后端（版本升级前请自行备份） |
| 全局交易哲学与技术分析标准 | `agent_prompts/global_base_prompt.md` | 实时读取，保存即生效 |
| 板块偏好 / 黑名单避雷 | Streamlit「个人交易偏好」页 → 行业黑白名单字段 | 保存立即生效（自动注入所有 Agent） |
| 私有战法 / 经验条目 | Streamlit「交易知识库」页（按适用 Agent 打标签） | 保存立即生效（向量检索注入，当日缓存自动失效） |
| 硬性底线（LLM 不得放宽的规则） | `backend/app/agents/common.py` 的 `HARD_RULES` 列表（当前为空，内有示例注释） | 改代码重启 |
| 量化因子列（送哪些数值给 LLM） | `backend/app/agents/discover.py` 的 `_TABLE_COLS` | 改代码重启 |
| 双模型路由与参数（flash/chat 模型 ID、max_tokens、reasoning_effort） | `.env` 的 `DEEPSEEK_DEFAULT_MODEL` / `DEEPSEEK_REASONING_MODEL` / `DEEPSEEK_FLASH_MAX_TOKENS` / `LLM_MAX_TOKENS` / `REASONING_EFFORT` | 重启后端 |
| LLM 调用统计（当日请求/缓存命中率/模型分布） | 首页「系统运行状态」→ LLM 运行统计模块 | 手动刷新，实时 |

## 每日候选池筛选机制 v2.0 补强

> 本节为 v2.0 增量升级（2026-08-04），在上一节 v1.0 机制基础上叠加，v1.0 原文保留在上节作对照。
> 不重构、不破坏既有五 Agent 体系 / 独立 Prompt 机制 / 存储抽象层；**代码仍只做客观数据采集与硬过滤，所有主观研判全部交给 LLM**，新增规则全部可经 Prompt / 配置 / 知识库持续调教，不写死黑盒。

### 一、硬性规则补强（HARD_RULES 四条强制底线，LLM 无权突破）

写入 `backend/app/agents/common.py` 的 `HARD_RULES`（已从 v1.0 的空列表改为四条全中文规则），以最高优先级注入所有 Agent 的 system prompt：

| 规则 | 内容 | 约束性质 |
|---|---|---|
| 板块权限硬约束 | 创业板（300 开头）仅做分析**不推荐买入**；科创板（688 开头）、北交所（8/4 开头）**不纳入候选池** | 强制 |
| 派发期一票否决 | 5 日涨幅 ≥15% + 主力资金净流出 + 换手率 ≥12% + 距 52 周高点 ≤10%，四者同时满足直接排除 | 强制（一票否决） |
| 一日游避雷 | 板块共振个股 <3 只，或盘中涨幅收窄 ≥0.5%，不纳入候选池 | 强制 |
| 超买否决 | 5 日累计涨幅 ≥15% 的标的**不得作建仓推荐**（关注类型不得为「低吸/突破」） | 强制 |

> 阈值（15%/12%/10%/0.5%/3只）均写在 `HARD_RULES` 文本中，可直接编辑调参，**LLM 无权放宽**。

### 二、研判知识体系补强（Prompt 注入，代码零新增判断）

- **全局基线 `agent_prompts/global_base_prompt.md` 追加**：
  - K168 三维分析标准：每只候选必须给出宏观/中观/微观三维结论，**三维矛盾必须显式提示风险**；
  - K189 主力骗局识别：七大骗局对照（卖点/砸盘/洗盘/试盘/诱多/对倒/出货），任一疑点即视为风险项。
- **DiscoverAgent Prompt（`agent_prompts/discover_prompt.py`）追加【v2.0 执行标准】**：
  - 技术研判覆盖：威科夫 5 阶段 / 量价 7 条 / 6 大 K 线形态 / 4 大谐波形态，**至少两套体系交叉验证**；
  - 估值研判：PE / PB / PEG / 市值对照**行业均值**（行业由数据层采集，代码不做估值打分）；
  - 先验板块共振：先判板块共振强度，再判个股，防止个股孤军。

### 三、输出格式强制升级（DiscoverCandidate Schema v2.0）

`backend/app/agents/schemas.py` 的 `DiscoverCandidate` 强制携带（pydantic 校验，缺失即重试）：

| 字段 | 约束 |
|---|---|
| `stock_code` + `stock_name` | 代码与股票全称**成对输出**，杜绝缺码 |
| `confidence_tier` + `confidence_pct` | K202 信心度档位：`谨慎观察` / `建议关注` / `强烈推荐`（0-100 百分比） |
| `macro_view` / `meso_view` / `micro_view` | 宏观/中观/微观三维分析结论 |
| `volume_analysis` | 量能判定（主力流入流出定性） |
| `risks` | 核心风险清单，**至少 2 项**（不足 2 项校验失败重试） |
| `focus_type` | 关注类型：`低吸` / `突破` / `观察` |
| `tech_view` | 技术面研判（可选字段）：威科夫/量价/K线形态/谐波至少两套体系交叉验证，标注体系名称与支撑依据 |
| `price_levels` | 关键价位（可选字段）：支撑位 / 压力位 / 建议关注区间 |
| `position_hint` | 操作建议（可选字段）：关注类型 + 参考仓位建议 |

> 初选节点（`llm_shortlist`）输出即含以上字段；缓存键升级为 `shortlist:v2:{date}` / `final:v2:{date}`，旧版 v1 JSON 不会复用。
> 三个可选字段默认 `""`：旧缓存/旧数据不回填校验不破坏，展示层自动降级（取 `meso_view` 兜底或提示重新触发挖掘）。

### 四、数据层增量采集（代码只采集原始数据，不做任何打分）

`llm_final` 最终确认前新增 `enrich_data` 节点，仅对**初选入围股**（非全市场）逐股增量采集，单项失败自动降级为缺失不阻塞：

- **资金结构**：超大单 / 大单 / 中单 / 小单净流入（当日）+ 主力净流入累计 3 / 5 / 10 日（`tail(3/5/10)` 纯求和）；
- **股东面**：股东户数环比增减比例（`stock_zh_a_gdhs_detail_em`）+ 机构持股占流通股比例（`stock_institute_hold` 全市场一次拉取建映射复用，6 小时缓存）；
- **52 周区间**：52 周最高 / 最低价 + 距高点幅度（从日 K 纯数学计算）；
- **盘中涨幅收窄**：`(当日最高 − 收盘) / 昨收 × 100%`（16:10 运行时当日分时已不可得，用日 K 近似）；
- **行业归属**：东财个股资料（item/value 两列解析）。

增量 13 列随最终数据表一并打包给 LLM（`_final_table_text`），金额列统一格式化（元 → 亿/万）。

### 五、调度前置：市况评分 → 候选池规模上限（市况驱动）

Discover 图新增首个节点 `market_condition`（`START → market_condition → hard_filter → llm_shortlist → enrich_news → enrich_data → llm_final`）：

1. **代码打包市况原始数据**（纯客观）：上证近 60 日区间位置 + 近 5 日涨跌、行业板块涨跌分布（前 5 / 后 5）、大盘资金流、全市场涨跌家数分布（含涨幅 ≥9.5% / 跌幅 ≤-9.5% 客观计数）；
2. **LLM 五维打分**（`agent_prompts/market_prompt.py`，`MarketConditionOutput` schema 校验）：指数位置 / 板块结构 / 资金方向 / 情绪指标 / 风险维度，各 0-10 分，共 0-50 分（数据不可用给保守 5 分）；
3. **代码纯算术落库**：总分求和（非主观）→ `repo.upsert_market_condition` 写入 `market_condition` 表；
4. **人工档位映射**（`config.market_band_info`，`.env` 可用 `MARKET_CAP_BANDS` JSON 覆盖）：

| 总分 | 档位 | 候选池规模上限 |
|---|---|---|
| 0-20 | 防御期 | 5 只 |
| 21-35 | 过渡期 | 10 只 |
| 36-45 | 温和期 | 15 只 |
| 46-50 | 强势期 | 20 只 |

5. `llm_final` 按上限**客观截断**最终候选数量（`output.candidates[:cap]`）；上限值随市况综述注入 Prompt，LLM 知道「上限 N 只、宁缺毋滥」；
6. 首页「今日操作提示」顶部同步展示：市况评分 X 分（档位，候选池上限 N 只）+ 五维分项 + LLM 综述（`GET /api/market-condition`）。

> 降级：市况接口拉取失败 / LLM 打分失败时，按默认档位（上限 20）放行，不阻塞每日挖掘。

### 六、可调教入口汇总（v2.0 新增）

| 想调什么 | 去哪里改 | 生效方式 |
|---|---|---|
| 四条硬性底线阈值（15%/12%/0.5%/共振3只等） | `backend/app/agents/common.py` 的 `HARD_RULES` 文本 | 改代码重启 |
| 市况五维打分标准 / 评分纪律 | `agent_prompts/market_prompt.py` | 重启后端 |
| 市况档位 → 候选池上限映射 | `.env` 的 `MARKET_CAP_BANDS`（JSON，留空用默认四档） | 重启后端 |
| 技术研判覆盖（威科夫/量价/K线/谐波）与估值对照标准 | `agent_prompts/discover_prompt.py` 的【v2.0 执行标准】 | 重启后端 |
| 三维分析与骗局识别标准 | `agent_prompts/global_base_prompt.md`（K168 / K189） | 实时读取，保存即生效 |
| 增量数据列（资金结构/股东面/52周区间等） | `backend/app/agents/discover.py` 的 `_ENRICH_COLS`（数据采集，不做打分） | 改代码重启 |
| 输出强制字段（信心度档位/三维分析/风险≥2项/关注类型） | `backend/app/agents/schemas.py` 的 `DiscoverCandidate` | 改代码重启（升级后缓存键版本化自动失效） |
| 双模型路由与 KV 缓存参数（flash/chat 模型 ID、token 上限、推理强度） | `.env` 的 `DEEPSEEK_DEFAULT_MODEL` / `DEEPSEEK_REASONING_MODEL` / `DEEPSEEK_FLASH_MAX_TOKENS` / `LLM_MAX_TOKENS` / `REASONING_EFFORT` | 重启后端（结果缓存按模型隔离，版本指纹变更自动失效） |

## 每日候选池页面（评级筛选 + 分模块详情）

「每日候选池」页为 DiscoverAgent 输出主入口，纯展示层（评级映射/排序/颜色仅为字段转换，不含任何二次判断）：

- **手动触发**：页面顶部「手动触发每日挖掘」按钮异步提交（返回即走，不阻塞页面），任务状态区显示执行进度；
- **日期选择**：按日期查看任意历史候选池（默认最新）；同日同股仅展示最新版本（数据库层面 `UNIQUE(code,date)` 保证，前端二次去重防御）；
- **评级筛选与排序**：全部 / 可建仓 A+B / 仅观察 C（默认全部；A=强烈推荐 / B=建议关注 / C=谨慎观察，为 LLM 信心度档位的纯展示映射）；列表按 A→B→C 置顶排序，组内按 LLM 优先级 rank 升序；
- **主表**：评级（A 红 / B 橙 / C 蓝颜色区分）+ 股票（代码+全称）+ 一句话核心理由 + 生成时间；
- **详情分模块**（点击展开）：技术面研判（标注所用技术体系与支撑依据）/ 量价与资金结论 / 关键价位（支撑/压力/建议关注区间）/ 核心风险点（≥2 项）/ 操作建议（关注类型+参考仓位）；三维分析、风险初判折叠查看；原始 JSON 一律折叠（「查看原始数据」）；
- **生成建仓方案**：单股异步提交 PositionAgent，完成后顶部任务状态区提示。

## 全局顶部状态栏与市场概览

### 顶部常驻状态栏（所有页面固定显示，不随滚动消失）

页面最顶部固定常驻信息栏，三栏布局（左=北京时间，每分钟自动刷新；中=账户核心资产；右=三大指数）：

- **账户核心资产 5 项**：总资产 / 总持仓成本 / 总盈亏（金额+比例）/ 整体仓位占比 / 可用资金；盈亏正红负绿（A 股习惯）；
- **账户双数据路径**（`holding_view.build_account_summary`）：
  - **有账户基准**（OCR 识别券商持仓截图后人工确认保存）：总资产/可用资金/仓位占比用券商真实值，盈亏与成本仍按持仓+最新市价实时计算；
  - **无账户基准**：总资产 = 基准本金（`TOTAL_CAPITAL`）+ Σ持仓盈亏（**估算**，界面标注「估算」标签）；
  - 行情整体失败且有持仓时：市价相关项显示「—」并标注 `quote_error`，**不伪造 0 值**；无持仓时总资产=基准本金、仓位 0%；
- **三大指数**：上证指数 / 深证成指 / 创业板指（名称 + 最新点位 + 涨跌幅，涨跌颜色区分），标注更新时间，60 秒缓存；接口失败自动降级新浪源；
- **失败降级**：接口失败显示上一次成功缓存值并标注「上次数据」，无缓存显示「数据加载中」，**不向页面抛原始报错**；
- **详情展开**：点「账户明细 ▼」「指数详情 ▼」展开详细数值与口径说明。

### 首页「今日热门板块」看板

位于「今日候选与建仓机会」模块上方，当日涨幅前 5 行业板块（客观排序，非主观筛选）：

- 每条含：板块名称 / 板块涨幅（正红负绿）/ 领涨龙头（代码+名称，来自板块行情「领涨股票」→ 全市场快照名称匹配代码，匹配失败降级拉该板块成分股按涨幅取最大）；
- 默认每 30 分钟自动更新（`st.fragment(run_every="30m")`），顶部「手动刷新全部数据」可立即刷新；
- **点击「筛选该行业」**跳转「每日候选池」页并按该行业筛选当日候选股（详情行业字段子串匹配），支持「清除行业筛选」返回全量。

### 新增后端接口（只读视图，不触任何研判链路）

| 接口 | 说明 |
|---|---|
| `GET /api/market/indices` | 三大指数实时行情（60s 缓存，东财→新浪降级） |
| `GET /api/market/hot-sectors` | 涨幅前 5 行业板块 + 领涨龙头 |
| `GET /api/account/summary` | 账户摘要（双数据路径，失败返回 `quote_error` 不抛 500） |
| `POST /api/account/baseline` | 保存账户基准（`account_baseline` 表，每次插入保留历史，取最新一条生效） |

## 持仓监控列表（自动去重合并 + 实时行情）

「持仓监控」页顶部持仓列表在进入页面时自动加载全量实时行情并展示：

- **自动去重合并（仅展示层，数据库原始记录完整保留，不删除任何数据）**：同一股票代码的多条持仓自动合并展示——同建仓日期的重复录入仅保留录入时间最晚一条，其余在「查看历史持仓明细」中标注「重复录入（已自动忽略）」；不同日期多笔建仓合并为**加权平均成本 + 总股数**，操作（监控/卖出决策/记录卖出）绑定「当前有效」持仓（建仓日期最新、录入时间最晚）；
- **实时行情自动填充**：拉取每只标的最新价，实时计算当前市值、持仓盈亏金额、持仓盈亏比例；行情获取失败时字段显示「—」并给出警示，不显示 0 值或空值；
- **参考止损/止盈自动补全**：取值顺序 = 手动设置 → 关联建仓计划 → 默认风控比例（`DEFAULT_STOP_LOSS_PCT`/`DEFAULT_TAKE_PROFIT_PCT`，.env 可调；仅展示参考，不触发任何判断）；**目标仓位%** = 当前市值 ÷ 基准本金（`TOTAL_CAPITAL`）；
- **行情刷新**：表格顶部标注「行情最后更新时间」（精确到分钟），可点击「手动刷新行情」重算；
- **展示规则**：股票强制「代码 + 名称」成对显示；盈亏金额/盈亏比例正收益红、负收益绿（A 股习惯，适配深色主题）；每只持仓可展开「查看历史持仓明细」查看每笔买入的原始记录（含被忽略的重复录入）。

## 持仓截图 OCR 识别（快捷录入）

在「持仓监控」页上传券商持仓截图，自动识别 **股票代码 + 股票全称、持仓数量、持仓成本价、当前市价、持仓盈亏金额、持仓盈亏比例**，整理为标准结构化表格供人工核对后批量创建持仓；识别到券商账户汇总区域时**同时提取总资产 / 可用资金 / 整体仓位比例**，预填「账户基准」表单。

- **识别结果不直接入库**：必须先人工核对修正字段，点击【确认创建持仓】才写入 `holding` 表，杜绝识别错误引发监控异常；
- **账户基准人工确认红线**：OCR 提取的账户汇总字段（总资产/可用资金/仓位比例）仅预填表单，点击【保存账户基准（人工确认无误后落库）】才写入 `account_baseline` 表，此后顶部状态栏总资产/可用资金/仓位占比改用券商真实值（不再估算）；OCR 未识别到账户信息则不显示该区块，绝不编造数值；
- **纯文字识别工具**：不做任何行情研判/交易决策，市场研判仍全部由 LLM 完成；截图仅内存/临时文件处理，识别完毕自动清理，不长期存储；
- **开关**：`.env` 设置 `OCR_ENABLE=true/false`（默认 false），关闭后页面自动提示并仅保留手动录入；
- **引擎选择**：默认优先 MiniMax M3 云端多模态识别（准确率更高），失败/无结果自动回退本地 PaddleOCR（离线兜底，不阻塞录入）；`MINIMAX_OCR_ENABLE=false` 可强制仅用本地引擎（详见下方章节）；
- **结构化输出**：识别结果自动整理为结构化表格（股票代码 + 股票全称、持仓数量、持仓成本价、当前市价、持仓盈亏金额、持仓盈亏比例），默认只展示表格；「查看原始识别内容」折叠展开原文；表格内可直接点击修改任意字段，缺失字段红色标注并提示「需补全」；
- **模型档位**：`OCR_MODEL_LEVEL=light`（默认，PP-OCRv4 轻量模型，体积约 20-50MB，首次识别自动下载并缓存于 `~/.paddlex/`）；追求更高精度可改 `full` 完整模型（体积约 150MB 级，安装占用更大）；
- **依赖**：CPU 运行装 `paddleocr + onnxruntime` 即可（Python 3.14 已验证；Python 3.11/3.12 或 Docker 可另装 `paddlepaddle` 提性能，GPU 则装 `paddlepaddle-gpu` 并设 `OCR_DEVICE=gpu`）；识别截图仅在临时文件处理，识别完毕立即删除，不持久化存储。

**截图识别使用小贴士**：

- 尽量保证截图清晰：建议直接用券商 App「持仓页」整页截图，避免拍屏、拉伸、低分辨率截图；
- 避开弹窗遮挡：识别前关闭涨跌弹窗、开户引导、新股申购提示等悬浮层，防止遮住代码/数量列；
- 截图只需包含持仓表格区域即可（代码/名称/数量/成本/市价几列齐全）；
- 识别缺失/错误的字段会在预览中标注，手动补全修正后保存即可，无需重新截图。

## MiniMax M3 可选多模态能力（默认开启云端 OCR，一键可关）

MiniMax M3 作为**可选多模态引擎**接入系统，用于持仓截图 OCR 识别（云端多模态识别，准确率远高于本地文本 OCR），
并为 K 线图形态研判 / 技术形态识别 / 财报截图解析等后续多模态场景预留了统一调用接口。

- **定位边界**：仅承担视觉专项任务，**不参与五 Agent 选股/建仓/监控等核心业务研判**（主模型仍为 DeepSeek）；
- **总开关**：`MINIMAX_ENABLE=false` 时系统行为与原版本完全一致——不加载任何依赖、不发起任何请求（`.env.example` 默认 false）；
- **配置项**（`.env`，密钥仅环境变量管理，更换只改这里）：
  - `MINIMAX_ENABLE=false|true` —— 多模态能力总开关；
  - `MINIMAX_API_KEY=<密钥>` —— MiniMax API 密钥（平台 platform.minimaxi.com 获取，严禁硬编码/提交版本库）；
  - `MINIMAX_BASE_URL=https://api.minimax.chat/v1` —— 官方 OpenAI 兼容端点（国际站 `api.minimaxi.com/v1`）；
  - `MINIMAX_MODEL=MiniMax-M3` —— 模型 ID（官方 ID 含连字符，勿去掉）；
  - `MINIMAX_OCR_ENABLE=true|false` —— 默认 `true`（云端优先）：持仓截图默认先走 MiniMax 云端识别，
    失败/无结果自动回退本地 PaddleOCR，不阻塞录入；设为 `false` 强制仅用本地 PaddleOCR（离线，零 API 消耗）。
- **OCR 引擎抽象**：持仓截图识别为双引擎链——MiniMax 云端（默认优先）→ 本地 PaddleOCR（兜底）；
  两引擎输出字段完全一致（股票代码/股票全称/持仓数量/持仓成本价/当前市价/持仓盈亏金额/持仓盈亏比例），
  识别结果强制整理为结构化表格，**不输出零散原文**，前端录入流程不变；
- **调用优化**：同一张截图 30 分钟内临时缓存识别结果，不重复识别、不重复消耗 API 调用次数；
- **前端交互**：默认仅展示结构化持仓表格；「查看原始识别内容」折叠按钮展开模型原文（排查用）；
  表格支持 inline 编辑任意字段；识别失败/字段缺失条目红色标注并提示「需补全」；
  识别结果**必须人工核对确认后才批量创建持仓，禁止自动落库**；
- **扩展预留**：多模态调用层为通用接口（图片 + 文本指令 → 文本输出），后续 K 线图/财报截图等场景
  直接复用，无需重构调用框架；识别结果为结构化字段，可落库参与后续 Agent 研判；
- **实现方式**：业务代码不依赖 MiniMax 原生 SDK，更换多模态模型只需新增实现类并修改工厂装配
  （`backend/app/services/multimodal.py`）。

## 个性化调教（三层体系 + 统一调教接口）

本系统的交易哲学、选股标准、仓位风格、预警偏好**全部集中且可调**，不写死在业务代码中。
调教方式分三层，从轻到重，可按需组合使用：

### 层级 1：轻量可视化调教（推荐入门，即时生效）

**入口**：Streamlit 面板 →「个人交易偏好」页（`sys_trade_profile` 表，前端可视化编辑，无需改代码）。

**可配置内容清单**：

| 字段 | 说明 | 示例值 |
|---|---|---|
| 持仓周期偏好 | 你的波段持仓周期与风格 | `波段趋势，持仓数周至数月` |
| 市值偏好 | 偏好标的市值区间 | `中大盘为主（100亿以上）` |
| 行业黑白名单 | 白名单=优先关注板块；黑名单=回避板块 | `{"白名单": ["半导体"], "黑名单": ["房地产"]}` |
| 单票仓位上限 | 单只股票占总资金的最大比例（%） | `40` |
| 整体仓位上限 | 全部持仓合计占总资金的最大比例（%） | `80` |
| 选股倾向 | 低吸为主 / 突破跟进等风格 | `回踩低吸为主，突破确认辅助` |
| 风险规避项 | 重点规避的风险类型（立案/商誉/减持等） | `["立案", "商誉减值", "大额减持"]` |

字段可自由增删（页面支持"新增字段"），保存**立即生效**（偏好版本号使 LLM 缓存自动失效）。

**机制**：每次 LLM 调用时自动加载 `sys_trade_profile` 内容并注入全部 Agent 的研判上下文，
修改一次、Discover/Score/Position/Monitor/Sell/Review 所有 Agent 同步生效。
支持**导出/导入 JSON**，方便备份与多环境迁移。

### 层级 2：深度风格调教（改写 Prompt，重启生效）

**入口**：项目根 `agent_prompts/` 下 6 个独立文件
（`discover_prompt.py` / `score_prompt.py` / `position_prompt.py` / `monitor_prompt.py` / `sell_prompt.py` / `review_prompt.py` 各一个）。

**全局通用知识库基线**（`agent_prompts/global_base_prompt.md`）：
- 所有 Agent 每次任务**最先加载**这份全局基线，再拼接自身专属 Prompt，互不覆盖；
- 内置：A股基础交易规则、基准本金（固定 36943 元）、系统边界（禁止自动下单）、
  技术分析执行标准（蜡烛图/威科夫/量价/谐波交易 + 至少两套体系交叉验证）、
  思考推理强制准则（因果闭环 / 多维推演）、主战场定位（吸筹末期 = 唯一进场点）、
  派发期最高风险原则（最高优先级，利好不压过派发信号）、通用风控底线（止损 -8% 参考/盈亏比 ≥3:1）、
  元规则（实时走势 > 主力资金 > 政策消息 > 技术形态 > 历史对比）、
  工具观 K22（框架皆为参考权重非死条件）、概率思维（信心度 + 前提假设）、预留扩展插槽；
- 纯指令文本，直接编辑即可；**实时读取，保存立即生效**（内容指纹使 LLM 缓存自动失效），无需重启。

**分职能战法知识库**（`agent_prompts/knowledge/`，沉淀自《潜力股发掘方法论》）：
- 按 Agent 拆分：`discover.md`（7 层漏斗/K8 六项/K16 十一项/威科夫阶段/量价七句/标的类型六类）、
  `score.md`（0-5 五维评分细则与决策阈值）、`market.md`（市况 7 维综合 + 5 档判定）、
  `monitor.md`（阶段演进/派发 7 项识别/止损止盈）、`sell.md`（卖出要点）、
  `review.md`（每日复盘模板/失职根因）、`counter_examples.md`（反例库：11 条硬性反例 +
  亨通惨案 600487 / 立讯精密 002475）；
- 由 `common.py` 统一调教接口在私有知识库之后、Agent 专属 Prompt 之前自动注入，
  声明为参考权重（与硬性规则冲突时以硬性规则为准）；
- 纯指令文本，直接编辑即可；**实时读取，保存立即生效**（内容指纹使 LLM 缓存自动失效），无需重启。

**规则**：

1. **不要修改 Python 业务逻辑**，只修改引号内的 Prompt 文本（中文内容）；
2. 每个 Agent 独立隔离：任意调整单个 Agent 的研判标准、输出格式、思考思路，**不影响其余 Agent**；
3. 可写入你的交易哲学、波段选股经验、排斥的行情形态，例如：
   > 我只做板块共振波段行情，独立个股题材行情谨慎参与；回避高位无量标的，优先均线结构健康的趋势股。
4. 修改完成后**重启后端服务**即可生效；
5. 建议**自行备份**修改后的 prompt 文件，版本升级时防止被覆盖。

### 层级 2.5：统一调教接口（私有知识库 + 硬性规则，保存立即生效）

**入口**：Streamlit 面板 →「交易知识库」页 + `agent_prompts/common.py` 的 `HARD_RULES`。

**私有知识库**（`private_knowledge` 表 + 向量检索）：
- 写入你的私有交易经验、战法、心得，每个条目可选「适用 Agent」（all=全部通用，或仅 Discover/Score/Position/Monitor/Sell/Review 之一）；
- 任一 Agent 每次启动任务时**自动检索对应标签（含 all）的知识条目注入研判上下文**；
- **保存/删除立即生效**（知识版本号使 LLM 缓存自动失效），无需重启。

**硬性规则**（`agent_prompts/common.py` 的 `HARD_RULES` 列表）：
- 人工写入的规则以最高优先级注入所有 Agent 的 system prompt，**LLM 不得放宽人工设定的业务底线**；
- 例如：`"不选上市不足一年的次新股"`、`"单日跌幅超过 -9% 的持仓必须触发减仓提醒"`。

### 层级 3：AI 自我迭代闭环（全链路优化建议，人工审核后生效）

**机制**：每次平仓后 ReviewAgent 自动复盘，对比**当初选股逻辑 vs 最终盈亏**，输出两类产物：
1. **偏好优化建议**（`profile_suggestion`：字段名 + 建议新值 + 事实理由）→ 「交易复盘」页一键采纳（自动更新偏好档案，版本号+1，全部 Agent 生效）或驳回；
2. **全链路 Agent 优化建议**（`agent_suggestions`：针对 Discover/Score/Position/Monitor/Sell 任一 Agent 的规则/参数调整提案）→ 「交易复盘」页「策略闭环」区审核：
   - `profile` 类：采纳后直接写入偏好档案，立即生效；
   - `prompt` 类：采纳后需**人工**在 `agent_prompts/` 对应文件按建议值修改；
   - ⚠️ **所有建议必须人工审核确认后才生效，系统严格禁止自动、无监督修改任何策略参数**。

> 层级关系：层级 1 管"参数"（够用），层级 2 管"风格与哲学"（进阶），层级 2.5 管"私有战法 + 硬性底线"（即时生效），层级 3 让系统从你的真实盈亏中持续自我进化（长期打磨，全程人工把关）。

## 目录结构

```
agent_prompts/        ★ 全局基线 global_base_prompt.md + knowledge/ 分职能战法知识库 + 六个 Agent 独立提示词（项目根，集中调教）
backend/
  app/
    core/            配置与日志（APP_ENV / DB_BACKEND / CACHE_BACKEND / QDRANT_MODE 开关）
    db/              ORM 模型 + repo.py（唯一数据网关）+ 会话
    cache.py         缓存网关（默认内存 / 可选 Redis）
    datasource/      akshare 主源（超时/重试/东财→新浪降级/列名兼容）+ 麦蕊增强源（可选，默认关闭）
    llm/             DeepSeek 结构化输出（json_object + pydantic + 重试）+ Embedding
    agents/          六 Agent 节点 + common.py（统一调教接口：HARD_RULES/偏好/知识注入）
    graph/           StockAgentState + 6 个 StateGraph + 图间编排
    services/        indicator（纯数学指标）/ vector_store（向量网关）/ multimodal（MiniMax 可选多模态，默认关闭）/ feishu / ocr
    scheduler/       APScheduler 定时任务（Asia/Shanghai）
    api/             REST API（仅数据存取 + 手动触发，零 SQL 直连）
  tests/             pytest：过滤/指标/LLM 解析/状态流转/调教闭环/DB/页面渲染
  scripts/           dev_run.py 启动 / smoke_test.py 全链路冒烟
streamlit/           Streamlit 展示面板（纯展示，无二次判断，8 个页面）
docker-compose.yml   backend + streamlit 两服务
.env.example        全部配置项模板（含中文注释）
data/                dev.db / qdrant_storage/ / logs（本地文件存储，复制即迁移）
```

## 存储规范（三网关收敛）

业务代码禁止直接硬编码 SQLite/Qdrant 原生调用，统一走三个抽象网关：

| 网关 | 职责 | 默认 | 可选 |
|---|---|---|---|
| `repo.py` | 全部结构化业务数据（候选/评分/方案/持仓/交易/告警/复盘/知识/建议） | SQLite 文件 `data/dev.db` | MySQL 8 |
| `cache.py` | LLM 结果缓存（按 Agent 分 TTL，版本号自动失效） | 进程内存 | Redis |
| `vector_store.py` | 私有知识检索（按 agent_tag 注入） | 本地文件 Qdrant `data/qdrant_storage/` | Qdrant server |

切换后端只需改 `.env` 三个开关（`DB_BACKEND` / `CACHE_BACKEND` / `QDRANT_MODE`），业务代码零改动。
所有持久化文件均为本地文件形式，**迁移系统直接复制 `data/` 目录即可**。

## 麦蕊智数可选增强数据源（默认关闭，零开销）

麦蕊智数（mairui.club）作为 akshare 的**补充数据源**，仅用于 v2.0 选股机制的高级资金面/股东面字段：

- **默认关闭**：`MAIRUI_ENABLE=false` 时系统行为与未接入完全一致，不增加任何依赖与请求；
- **配置项**（`.env`，更换证书只改这里，无需改动代码）：
  - `MAIRUI_ENABLE=false|true` —— 总开关；
  - `MAIRUI_LICENCE=<证书>` —— 麦蕊证书密钥（仅通过环境变量管理，严禁硬编码）；
  - `MAIRUI_BASE_URL=https://api.mairuiapi.com` —— 接口基础地址。
- **调用策略**：
  - 基础行情（快照/涨跌幅/成交额/日K/新闻/行业/财务/日历）**仅走 akshare**（东财→新浪双通道，不消耗麦蕊配额）；
  - 高级字段**按需调用**：成交分布（超大单/大单/中单/小单净流入 → 主力净流入）、股东户数变化；
  - 同日同标的**当日缓存**（86400 秒），重复请求不二次消耗配额；
  - 麦蕊失败 / 返回空 / 当日配额超限（101）→ 自动回退 akshare 现有字段，中文日志记录原因，前端友好提示，**不报错中断**。
- **已核实端点**：`/hsmy/lscjt/{code}/{licence}`（最近 10 天成交分布）、`/hscp/gdbh/{code}/{licence}`（股东变化趋势）。
- **边界说明**：机构持股占比、龙虎榜、财务分析等字段当前仍由 akshare 提供（麦蕊端点未实现，避免无认证前提下的接口漂移风险）。

## 存储空间维护与轻量化

### 运行时临时文件（自动清理）

- OCR 识别截图仅内存/临时文件处理，识别完毕立即删除，**不持久化持仓截图**；
- 数据源/LLM 结果缓存全部带 TTL（数据源 600 秒、LLM 当日 24h / 盘中 15min），到期自动失效，重启即清空，无残留文件；
- 日志自动轮转：单个文件超过 `LOG_MAX_BYTES_MB`（默认 10MB）自动切割，最多保留 `LOG_BACKUP_COUNT`（默认 5）份。

### 空间维护（自动 + 手动入口）

- **SQLite 真空收缩**：删除超期数据后执行 `VACUUM` 回收磁盘空间（MySQL 无对应操作，记录日志跳过）；
- **新闻/公告保留周期**：超过 `NEWS_RETENTION_DAYS`（默认 90 天）的新闻自动清理；候选/评分/持仓/复盘等关键分析数据**不清理**；
- **向量库索引同步清理**：超期新闻的 Qdrant 索引一并删除；
- **定时任务**：每周按 `DB_MAINTENANCE_DAY_OF_WEEK`（默认周日）凌晨 `DB_MAINTENANCE_HOUR:DB_MAINTENANCE_MINUTE`（默认 05:30）自动执行，`DB_MAINTENANCE_ENABLED=false` 可关闭；
- **手动入口**：`POST /api/db/maintenance` 随时触发；
- **Qdrant 压缩**：本地文件模式默认启用 INT8 标量量化压缩（`QDRANT_COMPRESSION=true`），减少向量库磁盘占用。

### 轻量备份清单（只备份这三处）

| 内容 | 位置 | 说明 |
|---|---|---|
| 全部业务数据 | `data/` | dev.db / qdrant_storage/ / logs，复制即迁移 |
| 全部调教成果 | `agent_prompts/` | 全局基线 + 六个 Agent 提示词 |
| 全部密钥配置 | `.env` | 含 DEEPSEEK/SILICONFLOW/麦蕊证书等密钥（严禁提交版本库） |

Prompt 与配置**只保留一个有效版本**，不自动创建备份文件——版本控制交给 Git，升级覆盖前请先确认已提交。

## 后台异步任务机制（手动触发不阻塞页面）

所有耗时手动操作（每日挖掘/单股打分/建仓方案/卖出决策/复盘/驳回重思考/知识库批量导入）提交即返回
任务ID，由后端单线程队列串行执行（防外部接口与 LLM 限流），页面可自由切换继续操作；
顶部统一任务状态区每 3 秒轮询，显示执行中明细，失败红色提示可一键重试，任务结束自动消失。

- 任务状态流转：`pending → running → done/failed`，保留最近 30 条，进程重启后清空（本地工具可接受）；
- 失败任务重试复用原任务ID；状态查询含提交/开始/完成时间与失败原因；
- **手动触发强制真实执行**：手动触发「每日挖掘」前自动失效当日 LLM 结果缓存（初选/终选/市况），
  强制重新执行完整链路（硬过滤 → LLM 初选 → 新闻核验 → 最终确认 → 批量打分）；
  落库采用**当日快照替换**——同日同股覆盖更新（时间戳刷新为最新执行时间），
  当日未入选的旧候选自动清除，不残留历史版本；
- **重复触发防护**：同类型任务正在执行/排队时拒绝重复提交（HTTP 409 + 中文提示），
  避免重复执行产生脏数据与资源浪费；
- **完成自动刷新**：任务完成瞬间页面自动刷新，候选池等模块立即展示最新结果，无需手动刷新；
- 接口：`POST /api/tasks/submit`（提交任意任务，body 为 `{kind, params}`）、
  `GET /api/tasks/recent`（最近任务，最新在前）、`GET /api/tasks/{tid}`（任务详情）、
  `POST /api/tasks/{tid}/retry`（失败重试）、`POST /api/knowledge/batch-import`（知识库批量导入）。

## API 一览（backend:8000）

任务触发：`POST /api/jobs/discover/run`、`GET /api/jobs/status`、`POST /api/score/{code}`、`POST /api/positions/plan`、
`POST /api/holdings/{id}/sell-decision`、`POST /api/reviews/{id}/reject`（提交后均返回 `task_id`，见上方异步任务机制）；
数据读取：`GET /api/candidates|/api/scores|/api/positions|/api/holdings|/api/alerts|/api/reviews`；
持仓：`GET /api/holdings`、`GET /api/holdings/quotes`（实时行情视图，只读）、`POST /api/holdings`、`POST /api/holdings/{id}/exit`（记录卖出；清仓时自动提交复盘任务，返回 `review_task_id`）、`POST /api/holdings/{id}/monitor`、
`POST /api/holdings/{id}/sell-decision`（SellAgent 决策）、`GET /api/holdings/{id}/sell-decisions`；
知识库：`GET/POST /api/knowledge`、`POST /api/knowledge/{id}/delete`、`POST /api/knowledge/batch-import`（批量导入）；
策略闭环：`GET /api/agent-suggestions`、`POST /api/agent-suggestions/{id}/approve|reject`（人工审核）；
偏好档案：`GET/PUT /api/profile`、`POST /api/profile/import|export`；
其他：`GET /api/ocr/status`、`POST /api/ocr/holding`、`POST /api/db/maintenance`（手动空间维护）、`GET /api/health`。

## 模型选型与缓存优化（双模型分场景路由 + KV 缓存命中率提升）

### 一、双模型分场景路由（LLM 调用层自动匹配，业务代码无感知）

| 模型 | 配置项 | 定位 | 适用场景 |
|---|---|---|---|
| 轻量模型 `deepseek-v4-flash` | `DEEPSEEK_DEFAULT_MODEL` | 高频低成本的批量/巡检任务 | DiscoverAgent 初筛（300 只大表）、MonitorAgent 盘中巡检 |
| 深度推理模型 `deepseek-chat` | `DEEPSEEK_REASONING_MODEL` | 低频高价值的深度研判 | Discover 最终确认、ScoreAgent 五维打分、PositionAgent 建仓、SellAgent 卖出决策、ReviewAgent 复盘、市况评分、驳回重思考 |

- 每个 Agent 在调用点声明场景等级 `model_level`（LIGHT=轻量 / DEEP=深度，默认 DEEP，历史语义不变）；调用层按等级自动选模型与参数，Agent 代码不感知具体模型名；
- 轻量模型不传 `reasoning_effort`（无推理参数），`max_tokens` 用 `DEEPSEEK_FLASH_MAX_TOKENS`（8192）；深度模型传 `reasoning_effort="low"` 与 `LLM_MAX_TOKENS`（32768）；
- **降级保障**：轻量模型连续失败 3 次自动降级为深度推理模型重试（最多 3 次），不阻塞主流程；深度模型保持原语义（本模型内重试 3 次，不引入额外降级）；
- 全部配置在 `.env`，修改后重启后端生效。

### 二、KV 缓存命中率优化（纯结构优化，不改变任何输出）

| 优化项 | 做法 | 收益 |
|---|---|---|
| system prompt 段序固定 | 全局基线 → 硬性规则 HARD_RULES → 个人交易偏好 → 私有知识库 → 分职能战法知识库 → Agent 专属 Prompt，顺序永久固定 | 相同前缀跨请求完全一致，服务端前缀缓存命中 |
| 固定内容前置、动态数据后置 | 所有动态数据（当日行情/持仓/候选表）一律放入 user 段，system 段同版本内 100% 重复 | 缓存命中时 system 段几乎零成本 |
| 版本指纹入缓存键 | 偏好档案版本 `v{n}` + 知识库变更感知 `k{count}:{max_id}` + 基线内容指纹 `g{md5}` + 分职能知识指纹 `a{md5}`，拼接进缓存 key | 人工修改调教内容后缓存自动失效、立即生效 |
| 恒定请求参数 | json_object / 温度 0.3 / max_tokens / schema 每次请求一致 | 服务端缓存有效性最大化 |
| 双模型独立缓存 | 缓存 key 按 agent+model 隔离（`llm:{agent}:{model}:{key}`） | 同一任务两模型各走各的缓存，互不污染 |
| 两段式 messages | 固定 system + user 两段，不追加多轮历史 | 符合主流缓存前缀模型，避免长轮次稀释命中 |

### 三、LLM 运行统计（首页「系统运行状态」看板）

- 每次成功响应自动记录服务端 usage（命中/未命中/输出 token），按自然日累计（`GET /api/llm/stats`）；
- 看板展示：当日请求次数 / 整体缓存命中率 / 命中·未命中 token / 模型调用分布（flash 与 chat 各自次数与占比）/ 统计截止时间，支持手动刷新；
- 存储于缓存抽象层（dev=内存 / prod=Redis），跨进程为近似值，仅作调优参考、不参与任何研判。

## 性能优化（数据库索引 + 查询缓存 + 首页聚合）

> 纯性能层优化：不改变任何 Agent 业务逻辑、Prompt 内容、输出格式、选股机制与模型路由，查询结果与优化前完全一致。

### 一、数据库层（SQLite 高频查询提速）

| 优化项 | 做法 | 收益 |
|---|---|---|
| 组合索引 | `stock_candidate(trade_date, rank)`、`holding(status)`、`review_result(exit_date, suggest_status)`、`agent_suggestion(status)`（MySQL 同步建 KEY，SQLite 由 `init_db()` 自动 `CREATE INDEX IF NOT EXISTS`） | 首页/列表页高频查询走索引，杜绝全表扫描（`EXPLAIN QUERY PLAN` 已验证） |
| WAL 模式 | `PRAGMA journal_mode=WAL` + `synchronous=NORMAL` | 读写互不阻塞，崩溃安全且大幅降低 fsync 次数 |
| 页缓存 | `PRAGMA cache_size=-20000`（20MB） | 降低磁盘 IO，重复查询更快 |
| 写锁等待 | `PRAGMA busy_timeout=5000` | 写锁竞争时等待 5 秒而非立即报错 |
| N+1 检查 | 列表接口全部批量查询 + 内存映射合并（如持仓实时行情单次快照拉取） | 无逐行查询，接口耗时稳定 |

- 手动空间维护入口 `POST /api/db/maintenance`（自动执行 VACUUM 回收磁盘空间 + 清理超期新闻）。

### 二、缓存层（高频读接口 60 秒结果缓存，写自动失效）

- 候选/评分/建仓/持仓/告警/复盘 6 个列表查询带 60 秒结果缓存：相同参数 60 秒内直接复用上次结果，不落库；
- **写操作自动失效**：任何写入（候选/评分/方案/持仓/告警/复盘增改）自动清空对应表缓存命名空间，下次读取立即拿到最新数据，缓存与库永远一致；
- 不同参数独立缓存键（md5 摘要），互不干扰；缓存存于既有缓存网关（dev=内存 / prod=Redis）；
- **开关**：`.env` 的 `DB_QUERY_CACHE_TTL`（秒，默认 60），设为 0 关闭读缓存（需要即时可见的场景）。

### 三、接口层（首页聚合，11 次串行请求 → 1 次）

- **`GET /api/dashboard` 首页聚合接口**：一次请求并行（ThreadPoolExecutor 8 线程）返回全部首页模块——系统状态 / LLM 统计 / 市况评分 / 持仓信号 / 候选评分方案 / 复盘建议 / 待审建议；
- **单模块失败隔离**：任一模块探活/查询失败仅标注该模块 `error`（异常类型名），其余模块与整体响应不受影响，页面显示友好提示；
- 列表接口均支持 `limit` 按需拉取，前端只取展示所需条数。

### 四、前端层（Streamlit 交互提速）

- **首页改单请求聚合数据源**：原先 11 个串行 HTTP 请求合并为 1 个 `dashboard()` 请求，最坏加载耗时从约 12 秒降至 2-4 秒；
- **候选池懒加载**：长列表首屏只渲染前 20 条，点击「加载更多」增量展示（分页进度随日期/筛选条件各自独立，切换自动回首页）；
- **候选池按日按需加载**：页面默认仅加载最新一天候选（轻量日期列表接口 `GET /api/candidates/dates`），切换历史日期再按需查询，避免初始化全量加载历史数据；
- **局部刷新**：LLM 统计看板 / 热门板块使用 `st.fragment` 独立刷新，不影响整页；
- **友好错误提示**：后端不可达/模块失败统一中文文案 + 异常类型名，不向页面暴露原始 Python 报错。

## 风险提示

- **DeepSeek 推理模型行为**：`deepseek-chat` 别名现路由到带内部推理的模型，推理 token 计入输出预算——`max_tokens` 过小且输入较大时（如候选池 300 行大表）会出现**空响应**（`finish_reason=length`、content 为空）或 JSON 截断。已在调用层固定 `reasoning_effort="low"`（推理量最小化）并把 `LLM_MAX_TOKENS` 提到 32768；轻量任务（初筛/巡检）默认走 `deepseek-v4-flash`（`DEEPSEEK_FLASH_MAX_TOKENS=8192`），连续失败自动降级深度模型重试；修改 `.env` 需重启后端生效。
- 数据源为 akshare 公开接口，可能限流/漂移，已做重试与降级但非 100% 稳定。
- LLM 输出仅供参考，存在幻觉可能；所有结论必须结合你的独立判断。
- **股市有风险，本系统不构成任何投资建议，一切盈亏由本人承担。**
