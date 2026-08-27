# 智能体研判环 批4-B：Monitor 高危信号 agentic 复核（LIGHT 主链不动）

- 生成：Lark 2026-08-27
- 决策：sir「三方向都要做」P1；依赖批4-A（工具裁剪/轮数控制已就绪）
- 类型：中等任务（Monitor 加"高危才触环"分支，主链零变化），改动 ≤ 90 行
- 上游：批4-A 已验收（agentic_call 支持 tools_allowlist/max_rounds）；Monitor 现状 `monitor.py:140 llm_signal`（LIGHT 高频）

## 一、目标

Monitor 是**高频 LIGHT 节流**节点（`monitor.py:227 model_level=LIGHT` + 小时级短 TTL + 分钟级触发），**不能套全环**（8 轮工具成本/延迟暴涨，违背节流初衷）。本批做**分级**：
- **常规**：维持现有 LIGHT 单发（零变化）。
- **高危**：当 LIGHT 单发判出 `severity in (warning, critical)` 时，**升级走 agentic 环复核**（DEEP + 裁剪工具 + 短轮数），用工具核验数据后给出更稳的最终信号。
- 高危环失败 → 回退 LIGHT 结果（不中断监控）。

## 二、架构约束

- 只动 `monitor.py`；复用批4-A 的 `agentic_call`（`common.py:375`）与 `select_tools`。
- **不动** `agentic.py` 环逻辑、`push_alert_node`（:258 刚性代码）、`_rule_fallback_alert`（:241）、graphs/router。
- 主链 LIGHT 单发 `agent_call` 零变化；agentic 仅在高危时追加一次 DEEP 复核。
- 不引新库 / 不改 DB 表。

## 三、规则

1. **`llm_signal`（:140）在现有 `agent_call` 之后**追加高危复核分支：
   ```text
   if settings.agentic_enable and output.severity in ("warning", "critical"):
       # 高危 → agentic 环复核（DEEP + 裁剪工具 + 短轮数）
       agentic_out, agentic_trace = agentic_call(
           agent="monitor", cache_key=f"{code}:{today}:{hour}:agentic",
           system_prompt=_AGENTIC_TOOL_NOTE + monitor_prompt.SYSTEM_PROMPT,
           user_prompt=monitor_prompt.build_user_prompt(holding_info, _compact(quote_data), news_context),
           schema=MonitorOutput, ttl_seconds=3600, model_level=ModelLevel.DEEP,
           tools_allowlist=["get_quote", "get_daily_kline", "get_news", "get_fund_flow", "search_knowledge"],
           max_rounds=4, target_label=f"{name}({code})")
       if agentic_out is not None:
           output = agentic_out   # 高危复核结果覆盖
           # 留痕：thinking/tool 摘要写入 state（供 trace 透传）
           state["agentic_trace"] = agentic_trace
   ```
   - `cache_key` 加 `:agentic` 后缀，与 LIGHT 主链键隔离（避免高危复核污染常规缓存）。
   - `ttl_seconds=3600`（1h，高危复核结果当日复用）；`max_rounds=4`（高危复核短轮，够核验关键数据即可）。
   - 工具白名单：**去 `get_financial`**（监控侧重行情/消息/资金，不看财务），挂 5 工具。
2. **留痕**：`push_alert_node`（:258）落库时，若 `state.get("agentic_trace")` 非空，把 `summarize_agentic_trace` 摘要写入告警 `ext_info`（`repo.insert_alert` 的 detail 参数，:253 已有该参）。**不新增表**。
3. **失败回退**：`agentic_call` 内部已回退单发（返回 None 时用 LIGHT 结果）；本分支 `if agentic_out is not None` 才覆盖，None 则保持 LIGHT 输出，不抛异常。
4. **节流保护**：高危复核仅当 `agentic_enable` 且 `severity` 高危才触发；常规 `info` 不触发，维持高频零额外成本。

## 四、执行顺序

1. `monitor.py:140 llm_signal` 在 `agent_call` 后加高危复核分支（规则1）。
2. `monitor.py:258 push_alert_node` 落库时透传 agentic 留痕（规则2）。
3. 验证清单 → 报告。

## 五、红线

1. **LIGHT 主链零变化**——`AGENTIC_ENABLE=false` 或 `severity=info` 时，Monitor 行为与现状完全一致（回归断言）。
2. 只动 `monitor.py` 1 文件；不动 `agentic.py`/`push_alert_node` 刚性逻辑/`_rule_fallback_alert`/graphs。
3. 高危复核 `cache_key` 必须带 `:agentic` 后缀，与 LIGHT 键隔离。
4. 不加新测试；沿用 monitor 相关回归 + 断言（高危触发/常规不触发/失败回退）。
5. 改动 ≤90 行（超额停下）。

**Claude 端省 token**：只 grep `agentic_enable`/`severity`/`agentic_trace`/`insert_alert` 定位；复用 `agentic_call`/`summarize_agentic_trace`/`_AGENTIC_TOOL_NOTE`；docstring≤3 行；报告 ≤10 行。

## 六、验证清单

- [ ] 回归：`AGENTIC_ENABLE=false` 下 monitor 相关测试全 pass（LIGHT 主链零变化）
- [ ] `AGENTIC_ENABLE=true` + `severity=info` → 不触发 agentic（常规高频零额外成本）
- [ ] `AGENTIC_ENABLE=true` + `severity=warning/critical` → 触发 agentic 复核，`cache_key` 带 `:agentic`，工具挂 5（无财务）、max_rounds=4
- [ ] agentic 复核失败（返回 None）→ 回退 LIGHT 结果，不中断
- [ ] 高危复核留痕写入告警 `ext_info`（thinking + tool_trace）
- [ ] 改动 ≤90 行；只动 monitor.py