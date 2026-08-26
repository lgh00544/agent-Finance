# 预测性选股重构 · 5 批次 Claude Code 执行指令（合一份单文件）

> **作者**：Lark
> **日期**：2026-08-21
> **依据**：`D:\self\经验沉淀与预测性选股_方案.md` §三 段 2（5 批次重构）
> **关联**：与段 1 急救（`经验沉淀急救_Claude执行指令.md`）可并行执行，互不依赖

---

## 〇 5 批次总览

### 〇.1 批次依赖图

```
┌──────────────────────────────────────────────────────────────────┐
│ 批次 2.1  前瞻子 Agent 注入（discover_prompt 5 子 Agent）  [1.5d] │
│   ↓                                                              │
│ 批次 2.2  历史胜率维度注入（ScoreAgent collect 段 7 维）    [1d]  │
│   ↓                                                              │
│ 批次 2.3  K 红线代码化（red_line_check.py 6 事实字段）     [1.5d] │
│   ↓                                                              │
│ 批次 2.4  游资数据真接入（K189 7+2 骗局代码化）           [2d]   │
│   ↓                                                              │
│ 批次 2.5  前瞻回填闭环（forward_view_history + cron）      [1.5d] │
└──────────────────────────────────────────────────────────────────┘
```

### 〇.2 工时预估表

| 批次 | 名称 | 依赖 | 工时 | 关键文件 |
|---|---|---|---|---|
| 2.1 | 前瞻子 Agent 注入 | 无 | 1.5d | `agent_prompts/discover_prompt.py` |
| 2.2 | 历史胜率维度注入 | 无（可与 2.1 并行） | 1d | `backend/app/agents/score.py` |
| 2.3 | K 红线代码化 | 无 | 1.5d | `backend/app/services/red_line_check.py`（新）+ 3 prompt |
| 2.4 | 游资数据真接入 | 2.3 | 2d | `backend/app/services/wash_trade_check.py`（新）+ 2 prompt |
| 2.5 | 前瞻回填闭环 | 2.1 | 1.5d | `backend/app/services/forward_view_history.py`（新）+ cron |

**总计**：~7.5 天（5 批次可流水线：2.1 + 2.2 + 2.3 并行，2.4 依赖 2.3，2.5 依赖 2.1）

### 〇.3 核心铁律

- **前瞻分析是 Discover 子 Agent，不另起 forward_view 服务**（sir 8/21 拍板）
- **不修改 6 因子权重**（动量 20% / 催化 20% / 估值 15% / 主线 15% / 资金 15% / 基本面 15%）
- **不修改交易规则 / 研判标准**（auto-merge 永远不动）
- **缺失数据兜底**：每个 service 返回带 `missing_data` 字段，绝不编造
- **前端默认改 React 新版**（8/20 铁律）；Streamlit 仅在阻塞时动

---

## 一、目标

让选股从「基于当日截面数据的诊断」升级为「**未来 1-2 周视角** + 当日截面」双重判断。**不**：

- 不改 6 因子权重
- 不改交易规则 / 研判标准 / ScoreAgent 节点流程
- 不新建独立 forward_view 服务（**sir 拍板**）
- 不覆盖 K 红线研判
- 不调 LLM 预测具体涨跌数字

**只做**：让"前瞻"从 LLM 艺术判断升级为 prompt 内的明确子 Agent + 历史先验 + 缺失数据兜底。

---

## 二、架构约束（5 铁律）

1. **Agent 解耦**：5 子 Agent 全部在 Discover prompt 内，**不新建** DiscoverAgent v2
2. **不超载既有 Agent**：collect 段追加字段，不重写节点流程
3. **缺失数据兜底**：每个新 service 返回 `{"data": {...}, "missing_data": bool, "reason": str}`，绝不编造
4. **auto-merge 永不碰**：0.85 阈值、影响因子阈值、tradeable 判定函数零改动
5. **前端归属**：本批次前端改动在 `web/src/`，不在 `streamlit/pages/`

---

## 三、规则（5 批次分段）

### 3.1 批次 2.1 —— 前瞻子 Agent 注入

**改 1 个文件**：`agent_prompts/discover_prompt.py`（在 line 89 主 Agent 收口段之前插入）

