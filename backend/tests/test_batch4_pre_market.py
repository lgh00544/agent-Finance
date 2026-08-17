"""批次4：盘前快筛 + 候选关联度 + 市况切换（dev SQLite，不触网）：
1. fetch_spot_quotes_batch force_realtime：默认非交易时段走快照（ulist 零调用，回归）；force=True 跳过闸门走 ulist
2. pre_market_screen：list_candidate_dates()[0] 取候选（非 today）；≤-3 warning / ≥+5 info / 无数据停牌；
   无异常零调用；action≤16；竞价数据不可用不推送；pre_close 缺失跳过判定
3. candidate_industry_concentration：coverage 计算 / max_concentration / 行业全空
4. market_shift_detect：评分差≥10 / 档位 / 候选池上限 / 阶段 / 风险偏好 各自触发并合并；无变化零推送；
   get_prev_market_condition 空/单条返回 None；market_condition 缺失时评分类跳过、phase/risk 仍可比
5. 候选池页接线（源码级）：行业集中度行在可建仓统计卡之前
"""
import hashlib
from pathlib import Path

import pytest
from sqlalchemy import delete

from app.cache import cache
from app.db import repo
from app.db.models import AlertLog, MarketCondition, MarketIntel, StockCandidate
from app.db.session import SessionLocal, init_db

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


@pytest.fixture(autouse=True)
def _cleanup():
    """隔离批次4测试副作用：清空候选/市况/研判/告警行 + 失效查询缓存"""
    cache.delete_prefix("dbq:")
    cache.delete("job:last_pre_market")
    with SessionLocal() as db:
        for m in (StockCandidate, MarketCondition, MarketIntel, AlertLog):
            db.execute(delete(m))
        db.commit()
    yield
    cache.delete_prefix("dbq:")
    with SessionLocal() as db:
        for m in (StockCandidate, MarketCondition, MarketIntel, AlertLog):
            db.execute(delete(m))
        db.commit()


def _seed_candidate(code: str, name: str, date: str = "2026-08-13",
                    pre_close: float | None = 10.0, industry: str | None = None) -> None:
    detail = {"enriched": {"industry": industry}} if industry else {}
    repo.upsert_candidate(code, name, date, 1, ["候选理由"], [],
                          {"pre_close": pre_close}, detail)


class _FakeQuotesSource:
    """假批量行情源：只返回 self.quotes 中存在且被请求的代码"""
    def __init__(self, quotes=None):
        self.quotes = quotes or {}
        self.calls = []

    def fetch_spot_quotes_batch(self, codes, force_realtime=False):
        self.calls.append({"codes": list(codes), "force_realtime": force_realtime})
        return {c: q for c, q in self.quotes.items() if c in codes}


# ==================== 1. fetch_spot_quotes_batch force_realtime ====================

def _clear_ak_cache(scope: str) -> None:
    from app.datasource.akshare_source import _cache_key
    cache.delete(_cache_key(scope))


def test_force_realtime_skips_realtime_gate(monkeypatch):
    """默认参数非交易时段走快照（ulist 零调用，零回归）；force_realtime=True 跳过闸门走 ulist"""
    from app.datasource import market_hours
    from app.datasource.akshare_source import AkshareSource

    src = AkshareSource()
    monkeypatch.setattr(market_hours, "realtime_open", lambda: False)
    monkeypatch.setattr(src, "_batch_from_universe", lambda codes: {})
    monkeypatch.setattr(src, "fetch_spot_quote", lambda code: {})
    ulist = {"n": 0}

    def _ulist(codes):
        ulist["n"] += 1
        return {"600001": {"code": "600001", "name": "测试", "price": 9.5,
                           "change_pct": -5.0, "time": "09:25"}}

    monkeypatch.setattr(src, "_batch_from_ulist", _ulist)
    # 默认：非交易时段 ulist 零调用
    _clear_ak_cache("batch_quote:600001")
    out1 = src.fetch_spot_quotes_batch(["600001"])
    assert ulist["n"] == 0
    assert out1 == {}
    # force_realtime=True：即使非交易时段也走 ulist
    _clear_ak_cache("batch_quote:600001")
    out2 = src.fetch_spot_quotes_batch(["600001"], force_realtime=True)
    assert ulist["n"] == 1
    assert out2["600001"]["change_pct"] == -5.0


