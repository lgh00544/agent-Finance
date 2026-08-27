# 智能体研判环 批4-A：动态轮数预算 + 工具裁剪（agentic 通道公共能力）

- 生成：Lark 2026-08-27
- 决策：sir「三个方向都要做，自定优先级」——本批为**公共能力底座**，0 依赖（后续 Monitor 接入、留痕展示都建立在裁剪+轮数控制之上），故列 P0 先行
- 类型：中等任务（改 agentic 通道底座，不改任何业务节点逻辑），改动 ≤ 90 行
- 上游：批1/2/3 已验收（a7d7bc5 / 98f4564 / 9898865）；公共层现为 `common.py:258 build_agent_context` / `:375 agentic_call`

## 一、目标

1. `agentic_call` 支持**工具白名单裁剪**（按节点只挂相关工具，省 token / 防模型跑偏调无关工具）。
2. `agentic_call` 支持**动态轮数预算**（按节点语义传 max_rounds，不再硬编码 8；配合 run_agentic_judge 已实现的"无工具调用即 final"天然早停）。
3. 默认 `None`＝全量 6 工具 + 8 轮，**对现有 score/sell 调用零行为变化**（兼容）。

## 二、架构约束

- 只改通用能力：`common.py` `agentic_call` + `agentic_tools.py` 加辅助；`score.py`/`sell.py` 各传一个裁剪白名单（作为该批的调用示例）。
- **不动** `agentic.py`/`run_agentic_judge` 环逻辑（只透传 max_rounds）、不改 graphs/router、不引新库。
- Agent 解耦：两节点各自白名单不相干，禁止共用一份。

## 三、规则

1. **`agentic_call` 加两可选参**（`common.py:375`）：
   ```
   tools_allowlist: list[str] | None = None   # None=全量6工具；非空=只挂白名单
   max_rounds: int | None = None              # None=8
   ```
   内部：`tools, tool_funcs = select_tools(tools_allowlist)`（取过滤后子集）；`run_agentic_judge(..., tools=tools, tool_funcs=tool_funcs, max_rounds=(max_rounds or 8))`。撤回：`import` 处不再裸传全局 `TOOLS/TOOL_FUNCS`，改经 `select_tools`。
2. **`agentic_tools.py` 加 `select_tools(allowlist)`**：
   ```python
   def select_tools(allowlist: list[str] | None = None):
       if not allowlist:
           return TOOLS, TOOL_FUNCS
       tools = [t for t in TOOLS if t["function"]["name"] in allowlist]
       funcs = {k: v for k, v in TOOL_FUNCS.items() if k in allowlist}
       return tools, funcs
   ```
3. **节点白名单（调用示例，体现"按需裁剪"）**：
   - `score.py:272` agentic 分支：`tools_allowlist=["get_quote","get_daily_kline","get_news","get_financial","get_fund_flow","search_knowledge"]`（全量，决策瓶颈可全核），`max_rounds=8`。
   - `sell.py` agentic 分支（`:213`）：**去财务**——`tools_allowlist=["get_quote","get_daily_kline","get_news","get_fund_flow","search_knowledge"]`，`max_rounds=6`（卖出判断侧重行情/消息/资金，不看财务，省一轮）。
4. 缓存键不变（裁剪不改缓存语义）；`_AGENTIC_TOOL_NOTE` 文案保持，不改工具说明。

## 四、执行顺序

1. `agentic_tools.py` 加 `select_tools()`（紧邻 TOOL_FUNCS 下方）。
2. `common.py:375` `agentic_call` 加两参，内部改 `select_tools` 取子集 + 透传 `max_rounds`。
3. `score.py` / `sell.py` 的 agentic 分支补两参（规则3）。
4. 验证清单 → 报告。

## 五、红线

1. **默认零行为**：`tools_allowlist=None / max_rounds=None` 时必须等价于旧全量8轮——单测断言 score/sell 未传时产出一致。
2. 只动 4 文件（agentic_tools.py / common.py / score.py / sell.py）；`agentic.py` 环逻辑不碰。
3. 不改缓存键 / `_AGENTIC_TOOL_NOTE` 文案。
4. 不加新测试，沿用批1/2 回归 + 断言（裁剪后 TOOLS 长度、无工具调用的早停）。

**Claude 端省 token**：只 grep `tools_allowlist`/`max_rounds`/`select_tools` 定位；复用 `agentic_call`/`run_agentic_judge`/`TOOLS`；docstring≤3 行；报告 ≤10 行；改动 ≤90 行（超额停下）。

## 六、验证清单

- [ ] 单发回归：score/sell 既有测试全 pass（未传裁剪时行为不变）
- [ ] `agentic_call(tools_allowlist=['get_quote'])` 单测 → 只挂 get_quote 一个工具，TOOLS 长度=1
- [ ] `max_rounds=1` 时若首轮无工具调用→即刻 final（早停生效）；有工具调用→终到 budget
- [ ] sell 实测：agentic 分支挂 5 工具（无财务）、6 轮上限
- [ ] 改动 ≤90 行；只动指定文件