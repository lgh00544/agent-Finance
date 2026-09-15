"""幂等创建候选因子表。"""
from app.db.models import FactorCandidate
from app.db.session import engine


def migrate() -> None:
    FactorCandidate.__table__.create(bind=engine, checkfirst=True)


if __name__ == "__main__":
    migrate()
