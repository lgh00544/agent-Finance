# Discover 前瞻兑现子 Agent · Claude Code 执行指令

> 生成：Lark / 2026-08-21 00:50
> 执行：Claude Code　|　决策人：sir
> 原则：仅含需求 + 规则 + 约束，不含实现代码；风格跟现有 Discover / repo / prompt 走。
> 依赖：无代码依赖。建议在「经验沉淀急救」合入后再跑，避免同一周两处改 `agent_call` 周边；**本指令不改经验沉淀**。
> 工时预估：1 批次，0.5–1 天。
> 关联方案：`D:\self\Discover前瞻子Agent_方案.md`（引用不重写）

---

## 〇、元信息与已核实事实（先读，禁止再猜）

**不是新业务 Agent。** 现有 8 个业务 Agent 名单不变。本需求 = Discover 漏斗里终选 prompt 的第 5 个思维角色 + 代码层一组对照事实。

**已核实**：

| 项 | 位置 / 事实 |
|---|---|
| Discover 图 | `backend/app/graph/graphs.py` `_build_discover`：`market_condition → hard_filter → llm_shortlist → enrich_news → enrich_data → llm_final`，**边不许改** |
| 子 Agent 现状 | `agent_prompts/discover_prompt.py` L79–90 已有 4 个子 Agent 文案；`discover.py` **无**对应节点 / 无第二次 LLM |
| 终选调用 | `discover.llm_final`：一次 `agent_call(agent="discover_final", DEEP, schema=DiscoverOutput)` |
| 终选 user | `discover_prompt.build_final_prompt(table, news, cap, market_note, hot_money_context)` |
| 截面列 | 威科夫：`pct_change_5d / dist_52w_high_pct / pos_52w / ma20_pos_pct / ma60_pos_pct / vol_5_20`；资金 enrich：`main_net_3d/5d/10d`（无当日则不写） |
| 已有前瞻碎片 | `common.agent_call` 拼接位 5.5 对 discover/discover_final 注入近 20 只 T+5 摘要；prompt 周期偏好「1–2 周 8–15%」无兑现检查 |
| T+N 实绩 | 见方案文档：T+3 胜率 65.7%、T+5 39.4%（近 20 只 35% / -0.12%）、B 的 T+5 差于 C |
| 落库 | `repo.upsert_candidate(..., detail=)`，detail 已含 dimensions / final_advice / stock_type |
| 前端 | React `CandidatesPage.tsx` 已展示 `confidence_tier` / `final_advice` / `dimensions`；Streamlit 本批次不动 |
| 对账表 | `candidate_track_verify` + `repo.list_track_verify`；`track_verify.get_selection_performance_summary("t5")` 已存在 |

**根因**：终选在问「现在像不像好票」，没问「这波 5 日更可能延续还是吐回去」；历史 T+5 只作为过去式摘要，没有对**当前这只**的同类对照。

---

## 一、目标 / 不做什么

**做**：

1. 代码层为 shortlist 每只组装【前瞻对照事实】（纯统计 / 已有列，零 LLM）
2. prompt 增加第 5 子 Agent「前瞻兑现」，主 Agent 收口受其约束
3. schema + 落库 `detail` 增加 `horizon_bias` / `horizon_clarity` / `horizon_note`
4. React 候选卡/详情展示前瞻三态（不改选股规则本身）
5. `final_advice` 必须带前瞻三态；回吐且清晰度非低 → 禁止强烈推荐

**不做**：

- 不新建 `forward_view.py`、不加 LangGraph 节点、不加第二次 `agent_call`
- 不预测涨跌幅 / 目标价 / 概率百分数
- 不改 Score 六因子、HARD_RULES、市况档位上限、`discover_top_n`、成交额硬过滤
- 不新建 history 表、不改 `candidate_track_verify` 表结构（可选：把 horizon 快照抄进已有 `verify_result` JSON，抄不了就只放 candidate.detail）
- 不改 Streamlit
- 不改经验沉淀 Worker / EXTRACT_SYSTEM
- 不把「同类样本不足」做成一票否决

---

## 二、架构约束

