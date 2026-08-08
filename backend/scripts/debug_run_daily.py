"""
【调试专用】非交易日强制跑每日挖掘全链路(Discover → 候选打分)
- 通过 monkeypatch 打开数据源层的交易日闸门(不改任何源码、不重启后端)
- 周末/节假日运行时,行情接口返回最近交易日(周五)收盘数据
- 数据直接落库 data/dev.db,面板刷新即可查看

用法: .venv/Scripts/python backend/scripts/debug_run_daily.py
"""
import os
import sys

# 项目根(含 agent_prompts 包)与 backend 目录都加入搜索路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.datasource import market_hours

# 打开交易日闸门:全市场快照 / 指数行情 / 单股实时行情全部放行
market_hours.is_trading_day = lambda: True

from app.graph import router as graph_router

print("=" * 60)
print("开始跑每日挖掘全链路(非交易日调试模式)...")
print("=" * 60)

result = graph_router.run_daily_pipeline()
print("\n" + "=" * 60)
print("pipeline 结果:", result)
print("=" * 60)
