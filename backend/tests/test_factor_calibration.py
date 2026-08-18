"""评级重做-C：因子回测校准闭环测试（dev SQLite，不触网）

覆盖（≥16 条）：
1. compute_factor_correlation 纯函数：basic 分组统计 / effective / ineffective / neutral /
   insufficient_sample / 无 factor_scores 行剔除 / t5_pct None 行剔除
2. _template_calibration_suggestions：单因子失效降权建议 / ≥3 因子失效整体复核 / 无失效零建议
3. get_score_factors：新格式提取 / 旧格式 None / 无评分 None / 当日优先回退最近
4. backfill_factor_scores：幂等跳过已填 / 无评分 no_score / 正常填充
5. get_factor_calibration / _format_calibration_text：无数据空串 / 有数据含分组胜率 / 缓存
6. repo upsert/update_track_verify factor_scores 落库
"""
import pytest
from sqlalchemy import delete

from app.cache import cache
from app.db import repo
from app.db.models import CandidateTrackVerify, StockScore
from app.db.session import SessionLocal, init_db

FACTORS = ("动量", "催化", "估值", "主线契合", "资金面", "基本面质量")


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _cleanup():
    cache.delete_prefix("dbq:")
    cache.delete("factor:calibration:t5")
    with SessionLocal() as db:
        db.execute(delete(CandidateTrackVerify))
        db.execute(delete(StockScore))
        db.commit()
    yield
    cache.delete_prefix("dbq:")
    cache.delete("factor:calibration:t5")
    with SessionLocal() as db:
        db.execute(delete(CandidateTrackVerify))
        db.execute(delete(StockScore))
        db.commit()


def _fs(momentum=5, catalyst=5, value=5, mainline=5, capital=5, quality=5) -> list[dict]:
    """构造六因子分值列表"""
    scores = {"动量": momentum, "催化": catalyst, "估值": value,
              "主线契合": mainline, "资金面": capital, "基本面质量": quality}
    return [{"factor": n, "score": scores[n]} for n in FACTORS]


def _row(pct, momentum=5, catalyst=5, **kw) -> dict:
    """构造单条 track_verify 行（带 factor_scores + t5_pct）"""
    return {"t5_pct": pct, "factor_scores": _fs(momentum=momentum, catalyst=catalyst, **kw)}


# ==================== 1. compute_factor_correlation 纯函数 ====================

def test_compute_factor_correlation_basic():
    """basic：高/低分组统计正确"""
    from app.services import track_verify as tv
    rows = [
        _row(5.0, momentum=8), _row(-2.0, momentum=8), _row(3.0, momentum=8),   # 高分组 n=3
        _row(8.0, momentum=2), _row(6.0, momentum=2), _row(4.0, momentum=2),   # 低分组 n=3
    ]
    corr = tv.compute_factor_correlation(rows, period="t5")
    assert corr["n_total"] == 6 and corr["n_with_factors"] == 6
    f = corr["factors"]["动量"]
    assert f["high"]["n"] == 3 and f["high"]["win_rate"] == 66.7
    assert f["low"]["n"] == 3 and f["low"]["win_rate"] == 100.0
    assert f["win_rate_diff"] == -33.3


def test_compute_factor_correlation_effective():
    """高分组胜率 >> 低分组 → effective"""
    from app.services import track_verify as tv
    rows = [
        _row(5.0, momentum=8), _row(6.0, momentum=8), _row(7.0, momentum=8),   # 高 100%
        _row(-5.0, momentum=2), _row(-6.0, momentum=2), _row(-7.0, momentum=2),  # 低 0%
    ]
    corr = tv.compute_factor_correlation(rows, period="t5")
    assert corr["factors"]["动量"]["status"] == "effective"
    assert corr["factors"]["动量"]["win_rate_diff"] > 10


def test_compute_factor_correlation_ineffective():
    """高分组胜率 << 低分组 → ineffective"""
    from app.services import track_verify as tv
    rows = [
        _row(-5.0, momentum=8), _row(-6.0, momentum=8), _row(-7.0, momentum=8),  # 高 0%
        _row(5.0, momentum=2), _row(6.0, momentum=2), _row(7.0, momentum=2),   # 低 100%
    ]
    corr = tv.compute_factor_correlation(rows, period="t5")
    assert corr["factors"]["动量"]["status"] == "ineffective"
    assert corr["factors"]["动量"]["win_rate_diff"] < -10


def test_compute_factor_correlation_neutral():
    """差值在 ±10pp 内 → neutral"""
    from app.services import track_verify as tv
    rows = [
        _row(3.0, momentum=8), _row(-1.0, momentum=8), _row(2.0, momentum=8),    # 高 66.7%
        _row(3.0, momentum=2), _row(-2.0, momentum=2), _row(1.0, momentum=2),   # 低 66.7%
    ]
    corr = tv.compute_factor_correlation(rows, period="t5")
    assert corr["factors"]["动量"]["status"] == "neutral"
    assert abs(corr["factors"]["动量"]["win_rate_diff"]) <= 10


