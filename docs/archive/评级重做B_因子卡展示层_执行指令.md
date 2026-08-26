# 评级重做-B：因子卡展示层可视化

> **前置依赖**：评级重做-A 已执行完成（593 passed）。ScoreAgent 的 `stock_score.detail` 已存储新格式：`{factors: [{factor, score, reason, signal}], potential_flag, cross_validation_note, final_advice}`。
>
> **本批次范围**：纯前端展示层，把六因子评分渲染成 sir 确认过的因子卡设计。不改后端、不改 Agent、不改 DB。

---

## 一、改动总览

| # | 文件 | 改动 |
|---|------|------|
| 1 | `streamlit/render.py` | 新增 `factor_cards()` 函数 + CSS（因子卡网格 + 潜力标识 + 交叉验证）；`_TRACE_MODULE_LABEL` 中 `"score": "五维评分"` → `"六因子评分"` |
| 2 | `streamlit/pages/2_评分报告.py` | `_tab_dims()` 检测新格式走 `factor_cards()`，旧格式保留 DataFrame 降级；docstring/caption/tab 标签 "五维" → "六因子" |

**不改的文件**（明确边界）：
- `1_每日候选池.py` / `3_建仓计划.py` / `4_持仓监控.py` / `6_交易复盘.py` — 这些页面的 `dimension_bars()` 渲染的是 DiscoverAgent / PositionAgent / MonitorAgent / SellAgent 的 `DiscoverDimension`（独立体系），与 ScoreAgent 的 ScoreFactor 无关
- `render.py` 的 `dimension_bars()` 函数 — 保持不动，上述页面仍用
- 后端所有文件 — 不改
- `0_系统概览.py` 的 "市况五维" — 指 MarketIntel 的 5 维度，与 ScoreAgent 无关，不改

---

## 二、详细规格

### 2.1 render.py — 新增 CSS

在现有 `/* ===== 维度归因条（v3.0 白盒框架）===== */` 段落之后（约 line 369 `.dim-advice` 之后），追加因子卡专用 CSS：

```css
/* ===== 六因子透明评分卡（v4.0 ScoreAgent 重构） ===== */
.factor-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin: 8px 0 12px;
}
.factor-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 14px;
  transition: border-color 0.2s ease;
}
.factor-card:hover { border-color: var(--border-hi); }
.factor-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.factor-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}
.factor-score {
  font-size: 20px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text);
}
.factor-score .max {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-mute);
}
.factor-bar {
  height: 6px;
  background: var(--bg-input);
  border-radius: 3px;
  overflow: hidden;
  margin: 4px 0 8px;
}
.factor-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}
.factor-signal {
  display: inline-block;
  font-size: 11px;
  padding: 0.05rem 0.4rem;
  border-radius: 3px;
  font-weight: 600;
  white-space: nowrap;
}
.factor-signal.bull {
  color: var(--up);
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.35);
}
.factor-signal.bear {
  color: var(--down);
  background: rgba(16, 185, 129, 0.12);
  border: 1px solid rgba(16, 185, 129, 0.35);
}
.factor-signal.neutral {
  color: var(--text-dim);
  background: rgba(156, 163, 175, 0.12);
  border: 1px solid var(--border);
}
.factor-reason {
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.6;
  margin-top: 6px;
}
/* 潜力标识横幅 */
.potential-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  margin: 6px 0 10px;
  border: 1px solid rgba(245, 158, 11, 0.45);
  border-left: 3px solid var(--warn);
  border-radius: 8px;
  background: rgba(245, 158, 11, 0.08);
  font-size: 13px;
  color: var(--warn);
  font-weight: 600;
}
.potential-banner .ic { font-size: 16px; }
/* 交叉验证结论卡 */
.cross-validation-card {
  border: 1px solid var(--primary-dim);
  border-left: 3px solid var(--primary);
  background: rgba(59, 130, 246, 0.06);
  border-radius: 8px;
  padding: 10px 14px;
  margin: 8px 0;
}
.cross-validation-card .cv-title {
  font-size: 12px;
  color: var(--info);
  font-weight: 600;
  margin-bottom: 4px;
}
.cross-validation-card .cv-body {
  font-size: 13px;
  color: var(--text);
  line-height: 1.7;
}
/* 响应式：窄屏因子卡降为 2 列 */
@media (max-width: 768px) {
  .factor-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
  .factor-score { font-size: 18px; }
}
```

### 2.2 render.py — 新增 factor_cards() 函数

