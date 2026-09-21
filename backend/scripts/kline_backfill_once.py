"""本地日线仓库 · 一次性全市场历史回补（批1.5）

用法:
  python backend/scripts/kline_backfill_once.py [--limit N] [--batch 200] [--rebuild]

- 可中断续跑：已足 250 根的票自动跳过（断点状态 = 本地库自身，不依赖进度文件）。
- 必须离线窗口跑（5564 只 × ~7s/只 ≈ 数小时）；跑完 16:50 扫描即全程只读本地库。
- 只写本地 SQLite（data/kline.db，KLINE_DB_PATH 可覆盖）；不动云端主库。
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from app.services import kline_backfill, kline_store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="本地日线仓库历史回补")
    parser.add_argument("--limit", type=int, default=0, help="只回补前 N 只（0=全市场）")
    parser.add_argument("--batch", type=int, default=kline_backfill.BATCH_SIZE)
    parser.add_argument("--rebuild", action="store_true", help="先删后拉（除权重置）")
    parser.add_argument("--codes", default="", help="逗号分隔指定代码（优先于股票池）")
    args = parser.parse_args()

    from app.datasource.fallback import get_datasource
    names: dict = {}
    spot = get_datasource().fetch_spot_universe()
    if spot is not None and not spot.empty and "name" in spot.columns:
        names = {str(r["code"]): str(r.get("name") or "") for r in spot.to_dict("records")}
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    if not codes:
        if spot is None or spot.empty:
            print("股票池为空（非交易日或数据源故障）→ 请用 --codes 指定，或交易日盘后重跑")
            return 2
        codes = [str(c) for c in spot["code"].tolist()]
    if args.limit:
        codes = codes[:args.limit]

    print("开始回补 codes=%d batch=%d rebuild=%s db=%s" % (len(codes), args.batch, args.rebuild, kline_store.db_path()))
    started = time.time()
    summary = kline_backfill.backfill(codes, batch_size=args.batch, rebuild=args.rebuild,
                                      names=names,
                                      on_progress=lambda done, total, s: print(
                                          "  进度 %d/%d ok=%d failed=%d bars=%d" %
                                          (done, total, s["ok"], s["failed"], s["written_bars"])))
    print("回补结束:", summary)
    print("仓库概览:", kline_store.stats())
    print("wall=%.0fs" % (time.time() - started))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
