"""真实调用候选因子 Agent，落库 pending 候选供人工拍板。"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.db.session import init_db  # noqa: E402
from app.services import factor_candidate  # noqa: E402


def main(context: str = "", limit: int = 5) -> list[dict]:
    """调用真实 LLM 并只生成 pending 候选。"""
    init_db()
    return factor_candidate.propose(context, limit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", default="")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(main(args.context, args.limit), ensure_ascii=False, default=str, indent=2))
