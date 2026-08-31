# 批5 · 留痕展示增强（React）— Claude Code 执行指令

## 0 元信息

- 生成者：Lark / 决策人：sir / 执行者：Claude Code
- 前置：批1-4 已验收（agentic 通道跑通，Score/Sell/Monitor 的思考+工具轨迹已写入 `ai_reasoning_trace.ext_info`，键为 `model_thinking`/`tool_trace`，均为文本摘要）
- 原则：React 新版唯一前端（Streamlit 已退役）；后端零改动；按需单查不拉全量长文本

## 一 目标

把已沉淀但前端未展开的 **agentic 研判轨迹**做成可读区：在 ReviewsPage 的「推理留痕」卡片里，对每一条留痕支持展开 agentic 时的 **思考轨迹（model_thinking）+ 工具执行轨迹（tool_trace）**。非 agentic 留痕维持现状。

- **不做**：不新建独立页面；不改后端/API/repo/reasoning_trace；不把所有 ext_info 全量拉进列表；不改其它入口（评分弹窗/持仓卡/告警卡）——本期仅 ReviewsPage 一处。

## 二 架构约束

- 只动 **React**（`web/src/`），后端/`api/traces` 零改动（能力已具备）。
- 沿用「轻量列表 + 详情按需单查」设计：列表 `traces()` 仍不含长文本；点开某条才 `traceDetail(traceId)` 拿 `ext_info`。

## 三 规则

- 数据链路（已就绪，只消费）：
  - 列表：`web/src/api/traces.ts:7 traces()` → `GET /api/traces`（轻量，无 `ext_info`）。
  - 详情：`web/src/api/traces.ts:19 traceDetail(traceId)` → `GET /api/traces/{id}` → 返回对象含 `ext_info`（**原始 JSON 字符串**）。本条已存在，复用。
  - `ext_info` JSON 内：`model_thinking`（思考文本）、`tool_trace`（工具执行摘要文本）；`tool_trace` 是**文本摘要**（非结构化数组），直接 pre 展示，**不要当作 JSON 列表渲染时间线**。）
- 渲染：
  - 有 `model_thinking` → 折叠区「🧠 思考轨迹」pre 全文。
  - 有 `tool_trace` → 折叠区「🛠 工具执行轨迹」pre 全文。
  - 无两键（非 agentic 留痕 / ext_info 为空）→ 只显示现在已有的 `summary/final_conclusion` 摘要，**不出现折叠区**，行为与现状一致。
- 解析容错：`ext_info` 字符串 `JSON.parse` 需 try/catch，解析失败仅显示现有摘要，**不抛错不白屏**。
- 位置：ReviewsPage 现有「推理留痕（ai_reasoning_trace · 该股该日）」卡片（`web/src/pages/ReviewsPage.tsx:146`）内，`renderItem` 每条留痕扩展。

## 四 执行顺序

1. 读 `package.json` 确认用 AntD（已有 `Card/List/Tag/Collapse`）与 `web/src/pages/ReviewsPage.tsx` 留痕卡片段（:146-165）。
2. 留痕卡片 `renderItem`：为每条加「详情」触发 → 复用 `traceDetail(row.trace_id)`；路由/状态控制（`useState<number|null>` 存展开的 traceId）。
3. 点开时 `get(`/traces/{id}`) → `JSON.parse(res.ext_info)` → 渲染两个折叠区（思考/工具轨迹），解析失败仅回退摘要。
4. 不 agentic 的留痕：不触发详情请求，渲染原样。
5. 类型：`AiTrace`（`web/src/types/index.ts:252`）可不动（`trace_detail` 返回 `Record<string,unknown>`）；如要提示可加 `ext_info?: string`（可选，不强制）。

## 五 验证清单

- [ ] `web` 目录 `tsc` 零错（未使用 import/变量需 grep 核对，tsc 不报警）
- [ ] React dev server（5173）实测：一条有 agentic 留痕的复盘（score/sell 走的 agentic 源）→ 展开显示「思考轨迹 + 工具执行轨迹」两折叠，pre 文本与 detail 返回一致
- [ ] 非 agentic 留痕：不出现折叠区、不白屏、不崩页面（现状行为）
- [ ] `ext_info` 非法 JSON 时仅回退摘要、不报错
- [ ] 后端零改动：git diff 确认无 `backend/`、`api/traces.ts`、`types` 改动

## 六 红线（决策底线）

1. **后端零改动**——`repo.get_trace/list_traces`、`reasoning_trace`、`/api/traces` 一律不动（detail 已返回 ext_info，改后端属于越界）。
2. **只动 React `web/src/`**，≤150 行；`agentic.py`/graphs/router/服务端不动。
3. **不拉全量**：列表仍是轻量摘要，长文本（思考几千字）只在点开该条时单查——严禁在列表直接带全量 ext_info。
4. `tool_trace` 是文本摘要，**不是 JSON 数组**，不得造「工具调用时间线」解析逻辑。
5. 不引新组件/新库，全部用 Ant traces + antd 现有部件。
6. **Claude Code 端省 token**：已读过本文件这 6 段信息不再 read 全量前端文件（grep `推理留痕`/`traceDetail` 定位）；只动 ReviewsPage.tsx；docstring ≤3 行；复用 `traces.ts` 已有 `trace_detail`；报告 ≤10 行；行数超 150 停下报告。