def test_force_realtime_default_trading_window_still_ulist(monkeypatch):
    """交易时段默认也走 ulist（现有行为不变）"""
    from app.datasource import market_hours
    from app.datasource.akshare_source import AkshareSource

    src = AkshareSource()
    monkeypatch.setattr(market_hours, "realtime_open", lambda: True)
    monkeypatch.setattr(src, "_batch_from_universe", lambda codes: {})
    monkeypatch.setattr(src, "fetch_spot_quote", lambda code: {})
    ulist = {"n": 0}

    def _ulist(codes):
        ulist["n"] += 1
        return {"600001": {"code": "600001", "name": "测试", "price": 10.0,
                           "change_pct": 1.0, "time": "10:00"}}

    monkeypatch.setattr(src, "_batch_from_ulist", _ulist)
    _clear_ak_cache("batch_quote:600001")
    src.fetch_spot_quotes_batch(["600001"])
    assert ulist["n"] == 1


# ==================== 2. pre_market_screen ====================

def test_pre_market_screen_uses_prev_candidate_date(monkeypatch):
    """候选取 list_candidate_dates()[0]（非 today）；force_realtime=True；只检查该日候选"""
    from app.services import pre_market_screen as pms

    _seed_candidate("600001", "测试甲", date="2026-08-13", pre_close=10.0)
    _seed_candidate("600002", "测试乙", date="2026-08-12", pre_close=20.0)  # 更早日期的候选不检查
    src = _FakeQuotesSource({"600001": {"code": "600001", "name": "测试甲",
                                        "price": 9.5, "change_pct": -5.0, "time": "09:25"}})
    monkeypatch.setattr(pms, "get_datasource", lambda: src)
    pushed = {"n": 0}
    monkeypatch.setattr(pms, "push_alert",
                        lambda *a, **k: (pushed.__setitem__("n", pushed["n"] + 1) or True))
    result = pms.pre_market_screen()
    assert src.calls[0]["force_realtime"] is True
    assert set(src.calls[0]["codes"]) == {"600001"}   # 只用最新日期 2026-08-13 的候选
    assert len(result["anomalies"]) == 1
    assert result["anomalies"][0]["code"] == "600001"
    assert pushed["n"] == 1                            # 合并一条飞书


def test_pre_market_screen_thresholds_and_suspended(monkeypatch):
    """≤-3 warning / ≥+5 info / 无数据可能停牌 / 正常波动零告警；逐条落库"""
    from app.services import pre_market_screen as pms

    _seed_candidate("600001", "低开", date="2026-08-13", pre_close=10.0)
    _seed_candidate("600002", "高开", date="2026-08-13", pre_close=10.0)
    _seed_candidate("600003", "停牌", date="2026-08-13", pre_close=10.0)
    _seed_candidate("600004", "正常", date="2026-08-13", pre_close=10.0)
    src = _FakeQuotesSource({
        "600001": {"code": "600001", "name": "低开", "price": 9.4, "change_pct": -6.0, "time": "09:25"},
        "600002": {"code": "600002", "name": "高开", "price": 10.8, "change_pct": 8.0, "time": "09:25"},
        # 600003 无数据 → 停牌
        "600004": {"code": "600004", "name": "正常", "price": 10.2, "change_pct": 2.0, "time": "09:25"},
    })
    monkeypatch.setattr(pms, "get_datasource", lambda: src)
    monkeypatch.setattr(pms, "push_alert", lambda *a, **k: True)
    result = pms.pre_market_screen()
    by_code = {a["code"]: a for a in result["anomalies"]}
    assert len(result["anomalies"]) == 3
    assert by_code["600001"]["severity"] == "warning"
    assert by_code["600001"]["action"] == "暂缓买入"
    assert by_code["600002"]["severity"] == "info"
    assert by_code["600002"]["action"] == "注意追高"
    assert by_code["600003"]["type"] == "suspended"
    assert "可能停牌" in by_code["600003"]["message"]
    assert "600004" not in by_code
    rows = [r for r in repo.list_alerts(limit=20) if r.get("source") == "pre_market"]
    assert len(rows) == 3


