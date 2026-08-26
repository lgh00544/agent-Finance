# 评级重做-C：因子回测校准闭环

> **目标**：让系统根据 T+N 实际表现自动计算"因子分高→胜率"相关性，生成权重校准建议（人工审核后生效），并将相关性事实注入 ScoreAgent prompt 作为参考——真正"提高准确率"的闭环。
>
> **前置条件**：评级重做-A（六因子评分体系）已执行完成，`stock_score.detail` 已存储 `factors: [{factor, score, reason, signal}]` 格式。

---

## 一、要什么

### 1.1 核心能力

| # | 能力 | 说明 |
|---|------|------|
| 1 | **因子分记录** | 候选追踪行创建时，自动从 `stock_score.detail.factors` 提取六因子分值存入 `candidate_track_verify.factor_scores` |
| 2 | **因子相关性计算** | 纯函数：对每个因子，将候选分为"高分(≥7)"和"低分(≤3)"两组，计算各组 T+N 胜率/平均涨幅，输出相关性事实 |
| 3 | **校准建议生成** | 因子高分组表现显著差于低分组时，生成"建议降低该因子权重"的 agent_suggestion（status=pending，人工审核后生效） |
| 4 | **相关性注入 ScoreAgent** | ScoreAgent 评分时注入最新因子相关性事实文本（类似 selection_performance_summary 模式），让 LLM 参考历史表现微调权重 |

### 1.2 因子相关性计算口径

```
对每个因子 F（动量/催化/估值/主线契合/资金面/基本面质量）：
  - 高分组：F 分值 ≥ 7 的候选
  - 低分组：F 分值 ≤ 3 的候选
  - 各组要求样本 ≥ 3（沿用 _MIN_SAMPLE），否则该因子不参与相关性计算
  - 指标：win_rate（胜率%）、avg_pct（平均涨幅%）、n（样本数）
  - 判定：
    - 高分组 win_rate > 低分组 win_rate + 10pp → "因子有效"（正向预测力）
    - 高分组 win_rate < 低分组 win_rate - 10pp → "因子失效"（反向预测，需校准）
    - 差值在 ±10pp 内 → "无显著差异"
```

### 1.3 校准建议触发条件

| 条件 | 建议类型 | 优先级 |
|------|----------|--------|
| 因子高分组的 avg_pct 显著低于低分组（差值 > 5pp） | 建议降低该因子权重 | high |
| 因子高分组的 avg_pct 显著高于低分组（差值 > 5pp） | 建议保持/提升该因子权重 | low（ informational） |
| 多个因子同时失效 | 建议人工复核整体评分体系 | high |

---

## 二、谁做

Claude Code 按本指令执行实现。

---

## 三、规则

1. **因子分仅从 stock_score 提取**：不从候选 detail 推测，不编造。旧格式（无 factors 列表）的评分记录无法提取因子分，对应追踪行 `factor_scores` 为空——诚实留空，不造假。
2. **相关性计算是纯函数**：`compute_factor_correlation(rows, period)` 接收行列表和周期参数，返回纯数据结构，无副作用，可单测。
3. **校准建议走人工审核闭环**：全部落 `agent_suggestion`（status=pending），任何权重调整必须经人工确认后才生效（与批次 1-5 保持一致）。
4. **相关性注入是只读的**：`get_factor_calibration()` 只读取统计数据生成文本，不修改 prompt 文件、不修改权重、不阻塞评分流程。
5. **最小样本门槛**：因子相关性计算要求每个因子的高分组和低分组各 ≥ 3 个样本；不足时该因子输出 `{status: "insufficient_sample"}`，不生成建议。
6. **不新增 LLM 调用**：因子相关性计算和校准建议模板生成都是确定性代码，不调用 LLM（与 `_template_suggestions` 模式一致）。后续如需 LLM 解读相关性，可扩展但不在本批次。
7. **幂等**：因子分提取在 `_init_candidates()` 中完成（创建追踪行时一次性写入）；相关性计算在 `run_verify_chain()` 中每次重算（纯函数无副作用）；建议生成走 `has_pending_suggestion` 去重。

