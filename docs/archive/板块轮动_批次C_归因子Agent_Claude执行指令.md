# 板块轮动 · 批次 C(归因子 Agent)— Claude Code 执行指令

## 〇 元信息
生成者:Lark(接替分析师)。执行者:Claude Code/DSH。决策人:sir。范围:**为板块轮动加"启动归因"子 Agent**,对 top10 板块各产出 reason_tags/reason_text/reason_chain/confidence 并落库 `sector_launch_reason`。
上游:批 A(3 表+cron)、批 B(状态机+churn/streak)已验收(commit 83999b6/2375351)。本批独立可交付。

## 一 目标
- 新增 `run_launch_reason(trade_date)` 子 Agent:对当日 top10 板块各一次 `agent_call`,输入证据 JSON → 输出启动归因,落 `sector_launch_reason`(同 trade_date 删后插)
- 新建 `agent_prompts/sector_launch_prompt.py`(SYSTEM + build_prompt):reason_chain 必须写出「通过什么消息/数据判定」,且证据只引用 evidence 内真实字段(K227)
- 打通手动触发:router 函数 + `POST /api/market/sector-rotation/run`

## 二 架构约束(解耦铁律)
1. **不新增 LangGraph 节点、不动 `graphs.py:20-32`**;子 Agent 走独立 `agent_call`(`agents/common.py:249`, agent="sector_launch_reason", model_level=LIGHT),仿 `router.py:220 run_market_intel` 模式
2. 只动:新建 `services/sector_launch_reason.py` + `agent_prompts/sector_launch_prompt.py` + `graph/router.py` 加 1 函数 + `api/routes.py` 加 1 端点 + 1 测试文件
3. 复用已有实现,不重写: `agent_call` / `upsert_sector_daily_snapshot` / `fetch_daily_kline:924` / `fetch_fund_flow:956` / `fetch_news:1017` / `fetch_board_box_positions:1048` / 批 B `sector_rotation.py`
4. 不碰 `sector_snapshot` 现有表;不引新库

## 三 规则(字段/阈值/口径)
**落库表** `sector_launch_reason`(已建, `models.py:749`,唯一键 trade_date+sector_name):
- 字段:rank_no / reason_tags / reason_text / **reason_chain**(Text) / evidence(JSON) / confidence(Float)
- 归因标签 tags: policy/news/fund/oversold/earnings/overseas/rotation(可多选逗号分隔)

**子 Agent 输入(evidence JSON, 代码层采集)**, `collect_evidence(sector_name)` 返回:
- 量比 / 换手 / 涨跌家数(已落 `sector_daily_snapshot`)
- 领涨股连板(`fetch_daily_kline:924`)、主力净流入(`fetch_fund_flow:956`)、新闻条数(`fetch_news:1017`)
- 箱位(批次 B `sector_rotation.py`)

**输出契约**(严格 JSON):
- reason_tags(逗号分隔) / reason_text(一段白话归因) / **reason_chain**(数组, 每条 `{"evidence_key": <evidence 内真实字段>, "inference": "通过该数据判定…"}`) / confidence(0-1)
- 缺口证据如实 NULL 或不引用,禁止编造;reason_chain 每条 evidence 必须真实存在于证据块(K227)

## 四 执行顺序
1. `services/sector_launch_reason.py` 新建:`collect_evidence` + `run_launch_reason`(循环 top10 各 1 次 agent_call)+ 删后插落库
2. `agent_prompts/sector_launch_prompt.py` 新建(SYSTEM + build_prompt),reason_chain 引用约束写死
3. `graph/router.py` 加 `run_sector_rotation(trade_date)`(仿 `router.py:220`),内部调 `services.sector_launch_reason.run_launch_reason`
4. `api/routes.py`: ① `_TASK_KINDS`(`routes.py:62`)加 `"sector_rotation": ("板块轮动分析", …)` ② 新增 `POST /market/sector-rotation/run`(仿 `routes.py:272 market_intel/run` 提交任务)
5. 测试 `tests/test_sector_launch_reason.py` **3 例**: ①证据采集字段齐全 ②reason_chain 非空且每条引用 evidence ③同 trade_date 删后插幂等
6. `cd backend && python -m pytest tests/test_sector_launch_reason.py -q` → 3 passed
7. 回归 `tests/test_sector_rotation.py`(批 B)+ `tests/test_sector_daily.py`(批 A)不破
8. commit `[批次C] 板块轮动:归因子 Agent + reason_chain + 手动触发`(不 push)

## 四 验证清单
- [ ] `sector_launch_prompt.py` 存在且 reason_chain 白名单约束
- [ ] `run_launch_reason` 对 top10 循环 agent_call, agent="sector_launch_reason", LIGHT
- [ ] 落库 `sector_launch_reason` 同 trade_date 删后插幂等
- [ ] `POST /market/sector-rotation/run` 可手动触发
- [ ] 3 测试全过 + 批 A/B 回归不破
- [ ] evidence 缺口如实 NULL,reason_chain 引用全部真实(K207)

## 五 红线 & 省 token
1. 不动 `graphs.py:20-32` 主图 / 2. 不动 `agent_call` 与 `push_alert_node` 内部 / 3. 阈值 churn=0.6、streak=3 定死走 review_log / 4. 不引新库、不接新数据源 / 5. 缺口数据如实 NULL,reason_chain 证据必须真实 / 6. 改动 ≤ 180 行,超出停手报 sir
**省 token**:①不复读本指令与方案全文(只 grep `reason_chain`/`run_sector_rotation` 确认行号)②只动本批列出的 4 文件 + 1 新测试 ③复用 `agent_call`/`upsert_sector_daily_snapshot`/`fetch_*` 已有实现,禁止重写 ④docstring ≤3 行,函数体不写注释(除关键 trade-off)⑤测试只写 3 例 ⑥报告 ≤10 行:①文件清单 ②测试结果 ③遗留风险。
