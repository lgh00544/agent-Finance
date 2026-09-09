"""只读候选历史规则分析。

仅 SELECT StockCandidate/CandidateTrackVerify；不调用网络、不写数据库、不读取 LLM。
用候选入选时 snapshot/detail 与随后已落库 T+N 结果做分组统计，避免使用后见评分理由。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.db.models import CandidateTrackVerify, StockCandidate  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def _num(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _stat(rows, horizon):
    vals = [_num(r.get(horizon)) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0, "wins": 0, "win_rate": None, "avg_pct": None, "median_pct": None}
    return {"n": len(vals), "wins": sum(v > 0 for v in vals),
            "win_rate": round(sum(v > 0 for v in vals) / len(vals) * 100, 1),
            "avg_pct": round(statistics.mean(vals), 2),
            "median_pct": round(statistics.median(vals), 2)}


def _bucket(value, edges):
    if value is None:
        return "缺失"
    for label, low, high in edges:
        if low <= value < high:
            return label
    return edges[-1][0] if value >= edges[-1][2] else edges[0][0]


def _feature(candidate):
    snap = candidate.snapshot or {}
    detail = candidate.detail or {}
    enrich = detail.get("enriched") or {}
    risks = " ".join(str(x) for x in (detail.get("risks") or []))
    return {
        "stock_code": candidate.stock_code, "select_date": candidate.trade_date,
        "confidence_tier": detail.get("confidence_tier", ""),
        "change_pct": _num(snap.get("change_pct")),
        "volume_ratio": _num(snap.get("volume_ratio")),
        "turnover_rate": _num(snap.get("turnover_rate")),
        "pct_change_5d": _num(enrich.get("pct_change_5d")),
        "dist_52w_high_pct": _num(enrich.get("dist_52w_high_pct")),
        "pos_52w": _num(enrich.get("pos_52w")),
        "ma20_pos_pct": _num(enrich.get("ma20_pos_pct")),
        "ma60_pos_pct": _num(enrich.get("ma60_pos_pct")),
        "vol_5_20": _num(enrich.get("vol_5_20")),
        "intraday_narrow_pct": _num(enrich.get("intraday_narrow_pct")),
        "main_net_5d": _num(enrich.get("main_net_5d")),
        "industry": enrich.get("industry") or "缺失",
        "stock_type": detail.get("stock_type") or "缺失",
        "risk_text": risks,
    }


def _join():
    with SessionLocal() as db:
        candidates = db.execute(select(StockCandidate)).scalars().all()
        tracks = db.execute(select(CandidateTrackVerify)).scalars().all()
    by_key = {(c.stock_code, c.trade_date): c for c in candidates}
    rows = []
    # 以追踪表为主表：候选快照被日快照替换/清理后仍保留历史收益，字段缺失必须显式标记。
    for t in tracks:
        c = by_key.get((t.stock_code, t.select_date))
        f = _feature(c) if c is not None else {
            "stock_code": t.stock_code, "select_date": t.select_date,
            "confidence_tier": "缺失", "risk_text": "",
            **{k: None for k in ("change_pct", "volume_ratio", "turnover_rate",
                                  "pct_change_5d", "dist_52w_high_pct", "pos_52w",
                                  "ma20_pos_pct", "ma60_pos_pct", "vol_5_20",
                                  "intraday_narrow_pct", "main_net_5d")},
            "industry": "缺失", "stock_type": "缺失",
        }
        f.update({"t3_pct": t.t3_pct, "t5_pct": t.t5_pct, "t10_pct": t.t10_pct,
                  "select_rating": t.select_rating or "未知"})
        rows.append(f)
    return rows


FEATURES = {
    "confidence_tier": None,
    "change_pct": [("<-3", float("-inf"), -3), ("-3~0", -3, 0), ("0~3", 0, 3),
                    ("3~6", 3, 6), (">=6", 6, float("inf"))],
    "volume_ratio": [("<0.8", float("-inf"), .8), ("0.8~1.2", .8, 1.2),
                      ("1.2~2", 1.2, 2), (">=2", 2, float("inf"))],
    "turnover_rate": [("<3", float("-inf"), 3), ("3~8", 3, 8), ("8~12", 8, 12),
                       (">=12", 12, float("inf"))],
    "pct_change_5d": [("<0", float("-inf"), 0), ("0~5", 0, 5), ("5~15", 5, 15),
                       ("15~30", 15, 30), (">=30", 30, float("inf"))],
    "vol_5_20": [("<0.8", float("-inf"), .8), ("0.8~1.2", .8, 1.2),
                  ("1.2~1.5", 1.2, 1.5), (">=1.5", 1.5, float("inf"))],
    "intraday_narrow_pct": [("<0.5", float("-inf"), .5), ("0.5~1", .5, 1),
                             ("1~2", 1, 2), (">=2", 2, float("inf"))],
    "main_net_5d": [("<0", float("-inf"), 0), ("0~1亿", 0, 1e8),
                    ("1~5亿", 1e8, 5e8), (">=5亿", 5e8, float("inf"))],
    "risk_keyword": None,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="可选 Markdown 输出路径")
    args = parser.parse_args()
    rows = _join()
    if not rows:
        print("无候选追踪交集")
        return 0
    rows.sort(key=lambda r: r["select_date"])
    split = rows[len(rows) // 2]["select_date"]
    periods = {"早期": [r for r in rows if r["select_date"] < split],
               "后期": [r for r in rows if r["select_date"] >= split],
               "全期": rows}
    lines = ["# 候选历史规则只读分析", "", f"样本：候选与追踪交集 {len(rows)}；时间分界 {split}；仅使用入选快照/detail 与已落库 T+N。", ""]
    for period, subset in periods.items():
        lines.append(f"## {period}（{len(subset)}）")
        for horizon in ("t3_pct", "t5_pct", "t10_pct"):
            lines.append(f"- {horizon}: {json.dumps(_stat(subset, horizon), ensure_ascii=False)}")
        for name, edges in FEATURES.items():
            groups = defaultdict(list)
            for r in subset:
                if name == "confidence_tier":
                    key = r.get(name) or "缺失"
                elif name == "risk_keyword":
                    text = r.get("risk_text", "")
                    key = "有风险文字" if text and text not in ("无", "无重大风险") else "无/缺失"
                else:
                    key = _bucket(r.get(name), edges)
                groups[key].append(r)
            lines.append(f"### {name}")
            for key in sorted(groups):
                lines.append(f"- {key}: n={len(groups[key])}, "
                             f"T5={json.dumps(_stat(groups[key], 't5_pct'), ensure_ascii=False)}")
        lines.append("")
    text = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