---

## 四、约束

1. **不改 ScoreAgent 的 prompt 权重**：prompt 中"约 20%/15%"的参考权重不变；相关性事实作为**参考信息**注入 user_prompt，LLM 可自行参考但不强制改变权重（人工审核的校准建议才是权重变更的唯一路径）。
2. **不改 StockScore 表结构**：因子分从 `stock_score.detail.factors` 读取（评级重做-A 已落地），不需要改 stock_score 表。
3. **不改前端**：本批次纯后端数据层+逻辑层改动；因子相关性的前端展示不在本批次范围（如需要可后续追加）。
4. **不改 graph 结构**：score 图节点与流转不变；相关性注入通过 `build_user_prompt` 参数传递，与 discover_context/market_intel_summary 模式一致。
5. **不新增 Agent**：不新建 Agent，不引入新 LLM 调用，不新建 graph 节点。
6. **旧数据兼容**：`factor_scores` 列新增后，旧行默认 null；相关性计算只使用有 factor_scores 的行，自动跳过无因子分的旧行。
7. **不破坏既有测试**：全量 pytest 593 passed 零回归（评级重做-B 的 577 non-AppTest + AppTest 环境性 flaky 不计）。

---

## 五、实现参考

### 5.1 models.py — CandidateTrackVerify 加列

```python
# 在 CandidateTrackVerify 类中，verify_result 之后新增：
factor_scores: Mapped[dict | None] = mapped_column(SafeJSON, nullable=True, default=None)
# 存储格式：[{"factor": "动量", "score": 7}, {"factor": "催化", "score": 8}, ...]
# null = 未提取（旧数据或无评分记录）；空列表 [] = 有评分记录但无 factors（旧格式评分）
```

### 5.2 session.py — 幂等加列

```python
def _ensure_track_verify_factor_scores(eng=None) -> None:
    """幂等补齐 candidate_track_verify.factor_scores 列（因子回测校准闭环；
    仅增量加列，不重建表不丢数据；旧数据为 NULL=未提取）"""
    eng = eng or engine
    with eng.begin() as conn:
        if eng.dialect.name == "sqlite":
            existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(candidate_track_verify)")}
            if "factor_scores" not in existing:
                conn.exec_driver_sql("ALTER TABLE candidate_track_verify ADD COLUMN factor_scores JSON")
        else:
            try:
                conn.exec_driver_sql("ALTER TABLE candidate_track_verify ADD COLUMN factor_scores JSON")
            except Exception:
                pass
```

在 `init_db()` 中 `_ensure_market_condition_next_day()` 之后调用 `_ensure_track_verify_factor_scores()`。

### 5.3 repo.py — 扩展 upsert_track_verify + 新增 get_score_factors

```python
def upsert_track_verify(stock_code, stock_name, select_date,
                        select_rating, base_close_price,
                        factor_scores=None) -> int:
    """初始化追踪行（幂等）。factor_scores 为 [{factor, score}] 列表或 None。
    已存在行不覆盖 factor_scores（防覆盖已提取的数据）。"""
    # ... 既有逻辑 ...
    if row is None:
        row = CandidateTrackVerify(..., factor_scores=factor_scores)
    # 已存在行不更新 factor_scores（幂等）
```

