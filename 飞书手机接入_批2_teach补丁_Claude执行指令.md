# 飞书手机接入_批2_Claude执行指令.md（teach 增量补丁 v2 — 修双写绕过 + agent 参数 + 黑名单误杀 + 同步/异步衔接 + 经验 stage 流程）

## 0 元信息
- 主题：批 2 增量 — 在智能路由上加 `teach/remember/forget` 三类意图，复用 web 既有调教通路（**v2 修正：rule_feedback 自带落库，禁用其整体调用；只复用提示词/schema，自己组装 verdict→pending**）
- 主提示词：`D:\self\飞书手机接入_批2_Claude执行指令.md`
- 方案：参见 `D:\self\飞书手机接入_方案.md` §5.3；新增意图枚举与既有 11 类并列（不扩展业务语义，只加"教"入口）
- 前置：批 1 已验收；teach 通路已在 web 侧验证可用
- 复用既有通路（不新建）：
  - 个人事实（"记住 X"/"忘掉 X"）→ `upsert_preference`（repo.py:903，`content` 字段为 dict，新增键或删键后 append 新 version）+ `get_latest_preference`（repo.py:895）注入 `build_agent_context`（common.py:258）
  - 规则/战法（"教 X"/"以后都 Y"）→ **只复用** agent_chat 的 `_RULE_SYSTEM_PROMPT` / `_rule_user_prompt` / `RuleFeedback` schema / `_VERDICT_LABELS`（agent_chat.py:77 / :103-108 / 同文件 _RULE_SYSTEM_PROMPT / _rule_user_prompt 定义；`rule_feedback` 函数本身**禁用** —— 它在 :375-378 直接 `repo.add_knowledge` 落库无审核门，会与 pending 双写绕过审核）+ `add_pending_experience`（repo.py:2478，签名 `(task_id, stage, summary, artifacts_ref)`）→ 现有审核页（routes.py:1523-1526 `GET /experience/pending`）走 manual fail-closed

## 一 目标
飞书对话内即可"教"机器人：个人事实即时生效（轻审/直写）、规则/战法**走 pending 审核门**（不再被双写绕过）、硬规则/策略阈值只读不可教。回复带"已生效 / 已提交待审核 / 该项只读"三态。

## 二 架构约束（增量，不动主提示词 §二架构）
1. 路由新增 3 个 intent（在方案 §5.3 11 类之外并列）：
   - `remember`（关键词"记住 / 别忘了 / 我持有 / 我的风格"）：个人事实 → upsert_preference 写入 → 下次 build_agent_context 自动注入
   - `forget`（关键词"忘掉 / 删掉 / 不要再说"）：从 AgentPreference.content 删键 → append 新 version（**不重写当前 version**，保持审计链）→ 回执"已删除"
   - `teach`（关键词"教 / 以后都 / 永远 / 改成"）：规则/战法 → **自组装 LLM 校验调用**（不调 `rule_feedback` 整体，避免双写绕过）→ 拿到 verdict 后只写 `add_pending_experience` → 回执"已提交待审核，审核后生效"
2. **不调 `agent_chat.rule_feedback` 整体**（它会绕过审核门），只 import：
   - `_RULE_SYSTEM_PROMPT` / `_rule_user_prompt(agent, proposal, meta)` / `RuleFeedback`（schema）/ `_VERDICT_LABELS`（agent_chat.py:77、:103-108）
   - `AGENT_CHAT_META` 字典（用于 `_require_agent(agent)` 拿 meta）
   - `common.agent_call(...)`（同款 LLM 调用封装，与 rule_feedback:368-371 同样的参数）
   - `repo.add_pending_experience`（repo.py:2478）
3. **三层守门**（防教错静默改研判）：
   - **个人事实**（remember）→ 黑名单**只硬拒**「明确修改硬阈值」类（含"改成/设为 + 阈值词"），其他正常个人事实直写。**关键修复**：`记住 我仓位不超过 5 成` 这种合法个人事实降级为 teach（待审），**不硬拒**——安全性由 teach 的 LLM 校验 + 审核门兜底，误杀大幅减少。
   - **规则/战法**（teach）→ 走 LLM 校验 → 采纳/部分采纳/维持原规则 → 采纳/部分采纳 `add_pending_experience` 落 pending → 回执"已提交待审核"（**唯一审核入口**，禁止直写 AgentPreference / Knowledge）
   - **硬规则/阈值明确修改**（如"止损改成 3%"，关键词"改成/设置/改为 + 阈值词"）→ 直接拒绝「该项属于硬规则，只读不可教」，不进 LLM、不落库