def test_pre_market_screen_no_anomaly_no_push(monkeypatch):
    """无异常 → 不调用 insert_alert、不调用 push_alert"""
    from app.services import pre_market_screen as pms

    _seed_candidate("600001", "正常", date="2026-08-13", pre_close=10.0)
    src = _FakeQuotesSource({"600001": {"code": "600001", "name": "正常",
                                        "price": 10.1, "change_pct": 1.0, "time": "09:25"}})
    monkeypatch.setattr(pms, "get_datasource", lambda: src)
    pushed = {"n": 0}
    monkeypatch.setattr(pms, "push_alert",
                        lambda *a, **k: (pushed.__setitem__("n", pushed["n"] + 1) or True))
    before = len(repo.list_alerts(limit=50))
    result = pms.pre_market_screen()
    assert result["anomalies"] == []
    assert pushed["n"] == 0
    assert len(repo.list_alerts(limit=50)) == before


def test_pre_market_screen_quotes_unavailable(monkeypatch):
    """竞价数据整体不可用 → 不报错不推送"""
    from app.services import pre_market_screen as pms

    _seed_candidate("600001", "测试", date="2026-08-13", pre_close=10.0)
    src = _FakeQuotesSource({})
    monkeypatch.setattr(pms, "get_datasource", lambda: src)
    pushed = {"n": 0}
    monkeypatch.setattr(pms, "push_alert",
                        lambda *a, **k: (pushed.__setitem__("n", pushed["n"] + 1) or True))
    result = pms.pre_market_screen()
    assert result["skipped"] == "竞价数据暂不可用"
    assert pushed["n"] == 0


def test_pre_market_screen_no_candidate_dates(monkeypatch):
    """无候选日期 → 直接返回不报错"""
    from app.services import pre_market_screen as pms
    assert pms.pre_market_screen()["skipped"] == "无候选日期"


def test_pre_market_screen_pre_close_missing_skip(monkeypatch):
    """change_pct 缺失且 pre_close 缺失 → 该股跳过判定不报错"""
    from app.services import pre_market_screen as pms

    _seed_candidate("600001", "测试", date="2026-08-13", pre_close=None)
    src = _FakeQuotesSource({"600001": {"code": "600001", "name": "测试",
                                        "price": 10.0, "change_pct": None, "time": "09:25"}})
    monkeypatch.setattr(pms, "get_datasource", lambda: src)
    result = pms.pre_market_screen()
    assert result["anomalies"] == []


def test_pre_market_actions_within_16_chars():
    """action 文案 ≤16 字符（alert 表 action 列 String(16)）"""
    from app.services import pre_market_screen as pms
    for action in (pms._ACTION_LOW, pms._ACTION_HIGH, pms._ACTION_STOP):
        assert len(action) <= 16


# ==================== 3. candidate_industry_concentration ====================

def test_concentration_computes_coverage_and_max():
    from app.services import pre_market_screen as pms
    _seed_candidate("600001", "甲", date="2026-08-13", industry="半导体")
    _seed_candidate("600002", "乙", date="2026-08-13", industry="半导体")
    _seed_candidate("600003", "丙", date="2026-08-13", industry="医药")
    _seed_candidate("600004", "丁", date="2026-08-13", industry="")  # 无行业
    result = pms.candidate_industry_concentration("2026-08-13")
    assert result["total"] == 4
    assert result["coverage"] == 75.0            # 3/4 有效行业
    assert result["max_concentration"] == 50.0   # 半导体 2/4
    assert result["max_industry"] == "半导体"
    assert result["groups"][0]["industry"] == "半导体"
    assert result["groups"][0]["count"] == 2