**新增 prompt 段**：
```
5. 前瞻子 Agent（横向校验，跨子 Agent 输出，输出三态）：
   收集上述 4 子 Agent 输出后，独立从"未来 1-2 周视角"做 3 件事：
   ① 趋势延续性：当前动量/资金/催化信号在未来 5-10 个交易日内是否大概率延续？
      弱信号（仅 1 个子 Agent 强）→ 谨慎；强信号（3+ 子 Agent 一致）→ 确认
   ② 均值回归风险：股价已处 20 日新高/60 日高位时，回归回调概率显著上升，
      需对照 K138 5 维超买/4 维超卖
   ③ 催化兑现概率：公告/政策/主力动作等催化是"未兑现"还是"已兑现"？
      未兑现催化强度 > 已兑现（兑现后利好出尽概率上升）
   输出三态：前瞻强（>=2 项强信号）/ 前瞻中性 / 前瞻弱（>=2 项弱信号）
   前瞻弱 + 评级 A/B → 强制降级为观察 C（不破红线）

   【硬约束】
   - 不预测具体涨跌数字（5%/10% 等），只输出三态
   - 不引用本段未列出的信号（K 红线外的"我感觉"不构成依据）
   - 前瞻弱不破红线：6 维硬检查 / K1-K227 仍按原优先级
```

**关键设计**：
- 这是 prompt 注入，**不改** `backend/app/agents/discover.py` 节点代码
- 前瞻子 Agent 输出进 `state["candidates"][i]["forward_view"]` 字段（前端展示）
- collect 段**不动**，仅 LLM 输出时新增一个 key

**红线**：
- 6 因子权重不动
- 4 现有子 Agent 描述不动
- 不引用 K 红线外的"我感觉"

### 3.2 批次 2.2 —— 历史胜率维度注入

**改 1 个后端文件**：`backend/app/agents/score.py:96-200`（collect_data 段追加）

**追加 1 维度**：
```python
# 历史胜率维度（仅在候选数 >= 5 时启用）
_historical_data = repo.get_similar_track_verify_stats(
    confidence_tier=state.get("confidence_tier", "B"),
    lookback_days=60,
    min_sample=5,
)
if _hist_data.get("missing_data"):
    state["historical_win_rate_dim"] = {
        "score": None, "missing_data": True, "reason": _hist_data["reason"]
    }
else:
    avg_t5 = _hist_data.get("avg_t5_pct", 0)
    if avg_t5 > 3: score = 9
    elif avg_t5 > 0: score = 7
    elif avg_t5 > -3: score = 4
    else: score = 2
    state["historical_win_rate_dim"] = {
        "score": score, "missing_data": False,
        "avg_t5_pct": avg_t5, "sample_size": _hist_data.get("n", 0)
    }
```

**应用层**（不改 6 因子权重）：
- `historical_win_rate_dim` 进 `output.factors` 列表作为第 7 维度（**总分占比保持 100%**，原 6 因子各缩 1/7）
- 或改为**综合分乘数项**（0.95-1.05 微调）——具体取哪个由 §三 决策点 2 决定

**新增 repo 函数**：`backend/app/db/repo.py::get_similar_track_verify_stats`
```python
def get_similar_track_verify_stats(confidence_tier: str, lookback_days: int = 60,
                                    min_sample: int = 5) -> dict:
    """查近 N 日同档位（A/B/C）候选的 T+5 表现统计
    返回: {"missing_data": bool, "reason": str, "n": int, "avg_t5_pct": float, "win_rate": float}"""
    with SessionLocal() as db:
        cutoff = (date.today() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        rows = db.execute(
            select(CandidateTrackVerify)
            .where(CandidateTrackVerify.select_date >= cutoff)
            .where(CandidateTrackVerify.t5_pct.isnot(None))
        ).scalars().all()
        # 注意：CandidateTrackVerify 表没有 confidence_tier 字段，需 join stock_score
        # 简化：先按 t5_pct 总体分布查，confidence_tier 维度 1 周后补
        if len(rows) < min_sample:
            return {"missing_data": True, "reason": f"样本不足 {len(rows)} < {min_sample}",
                    "n": len(rows)}
        t5_list = [r.t5_pct for r in rows]
        wins = [t for t in t5_list if t > 0]
        return {
            "missing_data": False,
            "n": len(t5_list),
            "avg_t5_pct": round(sum(t5_list) / len(t5_list), 2),
            "win_rate": round(len(wins) / len(t5_list), 4),
        }
```

