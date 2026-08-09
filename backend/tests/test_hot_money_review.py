"""子任务B·游资复盘闭环 + 权重迭代（自进化，人工审核后生效）

覆盖：
1. review_prompt 游资复盘规则（K189 诱多/对倒、K227 口径误读、信号有效性评估）；
2. collect_signals：席位（含协同席位）净买入信号收集、去重；
3. compute_win_rate：信号后5日跑赢大盘 = 有效；行情不足跳过；
4. run_win_rate_iteration：胜率事实落库（win_rate_5d/last_review_at）+ 降/升档建议生成
   （pending 待审核，绝不自动改档位）；样本 < 3 不产建议；
5. apply_tier_suggestion：仅 approved（人工审核）后才生效，否则拒绝；
6. trace_hot_money_review 留痕（source_module='hot_money_review'）；
7. hot_money_profile 新列迁移幂等。
"""
import pytest

from agent_prompts import review_prompt
from app.agents import review as review_agent
from app.agents.schemas import ReviewOutput
from app.db import repo
from app.db.models import AiReasoningTrace
from app.db.session import SessionLocal, _ensure_hot_money_profile_columns, init_db
from app.services import hot_money_review as hmr
from app.services import reasoning_trace
from sqlalchemy import select


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()
    repo.seed_default_hot_money_profiles()


# ================= 1. 复盘提示词含游资复盘规则 =================

def test_review_prompt_contains_hot_money_rules():
    """复盘提示词：失败标的回溯游资信号归类（K189 诱多/对倒、K227 口径误读）+ 有效性评估"""
    sp = review_prompt.SYSTEM_PROMPT
    assert "游资信号有效性回溯" in sp
    assert "游资诱多/对倒骗局（K189）" in sp
    assert "数据口径误读（K227）" in sp
    assert "跑赢大盘 = 有效" in sp
    assert "hot_money_review" in sp
    assert "绝不直接改任何游资档案/权重/提示词" in sp
    assert "hot_money_review" in review_prompt.SCHEMA_DESC


# ================= 2. 信号收集与胜率统计 =================

def _make_actor(name: str, seat: str, tier: str) -> None:
    repo.upsert_hot_money_profile(name, seat, tier, ["打板"], ["军工"], [], "测试")


def _seed_signals(trade_date, code, name, seat, net):
    repo.insert_lhb_flows([
        {"trade_date": trade_date, "stock_code": code, "stock_name": name,
         "lhb_type": "1d", "disclosure_reason": "日涨幅偏离值达7%",
         "seat_name": seat, "buy_amt": abs(net) + 1e6, "sell_amt": max(0.0, -net),
         "net_buy": net, "confidence": 0.8, "source": "eastmoney"},
    ])


def test_collect_signals_dedup_and_buy_only():
    """信号收集：仅净买入 + (标的,日期) 去重取净买最大 + 协同席位计入"""
    _make_actor("测试游资-收集", "测试营业部-收集路", "二线")
    _seed_signals("2026-08-13", "600101", "信号股A", "测试营业部-收集路", 1e7)
    _seed_signals("2026-08-13", "600101", "信号股A", "测试营业部-收集路", 1.5e7)  # 同键去重取大
    _seed_signals("2026-08-13", "600102", "信号股B", "测试营业部-收集路", -5e7)   # 净卖不统计
    _seed_signals("2026-08-14", "600103", "信号股C", "测试营业部-协同A", 2e7)     # 协同席位计入

    profile = repo.get_profile_by_actor("测试游资-收集")
    repo.upsert_hot_money_profile("测试游资-收集", profile["seat_code"], "二线",
                                  co_seats=["测试营业部-协同A"])
    profile = repo.get_profile_by_actor("测试游资-收集")
    signals = hmr.collect_signals(profile)
    assert len(signals) == 2  # 600101(去重) + 600103(协同)
    s1 = [s for s in signals if s["stock_code"] == "600101"][0]
    assert s1["net_buy"] == 1.5e7  # 同键取净买最大
    assert {s["stock_code"] for s in signals} == {"600101", "600103"}


def test_compute_win_rate_beats_index():
    """胜率统计：跑赢大盘 = 有效；行情不足跳过不计入"""
    signals = [{"stock_code": c, "stock_name": c, "trade_date": "2026-08-13", "net_buy": 1e7}
               for c in ("600101", "600102", "600103", "600104", "600105")]

    def _lookup(code, date):
        if code == "600105":
            return None  # 行情不足跳过
        return (5.0, 1.0) if code in ("600101", "600102") else (-3.0, 1.0)

    wr = hmr.compute_win_rate(signals, _lookup)
    assert wr["countable"] == 4 and wr["wins"] == 2
    assert wr["win_rate"] == 0.5
    assert wr["skipped"] == ["600105 2026-08-13"]


# ================= 3. 胜率迭代：事实落库 + 建议生成（不自动生效） =================