def test_concentration_all_empty():
    from app.services import pre_market_screen as pms
    _seed_candidate("600001", "甲", date="2026-08-13")
    _seed_candidate("600002", "乙", date="2026-08-13")
    result = pms.candidate_industry_concentration("2026-08-13")
    assert result["coverage"] == 0.0
    assert result["groups"] == []
    assert result["max_concentration"] == 0.0


# ==================== 4. market_shift_detect + get_prev_market_condition ====================

def test_get_prev_market_condition():
    """表空/仅一条 → None；两条 → 倒序第二条"""
    assert repo.get_prev_market_condition() is None
    repo.upsert_market_condition("2026-08-11", 40, {}, 15, "s1")
    assert repo.get_prev_market_condition() is None   # 仅一条
    repo.upsert_market_condition("2026-08-12", 25, {}, 10, "s2")
    prev = repo.get_prev_market_condition()
    assert prev is not None and prev["trade_date"] == "2026-08-11"
    assert prev["total_score"] == 40


def test_market_shift_detect_score_band_cap(monkeypatch):
    """评分差≥10 / 档位变 / 候选池上限变 → 各自触发并合并"""
    from app.services import pre_market_screen as pms
    repo.upsert_market_condition("2026-08-11", 38, {}, 15, "s1")   # 温和期 / 上限15
    repo.upsert_market_condition("2026-08-12", 25, {}, 10, "s2")   # 过渡期 / 上限10，差13
    pushed = {"n": 0}
    monkeypatch.setattr(pms, "push_alert",
                        lambda *a, **k: (pushed.__setitem__("n", pushed["n"] + 1) or True))
    changes = pms.market_shift_detect()
    dims = [c["dim"] for c in changes]
    assert "评分" in dims and "档位" in dims and "候选池上限" in dims
    assert pushed["n"] == 1                          # 合并一条飞书
    rows = [r for r in repo.list_alerts(limit=20) if r.get("source") == "market_shift"]
    assert len(rows) == 1
    assert "【市况切换】" in rows[0]["message"]
    assert len(rows[0]["action"]) <= 16


def test_market_shift_detect_phase_risk(monkeypatch):
    """阶段/风险偏好切换触发（market_condition 侧无数据时仍可比）"""
    from app.services import pre_market_screen as pms
    repo.upsert_market_intel("2026-08-11", "主升", "", "进取", {}, {}, {}, "m1", {})
    repo.upsert_market_intel("2026-08-12", "分化", "", "中性", {}, {}, {}, "m2", {})
    changes = pms.market_shift_detect()
    dims = [c["dim"] for c in changes]
    assert "行情阶段" in dims and "风险偏好" in dims
    assert "评分" not in dims                        # market_condition 缺失 → 评分类跳过


def test_market_shift_detect_no_change(monkeypatch):
    """无变化 → 返回空，不落库不推送"""
    from app.services import pre_market_screen as pms
    repo.upsert_market_condition("2026-08-11", 30, {}, 10, "s1")
    repo.upsert_market_condition("2026-08-12", 30, {}, 10, "s2")   # 同分同档同上限
    pushed = {"n": 0}
    monkeypatch.setattr(pms, "push_alert",
                        lambda *a, **k: (pushed.__setitem__("n", pushed["n"] + 1) or True))
    changes = pms.market_shift_detect()
    assert changes == []
    assert pushed["n"] == 0
    assert [r for r in repo.list_alerts(limit=20) if r.get("source") == "market_shift"] == []


# ==================== 5. 候选池页接线 ====================

def test_candidate_page_concentration_wired():
    """页面含 candidate_concentration 调用，且行业集中度行在可建仓统计卡之前"""
    src = (_PROJECT_ROOT / "streamlit" / "pages" / "1_每日候选池.py").read_text(encoding="utf-8")
    assert "candidate_concentration" in src
    assert src.index("候选行业集中度") < src.index("可建仓统计卡")