**红线**：
- 6 因子权重不改（仅追加 1 维度）
- 缺失数据不编造
- 不写"用历史胜率预测未来"（避免循环论证）

### 3.3 批次 2.3 —— K 红线代码化

**改 2 个文件**：
- 新增 `backend/app/services/red_line_check.py`：算 C1/C2/C3/K139 SOP/K226 9 主体 事实
- 3 个 prompt 收集段追加（`score_prompt.py` / `monitor_prompt.py` / `sell_prompt.py`）

**核心事实字段**：
```python
# red_line_check.py 核心接口
def compute_red_line_facts(stock_code: str, holding_id: int = None) -> dict:
    """计算该股的所有可注入红线事实
    返回: {
        "missing_data": bool,
        "facts": {
            "cost_3pct_below": float,     # C1 止损线（成本 -3%）
            "cost_8pct_below": float,     # C2 止损线（成本 -8%）
            "cost_92pct": float,           # C3 关键位（成本 × 0.92）
            "sop_breach": bool,            # 是否触发 K139 SOP 减仓
            "concentration_count": int,    # 9 主体同类持仓数
            "near_52w_high_pct": float,    # 距 52 周新高百分比
        }
    }"""
```

**注入示例**（`score_prompt.py::build_user_prompt`）：
```python
red_line_facts = red_line_check.compute_red_line_facts(code)
if not red_line_facts.get("missing_data"):
    prompt += f"\n【红线事实（代码层）】\n{json.dumps(red_line_facts['facts'], ensure_ascii=False)}\n"
else:
    prompt += "\n【红线事实】缺失数据，本维度不构成评级依据\n"
```

**红线**：
- 仅"算事实"，不"判定红线触发"——是否触发由 LLM 解读
- 9 主体分类表（main_subject_9）若未在代码中实现，需在本次一并定义（不复用 prompt 概念）
- 缺失数据填 `missing_data=True`，LLM 收到时跳过该维度

### 3.4 批次 2.4 —— 游资数据真接入

**改 2-3 个文件**：
- 复核 `backend/app/services/dragon_tiger_source.py`（已实现 vs 需补）
- 新增 `backend/app/services/wash_trade_check.py`（K189 7+2 骗局代码化）
- 2 个 prompt 收集段追加（`discover_prompt.py` / `score_prompt.py`）

**K189 7+2 骗局识别逻辑**（代码层）：
```python
def check_wash_trade_suspicion(stock_code: str, lookback_days: int = 30) -> dict:
    """K189 7+2 骗局：7 个买方席位 + 2 个对倒席位"""
    seats = repo.get_dragon_tiger_seats(stock_code, lookback_days)
    if len(seats) < 7:
        return {"suspicion": False, "missing_data": True, "reason": "席位数据不足"}
    buy_seats = [s for s in seats if s["side"] == "buy"][:7]
    sell_seats = [s for s in seats if s["side"] == "sell"][:2]
    buy_amount = sum(s["amount"] for s in buy_seats)
    float_mv = repo.get_float_market_value(stock_code)
    if not float_mv:
        return {"suspicion": False, "missing_data": True, "reason": "流通市值缺失"}
    buy_ratio = buy_amount / float_mv
    sell_amount = sum(s["amount"] for s in sell_seats)
    sell_to_buy = sell_amount / buy_amount if buy_amount else 0
    suspicion = (buy_ratio > 0.02 and sell_to_buy > 0.8 and len(buy_seats) >= 5)
    return {
        "suspicion": suspicion,
        "missing_data": False,
        "buy_ratio": round(buy_ratio, 4),
        "sell_to_buy": round(sell_to_buy, 4),
        "buy_seats_count": len(buy_seats),
    }
```

**注入示例**（`discover_prompt.py` collect 段）：
```python
wash = wash_trade_check.check_wash_trade_suspicion(code)
if not wash.get("missing_data") and wash.get("suspicion"):
    state["candidates"][i]["wash_trade_warning"] = "K189 7+2 骗局嫌疑"
```