4. **agent 归属**（P1 修）：teach 类必须传 agent tag 给 LLM 校验（`_rule_user_prompt` 第一参）：
   - LLM 路由时**顺带识别领域**：关键词"卖出/减仓/止盈/止损" → agent="sell"；"评分/选股/候选" → "score"；"监控/告警/盘中" → "monitor"；"复盘/反思/迭代" → "review"
   - 识别不到时默认 `agent="score"`（核心研判，捕获最广）
   - remember/forget 不传 agent（不调规则校验）
5. 关键词快路径 + LLM 兜底：批 2 §二.2 不变，teach 三类意图接入同一路由管线
6. **同步/异步衔接**（P2 修）：
   - **同步（直接调 LLM）**：proposal 字面 ≤50 字符（普通短教）
   - **异步（走 `task_queue.submit`）**：proposal >50 字符 或 LLM 预估重（多次拒绝/重写场景）
   - 同步完成 → 直接回执；异步提交 → 回执"已提交处理中，完成会通知你"（沿用批 2 长任务回推机制）
7. 会话上下文：批 2 §二.5 不变，teach 类不依赖上下文

## 三 规则（增量）
1. 路由关键词扩充：`记住|别忘了|我持有|我的风格|忘掉|删掉|不要再说|教|以后都|永远|改成|设为|改为`
2. 关键词路由先做硬规则检查（"改成/设为/改为 + 阈值词"才硬拒），黑名单：
   - 硬拒：`改成/设为/改为 + 止损|止盈|仓位|风控阈值|硬规则|红线|K\d+`
   - 黑名单词单独存在（如"止损"出现但不修改）→ 不硬拒，让 LLM 校验
3. handler 输出三态文案：
   - 生效：「已记住：{摘要}（下次对话生效）」
   - 待审：「已提交待审核：{摘要}（审核页确认后生效）」
   - 拒绝：「该项属于硬规则，只读不可教」
   - 异步：「已提交处理中，完成会通知你」
4. **remember/forget 必走 AgentPreference**：
   - remember：读 `get_latest_preference().content` → 新增键 `{key: proposal}` → `upsert_preference(content=新 dict, source_review_id=None)`（version 自增）
   - forget：读 content → 删键 → 若删完空 dict → 不写新 version，回执"无匹配偏好可删"；否则 `upsert_preference` 追加新 version（**不重写既有 version，保留审计链**）
5. **teach 必走 pending**（不直写）：
   - 自组装 `_RULE_SYSTEM_PROMPT` + `_rule_user_prompt(agent, proposal, meta)` + `common.agent_call(..., schema=RuleFeedback, model_level=ModelLevel.DEEP)`（同款于 agent_chat.py:368-371）
   - 拿到 verdict：
     - `maintained` → 直接回执「维持原规则：{reason}」，**不落库**
     - `adopted` / `partial` 且有 rule_title + rule_content → `add_pending_experience(task_id=飞书消息 id, stage="feishu_tutoring", summary=rule_title + "\n" + reason, artifacts_ref={"open_id":..., "source":"feishu", "agent":agent, "verdict":verdict, "rule_content":rule_content, "conflict_note":conflict_note})`
     - 字段警告：若 `experience_worker.route_draft` 不识别 `stage="feishu_tutoring"`，需**先把该 stage 加入 route_draft 的分支表**（grep `route_draft` + 各 stage 处理分支确认；如确需新增 stage 处理，仅改 experience_worker.py 的 stage→handler 映射表，**不改业务逻辑**）
6. 全部改动 ≤100 行（chat_router.py 关键词 +agent 识别 +12 行、chat_handlers.py 三个新 dispatch +80 行、bridge 不动、可能 experience_worker.py stage 映射 +5 行）
7. 与现有红线一致：禁止调用 `rule_feedback` 整体；**仅修改** experience_worker.py 的 stage 映射表（如确需新增 stage）；其余 import 只读

