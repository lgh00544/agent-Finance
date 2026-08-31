# 飞书手机接入_批2_Claude执行指令.md

## 0 元信息
- 主题：P1 智能路由（LLM 意图识别 + 全意图接线 + 长任务异步回推 + 会话上下文）
- 方案：参见 `D:\self\飞书手机接入_方案.md` §5.3 / §5.5 / §6
- 前置：批1 已验收（长连接 + 关键词路由 + 告警直发在位）

## 一 目标
机器人自动识别任意自然语言指令 → 判定意图/标的 → 调对应 Agent/服务执行 → 回结果；耗时任务先回执、完成后再回推。

## 二 架构约束
1. 新增 3 文件：`backend/app/prompts/chat_router.py`（提示词 + 输出 schema）、`backend/app/services/chat_router.py`（正则快路径 + flash LLM 结构化路由）、`backend/app/services/chat_handlers.py`（intent→调用映射 + format）；批1 的 `_route_keyword()` 迁入 chat_router.py，bridge 改调 `chat_router.route()`
2. LLM 路由：复用 `app.llm.structured` 双模型路由，用 LIGHT 模型（deepseek-v4-flash），结构化输出 `{intent, params:{code,name}, reply_hint}`；解析失败或低置信 → 回 `chat` 意图不执行
3. 意图分发全部**复用 routes.py 现有端点背后的实现**（grep 定位 handler 后 in-process 调用，禁止新写业务逻辑）：
   - holdings → `GET /holdings` + `GET /account/summary`
   - pnl → `GET /account/pnl`
   - score → `POST /score/{code}`
   - sell → `GET /holdings` 取持仓行 `id` 字段（即 hid，repo.py:1751 `list_holdings` 返回含 `"id": r.id` 于 :1758，已核实；**repo 行号会因并行改动漂移，实现时以 grep `def list_holdings` 实时定位为准**）→ `POST /holdings/{hid}/sell-decision`
   - discover → `GET /candidates`（最新日期）
   - market → `GET /market/indices` + `GET /market/sector-rotation`
   - monitor → `GET /alerts`（最新 N 条）
   - review → `GET /reviews`（最新）
   - trigger → `POST /jobs/discover/run` 等（经 `/tasks/submit` 提交，task_queue 执行）
   - help/status → 固定文案 + `GET /system/status`
   - chat → 复用 `agent_chat.py` 现有 Agent 问答
4. 长任务：耗时 handler（score/sell/discover/trigger）→ 先回「任务进行中，完成会通知你」→ `task_queue.submit` 异步执行（参照 routes.py `/tasks/submit` 用法）→ 完成直发结果
5. 会话上下文：bridge 内存 dict（open_id → deque 最近 5 轮），路由时透传最近 1 轮供指代消解（「它/那个」）

## 三 规则
1. 每个 intent 一个 `format_xxx()` 纯函数，输出 ≤500 字文本（股票标识统一「代码 名称」，项目风格）
2. 标的识别：prompt 前置「标的：名称(代码)」；schema 校验 code 为 6 位数字；识别失败回「请给出股票代码或名称」
3. 全链路兜底：handler 抛错回「处理失败: {短错误}」；LLM 调用失败自动回退关键词快路径
4. 意图枚举与分发表以方案 §5.3 为准，不得自增意图
5. 本批与 AGENTIC_ENABLE 正交：score 是否走研判环由现有配置决定，本批不干预；AGENTIC_ENABLE 开关切换不影响 chat_router.py 内部实现（路由只决定调哪个端点，不感知研判环开关）
6. 全部改动 ≤250 行（3 新文件 + bridge 小改）
7. sell/discover/trigger 等动作**只产出建议/结果文本回发，不调用任何执行/落单接口**（系统本无下单能力；回复统一注明「仅参考建议，交易需人工执行」），防手机端误操作

## 四 执行顺序
0. 先 grep 确认 `task_queue.submit` 函数签名与 routes.py `/tasks/submit` 请求体结构，再写长任务代码
1. `prompts/chat_router.py`：11 类意图枚举 + schema（JSON 示例，见方案 §5.3 表）
2. `chat_router.py`：正则快路径迁移（查持仓/今日盈亏/分析X/卖出X/帮助）+ LLM 结构化路由 + 低置信回退
3. `chat_handlers.py`：11 个 dispatch + format；调用目标 grep `routes.py` 定位（端点清单见方案 §6 已列）
4. bridge 接线：text → `chat_router.route()`；image/media/file 仍回「暂不支持」（批3）
5. 会话上下文 + 长任务回推
6. 自测（mock LLM 路由 + 真实轻量 intent）+ pytest 回归

## 五 验收
1. 手机实测：分析 600519 → 评分结果；卖出决策 600519 → 卖出建议；今天有什么发现 → 最新候选摘要；大盘怎么样 → 指数+板块轮动；最新告警 → 最近 N 条；跑一次选股 → 「任务进行中」→ 完成回推
2. 「它」能指代上一轮标的
3. 无把握指令走知识库问答，不瞎执行
4. pytest 全绿；批1 已验收行为零回归

## 六 红线
1. 低置信绝不执行；意图枚举不扩展
2. 只做查询/分析/任务触发，不新增交易能力
3. 密钥仅 .env；日志不打消息全文
4. 不修改 agent 研判逻辑/策略/阈值；不写超范围代码
5. Claude Code 端约束：不重复读提示词已固化信息；docstring ≤3 行；复用现有函数禁止重写；测试只写规定数量；报告 ≤10 行