**红线**：
- 仅"算嫌疑度"，不"判定骗局"——是否真实骗局由 LLM 解读
- 缺失数据填 `missing_data=True`
- dragon_tiger_source 已实现则复用，不重复造轮子

### 3.5 批次 2.5 —— 前瞻回填闭环

**改 4 个文件 + 1 个 cron**：
- 新增 `backend/app/services/forward_view_history.py`：落库前瞻判断快照
- 新增表 `forward_view_history`（按 trade_date+stock_code 索引）
- `backend/app/scheduler/jobs.py` 加 1 个 cron：每日 16:00 回填 T+5 实际涨跌
- `agent_prompts/score_prompt.py` collect 段：注入回填先验（历史前瞻准确率）
- 每周日 04:00 跑 backtest 校准先验

**表结构**：
```python
class ForwardViewHistory(Base):
    __tablename__ = "forward_view_history"
    __table_args__ = (
        UniqueConstraint("trade_date", "stock_code", name="uq_fwd_date_code"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(10), index=True)
    stock_code: Mapped[str] = mapped_column(String(16), index=True)
    forward_view: Mapped[str] = mapped_column(String(16))  # 强/中性/弱
    forward_signals: Mapped[dict] = mapped_column(SafeJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    # 回填字段
    t5_pct_actual: Mapped[float | None] = mapped_column(Float, nullable=True)
    t5_filled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 校准字段
    accuracy_bucket: Mapped[str | None] = mapped_column(String(16), nullable=True)  # correct/wrong/neutral
```

**回填 cron**：
```python
@scheduler.scheduled_job("cron", hour=16, minute=0)
def fill_forward_view_actual():
    """每日 16:00 回填 forward_view_history 的 t5_pct_actual 字段
    范围：选入日 <= today - 5 且 t5_pct_actual IS NULL"""
    today = date.today()
    cutoff = (today - timedelta(days=5)).strftime("%Y-%m-%d")
    pending = repo.list_unfilled_forward_view(cutoff_date=cutoff)
    for row in pending:
        actual = repo.get_track_verify_t5_pct(row.stock_code, row.trade_date)
        if actual is not None:
            bucket = "correct" if (
                (row.forward_view == "强" and actual > 0) or
                (row.forward_view == "弱" and actual < 0)
            ) else "wrong" if (
                (row.forward_view == "强" and actual < -3) or
                (row.forward_view == "弱" and actual > 3)
            ) else "neutral"
            repo.update_forward_view_actual(row.id, actual, bucket)
```

**校准 cron**（每周日 04:00）：
```python
@scheduler.scheduled_job("cron", day_of_week="sun", hour=4)
def calibrate_forward_view_prior():
    """回算近 30 日前瞻准确率，输出 calibration_log"""
    stats = repo.compute_forward_view_accuracy(lookback_days=30)
    logger.info("前瞻先验校准: %s", stats)
    # 写入 experience_config 的 forward_view_calibration 字段（不入库，仅日志）
```

**注入 score_prompt**：
```python
calibration = compute_recent_forward_view_accuracy(lookback_days=30)
prompt += f"\n【前瞻先验校准（近 30 日）】\n前瞻强 准确率 {calibration['strong']:.0%}（{calibration['strong_n']} 样本）\n前瞻弱 准确率 {calibration['weak']:.0%}（{calibration['weak_n']} 样本）\n"
```

**红线**：
- 不调 LLM 预测数字（纯统计）
- 不改 6 因子权重
- 不覆盖 K 红线研判
- horizon_clarity < 0.3 → 标 `missing_data=True` 跳过校准

---

## 四、实现参考（必读文件）