def test_iteration_high_winrate_upgrade_suggestion_pending():
    """胜率 ≥60% → 升档建议（pending 待审核）；档位未被自动修改；胜率事实落库"""
    _make_actor("测试游资-升档", "测试营业部-升档路", "二线")
    for i, c in enumerate(("600201", "600202", "600203", "600204", "600205")):
        _seed_signals("2026-08-13", c, f"升档股{i}", "测试营业部-升档路", 1e7)

    def _lookup(code, date):
        return (6.0, 1.0) if code in ("600201", "600202", "600203", "600204") else (-4.0, 1.0)

    summary = hmr.run_win_rate_iteration(price_lookup=_lookup)
    me = [u for u in summary["updated"] if u["actor_name"] == "测试游资-升档"][0]
    assert me["win_rate_5d"] == pytest.approx(0.8)
    # 事实落库
    profile = repo.get_profile_by_actor("测试游资-升档")
    assert profile["win_rate_5d"] == pytest.approx(0.8)
    assert profile["last_review_at"]
    assert profile["tier"] == "二线"  # 未自动升档（人工审核后生效）
    # 建议生成且 pending
    sug = [s for s in summary["suggestions"] if "测试游资-升档" in s["rule_name"]]
    assert len(sug) == 1
    row = repo.get_agent_suggestion(sug[0]["id"])
    assert row.status == "pending"
    assert row.suggested_value == "一线"
    assert "≥ 60%" in row.reason


def test_iteration_low_winrate_downgrade_and_caution():
    """胜率 <40% → 降档建议 + '谨慎/反向参考'标注（写入提示词由人工决定）"""
    _make_actor("测试游资-降档", "测试营业部-降档路", "一线")
    for i, c in enumerate(("600301", "600302", "600303", "600304", "600305")):
        _seed_signals("2026-08-14", c, f"降档股{i}", "测试营业部-降档路", 1e7)

    def _lookup(code, date):
        return (6.0, 1.0) if code == "600301" else (-4.0, 1.0)

    summary = hmr.run_win_rate_iteration(price_lookup=_lookup)
    me = [u for u in summary["updated"] if u["actor_name"] == "测试游资-降档"][0]
    assert me["win_rate_5d"] == pytest.approx(0.2)
    profile = repo.get_profile_by_actor("测试游资-降档")
    assert profile["tier"] == "一线"  # 未自动降档
    sug = [s for s in summary["suggestions"] if "测试游资-降档" in s["rule_name"]]
    assert len(sug) == 1
    row = repo.get_agent_suggestion(sug[0]["id"])
    assert row.suggested_value == "二线"
    assert "低于 40%" in row.reason
    assert "谨慎/反向参考" in row.reason


def test_iteration_small_sample_no_suggestion():
    """样本 < 3：只记统计事实，不产生档位建议（温和策略，防小样本误判）"""
    _make_actor("测试游资-小样本", "测试营业部-小样本路", "观察")
    _seed_signals("2026-08-15", "600401", "小样本股", "测试营业部-小样本路", 1e7)

    def _lookup(code, date):
        return (-5.0, 1.0)

    summary = hmr.run_win_rate_iteration(price_lookup=_lookup)
    sug = [s for s in summary["suggestions"] if "测试游资-小样本" in s["rule_name"]]
    assert sug == []
    profile = repo.get_profile_by_actor("测试游资-小样本")
    assert profile["win_rate_5d"] == 0.0  # 0/1 事实落库


# ================= 4. 人工审核后才生效（监管红线） =================

def test_apply_tier_suggestion_requires_human_approval():
    """pending 拒绝应用（抛错）；approved（人工审核）后才生效改档位"""
    _make_actor("测试游资-应用", "测试营业部-应用路", "二线")
    for i, c in enumerate(("600501", "600502", "600503", "600504", "600505")):
        _seed_signals("2026-08-16", c, f"应用股{i}", "测试营业部-应用路", 1e7)

    def _lookup(code, date):
        return (6.0, 1.0) if code in ("600501", "600502", "600503", "600504") else (-4.0, 1.0)

    summary = hmr.run_win_rate_iteration(price_lookup=_lookup)
    sug = [s for s in summary["suggestions"] if "测试游资-应用" in s["rule_name"]][0]
    sid = sug["id"]
    # pending：拒绝应用（代码绝不自动改权重生效）
    with pytest.raises(ValueError, match="人工审核"):
        hmr.apply_tier_suggestion(sid)
    assert repo.get_profile_by_actor("测试游资-应用")["tier"] == "二线"
    # 人工审核通过后才生效
    repo.update_agent_suggestion_status(sid, "approved")
    result = hmr.apply_tier_suggestion(sid)
    assert result["new_tier"] == "一线"
    assert repo.get_profile_by_actor("测试游资-应用")["tier"] == "一线"


def test_apply_tier_suggestion_rejected_refused():
    """已驳回建议：拒绝应用"""
    _make_actor("测试游资-驳回", "测试营业部-驳回路", "二线")
    for i, c in enumerate(("600601", "600602", "600603", "600604", "600605")):
        _seed_signals("2026-08-17", c, f"驳回股{i}", "测试营业部-驳回路", 1e7)

    def _lookup(code, date):
        return (6.0, 1.0) if code in ("600601", "600602", "600603", "600604") else (-4.0, 1.0)

    summary = hmr.run_win_rate_iteration(price_lookup=_lookup)
    sug = [s for s in summary["suggestions"] if "测试游资-驳回" in s["rule_name"]][0]
    repo.update_agent_suggestion_status(sug["id"], "rejected", reason="样本太少不可信")
    with pytest.raises(ValueError, match="人工审核"):
        hmr.apply_tier_suggestion(sug["id"])
    assert repo.get_profile_by_actor("测试游资-驳回")["tier"] == "二线"