在 `dimension_bars()` 函数之后（约 line 953 `_advice_card` 之后），新增：

```python
# ================= 六因子透明评分卡（v4.0 ScoreAgent 重构） =================
_FACTOR_SIGNAL_CLS = {"看多": "bull", "中性": "neutral", "看空": "bear"}
_FACTOR_SIGNAL_COLOR = {"看多": "var(--up)", "中性": "var(--text-dim)", "看空": "var(--down)"}


def factor_cards(
    factors: list[dict],
    potential_flag: bool = False,
    cross_validation_note: str = "",
    final_advice: str | None = None,
) -> None:
    """六因子透明评分卡（v4.0）：6 张因子卡 3×2 网格 + 潜力标识 + 交叉验证 + 综合评估。
    每因子卡 = 因子名 + 分值(0-10) + 评分条 + 信号徽章 + 打分依据。
    纯展示层映射，无任何研判语义；factors 为空或非 list 时不渲染因子网格。
    """
    factors = [f for f in (factors or []) if isinstance(f, dict)]
    # 潜力标识横幅（代码层已推导，此处纯展示）
    if potential_flag:
        st.markdown(
            '<div class="potential-banner">'
            '<span class="ic">⚠️</span>'
            '<span>潜力标识：催化强但动量弱，可能尚未被定价，值得关注</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    # 因子卡网格
    if factors:
        cards_html = []
        for f in factors:
            name = _esc(str(f.get("factor") or "因子"))
            try:
                score = float(f.get("score") or 0)
            except (TypeError, ValueError):
                score = 0.0
            score = max(0.0, min(10.0, score))
            signal = str(f.get("signal") or "中性")
            reason = _esc(str(f.get("reason") or ""))
            sig_cls = _FACTOR_SIGNAL_CLS.get(signal, "neutral")
            sig_color = _FACTOR_SIGNAL_COLOR.get(signal, "var(--text-dim)")
            width = f"{score * 10:.0f}%"
            cards_html.append(
                f'<div class="factor-card">'
                f'<div class="factor-head">'
                f'<span class="factor-name">{name}</span>'
                f'<span class="factor-score">{score:.0f}<span class="max">/10</span></span>'
                f'</div>'
                f'<div class="factor-bar"><div class="factor-bar-fill" '
                f'style="width:{width};background:{sig_color}"></div></div>'
                f'<span class="factor-signal {sig_cls}">{signal}</span>'
                f'<div class="factor-reason">{reason}</div>'
                f'</div>'
            )
        st.markdown(
            f'<div class="factor-grid">{"".join(cards_html)}</div>',
            unsafe_allow_html=True,
        )
    # 交叉验证结论
    if cross_validation_note:
        st.markdown(
            f'<div class="cross-validation-card">'
            f'<div class="cv-title">交叉验证（与 DiscoverAgent 选股逻辑对比）</div>'
            f'<div class="cv-body">{_esc(cross_validation_note)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    # 综合评估（复用既有 _advice_card）
    if final_advice:
        _advice_card(final_advice)
```

### 2.3 render.py — _TRACE_MODULE_LABEL 更新

将 `_TRACE_MODULE_LABEL` 中 `"score": "五维评分"` 改为 `"score": "六因子评分"`（约 line 1353）。

### 2.4 2_评分报告.py — _tab_dims() 适配新格式

**当前代码**（line 57-73）：
```python
def _tab_dims():
    dims = {k: v for k, v in d.items() if isinstance(v, dict) and "score" in v}
    if dims:
        dim_df = pd.DataFrame([...])
        st.dataframe(dim_df, ...)
    else:
        st.markdown("（该轮未输出分项明细）")
    if d.get("final_advice"):
        render.dimension_bars(None, final_advice=d.get("final_advice"))
```

**替换为**：
```python
def _tab_dims():
    # v4.0 六因子格式检测：detail 含 factors 列表 → 走因子卡渲染
    factors = d.get("factors")
    if isinstance(factors, list) and factors:
        render.factor_cards(
            factors=factors,
            potential_flag=bool(d.get("potential_flag")),
            cross_validation_note=d.get("cross_validation_note") or "",
            final_advice=d.get("final_advice"),
        )
    else:
        # 旧格式降级：{维度名: {score, verdict, advice}} 字典 → DataFrame
        dims = {k: v for k, v in d.items()
                if isinstance(v, dict) and "score" in v
                and k not in ("factors",)}
        if dims:
            dim_df = pd.DataFrame([
                {"维度": name, "得分": v.get("score", ""),
                 "结论": v.get("verdict", ""),
                 "研判依据": v.get("advice") or v.get("comment", "")}
                for name, v in dims.items()
            ])
            st.dataframe(dim_df, width="stretch", hide_index=True)
        else:
            st.markdown("（该轮未输出分项明细）")
        if d.get("final_advice"):
            render.dimension_bars(None, final_advice=d.get("final_advice"))
```