| 文件 | 必读理由 |
|---|---|
| `agent_prompts/discover_prompt.py:79-89` | 4 子 Agent 真实结构（批次 2.1 插入点） |
| `backend/app/agents/score.py:96-200` | collect_data 段（批次 2.2 追加点） |
| `backend/app/agents/score.py:245-266` | 6 因子 transparent score 写库点（批次 2.2 兼容性） |
| `backend/app/db/repo.py::CandidateTrackVerify` | 历史胜率查询表（批次 2.2 数据源） |
| `agent_prompts/score_prompt.py::build_user_prompt` | K 红线注入点（批次 2.3） |
| `agent_prompts/monitor_prompt.py / sell_prompt.py` | K 红线注入点（批次 2.3） |
| `backend/app/services/dragon_tiger_source.py` | 游资数据源复核（批次 2.4） |
| `backend/app/scheduler/jobs.py` | cron 注册（批次 2.5） |
| `backend/app/db/models.py:573-588` | PendingExperience 表（参考新表写法） |
| `backend/app/services/experience_worker.py` | 不动；仅参考 3.3 fallback 模式 |

**风格统一**：
- 中文 JSDoc 注释
- 中文日志 `logger.warning(...)`
- 错误信息保留 `exc_info=True` 风格
- 缺失数据返回 `{"missing_data": True, "reason": "..."}` 格式
- 每个 service 必须有 `compute_*` 命名空间

---

## 五、执行顺序

### 5.1 批次 2.1 + 2.2 + 2.3 并行启动（无依赖）

```bash
# 备份所有待改文件
cp agent_prompts/discover_prompt.py agent_prompts/discover_prompt.py.bak.fwd_v2
cp backend/app/agents/score.py backend/app/agents/score.py.bak.fwd_v2
cp backend/app/services/red_line_check.py backend/app/services/red_line_check.py.bak.fwd_v2 2>/dev/null
cp agent_prompts/score_prompt.py agent_prompts/score_prompt.py.bak.fwd_v2
cp agent_prompts/monitor_prompt.py agent_prompts/monitor_prompt.py.bak.fwd_v2
cp agent_prompts/sell_prompt.py agent_prompts/sell_prompt.py.bak.fwd_v2
cp backend/app/db/repo.py backend/app/db/repo.py.bak.fwd_v2
cp backend/app/scheduler/jobs.py backend/app/scheduler/jobs.py.bak.fwd_v2
```

**2.1 第 1 步**：在 `discover_prompt.py:88` 后插入 5 子 Agent 段
**2.1 第 2 步**：单测 `backend/tests/test_forward_view_prompt.py`，断言 prompt 包含"前瞻子 Agent" + 3 件事 + 三态
**2.1 第 3 步**：`pytest backend/tests/test_forward_view_prompt.py -v` 全部通过

**2.2 第 1 步**：在 `score.py:collect_data` 末尾追加 historical_win_rate_dim
**2.2 第 2 步**：在 `repo.py` 新增 `get_similar_track_verify_stats` 函数
**2.2 第 3 步**：单测 `backend/tests/test_historical_win_rate.py`，覆盖：样本不足 / 样本充足 / 缺失数据 三场景
**2.2 第 4 步**：`pytest backend/tests/test_historical_win_rate.py -v` 全部通过

**2.3 第 1 步**：新增 `backend/app/services/red_line_check.py`
**2.3 第 2 步**：在 3 个 prompt 收集段注入红线事实
**2.3 第 3 步**：单测 `backend/tests/test_red_line_check.py`，覆盖：持仓数据存在 / 缺失 / 9 主体计算
**2.3 第 4 步**：`pytest backend/tests/test_red_line_check.py -v` 全部通过

### 5.2 批次 2.4（依赖 2.3 的 red_line_check）

**2.4 第 1 步**：新增 `backend/app/services/wash_trade_check.py`
**2.4 第 2 步**：在 2 个 prompt 收集段注入 wash_trade_warning
**2.4 第 3 步**：单测 `backend/tests/test_wash_trade_check.py`，覆盖：席位不足 / 流通市值缺失 / 嫌疑度高
**2.4 第 4 步**：`pytest backend/tests/test_wash_trade_check.py -v` 全部通过

### 5.3 批次 2.5（依赖 2.1）

**2.5 第 1 步**：在 `models.py` 新增 `ForwardViewHistory` 表
**2.5 第 2 步**：新增 `backend/app/services/forward_view_history.py`
**2.5 第 3 步**：在 `jobs.py` 加 2 个 cron（每日 16:00 + 每周日 04:00）
**2.5 第 4 步**：在 `score_prompt.py` 注入回填先验
**2.5 第 5 步**：单测 `backend/tests/test_forward_view_history.py`，覆盖：回填 / 校准 / 缺失数据
**2.5 第 6 步**：`pytest backend/tests/test_forward_view_history.py -v` 全部通过

