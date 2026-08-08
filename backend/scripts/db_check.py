"""查看数据库各表数据量,快速确认系统当前存量"""
import sys

sys.path.insert(0, ".")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import inspect, text
from app.db.session import engine


def main() -> None:
    insp = inspect(engine)
    tables = insp.get_table_names()
    print(f"共 {len(tables)} 张表:")
    with engine.connect() as conn:
        for t in sorted(tables):
            n = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            marker = "  <-- 空" if n == 0 else ""
            print(f"  {t:40s} {n:>6d}{marker}")


if __name__ == "__main__":
    main()
