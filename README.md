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
DiscoverAgent  每日全市场潜力挖掘（硬过滤 → LLM 初选 → 新闻核实 → 落库）
ScoreAgent     单股 0-100 多维打分（基本面/技术/资金/舆情/行业景气）
PositionAgent  分批建仓方案（4 档区间 + 资金配比 + 止损止盈参考）
MonitorAgent   持仓监控预警（盘中每 5 分钟，飞书推送，LLM 信号研判）
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
4. 交易时段每 5 分钟 MonitorAgent 自动研判，触发预警推送飞书（未配置则落库告警日志）。
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
- 触发后执行 `run_daily_pipeline`（`backend/app/graph/router.py`）：先跑完整 Discover 图，随后对落库的每只候选**逐一自动执行 ScoreAgent 打分**。

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

## 持仓截图 OCR 识别（快捷录入）

在「持仓监控」页上传券商持仓截图，自动识别 **股票代码/名称/持仓数量/持仓成本/当前市价** 并回填新增持仓表单。

- **识别结果不直接入库**：必须先人工核对修正字段，点击【确认创建持仓】才写入 `holding` 表，杜绝识别错误引发监控异常；
- **纯文字识别工具**：不做任何行情研判/交易决策，市场研判仍全部由 LLM 完成；截图仅内存/临时文件处理，识别完毕自动清理，不长期存储；
- **开关**：`.env` 设置 `OCR_ENABLE=true/false`（默认 false），关闭后页面自动提示并仅保留手动录入；
- **依赖**：CPU 运行装 `paddleocr + onnxruntime` 即可（Python 3.14 已验证；Python 3.11/3.12 或 Docker 可另装 `paddlepaddle` 提性能，GPU 则装 `paddlepaddle-gpu` 并设 `OCR_DEVICE=gpu`）；首次识别自动下载模型约 150MB（缓存于 `~/.paddlex/`）。

**截图识别使用小贴士**：

- 尽量保证截图清晰：建议直接用券商 App「持仓页」整页截图，避免拍屏、拉伸、低分辨率截图；
- 避开弹窗遮挡：识别前关闭涨跌弹窗、开户引导、新股申购提示等悬浮层，防止遮住代码/数量列；
- 截图只需包含持仓表格区域即可（代码/名称/数量/成本/市价几列齐全）；
- 识别缺失/错误的字段会在预览中标注，手动补全修正后保存即可，无需重新截图。

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
  思考推理强制准则（因果闭环 / 多维推演）、预留扩展插槽（分职能规则 / 个性化交易体系拼接位）；
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
agent_prompts/        ★ 全局基线 global_base_prompt.md + 六个 Agent 独立提示词（项目根，集中调教）
backend/
  app/
    core/            配置与日志（APP_ENV / DB_BACKEND / CACHE_BACKEND / QDRANT_MODE 开关）
    db/              ORM 模型 + repo.py（唯一数据网关）+ 会话
    cache.py         缓存网关（默认内存 / 可选 Redis）
    datasource/      akshare 封装（超时/重试/东财→新浪降级/列名兼容）
    llm/             DeepSeek 结构化输出（json_object + pydantic + 重试）+ Embedding
    agents/          六 Agent 节点 + common.py（统一调教接口：HARD_RULES/偏好/知识注入）
    graph/           StockAgentState + 6 个 StateGraph + 图间编排
    services/        indicator（纯数学指标）/ vector_store（向量网关）/ feishu / ocr
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

## API 一览（backend:8000）

任务触发：`POST /api/jobs/discover/run`、`GET /api/jobs/status`、`POST /api/score/{code}`、`POST /api/positions/plan`；
数据读取：`GET /api/candidates|/api/scores|/api/positions|/api/holdings|/api/alerts|/api/reviews`；
持仓：`POST /api/holdings`、`POST /api/holdings/{id}/exit`（记录卖出并触发复盘）、`POST /api/holdings/{id}/monitor`、
`POST /api/holdings/{id}/sell-decision`（SellAgent 决策）、`GET /api/holdings/{id}/sell-decisions`；
知识库：`GET/POST /api/knowledge`、`POST /api/knowledge/{id}/delete`；
策略闭环：`GET /api/agent-suggestions`、`POST /api/agent-suggestions/{id}/approve|reject`（人工审核）；
偏好档案：`GET/PUT /api/profile`、`POST /api/profile/import|export`；
其他：`GET /api/ocr/status`、`POST /api/ocr/holding`、`GET /api/health`。

## 风险提示

- 数据源为 akshare 公开接口，可能限流/漂移，已做重试与降级但非 100% 稳定。
- LLM 输出仅供参考，存在幻觉可能；所有结论必须结合你的独立判断。
- **股市有风险，本系统不构成任何投资建议，一切盈亏由本人承担。**
