"""把 factor_ic.persist_history 的落盘兜底文件补交进 factor_ic_history。

用法：
    python backend/scripts/persist_factor_ic_fallback.py [兜底JSON路径]
不传路径时取 data 目录下最新的 factor_ic_persist_fallback_*.json。
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.services import factor_ic  # noqa: E402


def latest_fallback() -> Path:
    """取兜底目录下按文件名（时间戳）最新的一个"""
    target = Path(factor_ic.PERSIST_FALLBACK_DIR or factor_ic.settings.data_dir)
    candidates = sorted(target.glob("factor_ic_persist_fallback_*.json"))
    if not candidates:
        raise SystemExit("未找到兜底文件：%s/factor_ic_persist_fallback_*.json" % target)
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="补交因子 IC 落盘兜底批次")
    parser.add_argument("path", nargs="?", help="兜底 JSON 路径；缺省取 data 目录下最新一个")
    args = parser.parse_args()
    path = Path(args.path) if args.path else latest_fallback()
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") or []
    written = factor_ic.persist_history(rows)
    print("补交完成：%d 行（来源 %s）" % (written, path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