| 对象 | 动作 | 约束 |
|---|---|---|
| `agent_prompts/discover_prompt.py` | 改 SYSTEM_PROMPT 子 Agent 段 + SCHEMA_DESC；`build_final_prompt` 增加前瞻事实段参数 | 只改引号内中文 + 函数签名兼容；禁止在 prompt 文件写业务 Python 计算 |
| `backend/app/agents/schemas.py` `DiscoverCandidate` | 增 3 字段，**全部带默认值** | 与 MarketIntel v3 同样理由：旧缓存/旧输出不炸；pattern 锁死三态 |
| `backend/app/agents/discover.py` | enrich 后组装对照文本；`llm_final` 传入；落库写入 detail | 组装失败整段省略；热路径仍一次 LLM |
| `backend/app/services/track_verify.py` 或 discover 内纯函数 | 同类 T+5 分组统计 | 走 `repo.list_track_verify`，禁止新 SQL 网关文件；样本不足返回「不足」文本而非假数字 |
| `backend/app/graph/graphs.py` | **禁止改** | — |
| `web/src/pages/CandidatesPage.tsx` | 展示徽章 + note | 只改 React；涨=红、跌/回吐=绿（A 股惯例） |
| `common.py` 拼接位 5.5 | **保持**近 20 只摘要 | 前瞻段是 per-stock 对照，两者并存不互相替代 |

解耦：前瞻是 Discover 终选的输入切片，Score / Position / Monitor 不读 horizon 字段（本批次）。Agent 之间禁止因此互相调用。

---

## 三、规则

### 3.1 对照事实文本（代码层）

对 `state["shortlist"]` 每只输出一块，建议格式（语义必须有，排版可按项目紧凑表风格）：

```
【前瞻对照】{code} {name}
位置：5日斜率 {pct_change_5d}%；距52周高点 {dist}%；区间位置 {pos_52w}%；MA20 {ma20}% / MA60 {ma60}%；量能5/20 {vol_5_20}
资金：3/5/10日主力 {a}/{b}/{c}（无当日则写「当日资金不可用」）
同类T+5：桶={位置桶或类型} 样本={n} 胜率={wr}% 均收益={avg}%（n<5 写「样本不足，禁止当作结论」）
自身历史入选：{最近1–2次 select_date + t3 + t5，无则「无」}
```

位置桶建议（实现自定边界但必须写进注释并单测稳定）：按 `pos_52w` 分低/中/高三档（例如 &lt;40 / 40–70 / &gt;70），优先用桶；`stock_type` 在初选输出若已有则作为第二分组，样本仍 &lt;5 则退回仅桶，还不够则整段不足。

全市场近 20 只 T+5 摘要继续走拼接位 5.5，不要复制进这块。

### 3.2 三态定义（给 LLM 的，不是代码阈值）

| 态 | 含义（定性） | 收口含义 |
|---|---|---|
| 延续 | 位置未末端、量价未背离、同类 T+5 未明显为负 | 可维持当下档位 |
| 回归 | 中性/震荡，方向不明或样本不足 | 不得上调档位；clarity 低时按回归处理 |
| 回吐 | 高位 + 放量滞涨/短线已大涨 + 同类 T+5 偏负，或自身历史入选后 T+5 为负 | 禁止强烈推荐；优先观察或剔除 |

LLM **不得**输出除这三字以外的 bias。clarity：关键列缺失或同类 n&lt;5 → 低。

### 3.3 收口硬约束（prompt 软约束 + 代码硬兜底双层）

- `horizon_bias=回吐` 且 `horizon_clarity` 为高或中 → `confidence_tier` 不得为「强烈推荐」；`focus_type` 倾向「观察」；理由/风险须写回吐（写进 prompt）
- **代码层硬兜底（必做，6 行）**：`discover.py` `llm_final` 在 Pydantic parse 之后、`detail` 写入之前，**必须**加校验：若 `horizon_bias=回吐 且 clarity∈{高,中} 且 confidence_tier=强烈推荐`，强制降档 `confidence_tier="建议关注"` + `focus_type="观察"`，并 `logger.warning("[前瞻兜底] %s 回吐+清晰度%s → 强烈推荐降档建议关注", stock_code, clarity)`。理由：Pydantic schema 无字段间约束，prompt 软约束不够，必须代码硬兜底防 LLM 自作主张。
- 与当下强势冲突：允许保留在池内（宁缺毋滥仍由主 Agent 决定），但必须降档并在 `final_advice` 点明冲突
- clarity=低：前瞻不得单独作为剔除理由
- 禁止在任何字段写「预计涨 x% / 目标价 / 胜率 70%」——胜率数字只允许**引用**注入事实里已出现的历史统计

