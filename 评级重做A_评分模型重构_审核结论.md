# 评级重做A_评分模型重构_审核结论（2026-08-18）

> **结论：GO WITH CHANGES** —— 无 P0 阻塞项，全部集成点实测命中（12/12），文档质量高（cache_key v4 失效、前端展示降级、trace_score 双格式兼容、测试适配清单均已正确处理）。3 个 P1 设计增强建议（potential_flag 代码层推导 / factors 六项强校验 / 权重表述矛盾统一），修正后即可交 Claude Code 执行。
> 交付方式：原文档（`D:\self\评级重做A_评分模型重构_执行指令.md`，822 行）结构完整无需重写，按本结论中的【修订补丁】就地修改对应章节后即可执行。

---

## 一、审核发现（按级别）

### P0（0 个）——无阻塞项

### P1（3 个，建议全部采纳）

#### P1-1：potential_flag 应由代码层推导，而非信任 LLM 输出（解耦铁律）

**发现**：文档 1.3 定义 `potential_flag = 催化≥7 且 动量≤4`，但 3.1 规则 5 + 约束 5 要求"score、grade、potential_flag 全部由 LLM 输出"。这是纯数学条件——**factor 分值（LLM 艺术判断）→ flag（可执行事实）的换算正是 sir 确立的"LLM 输出艺术判断、代码层负责换算为可执行事实"哲学**。LLM 直接输出 bool 存在漏标/错标风险（prompt 指令不可靠），且 flag 与 factors 可能出现矛盾（flag=true 但催化只有 5 分）。

**修订**：schema 保留 `potential_flag` 字段（LLM 在 final_advice 文案中引用），但 `llm_score` 落库前代码强制覆写：

```python
# llm_score 中 agent_call 返回 output 之后、upsert_score 之前追加：
# ---- v4.0 代码层推导 potential_flag（不信任 LLM 自报；factor 分值为 LLM 判断，flag 为事实换算）----
_催化 = next((f.score for f in output.factors if f.factor == "催化"), 0)
_动量 = next((f.score for f in output.factors if f.factor == "动量"), 0)
output.potential_flag = bool(_催化 >= 7 and _动量 <= 4)
```

**测试补充**（test_score_refactor.py 新增）：
```python
def test_potential_flag_derived_from_factors(monkeypatch):
    """代码层按催化>=7 且 动量<=4 覆写 potential_flag（不信任 LLM 自报）"""
    from app.agents import score as score_mod
    # LLM 自报 True 但因子不满足 → 强制 False
    out = ScoreOutput(stock_code="600000", stock_name="测试", score=60, grade="C",
                      factors=[
                          ScoreFactor(factor="催化", score=5, reason="x", signal="中性"),
                          ScoreFactor(factor="动量", score=3, reason="x", signal="看空"),
                      ],
                      potential_flag=True, risk_list=[])
    def _fake_agent_call(**kwargs):
        return out
    monkeypatch.setattr(score_mod, "agent_call", _fake_agent_call)
    monkeypatch.setattr(score_mod.repo, "get_latest_preference", lambda: None)
    monkeypatch.setattr(score_mod.repo, "upsert_score", lambda *a, **k: None)
    state = {"stock_code": "600000", "stock_name": "测试", "trade_date": "2026-08-18",
             "trace": [], "tech_index": {}, "finance_data": [], "fund_flow_rows": [],
             "news_report": [], "basic_info": {}, "hot_money": None}
    score_mod.llm_score(state)
    assert out.potential_flag is False          # 自报 True 被覆写为 False
    out2 = ScoreOutput(stock_code="600000", stock_name="测试", score=60, grade="C",
                       factors=[
                           ScoreFactor(factor="催化", score=8, reason="x", signal="看多"),
                           ScoreFactor(factor="动量", score=4, reason="x", signal="中性"),
                       ],
                       potential_flag=False, risk_list=[])
    monkeypatch.setattr(score_mod, "agent_call", lambda **kw: out2)
    score_mod.llm_score(state)
    assert out2.potential_flag is True          # 因子满足 → 强制 True
```

#### P1-2：factors 六项强校验缺失（LLM 输出 5 项/自创因子名会无声破功）