def test_compute_factor_correlation_insufficient_sample():
    """某因子高分组 <3 → insufficient_sample"""
    from app.services import track_verify as tv
    rows = [
        _row(5.0, momentum=8), _row(4.0, momentum=8),                      # 高分组 n=2
        _row(3.0, momentum=2), _row(2.0, momentum=2), _row(1.0, momentum=2),  # 低分组 n=3
    ]
    corr = tv.compute_factor_correlation(rows, period="t5")
    assert corr["factors"]["动量"]["status"] == "insufficient_sample"
    assert corr["factors"]["动量"]["win_rate_diff"] is None


def test_compute_factor_correlation_no_factor_scores():
    """行无 factor_scores → 不参与计算，n_with_factors 不含该行"""
    from app.services import track_verify as tv
    rows = [_row(5.0, momentum=8), {"t5_pct": 3.0, "factor_scores": None},
            {"t5_pct": -1.0}]  # 无 factor_scores 键
    corr = tv.compute_factor_correlation(rows, period="t5")
    assert corr["n_total"] == 3 and corr["n_with_factors"] == 1


def test_compute_factor_correlation_null_pct():
    """factor_scores 有但 t5_pct=None → 不参与计算"""
    from app.services import track_verify as tv
    rows = [_row(5.0, momentum=8), _row(None, momentum=8), _row(None, momentum=2)]
    corr = tv.compute_factor_correlation(rows, period="t5")
    assert corr["n_with_factors"] == 1  # 仅第一条有效


# ==================== 2. _template_calibration_suggestions ====================

def _correlation_with(factor_status: dict) -> dict:
    """构造指定因子状态的 correlation dict"""
    factors = {}
    for name in FACTORS:
        st = factor_status.get(name, "neutral")
        if st == "insufficient_sample":
            factors[name] = {"status": st, "high": {"n": 1, "win_rate": 50.0, "avg_pct": 0.0},
                             "low": {"n": 1, "win_rate": 50.0, "avg_pct": 0.0},
                             "win_rate_diff": None, "avg_pct_diff": None}
        else:
            factors[name] = {"status": st,
                             "high": {"n": 3, "win_rate": 30.0 if st == "ineffective" else 70.0,
                                      "avg_pct": -2.0 if st == "ineffective" else 3.0},
                             "low": {"n": 3, "win_rate": 70.0 if st == "ineffective" else 30.0,
                                     "avg_pct": 3.0 if st == "ineffective" else -2.0},
                             "win_rate_diff": -40.0 if st == "ineffective" else 40.0,
                             "avg_pct_diff": -5.0 if st == "ineffective" else 5.0}
    return {"period": "t5", "n_total": 10, "n_with_factors": 8, "factors": factors,
            "calibration_notes": []}


def test_template_calibration_ineffective():
    """构造 ineffective 因子 → 生成降权建议，rule_name 含因子名"""
    from app.services import track_verify as tv
    corr = _correlation_with({"动量": "ineffective"})
    sugg = tv._template_calibration_suggestions(corr)
    ri = [s for s in sugg if "因子权重校准建议" in s["rule_name"]]
    assert len(ri) == 1
    assert "动量" in ri[0]["rule_name"]
    assert ri[0]["target_agent"] == "score"
    assert ri[0]["priority"] == "high"
    assert "降低该因子权重" in ri[0]["suggested_value"]


def test_template_calibration_multi_failure():
    """≥3 个因子失效 → 生成整体复核建议"""
    from app.services import track_verify as tv
    corr = _correlation_with({"动量": "ineffective", "催化": "ineffective",
                              "估值": "ineffective"})
    sugg = tv._template_calibration_suggestions(corr)
    overall = [s for s in sugg if "整体复核" in s["rule_name"]]
    assert len(overall) == 1
    assert "3个因子" in overall[0]["rule_name"]


def test_template_calibration_no_failure():
    """全部 effective/neutral → 不生成任何建议"""
    from app.services import track_verify as tv
    corr = _correlation_with({})
    sugg = tv._template_calibration_suggestions(corr)
    assert sugg == []


# ==================== 3. get_score_factors ====================

def test_get_score_factors_new_format():
    """detail 含 factors 列表 → 正确提取 [{factor, score}]"""
    detail = {"factors": _fs(momentum=8, catalyst=7), "final_advice": "综合评估"}
    repo.upsert_score("600001", "测试甲", "2026-08-10", 78.0, "B", detail, [])
    factors = repo.get_score_factors("600001", "2026-08-10")
    assert factors is not None and len(factors) == 6
    by_name = {f["factor"]: f["score"] for f in factors}
    assert by_name["动量"] == 8 and by_name["催化"] == 7


def test_get_score_factors_old_format():
    """detail 是旧维度字典（无 factors）→ 返回 None"""
    detail = {"技术趋势": {"score": 85, "verdict": "支持"}, "final_advice": "综合评估"}
    repo.upsert_score("600002", "测试乙", "2026-08-10", 80.0, "A", detail, [])
    assert repo.get_score_factors("600002", "2026-08-10") is None


