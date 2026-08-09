"""手动触发龙虎榜拉取（游资维度数据链）：拉取指定日期龙虎榜并落库
用法: .venv/Scripts/python backend/scripts/fetch_dragon_tiger.py [YYYY-MM-DD]
不传日期默认取最近一个交易日（T+1 语义：抓前一日）。
"""
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))
sys.path.insert(0, str(_BACKEND_DIR.parent))
os.environ.setdefault("APP_ENV", "dev")

from app.core.config import settings  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.db import repo  # noqa: E402


def _last_trade_date() -> str:
    """最近交易日（日历为全量静态历（1990~年末），取今天之前的最后一个交易日；失败回退工作日）"""
    today = date.today().strftime("%Y-%m-%d")
    try:
        from app.datasource.akshare_source import AkshareSource
        cal = AkshareSource().fetch_trade_calendar()
        past = [d for d in (cal or []) if d < today]
        if past:
            return past[-1]
    except Exception:  # noqa: BLE001
        pass
    return (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")


def main() -> int:
    init_db()
    repo.seed_default_hot_money_profiles()
    target = sys.argv[1] if len(sys.argv) > 1 else _last_trade_date()
    if not settings.dragon_tiger_enable:
        print(f"⚠️  DRAGON_TIGER_ENABLE=false（.env 未开启），抓取方法将返回空。"
              f"如需启用请在 .env 设置 DRAGON_TIGER_ENABLE=true 后重试。")
    from app.datasource.dragon_tiger_source import (fetch_dragon_tiger,
                                                    second_source_status)

    print(f"拉取龙虎榜: {target} ...")
    seats = fetch_dragon_tiger(target)
    ss = second_source_status()
    if not ss.get("available"):
        print(f"[注意] {ss.get('annotation')}（K227：单源数据标'置信度不足'仅参考，"
              f"不伪造第二源数据；第二源接入后自动升级多源采信）")
    rows = repo.list_lhb_flows(trade_date=target)
    print(f"完成: 席位级 {len(seats)} 条，落库流水 {len(rows)} 条（{target}）")
    fp = repo.hot_money_fingerprint()
    print(f"游资数据指纹: {fp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
