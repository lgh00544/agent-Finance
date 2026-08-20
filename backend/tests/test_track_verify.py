"""候选池标的 T+N 自动追踪验证模块测试：
T+N 计算纯函数、评级解析、回填幂等、到期标记、行情失败降级、
建议生成（LLM/模板来源 + 去重）、迁移幂等、任务提交。
全部注入假行情/假 LLM，零网络；数据层走 init_db + SessionLocal。"""
import datetime

import pandas as pd
import pytest
from sqlalchemy import select, text

from app.agents.schemas import AgentSuggestionItem, TrackVerifyOutput
from app.db import repo
from app.db.models import AgentSuggestion, CandidateTrackVerify, StockCandidate
from app.db.session import SessionLocal, init_db
from app.services import track_verify as tv


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _clean_track():
    """链路测试互不干扰：候选/追踪/建议表每用例清空 + 失效 dbq 缓存（防 60s 缓存串扰）"""
    with SessionLocal() as db:
        db.execute(CandidateTrackVerify.__table__.delete())
        db.execute(AgentSuggestion.__table__.delete())
        db.execute(StockCandidate.__table__.delete())
        db.commit()
        repo._invalidate("track_verify")
        repo._invalidate("candidate")
        yield
        db.execute(CandidateTrackVerify.__table__.delete())
        db.execute(AgentSuggestion.__table__.delete())
        db.execute(StockCandidate.__table__.delete())
        db.commit()
        repo._invalidate("track_verify")
        repo._invalidate("candidate")


def _kline(closes: list[float], start="2026-08-03") -> pd.DataFrame:
    """假日K：date 从 start 起每日递增（仅交易日语义，测试用）"""
    dates = []
    d = datetime.date.fromisoformat(start)
    for _ in closes:
        dates.append(d.strftime("%Y-%m-%d"))
        d += datetime.timedelta(days=1)
    return pd.DataFrame({"date": dates, "close": closes})


def _no_llm(stats_json, anomaly_types):
    return TrackVerifyOutput()


def _seed_candidate(code: str, select_date: str, base: float,
                    rating: str = "A") -> None:
    repo.upsert_candidate(code, f"测试{code}", select_date, 1, ["理由"], ["风险"],
                          {"price": base}, {"confidence_tier": rating})


# ================= 1. T+N 计算纯函数 =================

def test_tn_metrics_full_cycle():
    closes = [10, 10.2, 10.4, 10.1, 9.8, 9.9, 10.3, 10.6, 10.9, 11.2, 11.5, 11.8]
    dates = [d for d in _kline(closes)["date"]]
    m = tv.compute_tn_metrics(dates, closes, 10.2, "2026-08-04")  # t0=1
    assert m["t3"]["pct"] == pytest.approx(-3.92)   # 9.8/10.2-1
    assert m["t5"]["pct"] == pytest.approx(0.98)    # 10.3/10.2-1
    assert m["t10"]["pct"] == pytest.approx(15.69)  # 11.8/10.2-1
    assert m["due"] is True
    assert m["max_drawdown"] == pytest.approx(3.92)  # (10.2-9.8)/10.2
    assert m["min_close_date"] == "2026-08-07"


def test_tn_metrics_insufficient_periods():
    closes = [10, 10.5, 11]  # 仅到 T+2，T+3 起不足
    dates = [d for d in _kline(closes)["date"]]
    m = tv.compute_tn_metrics(dates, closes, 10.0, "2026-08-03")
    assert m["t3"]["pct"] is None and m["t5"]["pct"] is None
    assert m["t10"]["pct"] is None and m["due"] is False
    assert any("数据不足" in n for n in m["notes"])


def test_tn_metrics_boundary_t10_just_available():
    closes = list(range(10, 21))  # 11 日：t0=0 时 t10=10 < 11 ✓
    dates = [d for d in _kline(closes)["date"]]
    m = tv.compute_tn_metrics(dates, closes, 10.0, "2026-08-03")
    assert m["t10"]["pct"] == pytest.approx(100.0)
    assert m["due"] is True


def test_tn_metrics_select_date_missing_raises():
    closes = [10, 10.5, 11]
    dates = [d for d in _kline(closes)["date"]]
    with pytest.raises(ValueError):
        tv.compute_tn_metrics(dates, closes, 10.0, "2020-01-01")


def test_tn_metrics_base_fallback():
    """基准价缺失（0）时用选中日收盘兜底"""
    closes = [10, 10.5, 11, 11.5, 12, 13]
    dates = [d for d in _kline(closes)["date"]]
    m = tv.compute_tn_metrics(dates, closes, 0.0, "2026-08-03")
    assert m["t3"]["pct"] == pytest.approx(15.0)  # 11.5/10-1