```python
def get_score_factors(stock_code: str, trade_date: str) -> list[dict] | None:
    """从 stock_score.detail 提取六因子分值（只读，幂等）。
    返回 [{"factor": "动量", "score": 7}, ...] 或 None（无评分/旧格式无 factors）。
    当日评分优先，回退到最近一条过去评分。"""
    with SessionLocal() as db:
        score = db.execute(
            select(StockScore).where(StockScore.stock_code == stock_code,
                                     StockScore.trade_date == trade_date)
        ).scalar_one_or_none()
        if score is None:
            score = db.execute(
                select(StockScore).where(StockScore.stock_code == stock_code)
                .order_by(StockScore.trade_date.desc()).limit(1)
            ).scalar_one_or_none()
        if score is None:
            return None
        detail = score.detail or {}
        factors = detail.get("factors")
        if not isinstance(factors, list) or not factors:
            return None
        return [{"factor": f.get("factor", ""), "score": f.get("score", 0)}
                for f in factors if isinstance(f, dict)]
```

### 5.4 track_verify.py — 核心改动

#### 5.4.1 _init_candidates() 提取因子分

```python
def _init_candidates() -> int:
    initialized = 0
    for cand in repo.list_untracked_candidates():
        base = 0.0
        try:
            base = float((cand.get("snapshot") or {}).get("price") or 0)
        except (TypeError, ValueError):
            base = 0.0
        rating = repo.get_candidate_rating(cand["stock_code"], cand["trade_date"])
        # 新增：从 stock_score 提取六因子分值
        factor_scores = repo.get_score_factors(cand["stock_code"], cand["trade_date"])
        repo.upsert_track_verify(cand["stock_code"], cand["stock_name"],
                                 cand["trade_date"], rating, base,
                                 factor_scores=factor_scores)
        initialized += 1
    return initialized
```

#### 5.4.2 回填已有行的因子分

```python
def backfill_factor_scores() -> dict:
    """回填已有追踪行的 factor_scores（用于已存在但创建时未提取因子分的行）。
    幂等：已有 factor_scores 的行跳过；无对应 stock_score 的行跳过。
    返回 {"filled": int, "skipped": int, "no_score": int}"""
    filled = skipped = no_score = 0
    for row in repo.list_track_verify(limit=500):
        if row.get("factor_scores"):  # 已有则跳过
            skipped += 1
            continue
        factors = repo.get_score_factors(row["stock_code"], row["select_date"])
        if factors is None:
            no_score += 1
            continue
        repo.update_track_verify(row["id"], factor_scores=factors)
        filled += 1
    return {"filled": filled, "skipped": skipped, "no_score": no_score}
```

#### 5.4.3 update_track_verify 加 factor_scores 参数

```python
def update_track_verify(row_id, *, t3_pct=None, t5_pct=None, t10_pct=None,
                        max_drawdown=None, verify_result=None,
                        is_finished=0, factor_scores=None) -> None:
    # ... 既有逻辑 ...
    if factor_scores is not None:
        row.factor_scores = factor_scores
```

#### 5.4.4 compute_factor_correlation 纯函数

