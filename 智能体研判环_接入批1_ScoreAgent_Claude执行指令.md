# 智能体研判环 · 接入批 1（ScoreAgent）· Claude Code 执行指令

> 生成者：Lark（接力 dsh）· 执行者：Claude Code/DSH · 决策人：sir · 2026-08-27
> 依据：`D:\self\智能体研判环_方案.md`（§3.2 接入 / §5 优化 1、6）· `D:\self\智能体研判环_接入_执行指令.md`（本批是其落地版，已按 sir 拍板修正「不丢偏好/知识库注入」）
> PoC 已提交（commit `3f1c066`）：`backend/app/llm/agentic.py` + `backend/app/agents/agentic_tools.py` + `backend/scripts/agentic_poc.py` 均已在库
> 执行起点：main 最新 · 终点：单文件 commit（不 push）· 默认关、零影响主链

## 一、目标

把 PoC 的 ReAct 通道（`run_agentic_judge`）以 `AGENTIC_ENABLE` 开关接入 **ScoreAgent**，默认关、失败自动回退单发、结果共用 LLM 缓存。附带 `model_thinking`/`tool_trace` 留痕。

**sir 拍板红线**：agentic 的 system 上下文**必须复用 `agent_call` 的段拼接**（个人偏好档案 + 私有知识库 + 硬性规则 + 经验参考 + 战法库 + 市场研判注入 + 选股回顾），**不得裸传 `score_prompt.SYSTEM_PROMPT`**。

## 二、改动清单（5 文件，预计 ≤ 170 行）

1. `.env` + `.env.example`：加 `AGENTIC_ENABLE=false` + 注释（默认关）。
2. `backend/app/core/config.py`：`Settings` 加 `agentic_enable: bool = False`（仿 `config.py:172 dragon_tiger_enable` 写法）。
3. `backend/app/agents/common.py`：
   - **重构抽函数**：把 `agent_call` 内 `common.py:262-333`（段拼接位 0-4 + 市场研判注入 + 选股回顾）抽成公共 `build_agent_context(agent, system_prompt, user_prompt, with_profile, with_knowledge, knowledge_docs) -> tuple[str, str]`（返回拼好的 sys, user）。`agent_call` 改为内部调用它，**行为零变化**。
   - 新增 `agentic_call(...)`：`build_agent_context` 拼 sys/user → `run_agentic_judge(sys, user, schema, TOOLS, TOOL_FUNCS, max_rounds=8)`；
   - 返回 `(result, trace_dict)`；结果写缓存 `cache.set_llm_json(f"score:{_model_for(DEEP)}", cache_key, result.model_dump(), ttl)`（与 `call_llm_cached:146` 同键口径）；失败 `run_agentic_judge` 返回 None → 回退 `call_llm_cached` 原逻辑，并记 `AGENTIC_FALLBACK` 日志。
4. `backend/app/agents/score.py`：`llm_score`（`score.py:263` `agent_call` 调用点）改分支——
   - `settings.agentic_enable` 为真 → `agentic_call(agent="score", cache_key=同现有, system_prompt=score_prompt.SYSTEM_PROMPT, user_prompt=同现有 build_user_prompt(...), schema=ScoreOutput, ...)`；
   - 取回 `trace` → 摘要写入 `repo.upsert_score` 的 `detail` 或 `state`（供 trace_score 用）。
5. `backend/app/services/reasoning_trace.py`：`trace_score`（`reasoning_trace.py:186`）`submit` payload 的 `ext_info` 增 `model_thinking` + `tool_trace`（从 `score.py` 透传的 trace 摘要；无则空串）。**免 DB 迁移**（`ext_info` 已是 JSON Text，`_UP_COLS:29` 已含 `ext_info`）。

## 三、规则

