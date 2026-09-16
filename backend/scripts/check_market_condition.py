"""读取最新 MarketCondition 与当前激活的固定权重。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.db import repo  # noqa: E402
from app.services.market_condition_aware_weight import resolve_weights  # noqa: E402


def main() -> dict:
    """读取已落库市况，不重新触发 Agent。"""
    condition = repo.get_latest_market_condition()
    weights, reason = resolve_weights(condition)
    return {"market_condition": condition, "weights": weights, "reason": reason or None}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, default=str, indent=2))