def test_tn_metrics_drawdown_not_double_counted():
    """先涨后回撤不双计：回撤只相对基准最低收盘，与区间高点无关"""
    closes = [10, 11, 11.5, 11.2, 9.5, 9.8, 10.1]
    dates = [d for d in _kline(closes)["date"]]
    m = tv.compute_tn_metrics(dates, closes, 10.0, "2026-08-03")
    assert m["max_drawdown"] == pytest.approx(5.0)   # (10-9.5)/10，而非高点回撤
    assert m["min_close_date"] == "2026-08-07"


# ================= 2. 统计纯函数 =================

def _row(pct, dd=None, rating="A", date="2026-08-05"):
    return {"t5_pct": pct, "max_drawdown": dd,
            "select_rating": rating, "select_date": date}


def test_stats_countable_filter_and_pl_ratio():
    rows = [_row(5.0, 3.0), _row(-2.0, 4.0), _row(3.0, 1.0),
            _row(None, None)]  # 未到周期不参与
    s = tv.compute_stats(rows, "t5")
    assert s["n"] == 3 and s["wins"] == 2
    assert s["win_rate"] == pytest.approx(66.7)
    assert s["avg_pct"] == pytest.approx(2.0)
    assert s["pl_ratio"] == pytest.approx(4.0)  # (5+3)/2
    assert s["avg_max_dd"] == pytest.approx(2.67)


def test_stats_pl_ratio_none_when_no_loss():
    s = tv.compute_stats([_row(1.0), _row(2.0)], "t5")
    assert s["pl_ratio"] is None and s["win_rate"] == 100.0


def test_stats_grouping_by_rating_and_date():
    rows = [_row(1.0, rating="A", date="2026-08-05"),
            _row(-2.0, rating="B", date="2026-08-05"),
            _row(3.0, rating="建议关注", date="2026-08-06")]
    s = tv.compute_stats(rows, "t5")
    assert set(s["by_rating"]) == {"A", "B", "建议关注"}
    assert s["by_rating"]["A"]["n"] == 1
    assert set(s["by_date"]) == {"2026-08-05", "2026-08-06"}
    assert s["by_date"]["2026-08-05"]["wins"] == 1


# ================= 3. 异常检测 =================

def test_detect_consecutive_decline():
    stats = {"n": 9, "win_rate": 50.0, "avg_pct": 0.0, "period": "t5",
             "by_rating": {},
             "by_date": {"2026-08-05": {"n": 3, "win_rate": 60.0},
                         "2026-08-06": {"n": 3, "win_rate": 50.0},
                         "2026-08-07": {"n": 3, "win_rate": 40.0}}}
    a = tv.detect_anomalies(stats)
    assert any(x["type"] == "consecutive_decline" for x in a)


def test_detect_rating_inversion():
    stats = {"n": 6, "win_rate": 50.0, "avg_pct": 0.0, "period": "t5",
             "by_date": {},
             "by_rating": {"A": {"n": 3, "avg_pct": 1.0, "win_rate": 66.7},
                           "C": {"n": 3, "avg_pct": 3.0, "win_rate": 66.7}}}
    a = tv.detect_anomalies(stats)
    assert any(x["type"] == "rating_inversion" for x in a)
    # C 不高于 A 时不触发
    stats["by_rating"]["C"]["avg_pct"] = 0.5
    assert not any(x["type"] == "rating_inversion"
                   for x in tv.detect_anomalies(stats))


def test_detect_win_rate_low_and_small_sample():
    stats = {"n": 3, "win_rate": 35.0, "avg_pct": -1.0, "period": "t5",
             "by_rating": {}, "by_date": {}}
    assert any(x["type"] == "win_rate_low" for x in tv.detect_anomalies(stats))
    stats["n"] = 2  # 样本不足不触发
    assert tv.detect_anomalies(stats) == []


# ================= 4. 评级解析 =================

def test_candidate_rating_grade_first_then_tier():
    repo.upsert_score("600301", "测试评分股", "2026-08-03", 88.0, "B", {}, [])
    assert repo.get_candidate_rating("600301", "2026-08-03") == "B"
    # 无评分记录 → 回落 confidence_tier 原文
    _seed_candidate("600302", "2026-08-03", 10.0, "建议关注")
    assert repo.get_candidate_rating("600302", "2026-08-03") == "建议关注"
    # 全无 → 空串
    assert repo.get_candidate_rating("999999", "2026-08-03") == ""


# ================= 5. 回填幂等 =================

