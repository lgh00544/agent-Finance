# 智能体研判环 收尾微修：AlertLog.signal 干净（thinking 走 trace）

- 生成：Lark 2026-08-27
- 决策：sir「可以」（批4-B 遗留第1点设成收尾修）——批4-B 验收通过，本微修把 `AlertLog.signal` 里的 thinking 摘出去，与批3「业务表干净」原则对齐
- 类型：简单任务，改动 ≤ 20 行
- 上游：批4-B（monitor.py 高危复核已验，uncommitted）；参照批3 `upsert_score(thinking_summary=...)` 成熟模式

## 一、目标

`repo.insert_alert` 加可选 `extra` 参数：`AlertLog.signal` 保持干净（不混 thinking），thinking 只经 `trace_alert.ext_info` 进审计链——与批3 口径完全一致。

## 二、架构约束

- 只动 2 文件：`repo.py` + `monitor.py`。追 `insert_alert` 全部调用点（monitor / portfolio_sentinel / pre_market_screen / take_profit）**保持默认 None 零行为**，一并推。
- 不碰 `trace_alert` 既有 ext_info 逻辑（已天然透传 signal 除 reasons/key_levels/risks 外的全量键）。
- 不引新库 / 不改表。

## 三、规则

1. **`repo.py:790 insert_alert`** 加可选参 `extra: dict | None = None`：
   - `signal` 存**干净**版本：`row.signal = signal`（另 `extra` 从 signal 中剔除的中 thinking 键由调用方先剥，见规则2）。
   - `trace_alert`（签名于 `reasoning_trace.py:271`）改为：`ext_info` 额外 merge `extra`（若非空）：
     ```python
     _ext = {k: v for k, v in signal.items() if k not in ("reasons", "key_levels", "risks")}
     if extra:
         _ext.update(extra)
     ... "ext_info": _j(_ext) ...
     ```
   - 默认 `extra=None`：exactly 与现状等价（零行为）。
2. **`monitor.py:313`**（agentic 留痕处，批4-B 新增）改为：
   - 调 `insert_alert` 前，从 `signal` 中 `pop("model_thinking","")` / `pop("tool_trace","")` 到 `extra`；`signal` 传干净副本，`extra=({"model_thinking": m, "tool_trace": t} if (m or t) else None)`。
   - 这样 `AlertLog.signal` 不含 thinking；thinking 仍经 `trace_alert.ext_info` 留痕。
3. `monitor.py:272`（rule_fallback，无 thinking）与其他调用点（portfolio_sentinel / pre_market / take_profit）**不改**（不传 extra，零行为）。

## 四、执行顺序

1. `repo.py:790` 给 `insert_alert` 加 `extra=None` 参；重构其内 `trace_alert` 调用透传 extra。
2. `reasoning_trace.py:271 trace_alert` 加 `extra: dict | None = None` 参数，`ext_info` merge extra。
3. `monitor.py:313` agentic 分支：剥 thinking 到 extra，`signal` 干净。
4. 验证清单 → 报告。

## 五、红线

1. `AlertLog.signal` **必须干净**——DB 断言 `AGENTIC_ENABLE=true` 高危告警后 signal 无 `model_thinking/tool_trace`。
2. `trace_alert.ext_info` 仍含 thinking（审计不放丢）——断言 ext_info 有两键。
3. 默认 `extra=None` 零行为：既有 `insert_alert` 调用点（portfolio/pre_market/take_profit）回归全 pass。
4. 只动 2 文件（repo.py + reasoning_trace.py + monitor.py 实际3，因 trace_alert 在 reasoning_trace.py）；≤20 行。
5. 不引新库/新表。

**Claude 端省 token**：只 grep `insert_alert`/`trace_alert`/`extra` 定位；复用既有 trace_alert 透传；docstring≤3 行；报告 ≤10 行；改动 ≤20 行。

## 六、验证清单

- [ ] `AGENTIC_ENABLE=true` 高危告警：`AlertLog.signal` 无 thinking；`trace_alert.ext_info` 有 model_thinking/tool_trace
- [ ] `AGENTIC_ENABLE=false` + 非 agent 调用点（pre_market/take_profit/portfolio）回归全 pass（extra 默认 None 零行为）
- [ ] 改动 ≤20 行；只动 3 文件（实际：repo.py/reasoning_trace.py/monitor.py）