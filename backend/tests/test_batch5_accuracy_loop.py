"""批次5：准确率闭环增强（dev SQLite，不触网）：
#2 扩展评级倒挂检测（A-C/B-C/A-B 两两对比，pair 语义"高<低"，desc 动态化，rule_name 带 pair 防去重）
#4 市况次日指数回填（models 加列 / upsert 防覆盖 / update 函数 / 回填幂等 / 缺数据跳过）
"""
import pandas as pd
import pytest
from sqlalchemy import delete, select

from app.cache import cache
from app.db import repo
from app.db.models import MarketCondition
from app.db.session import SessionLocal, init_db

DATE = "2026-08-13"


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _cleanup():
    cache.delete_prefix("dbq:")
    cache.delete("job:last_market_accuracy")
    with SessionLocal() as db:
        db.execute(delete(MarketCondition))
        db.commit()
    yield
    cache.delete_prefix("dbq:")
    cache.delete("job:last_market_accuracy")
    with SessionLocal() as db:
        db.execute(delete(MarketCondition))
        db.commit()


def _rating_stats(a_avg=None, b_avg=None, c_avg=None, a_n=5, b_n=5, c_n=5):
    """构造含 A/B/C 档统计的 stats dict（供 detect_anomalies）"""
    by_rating = {}
    for grade, avg in (("A", a_avg), ("B", b_avg), ("C", c_avg)):
        by_rating[grade] = {"n": {"A": a_n, "B": b_n, "C": c_n}[grade],
                            "avg_pct": avg, "win_rate": 50.0, "pl_ratio": 1.0,
                            "avg_max_dd": -3.0, "wins": 2}
    return {"period": "t5", "n": a_n + b_n + c_n, "wins": 3, "win_rate": 50.0,
            "avg_pct": 1.0, "pl_ratio": 1.0, "avg_max_dd": -3.0,
            "by_rating": by_rating, "by_date": {}}


# ==================== #2 扩展倒挂检测 ====================

def test_rating_inversion_ac_still_triggers():
    from app.services import track_verify as tv
    anoms = tv.detect_anomalies(_rating_stats(a_avg=5.0, c_avg=20.0))
    inv = [a for a in anoms if a["type"] == "rating_inversion"]
    assert len(inv) == 1
    assert inv[0]["data"]["pair"] == "A<C"


def test_rating_inversion_bc_triggers():
    """新增：B 档 avg < C 档 avg → B<C 倒挂"""
    from app.services import track_verify as tv
    anoms = tv.detect_anomalies(_rating_stats(a_avg=5.0, b_avg=3.0, c_avg=10.0))
    inv = [a for a in anoms if a["type"] == "rating_inversion"]
    pairs = {a["data"]["pair"] for a in inv}
    assert "B<C" in pairs


def test_rating_inversion_ab_triggers():
    from app.services import track_verify as tv
    anoms = tv.detect_anomalies(_rating_stats(a_avg=2.0, b_avg=5.0, c_avg=1.0))
    inv = [a for a in anoms if a["type"] == "rating_inversion"]
    pairs = {a["data"]["pair"] for a in inv}
    assert "A<B" in pairs


def test_rating_inversion_no_inverse_when_better():
    """高评级 avg > 低评级 avg → 不倒挂"""
    from app.services import track_verify as tv
    anoms = tv.detect_anomalies(_rating_stats(a_avg=20.0, b_avg=10.0, c_avg=5.0))
    inv = [a for a in anoms if a["type"] == "rating_inversion"]
    assert inv == []


def test_rating_inversion_small_sample_skipped():
    """单边样本<3 不触发"""
    from app.services import track_verify as tv
    anoms = tv.detect_anomalies(_rating_stats(a_avg=5.0, b_avg=2.0, c_avg=2.0, c_n=2))
    inv = [a for a in anoms if a["type"] == "rating_inversion"]
    assert all(a["data"]["pair"] != "B<C" for a in inv)


def test_rating_inversion_desc_dynamic_pairs():
    """多条倒挂：desc 随 pair 动态化，不含硬编码 A/C"""
    from app.services import track_verify as tv
    anoms = tv.detect_anomalies(_rating_stats(a_avg=1.0, b_avg=2.0, c_avg=12.0))
    inv = [a for a in anoms if a["type"] == "rating_inversion"]
    pairs = {a["data"]["pair"] for a in inv}
    assert pairs == {"A<B", "A<C", "B<C"}   # 三条都触发（1<2, 1<12, 2<12）
    for a in inv:
        p = a["data"]["pair"]                 # 形如 "A<C"：左侧=高评级(avg 更差)，右侧=低评级(avg 更好/倒挂成立)
        hi_side, lo_side = p.split("<")
        # desc 措辞应为"低评级档平均涨幅高于高评级档"（倒挂方向），且随 pair 动态
        assert f"{lo_side} 档平均涨幅高于 {hi_side} 档" in a["desc"]