def test_chain_init_due_and_idempotent():
    closes = [10, 10.5, 11, 10.8, 11.2, 11.6, 11.4, 12, 12.3, 12.1, 12.5, 12.8]
    _seed_candidate("600101", "2026-08-03", 10.0)
    lookup = lambda c, d: _kline(closes, start=d)

    r1 = tv.run_verify_chain(backfill=False, price_lookup=lookup, llm_call=_no_llm)
    assert r1["initialized"] == 1 and r1["updated"] == 1 and r1["finished_new"] == 1
    row = repo.list_track_verify()[0]
    assert row["is_finished"] == 1
    assert row["t3_pct"] == pytest.approx(8.0)      # 10.8/10-1
    assert row["t5_pct"] == pytest.approx(16.0)     # 11.6/10-1
    assert row["t10_pct"] == pytest.approx(25.0)    # 12.5/10-1
    assert row["verify_result"]["periods"]["t3"]["win"] is True
    assert row["verify_result"]["latest_date"] == "2026-08-14"  # 12 个交易日末位

    r2 = tv.run_verify_chain(backfill=False, price_lookup=lookup, llm_call=_no_llm)
    assert r2["initialized"] == 0      # 幂等：不再初始化
    assert r2["updated"] == 0          # 已到期不再遍历
    assert repo.list_track_verify().__len__() == 1  # 无重复行


def test_chain_insufficient_keeps_tracking():
    closes = [10, 10.5, 11]  # T+3 不足
    _seed_candidate("600102", "2026-08-03", 10.0)
    r = tv.run_verify_chain(backfill=False,
                            price_lookup=lambda c, d: _kline(closes, start=d),
                            llm_call=_no_llm)
    assert r["updated"] == 1 and r["finished_new"] == 0
    row = repo.list_track_verify()[0]
    assert row["is_finished"] == 0 and row["t3_pct"] is None
    assert any("数据不足" in n for n in row["verify_result"].get("notes", []))


# ================= 6. 行情失败降级 =================

def test_chain_price_failure_degrades():
    closes_ok = [10, 10.5, 11, 10.8, 11.2, 11.6, 11.4, 12, 12.3, 12.1, 12.5, 12.8]
    _seed_candidate("600103", "2026-08-03", 10.0)
    _seed_candidate("600104", "2026-08-03", 10.0)

    def flaky(code, d):
        if code == "600103":
            raise RuntimeError("行情不可达")
        return _kline(closes_ok, start=d)

    r = tv.run_verify_chain(backfill=False, price_lookup=flaky, llm_call=_no_llm)
    assert r["updated"] == 1  # 另一只正常完成
    assert any("600103" in e for e in r["errors"])
    rows = {x["stock_code"]: x for x in repo.list_track_verify()}
    assert rows["600103"]["is_finished"] == 0  # 失败行保持追踪中，下次自动重试
    assert rows["600104"]["is_finished"] == 1


# ================= 7. 建议生成：LLM/模板来源 + 去重 =================

def test_suggestions_llm_source():
    stats = {"period": "t5", "n": 3, "win_rate": 35.0, "avg_pct": -1.0,
             "by_rating": {}, "by_date": {}}
    anomalies = [{"type": "win_rate_low", "desc": "d", "data": {}}]

    def fake_llm(stats_json, anomaly_types):
        assert "stats" in stats_json  # 统计 JSON 已注入
        return TrackVerifyOutput(summary_note="测试要点", agent_suggestions=[
            AgentSuggestionItem(target_agent="discover", target_kind="prompt",
                                rule_name="测试规则-LLM来源", current_value="c",
                                suggested_value="s", reason="r", evidence="e",
                                rule_type="soft", priority="medium",
                                rule_text="完整可落地条文"),
        ])

    out = tv.generate_suggestions(stats, anomalies, llm_call=fake_llm)
    assert len(out["suggestions"]) == 1
    assert out["suggestions"][0]["suggestion_source"] == "llm"
    assert out["summary_note"] == "测试要点"
    with SessionLocal() as db:
        row = db.execute(select(AgentSuggestion)
                         .where(AgentSuggestion.rule_name == "测试规则-LLM来源")
                         ).scalar_one()
    assert row.suggestion_source == "llm" and row.review_id == 0
    assert row.status == "pending"  # 走人工审核闭环