### 3.4 Schema + 落库防丢键

`DiscoverCandidate` 增加（名必须一致，前端/落库都用这套）：

- `horizon_bias: str` 默认 `"回归"`，pattern `延续|回归|回吐`
- `horizon_clarity: str` 默认 `"低"`，pattern `高|中|低`
- `horizon_note: str` 默认 `"前瞻数据不足"`

`dimensions` 仍固定五维（基本面 / 技术趋势 / 资金/游资 / 舆情/风险 / 行业景气）。`final_advice` 文案里的「N/5 维支持」口径不变，前瞻另起分句。

`llm_final` 写 detail 时三字段必须写入；缺则用 schema 默认，禁止静默丢键。

**额外防丢键（必做）**：`detail = {...}` 必须用防御式 merge，禁止整 dict 覆盖导致旧字段（`confidence_tier` / `final_advice` / `dimensions` / `risks` / `focus_type` / `enriched` 等 14 项）丢失。实现方式二选一：

- **方案 A（仅限 discover 调用点封装）**：`discover.py:634` 的 `detail = {...}` 构造前先 `existing = repo.get_candidate_detail(stock_code, trade_date) or {}; detail = {**existing, **new_detail}`，**只在本函数内封装**。**不要改 `repo.upsert_candidate` 内部**——该函数被 ScoreAgent / MonitorAgent / PendingExperienceWorker 共同调用，改一处会改变其他 Agent 的"整覆盖"语义，违反"不超载既有 Agent"铁律。
- **方案 B**：`discover.py:634` 的 detail 构造用 `existing = repo.get_candidate_detail(code, date) or {}; detail = {**existing, **new_detail}`

> **执行端选 B 或方案 A 局部封装**（不要直接动 `repo.upsert_candidate`）。

### 3.5 展示

React 候选列表与详情：

- 徽章文案：`前瞻·延续` / `前瞻·回归` / `前瞻·回吐`
- **颜色双维度独立**（不与 `confidence_tier` 抢色）：
  - 前瞻徽章用 antd Tag 三态：`延续='success'` / `回归='default'` / `回吐='warning'`
  - `confidence_tier` 维持原色 `'red' / 'orange' / 'blue'`（强烈推荐/建议关注/谨慎观察）
  - 视觉上前瞻徽章与信心档徽章是两个独立 Tag 并列，**不互相覆盖、不抢色**
  - **不**直接用 `var(--up)`（红）/`var(--down)`（绿）——会与 confidence_tier 强烈推荐=红撞色，且 A 股"涨红跌绿"在"涨跌"语境成立，在"延续/回吐"语境会误导
- 详情展示 `horizon_note` 原文，不改写

功能未成熟不展示 → 本字段有默认值即视为可展示；clarity=低 时徽章仍显示但 note 为「数据不足」，不要藏起来让人以为没跑。

---

## 四、实现参考

- 方案：`D:\self\Discover前瞻子Agent_方案.md`
- 图：`backend/app/graph/graphs.py` L18–33（只读）
- 终选：`backend/app/agents/discover.py` `enrich_data` / `llm_final`（约 L541–650）
- 初选表列：同文件 `_TABLE_COLS` / `_WYCKOFF_COLS` / `_ENRICH_COLS`
- Prompt：`agent_prompts/discover_prompt.py` `SYSTEM_PROMPT` 子 Agent 段、SCHEMA_DESC、`build_final_prompt`
- 全局纪律：`agent_prompts/common.py`「不预测绝对涨跌」——本需求是定性三态，不违反
- Schema：`backend/app/agents/schemas.py` `DiscoverCandidate`
- 统计：`backend/app/services/track_verify.py` `get_selection_performance_summary`；`repo.list_track_verify`
- 落库：`discover.llm_final` 内 `detail = {...}`
- 前端：`web/src/pages/CandidatesPage.tsx`（TIER_MAP / final_advice Alert 附近）
- 注入先例：`hot_money_svc.build_hot_money_context` 空则整段省略——前瞻组装照抄这个降级法
- 状态：`graph/state.py` 不必为 horizon 加顶层键（放 data_enrichment 或 llm_final 局部变量即可）

