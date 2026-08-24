import os
import sys
import tempfile
import time

os.environ.setdefault("APP_ENV", "dev")
os.environ.setdefault("DB_BACKEND", "sqlite")
os.environ.setdefault("SQLITE_PATH", os.path.join(tempfile.gettempdir(), "dbg_cap.db"))
sys.path.insert(0, r"D:\self\backend")

from app.db.session import init_db
init_db()
from app.api import routes
from app.services import capital_view as cv
from app import cache as cm

calls = {"n": 0}


def loader():
    calls["n"] += 1
    return {"stock_code": "600010", "trade_date": time.strftime("%Y-%m-%d"),
            "recent_actors": [], "coordination": "数据不足", "wash_suspect": False,
            "stats_30d": {"胜率": None, "盈亏比": None, "平均持仓天数": None},
            "theme_resonance": None, "source": "sse_only", "missing_data": ["stats_30d"],
            "dragon_tiger_rows": [], "capital_flow_rows": []}


cv._compute = lambda code, date: loader()
deleted = []
cm.cache.delete = lambda k: deleted.append(k)

key = f"capital_view:{time.strftime('%Y-%m-%d')}:600010"
print("expect key:", key)
r1 = routes.capital_view("600010")
print("r1 calls:", calls["n"], "store:", list(cm.cache._store.keys()))
r2 = routes.capital_view("600010")
print("r2 calls:", calls["n"])
r3 = routes.capital_view("600010", force=True)
print("r3 calls:", calls["n"], "deleted:", deleted)
print("after r3 store:", list(cm.cache._store.keys()))
