"""预测性选股 2.5：前瞻回填闭环（ForwardViewHistory 落库 / T+5 回填 bucket / 准确率校准）"""
import pytest
from sqlalchemy import select, text

from app.cache import cache
from app.db import repo
from app.db.models import ForwardViewHistory
from app.db.session import SessionLocal, init_db
from app.services import forward_view_history as fvh


@pytest.fixture(autouse=True)
def _db_and_cache():
    init_db()
    yield
    cache.delete_prefix("forward:calibration:")
    cache.delete_prefix("forward_view:")
    # 测试间隔离：清空本模块写入的表（共享会话 DB，防残留污染后续统计）
    with SessionLocal() as db:
        db.execute(text("DELETE FROM forward_view_history"))
        db.execute(text("DELETE FROM candidate_track_verify"))
        db.commit()


def _fwd_row(code: str, trade_date: str) -> ForwardViewHistory | None:
    with SessionLocal() as db:
        return db.execute(
            select(ForwardViewHistory).where(
                ForwardViewHistory.stock_code == code,
                ForwardViewHistory.trade_date == trade_date)
        ).scalar_one_or_none()


def _fwd_count() -> int:
    with SessionLocal() as db:
        return len(db.execute(select(ForwardViewHistory)).scalars().all())


# ================= 落库 =================

def test_forward_view_table_created():
    """init_db 幂等建 forward_view_history 表（无手写 DDL）"""
    init_db()
    with SessionLocal() as db:
        has = db.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='forward_view_history'"
        )).scalar()
    assert has == "forward_view_history"


def test_save_forward_view_persists():
    """延续+高 → forward_view=强 落库；signals 存触发事实"""
    ok = fvh.save_forward_view("600001", "2026-08-10", "延续", "高", {"position": "位置强"})
    assert ok is True
    row = _fwd_row("600001", "2026-08-10")
    assert row is not None
    assert row.forward_view == "强"
    assert row.forward_signals.get("position") == "位置强"


def test_save_forward_view_missing_data_skipped():
    """clarity=低 → missing_data 跳过（诚实不落库）"""
    ok = fvh.save_forward_view("600002", "2026-08-10", "延续", "低")
    assert ok is False
    assert _fwd_row("600002", "2026-08-10") is None


def test_save_forward_view_unknown_bias_skipped():
    """未知 bias → 跳过"""
    assert fvh.save_forward_view("600003", "2026-08-10", "观望", "高") is False
    assert _fwd_row("600003", "2026-08-10") is None


def test_save_forward_view_idempotent():
    """同 code+date 重复保存 → 更新不重复插（唯一约束）"""
    fvh.save_forward_view("600004", "2026-08-10", "延续", "高", {"v": 1})
    fvh.save_forward_view("600004", "2026-08-10", "回吐", "中", {"v": 2})
    assert _fwd_count() == 1
    row = _fwd_row("600004", "2026-08-10")
    assert row.forward_view == "弱"  # 回吐 → 弱（更新覆盖）
    assert row.forward_signals.get("v") == 2


# ================= 回填 =================

def _seed_track(code: str, date: str, t5: float | None) -> int:
    rid = repo.upsert_track_verify(code, "测试股", date, "A", 10.0)
    if t5 is not None:
        repo.update_track_verify(rid, t5_pct=t5)
    return rid


def test_fill_forward_view_actual_buckets():
    """回填 bucket：强+正→correct；弱+>3→wrong；无追踪行→诚实留空"""
    for code, view in [("610001", "强"), ("610002", "弱"), ("610003", "强")]:
        repo.upsert_forward_view(code, "2026-08-10", view, {})
    _seed_track("610001", "2026-08-10", 5.0)   # 强 + 5 > 0 → correct
    _seed_track("610002", "2026-08-10", 8.0)   # 弱 + 8 > 3 → wrong
    # 610003 无追踪行 → 留空

    res = fvh.fill_forward_view_actual()
    assert res["filled"] == 2
    r1 = _fwd_row("610001", "2026-08-10")
    assert r1.t5_pct_actual == 5.0 and r1.accuracy_bucket == "correct"
    r2 = _fwd_row("610002", "2026-08-10")
    assert r2.t5_pct_actual == 8.0 and r2.accuracy_bucket == "wrong"
    r3 = _fwd_row("610003", "2026-08-10")
    assert r3.t5_pct_actual is None and r3.accuracy_bucket is None  # 诚实留空


