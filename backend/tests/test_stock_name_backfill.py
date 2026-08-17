"""股票名称补齐测试（历史脏数据修复，查询层只读不写库）：
1. 名称缺失/等于代码的记录按「候选池最新 → 持仓 → 新闻」顺序反查真实名称；
2. 反查不到保留空名（前端展示「未知名称」）；
3. 名称正常的记录不受影响；
4. 各列表接口（评分/告警/复盘/建仓/持仓）返回的名称均经补全。"""
import pytest

from app.cache import cache
from app.db import repo
from app.db.models import Holding, NewsArticle, StockCandidate, StockScore
from app.db.session import SessionLocal


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    from app.db.session import init_db
    init_db()


@pytest.fixture()
def _clean(monkeypatch):
    """隔离测试数据：清空相关表 + 失效查询缓存（原生 SQLAlchemy 直写绕过 repo._invalidate，
    不清缓存会让后续同参数 list_* 读到 prior test 的脏缓存，产生顺序依赖 flake），测试后恢复"""
    cache.delete_prefix("dbq:")
    with SessionLocal() as db:
        for m in (StockCandidate, StockScore, Holding, NewsArticle):
            db.query(m).delete()
        db.commit()
    yield
    cache.delete_prefix("dbq:")
    with SessionLocal() as db:
        for m in (StockCandidate, StockScore, Holding, NewsArticle):
            db.query(m).delete()
        db.commit()


def _seed():
    with SessionLocal() as db:
        db.add_all([
            StockCandidate(stock_code="600001", stock_name="测试甲", trade_date="2026-08-05",
                           rank=1, reasons=[], risk_notice=[], snapshot={}, detail={}),
            # 候选池有两条历史（最新一条名称正确，验证取最新）
            StockCandidate(stock_code="600002", stock_name="测试乙旧名", trade_date="2026-08-01",
                           rank=1, reasons=[], risk_notice=[], snapshot={}, detail={}),
            StockCandidate(stock_code="600002", stock_name="测试乙", trade_date="2026-08-05",
                           rank=1, reasons=[], risk_notice=[], snapshot={}, detail={}),
            Holding(stock_code="600003", stock_name="测试丙", entry_date="2026-08-01",
                    entry_price=10.0, shares=100),
            NewsArticle(stock_code="600004", stock_name="测试丁", title="t", content="c"),
        ])
        db.commit()


@pytest.mark.usefixtures("_clean")
def test_backfill_priority_and_missing():
    """候选池最新名称优先；持仓/新闻兜底；全部查不到保留空名"""
    _seed()
    rows = [
        {"stock_code": "600001", "stock_name": "600001"},   # 等于代码 → 候选池
        {"stock_code": "600002", "stock_name": ""},          # 空名 → 候选池最新
        {"stock_code": "600003", "stock_name": "600003"},   # 等于代码 → 持仓
        {"stock_code": "600004", "stock_name": "600004"},   # 等于代码 → 新闻
        {"stock_code": "999999", "stock_name": "999999"},   # 无来源 → 保留空名
        {"stock_code": "600005", "stock_name": "正常名称"},  # 正常 → 不动
    ]
    out = repo._backfill_stock_names(rows)
    by_code = {r["stock_code"]: r["stock_name"] for r in out}
    assert by_code["600001"] == "测试甲"
    assert by_code["600002"] == "测试乙"      # 取最新日期，而非旧名
    assert by_code["600003"] == "测试丙"
    assert by_code["600004"] == "测试丁"
    assert by_code["999999"] == ""            # 前端兜底「未知名称」
    assert by_code["600005"] == "正常名称"


@pytest.mark.usefixtures("_clean")
def test_list_scores_names_backfilled():
    """评分列表接口：名称缺失记录自动补全（写库数据不动）"""
    _seed()
    with SessionLocal() as db:
        db.add(StockScore(stock_code="600001", stock_name="600001", trade_date="2026-08-05",
                          score=70.0, grade="B", detail={}, risk_list=[]))
        db.add(StockScore(stock_code="999999", stock_name="999999", trade_date="2026-08-05",
                          score=50.0, grade="C", detail={}, risk_list=[]))
        db.commit()
    rows = repo.list_scores(date="2026-08-05")
    by_code = {r["stock_code"]: r["stock_name"] for r in rows}
    assert by_code["600001"] == "测试甲"
    assert by_code["999999"] == ""  # 无来源保留空名，前端显示「未知名称」
    # 写库数据未被修改（查询层只读补全，不改任何存储）
    with SessionLocal() as db:
        raw = db.query(StockScore).filter_by(stock_code="600001").first()
        assert raw.stock_name == "600001"  # 库中仍是代码，展示层补全


@pytest.mark.usefixtures("_clean")
def test_list_alerts_and_plans_backfilled():
    """告警/建仓列表接口名称补全生效"""
    _seed()
    with SessionLocal() as db:
        from app.db.models import AlertLog, PositionPlan
        db.add(AlertLog(stock_code="600003", stock_name="600003", alert_type="t",
                        severity="info", message="m", action="hold", signal={}))
        db.add(PositionPlan(stock_code="600001", stock_name="600001", plan_date="2026-08-05",
                            total_pct=10.0, batches=[], rationale="r"))
        db.commit()
    alerts = repo.list_alerts(limit=10)
    assert any(a["stock_code"] == "600003" and a["stock_name"] == "测试丙" for a in alerts)
    plans = repo.list_plans(limit=10)
    assert any(p["stock_code"] == "600001" and p["stock_name"] == "测试甲" for p in plans)