def test_template_suggestions_pair_aware_rule_name_and_multi():
    """多条倒挂 → 产多条建议，rule_name 含 pair、互不误去重；文案 pair 感知"""
    from app.services import track_verify as tv
    anoms = tv.detect_anomalies(_rating_stats(a_avg=1.0, b_avg=2.0, c_avg=12.0))
    sugg = tv._template_suggestions(_rating_stats(a_avg=1.0, b_avg=2.0, c_avg=12.0), anoms)
    ri = [s for s in sugg if s["rule_name"].startswith("候选池评级正相关性校验")]
    assert len(ri) == 3
    names = {s["rule_name"] for s in ri}
    assert names == {"候选池评级正相关性校验（A<B 倒挂）",
                     "候选池评级正相关性校验（A<C 倒挂）",
                     "候选池评级正相关性校验（B<C 倒挂）"}
    # 文案 pair 感知，不含硬编码 A/C
    b_c = [s for s in ri if "B<C" in s["rule_name"]][0]
    assert "C 档平均" in b_c["suggested_value"] and "B 档" in b_c["suggested_value"]


# ==================== #4 市况次日指数回填 ====================

def test_market_condition_new_column_and_upsert_default():
    """新列存在；upsert 默认 None 不破坏既有调用"""
    repo.upsert_market_condition(DATE, 30, {}, 10, "s")
    with SessionLocal() as db:
        r = db.execute(select(MarketCondition).where(MarketCondition.trade_date == DATE)
                       ).scalar_one()
        assert r.next_day_index_pct is None


def test_update_market_condition_next_day_writes():
    repo.upsert_market_condition(DATE, 30, {}, 10, "s")
    repo.update_market_condition_next_day(DATE, 1.25)
    row = repo.get_latest_market_condition()
    assert row is not None
    with SessionLocal() as db:
        r = db.execute(select(MarketCondition).where(MarketCondition.trade_date == DATE)
                       ).scalar_one()
        assert r.next_day_index_pct == 1.25


def test_upsert_does_not_overwrite_backfilled():
    """防覆盖：upsert 二次写入（不传 next_day_index_pct）不抹掉已回填值"""
    repo.upsert_market_condition(DATE, 30, {}, 10, "s")
    repo.update_market_condition_next_day(DATE, 2.5)
    repo.upsert_market_condition(DATE, 32, {}, 10, "s2")   # 重跑 upsert，不传新字段
    with SessionLocal() as db:
        r = db.execute(select(MarketCondition).where(MarketCondition.trade_date == DATE)
                       ).scalar_one()
        assert r.next_day_index_pct == 2.5                 # 未被子覆盖
        assert r.total_score == 32                          # 其他字段正常更新


def test_backfill_computes_next_day_pct(monkeypatch):
    """回填：有下一交易日的行算对 pct"""
    from app.services import market_accuracy as ma
    repo.upsert_market_condition("2026-08-11", 30, {}, 10, "s1")
    repo.upsert_market_condition("2026-08-12", 28, {}, 10, "s2")

    class _Src:
        def fetch_index_daily(self, symbol, start, end):
            assert symbol == "sh000300"                     # P0：带交易所前缀
            return pd.DataFrame({"date": ["2026-08-11", "2026-08-12", "2026-08-13"],
                                 "close": [100.0, 110.0, 105.0]})
    monkeypatch.setattr(ma, "get_datasource", lambda: _Src())
    result = ma.fill_market_condition_next_day()
    assert "2026-08-11" in result["filled"]                 # (110/100-1)=10%
    assert "2026-08-12" in result["filled"]                 # (105/110-1)≈-4.55%
    with SessionLocal() as db:
        r1 = db.execute(select(MarketCondition).where(MarketCondition.trade_date == "2026-08-11")
                        ).scalar_one()
        r2 = db.execute(select(MarketCondition).where(MarketCondition.trade_date == "2026-08-12")
                        ).scalar_one()
    assert r1.next_day_index_pct == 10.00
    assert r2.next_day_index_pct == round((105/110 - 1) * 100, 2)


def test_backfill_idempotent_and_missing_skip(monkeypatch):
    """幂等：已填行跳过；缺下一交易日/数据缺失行跳过"""
    from app.services import market_accuracy as ma
    repo.upsert_market_condition("2026-08-10", 30, {}, 10, "s1")
    repo.upsert_market_condition("2026-08-11", 28, {}, 10, "s2")
    repo.upsert_market_condition("2026-08-12", 26, {}, 10, "s3")
    repo.update_market_condition_next_day("2026-08-10", 1.0)     # 已填

    class _Src:
        def fetch_index_daily(self, symbol, start, end):
            # 只有 08-12 一行（无下一交易日 → 08-11 无法回填；08-12 当日无 next）
            if start <= "2026-08-12":
                return pd.DataFrame({"date": ["2026-08-12"], "close": [100.0]})
            return pd.DataFrame(
                {"date": ["2026-08-10", "2026-08-11", "2026-08-12"], "close": [100.0, 102.0, 103.0]})
    monkeypatch.setattr(ma, "get_datasource", lambda: _Src())
    result = ma.fill_market_condition_next_day()
    # 08-10 已填 → 跳过（不在 filled/skipped）；08-11 缺下一交易日 → skipped
    assert "2026-08-10" not in result["filled"] and "2026-08-10" not in result["skipped"]
    with SessionLocal() as db:
        r10 = db.execute(select(MarketCondition).where(MarketCondition.trade_date == "2026-08-10")
                         ).scalar_one()
        assert r10.next_day_index_pct == 1.0    # 已填值未被改动


def test_backfill_today_row_skipped(monkeypatch):
    """当日行不参与回填（trade_date < 今日才查）"""
    from app.services import market_accuracy as ma
    repo.upsert_market_condition("2026-12-31", 30, {}, 10, "s_future")  # 未来日期模拟今日
    rows = ma.collect_unfilled_market_conditions()
    assert all(r["trade_date"] < ma._today() for r in rows)