def test_fill_forward_view_actual_neutral():
    """强 + actual∈(-3,0) → neutral（涨幅不足 3% 不判 wrong）"""
    repo.upsert_forward_view("610004", "2026-08-10", "强", {})
    _seed_track("610004", "2026-08-10", -2.0)
    fvh.fill_forward_view_actual()
    assert _fwd_row("610004", "2026-08-10").accuracy_bucket == "neutral"


# ================= 校准准确率 =================

def test_compute_forward_view_accuracy():
    """近 30 日样本：强 3correct+1wrong → 75%；弱 1correct+2neutral → 100%（neutral 不进分母）"""
    buckets = [("620001", "强", "correct"), ("620002", "强", "correct"), ("620003", "强", "correct"),
               ("620004", "强", "wrong"), ("620005", "弱", "correct"),
               ("620006", "弱", "neutral"), ("620007", "弱", "neutral")]
    for code, view, bucket in buckets:
        rid = repo.upsert_forward_view(code, "2026-08-20", view, {})
        repo.update_forward_view_actual(rid, 1.0 if bucket == "correct" else 5.0, bucket)
    stats = fvh.compute_recent_forward_view_accuracy(lookback_days=30)
    assert stats["strong_n"] == 4 and stats["strong"] == 0.75
    assert stats["weak_n"] == 1 and stats["weak"] == 1.0
    assert stats["neutral_n"] == 2
    assert stats["total"] == 7


def test_compute_forward_view_accuracy_no_samples():
    """无已回填样本 → 诚实 0 + n=0（不编造）"""
    stats = fvh.compute_recent_forward_view_accuracy(lookback_days=30)
    assert stats["strong_n"] == 0 and stats["strong"] == 0.0
    assert stats["weak_n"] == 0 and stats["weak"] == 0.0


# ================= score_prompt 注入文本 =================

def test_get_forward_calibration_text_no_samples():
    """缺样本 → 「样本不足」不编造"""
    assert "样本不足" in fvh.get_forward_calibration_text(lookback_days=30)


def test_get_forward_calibration_text_with_data():
    """有样本 → 文本含 前瞻强/弱 准确率与样本数"""
    rid = repo.upsert_forward_view("630001", "2026-08-20", "强", {})
    repo.update_forward_view_actual(rid, 5.0, "correct")
    text_val = fvh.get_forward_calibration_text(lookback_days=30)
    assert "前瞻强 准确率 100%" in text_val and "（1 样本）" in text_val


# ================= score_prompt 注入 =================

def test_score_prompt_forward_section_injects():
    """score_prompt.build_user_prompt 注入前瞻先验段：缺样本显「样本不足」，有样本显准确率"""
    from agent_prompts import score_prompt
    out_empty = score_prompt.build_user_prompt('{"k": 1}', '')
    assert "前瞻先验校准" in out_empty and "样本不足" in out_empty  # 缺样本不编造
    rid = repo.upsert_forward_view("650001", "2026-08-20", "强", {})
    repo.update_forward_view_actual(rid, 5.0, "correct")
    cache.delete("forward:calibration:30")  # 清 TTL 缓存使统计重算（否则读到上一步缓存）
    out_full = score_prompt.build_user_prompt('{"k": 1}', '')
    assert "前瞻强 准确率 100%" in out_full and "（1 样本）" in out_full


# ================= 衔接点：build_horizon_context 同步落库 =================

def test_build_horizon_context_saves_forward_view():
    """build_horizon_context 同步落库：延续+高→强；回吐+中→弱；clarity=低→跳过"""
    from app.services.track_verify import build_horizon_context
    shortlist = [
        {"stock_code": "640001", "stock_name": "强股", "horizon_bias": "延续", "horizon_clarity": "高", "horizon_note": "延续明显"},
        {"stock_code": "640002", "stock_name": "弱股", "horizon_bias": "回吐", "horizon_clarity": "中", "horizon_note": "冲高回吐"},
        {"stock_code": "640003", "stock_name": "缺数据", "horizon_bias": "延续", "horizon_clarity": "低", "horizon_note": "缺列"},
    ]
    text_val = build_horizon_context(shortlist, {}, trade_date="2026-08-10")
    assert "【前瞻对照】640001" in text_val  # 文本段照常
    assert _fwd_row("640001", "2026-08-10").forward_view == "强"
    assert _fwd_row("640002", "2026-08-10").forward_view == "弱"
    assert _fwd_row("640003", "2026-08-10") is None  # missing_data 跳过
