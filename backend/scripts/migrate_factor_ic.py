"""幂等创建因子 IC 历史表。"""
from app.db.models import FactorIcHistory
from app.db.session import engine


def migrate() -> None:
    FactorIcHistory.__table__.create(bind=engine, checkfirst=True)


if __name__ == "__main__":
    migrate()
