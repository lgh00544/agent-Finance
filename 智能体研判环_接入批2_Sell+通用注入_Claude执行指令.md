# 智能体研判环 接入批2：Sell 铺开 + 通用注入

- 生成：Lark 2026-08-27
- 决策：sir 拍板（批1 已验收 commit a7d7bc5）
- 原则：Agent 解耦、通用注入必抽公共层复用、不裸传 SYSTEM_PROMPT、默认关不碰主链、失败回退
- 上游方案：`D:\self\智能体研判环_方案.md`；批1 指令：`D:\self\智能体研判环_接入批1_ScoreAgent_Claude执行指令.md`（复用 §五步骤模式与实测方法，不重抄）

## 一、目标

1. 把批1 在 `score.py` 里**硬编码的注入**（工具引导 `_AGENTIC_TOOL_NOTE` +「标的」识别）**抽成公共复用**，供所有节点统一消费。
2. 把 agentic 通道**铺开到 SellAgent**（`llm_sell`），与批1 Score 完全对等：默认关、失败回退、缓存共用、thinking 留痕。
3. **本期不铺开 Discover / MarketIntel**（见红线#3，标的语义不符）。

## 二、架构约束

- 单发链路 `agent_call` **零行为变化**（回归依赖它）；agentic 是平行分支。
- 通用注入一律进 `build_agent_context`（`common.py:258`）或补齐参数，不做节点内二次复制。
- Agent 解耦：只动 `score.py`/`sell.py`/`common.py`/`reasoning_trace.py` 的 agentic 分支 + 公共常量，不动 graphs/router/scheduler。
- **不引新库、不改 DB 表**（ext_info 已是 JSON，透传非迁移）。

## 三、规则

1. **通用注入两件套**：
   - 「标的：{name}({code})」前置：在 `common.py` `agentic_call`（`:375`）内，新增 `target_label: str = ""` 参数；非空则 `user_prompt` 首行前置 `【本次研判标的】{target_label}`。`score`/`sell` 调用时传入 `f"{name}({code})"`。
   - 「工具引导」：把 `score.py:357-363` 的 `_AGENTIC_TOOL_NOTE` 常量**提升为公共常量**（放 `agentic_tools.py` 内、`TOOLS` 注释处），`score`/`sell` 的 agentic 分支统一 `system_prompt=_AGENTIC_TOOL_NOTE + 各自 SYSTEM_PROMPT`；`score.py` 删除本地常量改为 import。
2. **SellAgent 接入**（`sell.py:153 llm_sell`、`:200 agent_call`）：新增 agentic 分支，仿 `score.py:271-283`：
   ```text
   if settings.agentic_enable:
       output, agentic_trace = agentic_call(
           agent="sell", cache_key=f"selldec:{code}:{today}",
           system_prompt=_AGENTIC_TOOL_NOTE + sell_prompt.SYSTEM_PROMPT,
           user_prompt=sell_prompt.build_user_prompt(...同一四参...),
           schema=SellOutput, ttl_seconds=86400, model_level=ModelLevel.DEEP,
           target_label=f"{name}({code})")
   else:  # 原 agent_call 不动
   ```
   - `sell.py:11` 追加 `from app.agents.common import agentic_call`；`from app.core.config import settings`。
   - 缓存键沿用原 `selldec:{code}:{today}`；`agentic_call` 内模型用 `_model_for` 与单发共用 `sell:deepseek-chat`——同日二路不重复调 LLM。
   - tll0 结果按 `model_thinking`/`tool_trace` 两字段注入决策 dict：`output.model_dump()` 后补 `{"model_thinking": ..., "tool_trace": ...}`（译 `_summarize_agentic_trace(agentic_trace)`，已存在）。**落库前删除**，cl 不写入 `sell_decision` 表本体，只供 trace 透传。
4. **Sell 留痕透传**（`reasoning_trace.py:374 trace_sell`）：照 `trace_score`（`:186` 批1改法）在函数内 `model_thinking = str(decision.pop("model_thinking","") or "")`，`ext_info` 字段改传该两字段（原 `""`）。不复用表、新版调用兼容。
5. **缓存版本**：`sell` cache_key 现无 hash 后缀；注入工具引导是 system 层，缓存键不变（trigger来源无感），保持一致，不强制加指纹。

## 四、执行顺序

1. `common.py:258-353` `build_agent_context` 加 `target_label` 参数并入 user 前置（保持默认空＝零行为）。
2. `common.py:375 agentic_call` 签名加 `target_label`，透传给 `build_agent_context`。
3. `agentic_tools.py` 加公共常量 `_AGENTIC_TOOL_NOTE`（原文）。
4. `score.py`：删 `:357-363` 本地常量；`agentic_call` 加 `target_label=f"{name}({code})"`。
5. `sell.py`：`llm_sell` 加 agentic 分支（§三.2），补留痕两字段。
6. `reasoning_trace.py:trace_sell` 透传 `ext_info`。
7. 验证清单跑通 → 报告。

## 五、红线（不可越）

1. **通用注入必进公共层**——禁止在 `sell.py` 重抄 `_AGENTIC_TOOL_NOTE`/标的拼接；只用公共常量/参数。
2. **不裸传 SYSTEM_PROMPT**——system 必须由 `agentic_call`→`build_agent_context` 拼接；`target_label` 参数语义准确。
3. **本期 ONLY Sell**——Discover/MarketIntel/Monitor 是批量候选/市场级，工具环按标的查会错乱，一律不引入。如后续对它们开，先修工具语义，非本批。
4. 只动 5 文件（common.py / agentic_tools.py / score.py / sell.py / reasoning_trace.py）；不动 `agentic.py` 的环逻辑、不动 `graphs`/`router`/scheduler。
5. 默认 `AGENTIC_ENABLE=false` 回归通过；`true` 用一只持仓股经 sell 链路实测。
6. 测试用例不超过既有（sell 相关 + 批1 回归），不新增。

**Claude 端省 token**：只 grep `target_label`/`AGENTIC_TOOL_NOTE`/`agentic_enable` 定位；复用 `agentic_call`/`trace_*`/`_summarize_agentic_trace` 已有实现；docstring≤3 行；报告 ≤10 行；改动 ≤150 行（超额停下）。

## 六、验证清单

- [ ] 回归：`AGENTIC_ENABLE=false` 下 `test_score_refactor.py` + sell 相关全 pass（单发零变化）
- [ ] `AGENTIC_ENABLE=true` 用持仓股票跑 sell → 返 SellOutput；思考留痕落 `ext_info.model_thinking`，工具轨迹落 `tool_trace`
- [ ] 单发/agentic 同 code 同 sell key 不重复调 LLM（日志无双发）
- [ ] 工具引导文本在 sell 与 score agentic 分支均生效
- [ ] 改动 ≤150 行；只动指定文件