```python
_FACTOR_NAMES = ("动量", "催化", "估值", "主线契合", "资金面", "基本面质量")
_FACTOR_HIGH = 7    # 高分阈值（≥7 为高分组）
_FACTOR_LOW = 3     # 低分阈值（≤3 为低分组）
_FACTOR_MIN_GROUP = 3  # 每组最少样本（沿用 _MIN_SAMPLE）
_CALIBRATION_THRESHOLD = 5.0  # avg_pct 差值超过此值才生成校准建议

def compute_factor_correlation(rows: list[dict], period: str = "t5") -> dict:
    """因子相关性分析（纯函数，可单测）。
    
    输入：track_verify 行列表（需含 factor_scores 和 {period}_pct）
    输出：{
        "period": "t5",
        "n_total": 40,           # 总行数
        "n_with_factors": 25,    # 有因子分的行数
        "factors": {
            "动量": {
                "high": {"n": 8, "win_rate": 62.5, "avg_pct": 2.1},
                "low":  {"n": 5, "win_rate": 40.0, "avg_pct": -1.2},
                "status": "effective",   # effective/ineffective/neutral/insufficient_sample
                "win_rate_diff": 22.5,
                "avg_pct_diff": 3.3
            },
            ...
        },
        "calibration_notes": ["动量因子高分组的 T+5 胜率 62.5% 显著高于低分组 40.0%（差 22.5pp），因子有效"]
    }
    
    口径：
    - 高分组 = 该因子分值 ≥ 7 的候选
    - 低分组 = 该因子分值 ≤ 3 的候选
    - 每组样本 < 3 → status="insufficient_sample"，不参与比较
    - win_rate_diff = high.win_rate - low.win_rate（>10pp = effective, <-10pp = ineffective）
    - avg_pct_diff = high.avg_pct - low.avg_pct
    """
    col = f"{period}_pct"
    # 只取有因子分且有 T+N 数据的行
    usable = []
    for r in rows:
        fs = r.get("factor_scores")
        pct = r.get(col)
        if not isinstance(fs, list) or not fs or pct is None:
            continue
        # 转为 {因子名: 分值} 字典
        factor_map = {}
        for f in fs:
            if isinstance(f, dict) and f.get("factor"):
                try:
                    factor_map[f["factor"]] = int(f.get("score", 0))
                except (TypeError, ValueError):
                    pass
        if factor_map:
            usable.append({"pct": float(pct), "factors": factor_map})
    
    result = {
        "period": period,
        "n_total": len(rows),
        "n_with_factors": len(usable),
        "factors": {},
        "calibration_notes": [],
    }
    
    for fname in _FACTOR_NAMES:
        high_group = [u for u in usable if u["factors"].get(fname, -1) >= _FACTOR_HIGH]
        low_group = [u for u in usable if u["factors"].get(fname, -1) <= _FACTOR_LOW and u["factors"].get(fname, -1) >= 0]
        
        high_stats = _group_stats_simple([u["pct"] for u in high_group])
        low_stats = _group_stats_simple([u["pct"] for u in low_group])
        
        entry = {
            "high": high_stats,
            "low": low_stats,
            "status": "insufficient_sample",
            "win_rate_diff": None,
            "avg_pct_diff": None,
        }
        
        if high_stats["n"] >= _FACTOR_MIN_GROUP and low_stats["n"] >= _FACTOR_MIN_GROUP:
            wr_diff = (high_stats["win_rate"] or 0) - (low_stats["win_rate"] or 0)
            ap_diff = (high_stats["avg_pct"] or 0) - (low_stats["avg_pct"] or 0)
            entry["win_rate_diff"] = round(wr_diff, 1)
            entry["avg_pct_diff"] = round(ap_diff, 2)
            if wr_diff > 10:
                entry["status"] = "effective"
            elif wr_diff < -10:
                entry["status"] = "ineffective"
            else:
                entry["status"] = "neutral"
        
        result["factors"][fname] = entry
        
        # 生成校准备注
        if entry["status"] == "ineffective" and abs(entry["avg_pct_diff"] or 0) >= _CALIBRATION_THRESHOLD:
            result["calibration_notes"].append(
                f"{fname}因子高分组的{ {'t3':'T+3','t5':'T+5','t10':'T+10'}.get(period,'T+N') }"
                f"胜率 {high_stats['win_rate']}% 低于低分组 {low_stats['win_rate']}%"
                f"（差 {entry['win_rate_diff']}pp），平均涨幅差 {entry['avg_pct_diff']}pp，"
                f"因子预测力失效，建议人工复核权重"
            )
        elif entry["status"] == "effective" and abs(entry["avg_pct_diff"] or 0) >= _CALIBRATION_THRESHOLD:
            result["calibration_notes"].append(
                f"{fname}因子高分组的{ {'t3':'T+3','t5':'T+5','t10':'T+10'}.get(period,'T+N') }"
                f"胜率 {high_stats['win_rate']}% 高于低分组 {low_stats['win_rate']}%"
                f"（差 {entry['win_rate_diff']}pp），因子预测力有效"
            )
    
    return result


def _group_stats_simple(pcts: list[float]) -> dict:
    """简化的组统计（只算 n/wins/win_rate/avg_pct）"""
    n = len(pcts)
    if n == 0:
        return {"n": 0, "wins": 0, "win_rate": None, "avg_pct": None}
    wins = sum(1 for p in pcts if p > 0)
    return {
        "n": n,
        "wins": wins,
        "win_rate": round(wins / n * 100, 1),
        "avg_pct": round(sum(pcts) / n, 2),
    }
```

