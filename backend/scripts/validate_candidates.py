"""用真实行情构造最近 24 个月样本并验证 pending 候选。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.datasource.fallback import get_datasource  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.services import factor_candidate, factor_ic  # noqa: E402


def _month_ends(source) -> list[str]:
    calendar = source.fetch_trade_calendar()
    return factor_ic._month_ends(calendar, 24)


def main(candidate_ids: list[str] | None = None) -> list[dict]:
    """读取真实行情并写入候选验证结果；缺失因子值明确返回原因。"""
    init_db()
    source = get_datasource()
    ends = _month_ends(source)
    universe = source.fetch_spot_universe()
    codes = universe["code"].astype(str).str.zfill(6).tolist() if "code" in universe else []
    records = factor_ic.collect_month_records(source, ends, codes)
    pending = factor_candidate.get_pending_for_sir()
    wanted = set(candidate_ids or [row["candidate_id"] for row in pending])
    output = []
    for row in pending:
        if row["candidate_id"] not in wanted:
            continue
        result = factor_candidate.validate(row["candidate_id"], records)
        if result.get("mean_ic") is None:
            result["reason"] = "候选公式未注册为可计算因子，IC=None；需人工实现并复核后再启用"
        output.append(result)
    return output


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, default=str, indent=2))