**发现**：3.1 规则 6 要求"LLM 必须输出恰好 6 个因子、因子名固定"，但 schema `factors: list[ScoreFactor]` 不限制长度与名称——LLM 输出 5 项或自创"情绪面"因子时 pydantic 不拦截，六因子体系静默失效，下游 trace/前端/回测全部基于错误结构。

**修订**：`ScoreOutput` 增加 `model_validator`（与 DiscoverCandidate 的 pattern 强校验风格一致）：

```python
from pydantic import model_validator

_FACTOR_NAMES = {"动量", "催化", "估值", "主线契合", "资金面", "基本面质量"}

class ScoreOutput(BaseModel):
    # ... 原字段不变 ...

    @model_validator(mode="after")
    def _check_six_factors(self):
        names = [f.factor for f in self.factors]
        if len(names) != 6 or set(names) != _FACTOR_NAMES:
            raise ValueError(
                f"factors 必须恰好为六因子且名称固定，收到 {names}（期望 {sorted(_FACTOR_NAMES)}）")
        return self
```

**为什么安全**：校验失败抛 ValidationError → 走 `llm_call_json` 既有重试机制（structured.py:84-131 实测：错误信息回灌 prompt 要求修正，DEEP 3 次；LIGHT 3 次失败降级 DEEP 再 3 次），不新增崩溃路径；`call_llm_cached` 缓存命中路径（structured.py:144 `schema.model_validate(cached)`）因 cache_key 已加 v4 前缀不会命中旧缓存，风险可接受。

**测试补充**：
```python
def test_score_output_rejects_partial_factors():
    """少于 6 因子或因子名不合法 → pydantic 拦截（走 LLM 重试修正）"""
    with pytest.raises(Exception):
        ScoreOutput(stock_code="600519", stock_name="贵州茅台", score=78, grade="B",
                    factors=[ScoreFactor(factor="动量", score=5, reason="x", signal="中性")],
                    risk_list=[])
    with pytest.raises(Exception):
        ScoreOutput(stock_code="600519", stock_name="贵州茅台", score=78, grade="B",
                    factors=[
                        ScoreFactor(factor=n, score=5, reason="x", signal="中性")
                        for n in ["动量", "催化", "估值", "主线契合", "资金面", "自创因子"]],
                    risk_list=[])
```

#### P1-3：1.1 表 vs 3.1 规则 7 表述自相矛盾（权重计算归属）

**发现**：1.1 表"综合分计算"行写 `Σ(因子分 × 权重 × 10)，代码可校验`，但 3.1 规则 7 + 约束 5 写"代码层不做权重计算，score 由 LLM 输出"。若实现者按表格在代码层校验/重算，会形成"代码一套权重、prompt 一套权重"的双实现漂移风险（LLM 微调权重后代码校验误报）。

**修订**：1.1 表格该行改为"综合分计算 | LLM 按 prompt 六因子权重汇总输出 0-100（代码仅透传存储）"，并在 3.1 规则 7 末尾补一句："权重一致性校验（因子分×权重×10 vs score）属评级重做-C 回测环节，本批次不做。"

---

## 二、实测验证记录（全部命中，12/12）

| # | 验证点 | 实测结果 |
|---|--------|---------|
| 1 | ScoreDimension/ScoreOutput 现状（schemas.py:112-128） | 五维 0-100，`dimensions: list[ScoreDimension]`，与文档描述一致 |
| 2 | ScoreDimension 全局引用范围（文档要求执行时搜索） | **已代验**：仅 schemas.py（定义+引用）+ test_hot_money_inject.py 2 测试 4 处（41/44/65/68 行），无其他引用 |
| 3 | Position/Sell/Review 是否依赖 ScoreOutput | 独立：position.py:104 是 PositionOutput 自身 dimensions（DiscoverDimension 系），Sell/Review 零引用 ScoreOutput |
| 4 | StockCandidate.reasons 字段 | models.py:53 存在（SafeJSON list）；实测 30 条候选有数据 |
| 5 | StockCandidate.detail 含 confidence_tier/focus_type/final_advice | 实测 2026-08-17 候选（京东方A/中国巨石/华天科技）均含，get_candidate_context 依赖成立 |
| 6 | get_candidate_snapshot 位置 | repo.py:104 实测存在，get_candidate_context 为新增只读函数（不冲突） |
| 7 | get_latest_market_intel() 返回结构 | repo.py:201-215 实测：trade_date/phase/…/summary/raw，含 summary 供注入 |
| 8 | reasoning_trace.trace_score 现状 | reasoning_trace.py:186-206 按维度名硬编码归因（技术趋势/资金流向/基本面…），兼容改造**必要**且文档实现正确 |
| 9 | call_llm_cached 缓存命中逻辑 | structured.py:141-144 命中后直接 `schema.model_validate(cached)`——**cache_key 不加版本必命中旧格式报错**；文档 v4 前缀（第 65/418 行）处理正确且是必须项 |
| 10 | llm_call_json 校验失败重试 | structured.py:84-131：ValidationError 回灌 prompt 重试（DEEP×3 / LIGHT 降级×3）——P1-2 的 model_validator 方案安全 |
| 11 | upsert_score/detail 列 | repo.py:392，detail 为 SafeJSON dict，新格式 `{"factors": [...], ...}` 兼容 |
| 12 | 前端 2_评分报告.py 兼容性 | `_tab_dims`（第 39 行起）只收 `isinstance(v, dict) and "score" in v` 的字段——factors 列表不进表**不报错**（展示降级），final_advice 高亮仍在；文档"前端不动、评级重做-B 处理"成立 |