## 四 执行顺序
0. 先 grep 确认（不许跳过）：
   - `agent_chat.py` 里 `_RULE_SYSTEM_PROMPT`=:150 / `_rule_user_prompt`=:173 / `AGENT_CHAT_META`=:30（已核实；行号可能漂移，仍以 grep 实际为准）
   - `experience_worker.py` `route_draft` 内部 switch/分支对各 stage 的处理（确认是否需新增 `feishu_tutoring` 分支或 fallback）
   - `repo.upsert_preference` 实际签名 + `get_latest_preference` 返回结构（content 是 dict 还是其他）
1. `chat_router.py`：关键词正则追加 + agent 领域识别（5 类关键词 → 5 个 agent tag）
2. `chat_handlers.py`：新增 `handle_remember` / `handle_forget` / `handle_teach` 三个 dispatch；同步/异步分流逻辑（>50 字符走 task_queue）
3. `experience_worker.py`（如确需）：仅 stage 映射表新增 `feishu_tutoring` → 与现有"通用待审"分支共用（不改研判）
4. `bridge` 不动
5. 自测：
   - "记住 我持有 600519" → 生效
   - "记住 仓位不超过 5 成" → 待审（**不硬拒**，P1 修复点）
   - "教 以后都追涨停" → 待审
   - "止损改成 3%" → 拒绝（明确修改硬阈值）
   - "止损是 5%" → 进 LLM 校验（黑名单词单独存在不硬拒）
   - "忘掉 我持有 600519" → 删除
   - 长 proposal（>50 字符）→ 异步回执
6. pytest 回归（teach 三类各 2 个用例 + 黑名单/降级 3 个 + 同步/异步 1 个 + forget 边界 1 个，共 ≤9 个）

## 五 验收
1. 手机实测 7 句（覆盖三态 + 同步/异步 + 降级）→ 回执全部正确
2. **关键 P0**：teach 提交后查 `GET /experience/pending?stage=feishu_tutoring` → 命中；**`SELECT * FROM knowledge WHERE content LIKE '%教内容%'` 必须 0 命中**（证明未走 add_knowledge 绕过审核）
3. 硬规则（"止损改成 X"）直接拒绝，不进 LLM、不落库
4. 降级路径（"记住 仓位 X"）→ 进 pending 不硬拒
5. remember 生效后再说"我持有 600519" → 机器人引用（验证 build_agent_context 注入了）
6. forget 后该键不再被引用
7. pytest 全绿；批 1 已验收行为零回归

## 六 红线
1. **禁止调用 `rule_feedback` 整体**：会绕过审核门，违反本补丁红线
2. **teach 必走 pending**：禁止直写 AgentPreference / Knowledge，**唯一审核入口**
3. **不修改 agent_chat.py 内部**：仅 import 常量/schema；不修改 rule_feedback / learn_from_image / 任何写操作函数
4. **experience_worker.py 仅可改 stage 映射表**：不修改研判/分级/审核业务逻辑
5. **硬规则只读**：「改成/设为/改为 + 阈值词」直接拒绝；黑名单词单独存在让 LLM 校验
6. **不修改 prompt/策略/阈值**：teach 写入的是 knowledge（经审核）/ preference，不动研判逻辑
7. **Claude Code 端省 token**：不重复读主提示词已固化信息；只 grep 5 个新增 import 定位；docstring ≤3 行；复用现有函数禁止重写；测试 ≤9 个；报告 ≤10 行。代码改动预算 ≤100 行，超出停下报告 sir。

## 七 teach 多轮草稿模式补丁

1. 草稿仅存在 `feishu_bridge._drafts` 内存表，按 `open_id` 隔离，24 小时过期清理，不写 DB。
2. 路由新增草稿关键词：`教·存草稿` / `先存着` / `补一条` / `完成` / `放弃`。
3. 已开草稿时，`教 X` / `记住 X` 只追加草稿 piece，不直接写 pending 或 trade profile。
4. `完成` 时逐条提交：fact 走 `update_trade_profile`，rule 仍走 `_handle_teach` 审核链路进入 pending。
5. 单回合 teach 被 LLM 判 `maintained` 时追加软引导：`如需多轮教，先发「教·存草稿」开草稿`。