#### 5.4.5 校准建议模板

```python
def _template_calibration_suggestions(correlation: dict) -> list[dict]:
    """因子校准建议模板（确定性，全部 suggestion_source=template）。
    仅对 status=ineffective 且 avg_pct_diff 超阈值的因子生成建议。"""
    out = []
    period = correlation.get("period", "t5")
    period_label = {"t3": "T+3", "t5": "T+5", "t10": "T+10"}.get(period, "T+N")
    factors = correlation.get("factors", {})
    
    ineffective = []
    for fname, data in factors.items():
        if data.get("status") == "ineffective" and abs(data.get("avg_pct_diff") or 0) >= _CALIBRATION_THRESHOLD:
            ineffective.append(fname)
            high = data["high"]
            low = data["low"]
            out.append({
                "target_agent": "score", "target_kind": "prompt", "rule_type": "soft",
                "priority": "high",
                "rule_name": f"因子权重校准建议（{fname} 预测力失效）",
                "current_value": f"{fname}因子参考权重约 {_FACTOR_DEFAULT_WEIGHTS.get(fname, '15%')}，"
                                 f"高分组合格率 {high['win_rate']}%，低分组 {low['win_rate']}%",
                "suggested_value": (f"{fname}因子高分组的{period_label}胜率 {high['win_rate']}% "
                                    f"低于低分组 {low['win_rate']}%（差 {data['win_rate_diff']}pp），"
                                    f"建议人工复核降低该因子权重"),
                "reason": (f"统计显示 {fname} 因子高分组（≥7分）表现反而差于低分组（≤3分），"
                           f"该因子对后续涨幅的预测力失效，可能误导评分"),
                "evidence": (f"高分组 n={high['n']} 胜率 {high['win_rate']}% 平均 {high['avg_pct']}%，"
                             f"低分组 n={low['n']} 胜率 {low['win_rate']}% 平均 {low['avg_pct']}%"),
                "rule_text": (f"当 {fname} 因子高分组胜率持续低于低分组（差值>10pp 且 avg_pct 差>"
                              f"{_CALIBRATION_THRESHOLD}pp）时，应在评分提示词中降低该因子权重，"
                              f"直至因子预测力恢复后人工复核恢复"),
                "problem_desc": f"{fname}因子与后续表现相关性倒挂，可能误导评级与仓位分配",
                "expected_effect": "恢复因子与表现的正常相关性，失效期降低该因子对评分的影响",
                "risk_note": "小样本可能为噪声，需连续 2 个统计期确认后才调整权重",
                "file_path": "agent_prompts/score_prompt.py",
                "insert_position": "六因子定义与参考权重段",
            })
    
    # 多因子同时失效 → 整体复核建议
    if len(ineffective) >= 3:
        out.append({
            "target_agent": "score", "target_kind": "prompt", "rule_type": "soft",
            "priority": "high",
            "rule_name": f"评分体系整体复核建议（{len(ineffective)}个因子同时失效）",
            "current_value": f"六因子中 {', '.join(ineffective)} 预测力失效",
            "suggested_value": "建议人工全面复核评分体系，考虑调整因子结构或引入新因子",
            "reason": "多个因子同时失效说明当前评分体系可能不适应近期市场环境",
            "evidence": f"失效因子：{', '.join(ineffective)}",
            "rule_text": "当六因子中≥3个因子预测力同时失效时，应触发评分体系整体复核",
            "problem_desc": "评分体系整体预测力下降，多因子同时与后续表现脱钩",
            "expected_effect": "及时识别评分体系系统性失效，避免持续误导",
            "risk_note": "整体复核须人工执行，禁止系统自动改变因子结构",
            "file_path": "agent_prompts/score_prompt.py",
            "insert_position": "六因子定义段",
        })
    
    return out
```