---

## 五、执行顺序

1. 对照方案 §1 自己用 SQL 复核 T+3/T+5 数量（防数据已变），写进执行报告开头
2. 纯函数：输入 shortlist + track 列表 → 前瞻对照文本；n&lt;5 / 缺列 单测
3. `build_final_prompt` 增加可选参数 `horizon_context: str = ""`，空则整段省略；**先 `grep -rn build_final_prompt backend/ tests/` 验证无 assert 严格匹配 prompt 长度**（避免 `tests/test_hot_money_inject.py:85` 等老测试因 prompt 多一段而 fail）
4. SYSTEM_PROMPT：4 子 Agent 改为 5；SCHEMA_DESC 补三字段示例；收口硬约束写入
5. Schema 三字段带默认 + pattern
6. `llm_final`：组装 → 传入 → detail 写入
7. React 徽章 + note
8. 单测：  
   - prompt 组装含/不含前瞻段  
   - schema 缺字段仍能 parse（默认回归/低）  
   - 对照统计：人为 10 条同桶 track → 文本含胜率；3 条 → 样本不足  
   - **不**对 LLM 输出做「必须回吐」金标测试
9. `grep -n horizon_bias backend web` 与 `graphs.py` diff 核对未改边
10. 停下来报告 sir：改了哪些文件、一条样例 detail JSON、前端截图或说明。等验收后再动 Score / 校准

---

## 六、验证清单

- [ ] `graphs.py` 无 diff（或仅无关空行以外的零业务改动；有业务改动即失败）
- [ ] 无新文件 `forward_view.py` / 无新 Agent 模块 / 无新表 migration
- [ ] `DiscoverCandidate` 三字段有默认值 + pattern
- [ ] `upsert_candidate` 的 detail 含 `horizon_bias/clarity/note`，**且为防御式 merge 而非整 dict 覆盖**（见 §3.4）
- [ ] **代码层硬兜底已加**：在 `discover.py` `llm_final` 验证 `回吐+高/中 clarity+强烈推荐 → 强制降档建议关注+观察` 的 6 行兜底逻辑存在（见 §3.3）
- [ ] SYSTEM_PROMPT 能 grep 到「前瞻兑现」且仍能 grep 到原 4 个子 Agent 职责
- [ ] `build_final_prompt` 无对照事实时行为与今日一致（可 diff 旧调用默认空串）
- [ ] 拼接位 5.5 近 20 只摘要仍在 `common.py`
- [ ] HARD_RULES / Score prompt / 六因子未改
- [ ] CandidatesPage 能看到前瞻徽章（`success/default/warning` 三态，与 confidence_tier 独立），Streamlit 未改
- [ ] 单测覆盖：①统计不足 + schema 默认 ②硬兜底逻辑（构造一条 `回吐+强烈推荐` 断言降档）③防丢键（构造 detail 含旧字段，验证不被覆盖）
- [ ] 未在 prompt 或代码里让 LLM 输出目标涨跌幅
- [ ] **离线回放 8/12 那批「T+3 大涨 T+5 吐」票，≥60% 的票前瞻 bias=回吐 即算合格**（人工抽验说明，不作硬单测；市况不可复现）

---

## 七、红线

- auto-merge / 本批次 **永不**修改交易规则表、HARD_RULES、研判标准死阈值（K8 的 30%/1 亿等仍只在知识库作参考权重）
- 禁止新建业务 Agent、禁止 Discover 图加节点、禁止终选再打一枪 LLM
- 禁止用 LLM 报具体涨跌数字；代码层禁止发明「延续概率」模型分冒充事实
- 同类样本不足不得一票否决
- 遇「必须改 agent_call 段序才能注入」或「必须改 Score 权重」→ 停下报告 sir，不自行扩 scope
- 经验沉淀急救若尚未验收：本批次文件集合不要去碰 `experience_worker.py` / `experience_prompt.py` / `router._exp_summary`
