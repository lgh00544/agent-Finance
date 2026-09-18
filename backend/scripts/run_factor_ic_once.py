"""运行一次 36 个月真实因子 IC 回测并输出最新期摘要。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.db.session import init_db  # noqa: E402
from app.services import factor_ic  # noqa: E402


def main() -> dict:
    """执行回测、落库并返回最新期排名摘要。"""
    init_db()
    result = factor_ic.run_factor_ic_backtest_job(months=36)
    rows = factor_ic.list_history(limit=500)
    # 最新月可能因 20 日前瞻收益尚未走完而无样本，摘要须取「最近一个有样本的月」
    periods = sorted({row["period"] for row in rows if row["sample_size"]})
    latest = [row for row in rows if periods and row["period"] == periods[-1]]
    latest.sort(key=lambda row: (row["ic"] is None, -(row["ic"] or 0), row["factor_id"]))
    weak = [row["factor_id"] for row in latest if row["status"] == "deprecated_candidate"]
    return {
        "job": result, "period": periods[-1] if periods else None,
        "top3": latest[:3], "bottom3": latest[-3:], "weak": weak,
        "reason": None if latest else "未生成 IC 记录",
    }


if __name__ == "__main__":
    payload = main()
    print(json.dumps(payload, ensure_ascii=False, default=str, indent=2))
    # 取数异常时打印结构化结果（而非裸 traceback）并仍以 1 退出，供 cron 定位
    raise SystemExit(1 if payload["job"].get("error_kind") else 0)
