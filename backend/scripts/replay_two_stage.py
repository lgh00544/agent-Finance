"""两段式评分粗筛回放验证脚本（临时工具，不进调度）

用途：回放最近 N 个交易日的候选池历史数据，对比「全量 DEEP 精打」与「两段式粗筛」：
- 全量 DEEP 结果直接读取库存 stock_score（历史打分已落库，不再重复打 DEEP）；
- 两段式粗筛：对每交易日候选执行 score.prefilter_candidates（LIGHT 低成本调用）；
- 误杀率 = 被粗筛淘汰、但全量 DEEP 总分 ≥ 及格线（0.6×100=60 分，0-100 制）的候选占比；
- 误杀率 < 5% 才允许把 SCORE_TWO_STAGE 置 True（人工决策，脚本只出数字）。

用法：python backend/scripts/replay_two_stage.py [--days 10] [--pass 60]
"""
import argparse
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND.parent))

from app.db import repo  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402

# 候选输入字段（与 score._compact_prefilter_row 对齐；DB 缺失字段自动省略，不编造）
_COMPACT_KEYS = [
    ("confidence_tier", "confidence_tier"), ("focus_type", "focus_type"),
    ("stock_type", "stock_type"), ("change_pct", "change_pct"),
    ("reason", "reason"),
]


def _load_candidates_by_day(days: list[str]) -> dict[str, list[dict]]:
    """按交易日加载候选，构造 compact 候选 dict（来自快照/detail，不新拉数据）"""
    init_db()
    out: dict[str, list[dict]] = {}
    for day in days:
        rows = (repo.list_candidates(date=day, limit=200) or [])
        cands = []
        for c in rows:
            snaps = c.get("snapshot") or {}
            detail = c.get("detail") or {}
            reasons = c.get("reasons") or []
            if isinstance(reasons, str):
                try:
                    reasons = json.loads(reasons)
                except Exception:
                    reasons = [reasons]
            cand = {
                "stock_code": c.get("stock_code"), "stock_name": c.get("stock_name") or "",
                "reason": "；".join(str(r) for r in reasons)[:200],
                "change_pct": snaps.get("change_pct"),
                "market_cap": (detail.get("enriched") or {}).get("market_cap"),
                "industry": (detail.get("enriched") or {}).get("industry"),
                "stock_type": detail.get("stock_type"),
                "confidence_tier": detail.get("confidence_tier"),
                "focus_type": detail.get("focus_type"),
            }
            cands.append(cand)
        out[day] = cands
    return dict(sorted(out.items(), reverse=True))


def _full_score_map(day: str) -> dict[str, float]:
    """该交易日库存的全量 DEEP 打分（0-100），code → score"""
    init_db()
    with SessionLocal() as db:
        from sqlalchemy import select
        from app.db.models import StockScore
        rows = db.execute(select(StockScore).where(
            StockScore.trade_date == day)).scalars().all()
        return {r.stock_code: float(r.score) for r in rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="两段式粗筛回放验证")
    parser.add_argument("--days", type=int, default=10, help="回放最近 N 个交易日（默认 10）")
    parser.add_argument("--pass", dest="pass_line", type=float, default=60.0,
                        help="及格线（0-100 制，DEEP 总分>=此值判定为好票；文档 0.6 换算为 60）")
    args = parser.parse_args()

    from app.agents import score as score_mod

    days = repo.list_candidate_dates(limit=args.days)
    by_day = _load_candidates_by_day(days)
    if not days:
        print("[ERROR] 库中无候选历史数据")
        return 2

    total_cand = 0
    total_kept = 0
    total_killed_bad = 0  # 被淘汰且是好票（误杀）
    print(f"{'交易日':<12}{'候选':>5}{'保留':>5}{'淘汰':>5}{'误杀':>5}"
          + f"{'误杀率':>8}  全量DEEP调用")
    print("-" * 60)
    for i, day in enumerate(days, 1):
        cands = by_day[day]
        score_map = _full_score_map(day)
        # 两段式粗筛（真实 LIGHT 调用）
        try:
            kept = score_mod.prefilter_candidates(cands, day)
        except Exception as exc:  # noqa: BLE001 该日粗筛失败：保守视为全保留
            print(f"[WARN] {day} 粗筛失败（{exc}），该日按全量保留处理")
            kept = cands
        kept_codes = {c.get("stock_code") for c in kept if c}
        eliminated = [c for c in cands if c.get("stock_code") not in kept_codes]
        # 误杀：被淘汰但全量 DEEP 总分 >= 及格线（0-100 制）
        killed_good = [c for c in eliminated
                       if score_map.get(c.get("stock_code"), 0) >= args.pass_line]
        n = len(cands)
        k = len(kept_codes)
        e = len(eliminated)
        kg = len(killed_good)
        rate = kg / n if n else 0.0
        total_cand += n
        total_kept += k
        total_killed_bad += kg
        print(f"{day:<12}{n:>5}{k:>5}{e:>5}{kg:>5}{rate*100:>7.1f}%   {n} 次")
        # 明细（可选）：误杀名单
        for c in killed_good:
            print(f"    误杀: {c.get('stock_code')} {c.get('stock_name')} "
                  f"score={score_map.get(c.get('stock_code'))}")
    print("-" * 60)
    overall_rate = total_killed_bad / total_cand if total_cand else 0.0
    print(f"合计: {total_cand} 候选 / 保留 {total_kept} / 淘汰 {total_cand - total_kept}"
          f" / 误杀 {total_killed_bad}")
    print(f"整体误杀率 = {overall_rate*100:.2f}%  "
          + ("(<5%，可考虑开启 SCORE_TWO_STAGE)" if overall_rate < 0.05
             else "(≥5%，默认保持关闭，不建议开启)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