**关键点**：
- 新格式检测条件：`d.get("factors")` 是 list 且非空 → 走 `factor_cards()`
- 旧格式降级：保留原 DataFrame 逻辑，但排除 `"factors"` 键（防止新格式混入旧渲染）
- `potential_flag` 和 `cross_validation_note` 仅在新格式路径展示（旧数据无此字段）

### 2.5 2_评分报告.py — 文案更新

| 行 | 当前 | 改为 |
|----|------|------|
| 1 | `"""评分报告：ScoreAgent 五维评分（A/B/C 分级 + 风险清单，自然语言分段展示）` | `"""评分报告：ScoreAgent 六因子透明评分（A/B/C 分级 + 因子卡 + 风险清单）` |
| 5 | `详情分区卡片化（五维/K202/派发期/三维/操作建议/风险），原始 JSON 永久折叠在最底部。` | `详情分区卡片化（六因子/K202/派发期/三维/操作建议/风险），原始 JSON 永久折叠在最底部。` |
| 23 | `caption="ScoreAgent 五维评分（A/B/C 分级 + 风险清单）；表格选行后详情即时切换，零网络请求。"` | `caption="ScoreAgent 六因子透明评分（A/B/C 分级 + 因子卡 + 交叉验证）；表格选行后详情即时切换，零网络请求。"` |
| 55 | `# 批次2：详情分区 Tab 化（默认停在「五维分项评分」；` | `# 详情分区 Tab 化（默认停在「六因子评分」；` |
| 58 | `# 五维分项评分（结构为 {维度: {score, verdict/advice}} 的字段才进表；` | `# 六因子评分（v4.0 新格式走 factor_cards；旧格式降级 DataFrame；` |
| 102 | `_sections = [("五维分项评分", _tab_dims)]` | `_sections = [("六因子评分", _tab_dims)]` |

### 2.6 1_每日候选池.py — _TRACE_MODULE 标签（可选）

`_TRACE_MODULE` 中 `"score": "五维评分"` → `"六因子评分"`（line 43）。纯标签，不影响功能。

---

## 三、规则

1. **纯展示层**：`factor_cards()` 只做字段映射与 HTML 渲染，不产生任何研判内容，不做任何计算（分值条宽度 = score/10 是纯展示换算，不是评分计算）。
2. **新旧兼容**：`_tab_dims()` 必须同时支持新格式（`factors` 列表）和旧格式（维度名字典）。旧评分数据在 DB 中仍存在，打开旧记录不能报错。
3. **不动 dimension_bars**：`dimension_bars()` 函数保持不动，候选池/建仓/持仓/复盘页面仍用它渲染 DiscoverDimension。
4. **HTML 转义**：factor_name 和 reason 文本必须经过 `_esc()` 转义（LLM 输出可能含 `<>&`）。
5. **信号色板**：看多=红(var(--up))、中性=灰(var(--text-dim))、看空=绿(var(--down))，对齐 A 股涨红跌绿惯例。
6. **潜力标识展示**：`potential_flag=True` 时在因子卡网格上方显示琥珀色横幅（代码层已推导 flag 值，此处纯展示）。
7. **不引入新依赖**：纯 Streamlit + HTML/CSS，不引入新第三方库。

---

## 四、约束

1. **改前备份**：`render.py` → `.bak.batchB`，`2_评分报告.py` → `.bak.batchB`。
2. **不改变 API 接口**：前端只消费后端已有 `/api/scores` 返回的 `detail` 字段，不新增/修改 API。
3. **不改变 DB 结构**：纯前端改动，不碰 `stock_score` 表。
4. **不改变后端逻辑**：不碰 Agent / graph / repo / services。
5. **不改其他页面**：1/3/4/6 页面的 `dimension_bars` 调用不动（它们用 DiscoverDimension，不是 ScoreFactor）。
6. **全量 pytest 零回归**：本批次是纯前端改动，后端测试不受影响，但仍需跑一遍确认 593 passed。

---

## 五、实现参考

### 5.1 factor_cards() 在 render.py 中的位置

