"""端到端冒烟测试：真实 akshare 数据 + 真实 DeepSeek 跑全链路
覆盖 5 个 Agent：discover → score → position → 模拟持仓+monitor → 卖出+review
验证：SQLite 各业务表数据落库且结构合法（结构来自 ORM，此处只验证行数与可达性）
用法: python backend/scripts/smoke_test.py [--skip-discover]
退出码: 0=全链路通过, 1=存在失败环节或未配置密钥
"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))
sys.path.insert(0, str(_BACKEND_DIR.parent))  # 项目根：agent_prompts/ 提示词包所在
os.environ.setdefault("APP_ENV", "dev")

from app.core.config import settings  # noqa: E402

TEST_CODE = "600519"   # 贵州茅台：流动性足、新闻多、指标稳定
TEST_NAME = "贵州茅台"


def _stage(name: str, fn) -> bool:
    t0 = time.time()
    try:
        fn()
        print(f"  [OK]   {name}（{time.time() - t0:.1f}s）")
        return True
    except Exception as exc:  # noqa: BLE001 冒烟测试逐环节判定
        print(f"  [FAIL] {name}: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-discover", action="store_true", help="跳过全市场挖掘（较慢）")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print("=" * 64)
    print("全链路冒烟测试：真实 akshare 数据 + 真实 DeepSeek")
    print("=" * 64)
    if not settings.deepseek_api_key:
        print("[FAIL] 未配置 DEEPSEEK_API_KEY：请复制 .env.example 为 .env 并填写后重试")
        return 1

    from app.db import repo  # noqa: F401
    from app.db.session import SessionLocal, init_db
    from app.graph import router
    from app.db.models import (  # noqa: F401
        AgentPreference, AlertLog, Holding, PositionPlan, ReviewResult,
        StockScore, TradeProfile, TradeRecord,
    )
    from sqlalchemy import func, select

    init_db()
    ok = True

    def check(name, fn):
        nonlocal ok
        ok = _stage(name, fn) and ok

    today = time.strftime("%Y-%m-%d")

    # 1) DiscoverAgent 全市场挖掘（可选）
    if not args.skip_discover:
        check("DiscoverAgent 全市场潜力挖掘", lambda: router.run_discover(today))

    # 2) ScoreAgent 单股多维打分
    check("ScoreAgent 单股打分", lambda: router.run_score(TEST_CODE, TEST_NAME))

    # 3) PositionAgent 分批建仓方案
    check("PositionAgent 建仓方案", lambda: router.run_position(TEST_CODE, TEST_NAME))

    # 4) MonitorAgent 持仓监控（先模拟人工录入一笔持仓）
    holding_id = None

    def run_monitor_stage():
        nonlocal holding_id
        holding_id = repo.insert_holding(
            TEST_CODE, TEST_NAME, "2026-07-15", 1500.0, 200, 300000.0,
            stop_loss=1350.0, take_profit=1800.0, target_pct=30.0,
            note="冒烟测试模拟持仓")
        repo.add_trade(holding_id, TEST_CODE, "buy", 1500.0, 200, "2026-07-15", "冒烟建仓")
        router.run_monitor(holding_id)

    check("MonitorAgent 持仓监控", run_monitor_stage)

    # 5) ReviewAgent 卖出复盘（模拟人工卖出并录入）
    def run_review_stage():
        repo.add_trade(holding_id, TEST_CODE, "sell", 1600.0, 200, today, "冒烟卖出")
        repo.update_holding(holding_id, status="exited")
        router.run_review(holding_id)

    check("ReviewAgent 卖出复盘", run_review_stage)

    # 6) 数据表落库验证
    def verify_tables():
        with SessionLocal() as db:
            counts = {
                "stock_score": db.execute(select(func.count()).select_from(StockScore)).scalar_one(),
                "position_plan": db.execute(select(func.count()).select_from(PositionPlan)).scalar_one(),
                "alert_log": db.execute(select(func.count()).select_from(AlertLog)).scalar_one(),
                "holding": db.execute(select(func.count()).select_from(Holding)).scalar_one(),
                "trade_record": db.execute(select(func.count()).select_from(TradeRecord)).scalar_one(),
                "review_result": db.execute(select(func.count()).select_from(ReviewResult)).scalar_one(),
                "sys_trade_profile": db.execute(select(func.count()).select_from(TradeProfile)).scalar_one(),
                "agent_preference": db.execute(select(func.count()).select_from(AgentPreference)).scalar_one(),
            }
        for table, n in counts.items():
            print(f"      {table}: {n} 行")
        assert counts["stock_score"] >= 1, "score 未落库"
        assert counts["position_plan"] >= 1, "position_plan 未落库"
        assert counts["alert_log"] >= 1, "alert_log 未落库"
        assert counts["holding"] >= 1 and counts["trade_record"] >= 2, "持仓/交易流水未落库"
        assert counts["review_result"] >= 1, "review_result 未落库"
        assert counts["sys_trade_profile"] >= 1, "sys_trade_profile 未落库"
        assert counts["agent_preference"] >= 1, "agent_preference 未落库"

    check("数据表落库验证", verify_tables)

    print("=" * 64)
    print("全部通过" if ok else "存在失败环节，请查看上方 [FAIL] 输出与日志")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