**数值域一致性核查**：六因子 0-10 满分 10 → Σ(因子分×权重×10) = 100（权重和 100%），综合 score 0-100 域与评级阈值 A≥75/B 55-74/C<55 一致，无错位。

**graph/router 影响核查**：graphs.py:39-42（collect_data → llm_score → END）节点名不动；router.py:116 消费 `grade` 字符串（A/B/C），阈值变化不影响判定逻辑。

---

## 三、修订补丁汇总（执行前就地对原文档修改）

| 位置 | 修改内容 |
|------|---------|
| 1.1 表"综合分计算"行 | `Σ(因子分 × 权重 × 10)，代码可校验` → `LLM 按 prompt 六因子权重汇总输出 0-100（代码仅透传存储）` |
| 3.1 规则 7 末尾 | 追加"权重一致性校验属评级重做-C 回测环节，本批次不做" |
| 6.1 ScoreOutput schema 定义 | 追加 `model_validator _check_six_factors`（见 P1-2 补丁） |
| 6.2 说明段 | 补充实测结论："全局搜索已完成，ScoreDimension 引用仅 schemas.py + test_hot_money_inject.py 两处" |
| 6.4.2 llm_score 代码 | `agent_call` 返回后、`upsert_score` 前插入 potential_flag 代码覆写（见 P1-1 补丁） |
| 6.7.3 test_score_refactor.py | 新增 `test_potential_flag_derived_from_factors`、`test_score_output_rejects_partial_factors` 两条 |

---

## 四、可执行同步段（直接复制给其他 Agent）

> **审核结论（评级重做A）**：无 P0 阻塞，结论 GO WITH CHANGES。发现的 3 个 P1 设计增强——① `potential_flag` 目前由 LLM 输出，但判定条件"催化≥7 且 动量≤4"是纯数学换算，已要求改为代码层在 `llm_score` 落库前强制覆写（LLM 因子分值为判断、flag 为事实换算，符合解耦铁律，防止 LLM 漏标/自相矛盾）；② schema 的 `factors: list[ScoreFactor]` 不限制长度与因子名，LLM 输出 5 项或自创因子名会无声破功，已要求加 `model_validator` 强校验六因子（校验失败走 `llm_call_json` 既有重试，不新增崩溃路径）；③ 文档 1.1 表"Σ(因子分×权重×10) 代码可校验"与 3.1/约束"代码层不做权重计算"自相矛盾，已统一为"LLM 按 prompt 权重汇总、代码仅透传、一致性校验留到评级重做-C"。其余 12 个集成点全部实测命中（ScoreDimension 引用范围仅 schemas.py+test_hot_money_inject.py 两处、Position/Sell/Review 独立 DiscoverDimension、StockCandidate.reasons/detail 字段齐全、cache_key v4 失效处理正确且必须、前端展示降级方案成立、数值域 0-100 与阈值一致）。按原文档执行即可，仅需就地应用上述 3 处补丁（含 2 条新增测试）。交付物：`D:\self\评级重做A_评分模型重构_审核结论.md`，原文档 `D:\self\评级重做A_评分模型重构_执行指令.md` 无需重写。