def test_get_score_factors_no_score():
    """无评分记录 → 返回 None"""
    assert repo.get_score_factors("999999", "2026-08-10") is None


def test_get_score_factors_fallback_recent():
    """当日无评分 → 回退最近一条过去评分"""
    repo.upsert_score("600003", "测试丙", "2026-08-05", 70.0, "B",
                      {"factors": _fs(momentum=6)}, [])
    factors = repo.get_score_factors("600003", "2026-08-10")
    assert factors is not None and len(factors) == 6


# ==================== 4. backfill_factor_scores ====================

def _seed_track(code, date, factor_scores=None):
    rid = repo.upsert_track_verify(code, f"测试{code}", date, "A", 10.0,
                                   factor_scores=factor_scores)
    cache.delete_prefix("dbq:track_verify:")
    return rid


def test_backfill_factor_scores_idempotent():
    """已有 factor_scores 的行跳过；无评分行 no_score；有评分行填充"""
    from app.services import track_verify as tv
    # 行1：已有 factor_scores → skipped
    _seed_track("600010", "2026-08-01", factor_scores=_fs())
    # 行2：无评分记录 → no_score
    _seed_track("600011", "2026-08-01", factor_scores=None)
    # 行3：有评分记录（factors）→ filled
    _seed_track("600012", "2026-08-01", factor_scores=None)
    repo.upsert_score("600012", "测试600012", "2026-08-01", 70.0, "B",
                      {"factors": _fs(momentum=8)}, [])
    cache.delete_prefix("dbq:track_verify:")

    result = tv.backfill_factor_scores()
    assert result["skipped"] == 1
    assert result["no_score"] == 1
    assert result["filled"] == 1
    # 幂等：再跑一次无新填充
    result2 = tv.backfill_factor_scores()
    assert result2["filled"] == 0


def test_upsert_update_track_verify_factor_scores_persist():
    """upsert 创建时写 factor_scores；update 可回填"""
    rid = _seed_track("600013", "2026-08-01", factor_scores=_fs(momentum=9))
    repo.update_track_verify(rid, factor_scores=_fs(momentum=7))
    cache.delete_prefix("dbq:track_verify:")
    rows = repo.list_track_verify(limit=10)
    row = [r for r in rows if r["id"] == rid][0]
    by_name = {f["factor"]: f["score"] for f in row["factor_scores"]}
    assert by_name["动量"] == 7


# ==================== 5. get_factor_calibration / _format_calibration_text ====================

def test_format_calibration_text_empty():
    """n_with_factors < 3 → 返回空字符串"""
    from app.services import track_verify as tv
    corr = {"period": "t5", "n_with_factors": 2, "factors": {}, "calibration_notes": []}
    assert tv._format_calibration_text(corr) == ""


def test_format_calibration_text_with_data():
    """有数据 → 文本含各因子高/低分组胜率"""
    from app.services import track_verify as tv
    corr = _correlation_with({"动量": "effective", "催化": "neutral"})
    text = tv._format_calibration_text(corr)
    assert "因子校准相关性" in text
    assert "动量" in text and "高分组" in text and "低分组" in text
    assert "有效" in text and "无显著差异" in text
    assert "此为参考信息" in text


def test_get_factor_calibration_cached():
    """缓存生效：首次生成后命中缓存"""
    from app.services import track_verify as tv
    for i in range(6):
        rid = _seed_track(f"60002{i}", "2026-08-01",
                          factor_scores=_fs(momentum=8 if i < 3 else 2))
        repo.update_track_verify(rid, t5_pct=5.0 if i < 3 else -3.0)
    cache.delete_prefix("dbq:track_verify:")
    cache.delete("factor:calibration:t5")
    text1 = tv.get_factor_calibration("t5")
    assert text1  # 有因子分且有 T+5 数据 → 非空
    assert cache.get("factor:calibration:t5") == text1
    assert tv.get_factor_calibration("t5") == text1  # 命中缓存返回相同文本


def test_get_factor_calibration_empty_no_data():
    """无数据 → 返回空字符串不报错"""
    from app.services import track_verify as tv
    cache.delete("factor:calibration:t5")
    assert tv.get_factor_calibration("t5") == ""


# ==================== 6. build_user_prompt factor_calibration 参数 ====================

def test_build_user_prompt_factor_calibration_param():
    """build_user_prompt 新增 factor_calibration 参数：有值注入，无值不注入"""
    from agent_prompts import score_prompt
    p1 = score_prompt.build_user_prompt("data", "pref")
    assert "因子校准相关性参考" not in p1
    p2 = score_prompt.build_user_prompt("data", "pref",
                                        factor_calibration="因子校准相关性（3 个样本）")
    assert "因子校准相关性参考" in p2
    assert "因子校准相关性（3 个样本）" in p2