```
line 953: _advice_card() 结束
line 954: ↓ 紧接其后插入 factor_cards() 及相关常量
```

### 5.2 CSS 在 _GLOBAL_THEME_CSS 中的位置

```
line 369: .dim-advice { ... }  ← 维度归因条 CSS 结束
line 370: ↓ 紧接其后追加因子卡 CSS
```

### 5.3 _tab_dims() 替换边界

从 `def _tab_dims():` 到 `render.dimension_bars(None, final_advice=d.get("final_advice"))` 整段替换（line 57-73）。

### 5.4 旧格式降级的关键区别

旧格式 `detail` 结构：
```json
{"基本面": {"score": 75, "verdict": "支持", "advice": "..."},
 "技术趋势": {"score": 60, "verdict": "中性", "advice": "..."},
 ...,
 "final_advice": "..."}
```

新格式 `detail` 结构：
```json
{"factors": [{"factor": "动量", "score": 7, "reason": "...", "signal": "看多"}, ...],
 "potential_flag": false,
 "cross_validation_note": "...",
 "final_advice": "..."}
```

检测逻辑：`isinstance(d.get("factors"), list) and d.get("factors")` → 新格式；否则 → 旧格式降级。

---

## 六、执行顺序

1. 备份 `render.py` 和 `2_评分报告.py` 为 `.bak.batchB`
2. `render.py`：追加因子卡 CSS（在 `.dim-advice` 之后）
3. `render.py`：新增 `factor_cards()` 函数 + 常量（在 `_advice_card` 之后）
4. `render.py`：`_TRACE_MODULE_LABEL` 中 `"score": "五维评分"` → `"六因子评分"`
5. `2_评分报告.py`：替换 `_tab_dims()` 函数
6. `2_评分报告.py`：更新 docstring/caption/comment/tab 标签（6 处文案）
7. `1_每日候选池.py`：`_TRACE_MODULE` 中 `"score": "五维评分"` → `"六因子评分"`（可选）
8. 全量 pytest 确认零回归

---

## 七、验证清单

- [ ] `render.py` 新增 `factor_cards()` 函数，接收 `factors/potential_flag/cross_validation_note/final_advice` 四个参数
- [ ] CSS 类名：`.factor-grid` / `.factor-card` / `.factor-head` / `.factor-name` / `.factor-score` / `.factor-bar` / `.factor-bar-fill` / `.factor-signal` / `.factor-reason` / `.potential-banner` / `.cross-validation-card` 全部定义
- [ ] 信号色板：看多=红(bull)、中性=灰(neutral)、看空=绿(bear)
- [ ] `_tab_dims()` 新格式检测：`isinstance(d.get("factors"), list) and d.get("factors")` → 走 `factor_cards()`
- [ ] `_tab_dims()` 旧格式降级：保留 DataFrame 渲染，排除 `"factors"` 键
- [ ] `potential_flag=True` 时显示琥珀色横幅
- [ ] `cross_validation_note` 非空时显示蓝色交叉验证卡
- [ ] `final_advice` 非空时显示综合评估卡（复用 `_advice_card`）
- [ ] 文案更新：docstring/caption/comment/tab 标签 "五维" → "六因子"（6 处）
- [ ] `_TRACE_MODULE_LABEL` / `_TRACE_MODULE` 中 `"score"` 标签更新
- [ ] `dimension_bars()` 函数未被修改
- [ ] 其他页面（1/3/4/6）未被修改
- [ ] 全量 pytest 593 passed 0 failed
- [ ] 备份 `.bak.batchB` 存在

---

## 八、运行时验证（手动，部署后执行）

1. 启动后端 + Streamlit，打开「评分报告」页面
2. 触发一次新评分（手动打分），确认：
   - Tab 标签显示「六因子评分」
   - 6 张因子卡 3×2 网格排列，每卡显示因子名/分值/评分条/信号/依据
   - 信号色板正确：看多红/中性灰/看空绿
   - potential_flag=true 时琥珀横幅显示
   - cross_validation_note 蓝色卡显示
   - final_advice 综合评估卡显示
3. 打开一条旧评分记录（评级重做-A 之前的），确认：
   - Tab 标签仍显示「六因子评分」（统一标签）
   - 旧数据走 DataFrame 降级渲染，不报错
   - 无 potential_flag/cross_validation_note 显示（旧数据无此字段）
4. 打开「每日候选池」页面，确认 dimension_bars 仍正常渲染（不受影响）
