"""建仓流水缺失一次性回填：遍历全部持仓（含 exited）调 ensure_opening_trade，打印汇总。

用法（backend 目录）: python scripts/backfill_opening_trades.py
幂等：补录 note='建仓补录'，同持仓已存在该 note 时跳过，可重复执行（二次运行 0 新增）。
K227：Σbuy 与 cost 对不上（Σbuy>cost / 股数未知 / cost 无效）→ 如实跳过并打印原因，不硬凑。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 项目根：agent_prompts/ 所在

from sqlalchemy import select  # noqa: E402

from app.db import repo  # noqa: E402
from app.db.models import Holding  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main() -> None:
    with SessionLocal() as db:
        holdings = list(db.execute(select(Holding).order_by(Holding.id)).scalars().all())
    applied: list[tuple[int, str, int, float, float]] = []
    for h in holdings:
        r = repo.ensure_opening_trade(h)
        if r["applied"]:
            applied.append((h.id, h.stock_code, r["shares"], r["price"], r["amount"]))
        else:
            print(f"  hold#{h.id} {h.stock_code}: 跳过 [{r['reason']}]")
    print(f"回填完成: 补录 {len(applied)} 只")
    for h_id, code, shares, price, amount in applied:
        print(f"  hold#{h_id} {code}: 补录 {shares}股@{price} = RMB{amount}（note=建仓补录）")


if __name__ == "__main__":
    main()