#### 5.4.6 get_factor_calibration() — 注入 ScoreAgent 的相关性文本

```python
_CALIBRATION_TTL = 3600  # 因子校准摘要缓存（1 小时）

def get_factor_calibration(period: str = "t5") -> str:
    """因子校准相关性摘要（紧凑文本，供 ScoreAgent build_user_prompt 注入）。
    只读本模块统计，不改任何逻辑。无数据/读取失败 → 返回空字符串。"""
    key = f"factor:calibration:{period}"
    try:
        cached = cache.get(key)
        if cached:
            return cached
        rows = repo.list_track_verify(limit=500)
    except Exception as exc:
        logger.warning("因子校准摘要读取失败（跳过注入）: %s", exc)
        return ""
    
    correlation = compute_factor_correlation(rows, period=period)
    text = _format_calibration_text(correlation)
    if text:
        try:
            cache.set(key, text, _CALIBRATION_TTL)
        except Exception as exc:
            logger.warning("因子校准摘要缓存写入失败: %s", exc)
    return text


def _format_calibration_text(correlation: dict) -> str:
    """因子相关性 → 紧凑文本（客观事实，不给结论性建议）。"""
    n = correlation.get("n_with_factors", 0)
    if n < _FACTOR_MIN_GROUP:
        return ""
    period_label = {"t3": "T+3", "t5": "T+5", "t10": "T+10"}.get(correlation.get("period", ""), "T+N")
    lines = [f"因子校准相关性（{n} 个有因子分的样本，{period_label}周期）："]
    for fname in _FACTOR_NAMES:
        f = correlation.get("factors", {}).get(fname)
        if not f or f.get("status") == "insufficient_sample":
            continue
        high, low = f["high"], f["low"]
        status_map = {"effective": "有效", "ineffective": "失效", "neutral": "无显著差异"}
        lines.append(
            f"- {fname}：高分组({high['n']}只)胜率{high['win_rate']}%/均涨{high['avg_pct']}% "
            f"vs 低分组({low['n']}只)胜率{low['win_rate']}%/均涨{low['avg_pct']}% → {status_map.get(f['status'], '未知')}"
        )
    if len(lines) <= 1:
        return ""
    lines.append("以上为因子预测力的历史统计事实，供你评分时参考。表现差的因子可适当降低权重，"
                 "但不得增减因子数量。此为参考信息，不改变已有规则。")
    return "\n".join(lines)
```

#### 5.4.7 扩展 run_verify_chain()

```python
def run_verify_chain(backfill: bool = False, price_lookup=None, llm_call=None) -> dict:
    # ... 既有逻辑 ...
    if finished_new > 0 or backfill:
        rows = repo.list_track_verify()
        stats = compute_stats(rows, period="t5")
        anomalies = detect_anomalies(stats)
        # 新增：因子相关性计算
        correlation = compute_factor_correlation(rows, period="t5")
        result["stats"] = stats
        result["anomalies"] = anomalies
        result["factor_correlation"] = correlation
        result["suggestions"] = generate_suggestions(stats, anomalies, llm_call=llm_call)
        # 新增：因子校准建议（模板兜底，走人工审核闭环）
        cal_suggestions = _template_calibration_suggestions(correlation)
        for tpl in cal_suggestions:
            if repo.has_pending_suggestion(tpl["rule_name"], tpl["target_agent"]):
                continue
            repo.insert_agent_suggestion(
                0, tpl["target_agent"], tpl["rule_name"],
                tpl["current_value"], tpl["suggested_value"],
                tpl["reason"], tpl["evidence"],
                target_kind=tpl["target_kind"],
                rule_type=tpl["rule_type"], priority=tpl["priority"],
                problem_desc=tpl["problem_desc"], rule_text=tpl["rule_text"],
                expected_effect=tpl["expected_effect"], risk_note=tpl["risk_note"],
                file_path=tpl["file_path"], insert_position=tpl["insert_position"],
                suggestion_source="template")
    # ... 既有逻辑 ...
```

