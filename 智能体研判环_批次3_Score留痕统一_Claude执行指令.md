# 智能体研判环 批次3：Score 留痕统一（detail 干净 + thinking 只进 trace）

- 生成：Lark 2026-08-27
- 决策：sir 拍板「统一」（批1 score 与批2 sell 的 thinking 语义不一致，统一为：**业务表干净，思考过程只进 ai_reasoning_trace 审计链**）
- 上游：批1 `智能体研判环_接入批1_ScoreAgent_Claude执行指令.md`；批2 `智能体研判环_接入批2_Sell+通用注入_Claude执行指令.md`
- 类型：简单任务（单功能对齐），改动 ≤ 40 行

## 一、目标

把 score 的 agentic 留痕从「thinking 塞进 `StockScore.detail` 业务表」改为「业务表干净、thinking 只透传 `ai_reasoning_trace.ext_info`」，与批2 sell 口径一致。**不新建页面**（留痕展示前端已存在：CandidatesPage 弹窗 / ReviewsPage 复盘卡）。

## 二、架构约束

- 单发链路 `agent_call` 零变化；`AGENTIC_ENABLE=false` 时 thinking 本就是空，本批对单发 path 行为完全无感。
- 只动 2 文件：`repo.py` + `score.py`。**不动** reasoning_trace.py、position.py、前端、sell.py。
- 不引新库 / 不改 DB 表（ext_info 已 JSON）。

## 三、规则

1. **`repo.upsert_score` 加可选参数 `thinking_summary: tuple[str, str] | None = None`**（默认 None＝旧行为，兼容 position/discover 等既有调用）：
   - 业务表：`row.detail = detail` **不含 thinking**（调用方已把 thinking 从 detail 剥离，见规则2）。
   - trace：构造 `trace_ctx = dict(detail)`，若 thinking 非空则 `trace_ctx["model_thinking"], trace_ctx["tool_trace"] = thinking_summary`，再 `trace_score(..., trace_ctx, risk_list)`（:753）。这样 thinking 只进 trace，绝不出现在业务表 detail。
   - 参考行：repo.py:739 `def upsert_score(...)`、:749 `row.detail=...`、:753 `trace_score(...detail...)`。
2. **`score.py` `llm_score` 末尾改**：
   - `detail` 维持构造 `{factors, potential_flag, cross_validation_note, final_advice}`，**不再塞 `model_thinking/tool_trace`**。
   - agentic 时调用 `repo.upsert_score(code, name, today, score, grade, detail, risk_list, thinking_summary=summarize_agentic_trace(agentic_trace))`；非 agentic 不传该参（None）。
   - 现有 `if agentic_trace: detail["..."] = ...` 注释掉/删除，改为传入参数。
3. **追溯**：position.py:43 读取的 `score_row.detail` 将自动变干净（不再含 thinking），`position_plan.detail` 不再被污染——本文件自愈于 trace 通道，无需 position 改动。

## 四、执行顺序

1. `repo.py:739` 给 `upsert_score` 加 `thinking_summary=None` 参数与文档字符串。
2. `repo.py:749` 保持 `row.detail = detail` 不变；`:753` 前构造 `trace_ctx` 并在非空时注入 thinking。
3. `score.py:328-341` 修改 detail 构造与 upsert_score 调用（规则2）。
4. 验证清单跑通 → 报告。

## 五、红线

1. **业务表 detail 必须干净**——`StockScore.detail` / `position_plan.detail` 不得再含 `model_thinking`/`tool_trace`。用 DB 查询或单测断言。
2. 默认 `AGENTIC_ENABLE=false` 单发回归全 pass（thinking 空，行为零变化）。
3. 只动 repo.py + score.py 2 文件；不动 trace.py / position.py / graphs / sell.py。
4. `thinking_summary=None` 默认兼容旧调用，不破坏既有 `upsert_*` 调用点。
5. 不加新测试；沿用既有 `test_score` / `test_reasoning` 回归 + 一条断言（细节）。

**Claude 端省 token**：只 grep `thinking_summary`/`upsert_score` 定位；复用 `trace_score`/`summarize_agentic_trace`；docstring ≤3 行；报告 ≤10 行；改动 ≤40 行（超额停下）。

## 六、验证清单

- [ ] `AGENTIC_ENABLE=false` 回归：score 相关测试全 pass 且 `StockScore.detail` 无 thinking
- [ ] `AGENTIC_ENABLE=true` 600519 实测：`StockScore.detail` 干净（断言无 model_thinking/tool_trace）；`ai_reasoning_trace.ext_info` 含 model_thinking + tool_trace
- [ ] 行为只动 repo.py + score.py 两文件
- [ ] 改动 ≤ 40 行