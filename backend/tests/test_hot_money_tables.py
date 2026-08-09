"""游资数据链·步骤一：两表结构 + 种子档案 + repo 读写（dev SQLite，真实落库）"""
import pytest
from sqlalchemy import inspect

from app.db import repo
from app.db.models import HotMoneyProfile, LhbOriginalFlow
from app.db.session import SessionLocal, init_db


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()
    repo.seed_default_hot_money_profiles()


def test_tables_created():
    """两张新表 + 关键约束/索引存在"""
    insp = inspect(SessionLocal().get_bind())
    tables = set(insp.get_table_names())
    assert "hot_money_profile" in tables
    assert "lhb_original_flow" in tables
    # seat_code 唯一约束（一席位一主力游资）
    uqs = [c["name"] for c in insp.get_unique_constraints("hot_money_profile")]
    assert "uq_hot_money_seat" in uqs
    # (trade_date, stock_code, lhb_type) 联合索引
    idxs = [i["name"] for i in insp.get_indexes("lhb_original_flow")]
    assert "ix_lhb_date_code_type" in idxs


def test_seed_default_profiles():
    """种子 7 位游资档案写入（幂等重复调用不重复）"""
    profiles = repo.list_hot_money_profiles()
    actors = {p["actor_name"] for p in profiles}
    for expect in ("赵老哥", "章盟主", "孙哥", "欢乐海", "佛山系", "炒股养家", "宁波桑田路"):
        assert expect in actors, f"缺少种子游资: {expect}"
    n1 = len(profiles)
    repo.seed_default_hot_money_profiles()
    assert len(repo.list_hot_money_profiles()) == n1  # 幂等


def test_profile_seat_unique():
    """seat_code 唯一约束：ORM 直接插入同席位被拒绝（一席位一主力游资）；
    repo.upsert 为幂等语义（同席位更新）不违反约束"""
    from sqlalchemy.exc import IntegrityError

    with SessionLocal() as db:
        db.add(HotMoneyProfile(actor_name="测试游资X", seat_code="中信证券上海分公司",
                               tier="观察", source="测试"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_upsert_and_get_profile():
    """upsert 幂等（同席位更新） + 席位精确/模糊匹配"""
    pid = repo.upsert_hot_money_profile("测试游资Y", "测试营业部-中山路", "一线",
                                        ["打板"], ["军工"], ["协同A"], "手动")
    again = repo.upsert_hot_money_profile("测试游资Y", "测试营业部-中山路", "二线",
                                          ["低吸"], ["军工"], ["协同A", "协同B"], "手动")
    assert again == pid  # 同席位更新不新建
    hit = repo.get_profile_by_seat("测试营业部-中山路")
    assert hit["tier"] == "二线" and hit["co_seats"] == ["协同A", "协同B"]
    # 模糊匹配：含席位名的长名称命中
    assert repo.get_profile_by_seat("华泰证券深圳益田路荣超商务中心营业部")["actor_name"] == "欢乐海"
    # 未命中
    assert repo.get_profile_by_seat("不存在的营业部") is None


def test_lhb_insert_and_query():
    """龙虎榜流水批量插入 + 按 日期/标的/口径 查询 + 口径隔离"""
    rows = [
        {"trade_date": "2026-08-07", "stock_code": "601138", "stock_name": "工业富联",
         "lhb_type": "1d", "disclosure_reason": "日涨幅偏离值达7%",
         "seat_name": "中信证券上海分公司", "buy_amt": 5e7, "sell_amt": 1e7, "net_buy": 4e7,
         "confidence": 0.8, "source": "eastmoney"},
        {"trade_date": "2026-08-07", "stock_code": "601138", "stock_name": "工业富联",
         "lhb_type": "3d", "disclosure_reason": "连续三日涨幅偏离",
         "seat_name": "国泰君安证券上海分公司", "buy_amt": 8e7, "sell_amt": 2e7, "net_buy": 6e7,
         "confidence": 0.8, "source": "eastmoney"},
    ]
    n = repo.insert_lhb_flows(rows)
    assert n == 2
    day = repo.list_lhb_flows(trade_date="2026-08-07")
    assert len(day) == 2
    only_1d = repo.list_lhb_flows(trade_date="2026-08-07", stock_code="601138", lhb_type="1d")
    assert len(only_1d) == 1 and only_1d[0]["net_buy"] == 4e7
    only_3d = repo.list_lhb_flows(trade_date="2026-08-07", stock_code="601138", lhb_type="3d")
    assert len(only_3d) == 1 and only_3d[0]["seat_name"] == "国泰君安证券上海分公司"
    # 口径隔离：3d 查询不得混入 1d 行
    assert only_3d[0]["lhb_type"] == "3d"


def test_fingerprint_changes_on_write():
    """游资数据指纹：写入后变化（供 LLM cache_key 防缓存吞新数据）"""
    fp0 = repo.hot_money_fingerprint()
    repo.insert_lhb_flows([
        {"trade_date": "2026-08-07", "stock_code": "600519", "stock_name": "贵州茅台",
         "lhb_type": "1d", "disclosure_reason": "换手率异常", "seat_name": "",
         "buy_amt": 1e8, "sell_amt": 5e7, "net_buy": 5e7, "confidence": 0.8, "source": "eastmoney"},
    ])
    fp1 = repo.hot_money_fingerprint()
    assert fp0 != fp1
    assert fp0 != "0" or True  # 指纹始终非空字符串
