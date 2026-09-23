"""买卖点信号体系 · 只读查看入口（批 1 观察期专用；不改任何数据、不碰后端进程）

用法：
    D:/self/.venv/Scripts/python.exe D:/self/signal_view.py              全量概览
    D:/self/.venv/Scripts/python.exe D:/self/signal_view.py 2026-09-17  指定日期明细
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ENV = Path(r"D:/self/.env")


def load_env() -> dict:
    env = {}
    for line in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if "=" in s and not s.startswith("#"):
            k, v = s.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main() -> None:
    day = sys.argv[1] if len(sys.argv) > 1 else None
    import pymysql

    env = load_env()
    conn = pymysql.connect(
        host=env["MYSQL_HOST"], port=int(env["MYSQL_PORT"]), user=env["MYSQL_USER"],
        password=env["MYSQL_ROOT_PASSWORD"], database=env["MYSQL_DATABASE"],
        connect_timeout=15, ssl={"ssl": {}},
    )
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM signal_trigger")
    print("总触发行数:", cur.fetchone()[0])

    cur.execute("SELECT trade_date, COUNT(*) FROM signal_trigger GROUP BY trade_date ORDER BY trade_date DESC LIMIT 10")
    print("按交易日（近 10）:", cur.fetchall())

    cur.execute("SELECT signal_id, COUNT(*) n FROM signal_trigger GROUP BY signal_id ORDER BY n DESC LIMIT 12")
    print("按信号（Top 12）:", cur.fetchall())

    cur.execute("SELECT COUNT(*) FROM signal_trigger WHERE dedup = 1")
    print("其中 dedup=1（冷却期内重复触发，不计入统计样本）:", cur.fetchone()[0])

    if day:
        cur.execute("SELECT COUNT(*) FROM signal_trigger WHERE trade_date = %s", (day,))
        print(f"[{day}] 触发数:", cur.fetchone()[0])
        cur.execute(
            "SELECT stock_code, signal_id, direction, trigger_close, limit_up, is_st, dedup "
            "FROM signal_trigger WHERE trade_date = %s ORDER BY id DESC LIMIT 20", (day,))
        for r in cur.fetchall():
            print("   ", r)

    conn.close()


if __name__ == "__main__":
    main()