- **开关默认 false**：`agentic_enable=false` 时 `llm_score` 走原 `agent_call`，行为与改造前逐字节一致。
- **缓存复用**：agentic 结果与单式共用 `cache_agent=score:deepseek-chat` + `cache_key=code:date:v4:h{fingerprint}`（同 `score.py:265`）。同日起二路命中，不重复调 LLM。
- **失败回退**：agentic 任一行（LLM 调用 / 工具崩溃 / 产物校验失败）→ None → 回退 `call_llm_cached` 原逻辑，**不抛异常不中断评分**。
- **只读红线**：全部走 `agentic_tools.TOOLS/TOOL_FUNCS`（已确认全只读，`agentic_tools.py:1-6` 工具 + `reasoning_trace` 无写库路径）。产出仅"建议"，无自动下单。
- **轮数**：`max_rounds=8`；工具结果已在 `agentic.py:105` 截断 3000 字符。
- **版本指纹**：`build_agent_context` 重构后 `agent_call` 缓存键仍含 `version/fingerprint`，不破坏旧缓存含义（键文本不变，仅拼接位置变化）。

## 四、执行顺序

1. `common.py:249-353` 通读 → 抽 `build_agent_context`（约 60 行），`agent_call` 改调它（最终仍返回 `call_llm_cached` 的结果，行为不变）。
2. `common.py` 顶部 `from app.agents.agentic_tools import TOOLS, TOOL_FUNCS`（注意 `llm/agentic.py` 位于 `app.llm`，`run_agentic_judge` 已在库）→ 加 `agentic_call`（约 30 行）。
3. `config.py` + `.env` + `.env.example` 加开关。
4. `score.py: llm_score` 加分支（约 15 行）。
5. `reasoning_trace.py: trace_score` `ext_info` 透传（约 6 行）。
6. 测试：跑 `backend/tests/test_score_refactor.py` + 手跑一条 `AGENTIC_ENABLE=true` 的 600519 打分（`scripts/agentic_poc.py` 已证隧道通）。
7. 回归：`test_reasoning_trace.py` 必须仍绿（`trace_score` 签名兼容旧调用）。
8. commit `feat(backend): Score 接入 ReAct agentic 通道（AGENTIC_ENABLE 开关 + 上下文复用 + thinking 留痕`)`。

## 五、验证清单

- [ ] `AGENTIC_ENABLE=false` → `POST /api/score/600519` 行为与改造前一致（`test_score_refactor` 绿）；
- [ ] `AGENTIC_ENABLE=true` → 日志见「工具调用」轨迹、最终 `ScoreOutput` 校验通过；
- [ ] 同日二开（agentic 与单式切换） → 共享 LLM 缓存不重复调用；
- [ ] 人为断数据源 → agentic 仍产出（工具降级 + 如实标注缺口），连续失败回退单式成功；
- [ ] `trace_score` `ext_info` 含 `model_thinking`/`tool_trace`（agentic 模式有值，单轮为空串）；
- [ ] 红线：无自动下单/写库路径新增（`agentic.py` 仅只读）。
- [ ] 改动行数 ≤ 170（超出停下报告 sir）。

## 六、红线

1. 不新增 LangGraph 节点、不碰 `graphs.py` 主图 / `router.py` 路由结构。
2. `agentic.py` / `agentic_tools.py` / `agentic_poc.py` 这三个已入库的 PoC 文件**不改**（管线已证）。
3. 不动 `structured.py` 单式链路 `call_llm_cached`（agentic 走平行通道）。
4. **不得裸传 SYSTEM_PROMPT** —— 系统上下文必须用 `build_agent_context` 拼接。
5. 不引新库；只用 deepseek-chat（推理模型，低 effort）+ 已存 LLM cache。
6. 无自动下单、无写库新路径；0 条修改 `stock_*` / 交易规则 / 阈值。

**Claude 端省 token 约束**：不复读——只 grep `AGENTIC_ENABLE`/`build_agent_context`/`agentic_call` 确认行号；只动上述 5 文件；`docstring` ≤3 行；复用 `agent_call`/`trace_score`/`run_agentic_judge` 已有实现；测试 3 个不多写；报告 ≤10 行（文件清单 + 测试结果 + AGENTIC_ENABLE=true 实测结论 + 遗留）。