### 5.5 score_prompt.py — build_user_prompt 注入校准文本

```python
# build_user_prompt 新增 factor_calibration 参数：
def build_user_prompt(data_pack, preference="", discover_context="",
                     market_intel_summary="", factor_calibration="") -> str:
    # ... 既有逻辑 ...
    # 在 market_intel_summary 之后追加：
    if factor_calibration:
        parts.append(f"【因子校准相关性参考】\n{factor_calibration}")
    # ... 既有逻辑 ...
```

### 5.6 score.py — collect_data 注入校准文本

```python
def collect_data(state):
    # ... 既有逻辑 ...
    # 在 market_intel_summary 之后新增：
    factor_calibration = ""
    try:
        from app.services.track_verify import get_factor_calibration
        factor_calibration = get_factor_calibration()
    except Exception:
        pass  # 读取失败不阻塞评分
    state["factor_calibration"] = factor_calibration
    # ... 既有逻辑 ...

def llm_score(state):
    # ... 既有逻辑 ...
    user_prompt = score_prompt.build_user_prompt(
        data_pack, preference=state.get("preference", ""),
        discover_context=state.get("discover_context", ""),
        market_intel_summary=state.get("market_intel_summary", ""),
        factor_calibration=state.get("factor_calibration", ""),
    )
    # ... 既有逻辑 ...
```

### 5.7 scheduler/jobs.py — 回填任务注册

在 `track_verify_job()` 末尾追加因子分回填（不新建独立 job，复用 16:00 窗口）：

```python
def track_verify_job() -> None:
    # ... 既有逻辑 ...
    result = track_verify.run_verify_chain(backfill=False)
    # ... 既有日志 ...
    # 新增：因子分回填（幂等，已有则跳过）
    try:
        backfill_result = track_verify.backfill_factor_scores()
        if backfill_result["filled"] > 0:
            logger.info("因子分回填: %s", backfill_result)
    except Exception as exc:
        logger.warning("因子分回填失败: %s", exc)
```

---

## 六、测试清单

### 6.1 新建 test_factor_calibration.py

| # | 测试 | 要点 |
|---|------|------|
| 1 | `test_compute_factor_correlation_basic` | 构造 10 行数据（6 因子分 + t5_pct），验证 high/low 分组统计正确 |
| 2 | `test_compute_factor_correlation_effective` | 高分组胜率 >> 低分组 → status="effective" |
| 3 | `test_compute_factor_correlation_ineffective` | 高分组胜率 << 低分组 → status="ineffective" |
| 4 | `test_compute_factor_correlation_neutral` | 差值在 ±10pp 内 → status="neutral" |
| 5 | `test_compute_factor_correlation_insufficient_sample` | 某因子高分组 <3 → status="insufficient_sample" |
| 6 | `test_compute_factor_correlation_no_factor_scores` | 行无 factor_scores → 不参与计算，n_with_factors 不含该行 |
| 7 | `test_compute_factor_correlation_null_pct` | factor_scores 有但 t5_pct=None → 不参与计算 |
| 8 | `test_template_calibration_ineffective` | 构造 ineffective 因子 → 生成降权建议，rule_name 含因子名 |
| 9 | `test_template_calibration_multi_failure` | ≥3 个因子失效 → 生成整体复核建议 |
| 10 | `test_template_calibration_no_failure` | 全部 effective/neutral → 不生成任何建议 |
| 11 | `test_get_score_factors_new_format` | detail 含 factors 列表 → 正确提取 [{factor, score}] |
| 12 | `test_get_score_factors_old_format` | detail 是旧维度字典 → 返回 None |
| 13 | `test_get_score_factors_no_score` | 无评分记录 → 返回 None |
| 14 | `test_backfill_factor_scores_idempotent` | 已有 factor_scores 的行跳过 |
| 15 | `test_format_calibration_text_empty` | n_with_factors < 3 → 返回空字符串 |
| 16 | `test_format_calibration_text_with_data` | 有数据 → 文本含各因子高/低分组胜率 |