# ================= 5. 复盘闭环留痕（hot_money_review） =================

def test_trace_hot_money_review_lands():
    """复盘游资回溯结论落 ai_reasoning_trace（source_module='hot_money_review'）"""
    reasoning_trace.trace_hot_money_review(
        "601138", "工业富联", "2026-08-09",
        {"classification": "游资诱多/对倒骗局(K189)", "signal_effective": False,
         "basis": "游资买入后 5 日 -12%，跑输沪深300 +1.5%",
         "weight_suggestion": "建议纳入胜率统计并降档（须人工审核）"})
    reasoning_trace.flush()
    with SessionLocal() as db:
        rows = db.execute(select(AiReasoningTrace).where(
            AiReasoningTrace.source_module == "hot_money_review",
            AiReasoningTrace.stock_code == "601138")).scalars().all()
    assert rows
    t = rows[-1]
    assert "游资诱多" in t.capital_reasoning
    assert "signal_effective" in t.final_conclusion
    assert "K189" in t.rule_refs


def test_review_agent_writes_hot_money_review_trace(monkeypatch):
    """llm_review：LLM 输出 hot_money_review → 自动写 hot_money_review 留痕"""
    class _FakeOutput(ReviewOutput):
        pass

    out = ReviewOutput(
        plan_vs_actual={"入场逻辑": "游资加持", "兑现程度": "未兑现", "关键偏差": "诱多", "复盘结论": "被骗"},
        lesson="跟游资要警惕对倒", feedback={"偏好": "警惕高位游资票"},
        hot_money_review={"classification": "主力方向偏差", "signal_effective": False,
                          "basis": "回溯留痕信号后5日跑输大盘",
                          "weight_suggestion": "降权建议"})

    captured = {}

    def _fake_agent_call(agent, cache_key, system_prompt, user_prompt, schema,
                         ttl_seconds=86400, with_profile=True, with_knowledge=True, model_level=None):
        captured["prompt"] = user_prompt
        return out

    monkeypatch.setattr(review_agent, "agent_call", _fake_agent_call)
    state = {
        "stock_code": "601138", "stock_name": "工业富联", "trade_date": "2026-08-09",
        "holding_id": 99,
        "exit_suggest": {
            "holding": {"entry_date": "2026-08-01", "entry_price": 18.0, "shares": 1000,
                        "stop_loss": 16.5, "take_profit": 24.0, "note": ""},
            "trades": [], "plan": {}, "score": {}, "monitor_signals": [],
            "sell_decisions": [], "hot_money_signals": [], "hold_days": 8, "pnl_pct": -5.0,
            "price_stats": {},
        },
        "trace": [],
    }
    review_agent.llm_review(state)
    reasoning_trace.flush()
    with SessionLocal() as db:
        rows = db.execute(select(AiReasoningTrace).where(
            AiReasoningTrace.source_module == "hot_money_review",
            AiReasoningTrace.stock_code == "601138",
            AiReasoningTrace.generate_date == "2026-08-09")).scalars().all()
    assert rows, "llm_review 未写 hot_money_review 留痕"
    assert "主力方向偏差" in rows[-1].capital_reasoning
    # 复盘数据包注入游资信号历史（collect_review 侧由既有数据驱动，此处验证注入键存在）
    assert "hot_money_signals" in state["exit_suggest"]


# ================= 6. 新列迁移幂等 =================

def test_profile_migration_adds_columns_idempotent(tmp_path):
    """旧结构 hot_money_profile（无 win_rate_5d/last_review_at）→ 增量补列，数据不丢，可重复执行"""
    from sqlalchemy import create_engine

    eng = create_engine(f"sqlite:///{tmp_path / 'legacy_hm.db'}")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE hot_money_profile ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, actor_name VARCHAR(32), "
            "seat_code VARCHAR(64), tier VARCHAR(8), style_tags JSON, good_themes JSON, "
            "co_seats JSON, source VARCHAR(16), created_at DATETIME, updated_at DATETIME)")
        conn.exec_driver_sql(
            "INSERT INTO hot_money_profile (actor_name, seat_code, tier) "
            "VALUES ('旧游资', '旧席位', '一线')")

    _ensure_hot_money_profile_columns(eng)
    _ensure_hot_money_profile_columns(eng)  # 幂等：第二次不报错

    with eng.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(hot_money_profile)")}
        assert "win_rate_5d" in cols and "last_review_at" in cols
        row = conn.exec_driver_sql("SELECT actor_name, last_review_at "
                                   "FROM hot_money_profile").fetchone()
        assert row[0] == "旧游资", "迁移不应丢数据"
        assert row[1] == "", "迁移默认迭代时间为空"