### 5.4 总体收尾

```bash
# 5 个批次全跑完后：全量回归
D:\self\.venv\Scripts\python.exe -m pytest backend/tests --ignore=backend/tests/test_streamlit_pages_smoke.py --ignore=backend/tests/test_system_status.py -q
```

预期：≥ 599 passed + 5 批次新增测试全部通过

---

## 六、验证清单（sir 独立验收用）

### 6.1 静态验收（每批次）
- [ ] `python -m py_compile <本批次所有改动文件>` 0 error
- [ ] `grep -nE "前瞻子 Agent|historical_win_rate_dim|red_line_facts|wash_trade_warning|forward_view_history" <本批次文件>` 命中数 ≥ 批次定义的 grep 数
- [ ] `git diff --stat` 只出现本批次约定文件

### 6.2 运行时验收（每批次）
- [ ] `pytest backend/tests/test_<本批次>.py -v` 全部通过
- [ ] 全量回归 ≥ 599 passed + 新增测试通过
- [ ] 手动跑 1 次对应主流程：
  - 2.1 跑 `run_discover()` → 候选 detail 含 `forward_view` 字段
  - 2.2 跑 `run_score("600547")` → 评分 detail 含 `historical_win_rate_dim`
  - 2.3 跑 `compute_red_line_facts("600547")` → 返回 6 事实
  - 2.4 跑 `check_wash_trade_suspicion("600547")` → 返回嫌疑度
  - 2.5 跑 `fill_forward_view_actual()` → DB 有回填记录

### 6.3 红线验收（每批次）
- [ ] `git diff --stat` 5 批次合并后不出现：
  - `agent_prompts/*_prompt.py` 阈值字段
  - `backend/app/agents/score.py` 6 因子权重
  - `backend/app/services/candidate_tradeable.py` 判定函数
  - `backend/app/services/experience_worker.py`（段 1 单独改，本批次不动）
  - `streamlit/pages/` 任何文件
- [ ] auto-merge 阈值 0.85 未变
- [ ] 交易规则 / 研判标准表零改动

### 6.4 业务验收（1 周后看）
- [ ] `experience` 表周增量 ≥ 30 行（段 1 急救生效）
- [ ] 候选池标的 detail 含 `forward_view` 字段（2.1 生效）
- [ ] 评分 detail 含 `historical_win_rate_dim`（2.2 生效）
- [ ] 评分 / 监控 / 卖出 prompt 输出含"红线事实"段落（2.3 生效）
- [ ] 候选池标的 detail 含 `wash_trade_warning` 字段（2.4 生效）
- [ ] `forward_view_history` 表周增量 ≥ 100 行（2.5 回填生效）
- [ ] **核心指标**：sir 复盘页能看到「前瞻子 Agent 强/中/弱」分布 + 历史回填命中率

---

## 七、红线（5 条必守）

1. **不改 6 因子权重**（动量 20% / 催化 20% / 估值 15% / 主线 15% / 资金 15% / 基本面 15%）
2. **不新建独立 forward_view 服务**（sir 8/21 拍板）——前瞻分析是 Discover 的子 Agent
3. **不修改交易规则 / 研判标准**（auto-merge 永远不动）
4. **不调 LLM 预测具体涨跌数字**（仅输出三态 + 校准先验）
5. **前端默认改 React 新版**（8/20 铁律）；本批次前端改动在 `web/src/`，不在 `streamlit/pages/`

---

## 八、Claude Code 执行前必读清单

1. **从 §5.1 批次 2.1 第 1 步开始**
2. 先备份所有文件（§5.1 顶部 cp 命令）
3. **每个批次完成后停下来报告 sir**，等验收再进下一批次
4. 遇方案决策点 → 先停下问 sir，不自行决定
5. 遇红线触碰（必须改 6 因子权重 / 必须改交易规则表）→ 立即停下报告
6. 5 批次全部完成后跑全量回归（§5.4）