def test_suggestions_template_fallback():
    stats = {"period": "t5", "n": 6, "win_rate": 50.0, "avg_pct": 0.0,
             "by_rating": {}, "by_date": {}}
    anomalies = [{"type": "rating_inversion", "desc": "倒挂",
                  "data": {"pair": "A<C",
                           "A": {"n": 3, "avg_pct": 1.0},
                           "C": {"n": 3, "avg_pct": 3.0}}}]

    def boom_llm(stats_json, anomaly_types):
        raise RuntimeError("LLM 不可用")

    out = tv.generate_suggestions(stats, anomalies, llm_call=boom_llm)
    assert len(out["fallbacks"]) == 1
    assert out["fallbacks"][0]["suggestion_source"] == "template"
    assert out["fallbacks"][0]["rule_name"] == "候选池评级正相关性校验（A<C 倒挂）"
    with SessionLocal() as db:
        row = db.execute(select(AgentSuggestion).where(
            AgentSuggestion.rule_name == "候选池评级正相关性校验（A<C 倒挂）")).scalar_one()
    assert row.suggestion_source == "template"
    assert "3.0" in row.evidence  # 模板条文携带事实数值


def test_suggestions_dedup_skip_existing_pending():
    stats = {"period": "t5", "n": 3, "win_rate": 35.0, "avg_pct": -1.0,
             "by_rating": {}, "by_date": {}}
    repo.insert_agent_suggestion(0, "discover", "测试规则-已存在", "c", "s",
                                 "r", "e", target_kind="prompt",
                                 suggestion_source="llm")

    def fake_llm(stats_json, anomaly_types):
        return TrackVerifyOutput(agent_suggestions=[
            AgentSuggestionItem(target_agent="discover", target_kind="prompt",
                                rule_name="测试规则-已存在", current_value="c",
                                suggested_value="s", reason="r", evidence="e",
                                rule_type="soft", rule_text="条文"),
        ])

    out = tv.generate_suggestions(stats, [], llm_call=fake_llm)
    assert out["suggestions"] == [] and out["deduped"] == 1
    with SessionLocal() as db:
        cnt = db.execute(select(AgentSuggestion).where(
            AgentSuggestion.rule_name == "测试规则-已存在")).scalars().all()
    assert len(cnt) == 1  # 不重复插入


def test_template_only_for_anomalies():
    """无异常时模板不产建议（LLM 空输出也干净返回）"""
    stats = {"period": "t5", "n": 3, "win_rate": 66.7, "avg_pct": 2.0,
             "by_rating": {}, "by_date": {}}
    out = tv.generate_suggestions(stats, [], llm_call=_no_llm)
    assert out["suggestions"] == [] and out["fallbacks"] == []


# ================= 8. 迁移幂等 =================

def test_migration_idempotent():
    init_db()  # 二次执行不报错（幂等）
    with SessionLocal() as db:
        cols = {r[1] for r in db.execute(text("PRAGMA table_info(agent_suggestion)")).all()}
        assert "suggestion_source" in cols
        tables = {r[0] for r in db.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")).all()}
        assert "candidate_track_verify" in tables


# ================= 9. 任务提交与端点 =================

def test_track_endpoints_submit_task(monkeypatch):
    from app.api import routes

    submitted = {}
    monkeypatch.setattr(routes, "_submit_task",
                        lambda kind, params: (submitted.update(kind=kind) or {"task_id": "t1"}))
    routes.track_verify_run(routes.TrackVerifyRunBody(backfill=False))
    assert submitted["kind"] == "track_verify"
    routes.track_verify_run(routes.TrackVerifyRunBody(backfill=True))
    assert submitted["kind"] == "track_backfill"
    routes.track_verify_suggest()
    assert submitted["kind"] == "track_suggest"
    # 读端点空库不报错
    assert routes.track_verify_list() == []
    assert routes.track_verify_dates() == []
    stats = routes.track_verify_stats("t5")
    assert stats["n"] == 0 and stats["anomalies"] == []


def test_task_track_verify_wrapper_both_suggestion_shapes(monkeypatch):
    """包装层兼容两种建议形状：生成时 dict / 未触发（finished_new=0 且非回填）时空列表，
    都不能崩（2026-08-10 真实运行回归：list.get AttributeError）"""
    from app.api import routes
    from app.services import track_verify as tv_mod

    def _chain_with_dict(backfill=False, price_lookup=None, llm_call=None):
        return {"initialized": 1, "updated": 0, "finished_new": 0, "errors": [],
                "stats": {}, "suggestions": {"suggestions": [{"rule_name": "x"}],
                                             "fallbacks": [], "deduped": 0}}

    def _chain_with_list(backfill=False, price_lookup=None, llm_call=None):
        return {"initialized": 0, "updated": 0, "finished_new": 0, "errors": [],
                "stats": None, "suggestions": []}

    monkeypatch.setattr(tv_mod, "run_verify_chain", _chain_with_dict)
    out = routes._task_track_verify(True)
    assert out["suggestion_count"] == 1 and out["deduped"] == 0 and "stats" not in out

    monkeypatch.setattr(tv_mod, "run_verify_chain", _chain_with_list)
    out = routes._task_track_verify(False)
    assert out["suggestion_count"] == 0 and out["deduped"] == 0