### 6.2 适配既有测试

- `test_batch5_accuracy_loop.py`：如 `run_verify_chain` mock 需适配新增的 `factor_correlation` 返回字段（但不破坏既有断言）
- `test_track_verify.py`：`run_verify_chain` 返回值新增 `factor_correlation` 字段，既有测试不断言该字段则无需改

---

## 七、验证清单

- [ ] `test_factor_calibration.py` 全部通过（≥16 条新测试）
- [ ] `get_score_factors` 正确提取新格式因子分，旧格式返回 None
- [ ] `compute_factor_correlation` 纯函数：effective/ineffective/neutral/insufficient_sample 四态正确
- [ ] 校准建议走 `has_pending_suggestion` 去重，全部 status=pending
- [ ] `get_factor_calibration()` 缓存生效，无数据返回空字符串不报错
- [ ] `build_user_prompt` 新增 `factor_calibration` 参数有默认值，既有调用不传不报错
- [ ] `score.py` collect_data 读取失败不阻塞评分（try/except 吞异常）
- [ ] 全量 pytest 593 passed 0 failed（零回归）
- [ ] 改前备份涉及文件为 `.bak.batchC`

---

## 八、运行时验证（手动，部署后）

1. **手动触发回填**：应用启动后调 `backfill_factor_scores()`，确认已有 40 行追踪行的因子分回填情况（有评分记录的行提取因子分，无评分/旧格式的行 factor_scores=null）
2. **手动触发相关性计算**：调 `run_verify_chain(backfill=True)`，检查返回值中 `factor_correlation` 字段是否包含六因子的高/低分组统计
3. **手动触发评分**：跑一次 ScoreAgent，检查 `build_user_prompt` 中是否注入了因子校准相关性文本（有数据时注入，无数据时空字符串不注入）

---

## 九、执行顺序

1. `models.py` — CandidateTrackVerify 加 `factor_scores` 列
2. `session.py` — 新增 `_ensure_track_verify_factor_scores()` + 在 `init_db()` 中调用
3. `repo.py` — `upsert_track_verify` 加 `factor_scores` 参数 + `update_track_verify` 加 `factor_scores` 参数 + 新增 `get_score_factors()`
4. `track_verify.py` — `_init_candidates()` 提取因子分 + `backfill_factor_scores()` + `compute_factor_correlation()` + `_group_stats_simple()` + `_template_calibration_suggestions()` + `get_factor_calibration()` + `_format_calibration_text()` + 扩展 `run_verify_chain()`
5. `score_prompt.py` — `build_user_prompt` 加 `factor_calibration` 参数
6. `score.py` — `collect_data` 注入校准文本 + `llm_score` 传递参数
7. `scheduler/jobs.py` — `track_verify_job` 末尾追加回填调用
8. 新建 `test_factor_calibration.py`
9. 全量 pytest 确认零回归

---

## 十、_FACTOR_DEFAULT_WEIGHTS 常量

在 `track_verify.py` 顶部定义（供校准建议文案引用当前权重）：

```python
_FACTOR_DEFAULT_WEIGHTS = {
    "动量": "20%", "催化": "20%", "估值": "15%",
    "主线契合": "15%", "资金面": "15%", "基本面质量": "15%",
}
```
