"""推理留痕（ai_reasoning_trace）测试：字段组装映射 / 原子 upsert / 落库联动 / 查询缓存

【测试策略】写入为异步批量（工作线程），所有断言前先 reasoning_trace.flush() 同步排空；
flush 幂等，测试间互不影响。rule_refs 仅 discover 先行（其余模块为空串）。
"""
import pytest
from sqlalchemy import func, select

from app.agents.schemas import DiscoverCandidate
from app.db import repo
from app.db.models import AiReasoningTrace
from app.db.session import SessionLocal, init_db
from app.services import reasoning_trace


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _traces() -> list[AiReasoningTrace]:
    with SessionLocal() as db:
        return list(db.execute(select(AiReasoningTrace).order_by(
            AiReasoningTrace.trace_id)).scalars().all())


def _trace(code: str, module: str) -> AiReasoningTrace:
    with SessionLocal() as db:
        return db.execute(select(AiReasoningTrace).where(
            AiReasoningTrace.stock_code == code,
            AiReasoningTrace.source_module == module)).scalar_one()


def test_discover_mapping_and_rule_refs():
    detail = {
        "tech_view": "技术面研判内容", "meso_view": "中观判断",
        "volume_analysis": "量能结论", "micro_view": "微观判断",
        "macro_view": "宏观判断", "risks": ["风险1", "风险2"],
        "stock_type": "拉升初期-突破型", "focus_type": "突破",
        "price_levels": "支撑 10 / 压力 12", "position_hint": "回踩低吸",
        "confidence_tier": "建议关注", "confidence_pct": 72.0,
        "rule_refs": ["K8 量价硬检查", "K202 信心度"],
    }
    reasoning_trace.trace_candidate(
        "600101", "测试股101", "2026-08-05",
        ["候选理由A"], ["风险初判B"], {"price": 10.5, "amount": 9999}, detail)
    reasoning_trace.flush()
    t = _trace("600101", "discover")
    assert t.fact_basis.startswith('{"price"')
    assert "技术面研判内容" in t.technical_reasoning and "中观判断" in t.technical_reasoning
    assert "量能结论" in t.capital_reasoning and "微观判断" in t.capital_reasoning
    assert t.fundamental_reasoning == "宏观判断"
    assert "风险1" in t.risk_reasoning and "风险初判B" in t.risk_reasoning
    assert t.rule_refs == "K8 量价硬检查, K202 信心度"
    assert "拉升初期-突破型" in t.final_conclusion
    assert t.confidence == pytest.approx(0.72)
    assert t.data_source


def test_score_mapping_dimension_split():
    detail = {
        "技术趋势": {"score": 85, "comment": "均线多头排列"},
        "舆情风险": {"score": 60, "comment": "负面舆情较少"},
        "资金流向": {"score": 80, "comment": "主力连续净流入"},
        "基本面": {"score": 70, "comment": "业绩稳定增长"},
        "行业景气": {"score": 75, "comment": "行业景气上行"},
        "summary": "综合评分 78",
    }
    reasoning_trace.trace_score("600102", "测试股102", "2026-08-05",
                                78.0, "B", detail, ["减持风险"])
    reasoning_trace.flush()
    t = _trace("600102", "score")
    assert "均线多头排列" in t.technical_reasoning and "负面舆情较少" in t.technical_reasoning
    assert "主力连续净流入" in t.capital_reasoning
    assert "业绩稳定增长" in t.fundamental_reasoning and "行业景气上行" in t.fundamental_reasoning
    assert "减持风险" in t.risk_reasoning
    assert '"score": 78.0' in t.final_conclusion and "综合评分 78" in t.final_conclusion


def test_plan_alert_review_sell_mapping():
    batches = [{"tranche": 1, "price_zone": "10~10.5", "ratio_pct": 30.0}]
    pid = repo.insert_plan("600103", "测试股103", "2026-08-05", 60.0,
                           batches, 9.5, 12.0, "分批建仓逻辑")
    reasoning_trace.flush()
    t = _trace("600103", "position")
    assert '"plan_id": %d' % pid in t.final_conclusion
    assert "分批建仓逻辑" in t.technical_reasoning

    signal = {"reasons": ["跌破止损位"], "risks": ["继续下探风险"],
              "key_levels": {"止损": 9.5}, "severity": "critical"}
    reasoning_trace.trace_alert("600103", "测试股103", "2026-08-06",
                                "触及止损", "critical", "已破止损位", "清仓", signal)
    reasoning_trace.flush()
    t = _trace("600103", "alert")
    assert "跌破止损位" in t.technical_reasoning
    assert "继续下探风险" in t.risk_reasoning
    assert '{"止损":9.5}' in t.fact_basis.replace(" ", "")  # fact=key_levels
    assert "清仓" in t.final_conclusion

    rid = repo.insert_review("600104", "测试股104", 55, "2026-08-05", 20, -5.0,
                             {"兑现程度": "未兑现"}, "教训内容", {"偏好": "更保守"})
    reasoning_trace.flush()
    t = _trace("600104", "review")
    assert "未兑现" in t.fact_basis
    assert t.technical_reasoning == "教训内容"
    assert "更保守" in t.final_conclusion

    reasoning_trace.trace_sell("600105", "测试股105", "2026-08-06",
                               {"action": "清仓", "reasons": ["趋势破坏"],
                                "exit_price_zone": "9.8~10.2", "risk_warning": "破位风险",
                                "check_list": ["确认止损"]})
    reasoning_trace.flush()
    t = _trace("600105", "sell")
    assert "趋势破坏" in t.technical_reasoning
    assert "破位风险" in t.risk_reasoning
    assert "9.8~10.2" in t.final_conclusion and "确认止损" in t.final_conclusion


def test_same_key_latest_wins_atomic():
    """同键（code+date+module）多次写入只保留最新：单批内重复与跨批重复均安全（原子 upsert）"""
    reasoning_trace.trace_score("600106", "测试股106", "2026-08-05",
                                80.0, "B", {"技术趋势": {"comment": "第一版"}}, [])
    reasoning_trace.trace_score("600106", "测试股106", "2026-08-05",
                                90.0, "A", {"技术趋势": {"comment": "第二版"}}, ["新风险"])
    reasoning_trace.flush()
    rows = [t for t in _traces()
            if t.stock_code == "600106" and t.source_module == "score"]
    assert len(rows) == 1
    assert "第二版" in rows[0].technical_reasoning
    assert "新风险" in rows[0].risk_reasoning


def test_repo_landing_writes_trace():
    """repo 六个落库函数均联动写留痕（异步 → flush 后可见）"""
    repo.upsert_candidate("600107", "测试股107", "2026-08-05", 1,
                          ["理由"], ["风险"], {"price": 1.0},
                          {"tech_view": "联动技术研判", "rule_refs": ["K16"]})
    repo.upsert_score("600107", "测试股107", "2026-08-05", 88.0, "A",
                      {"技术趋势": {"comment": "联动评分"}}, [])
    reasoning_trace.flush()
    assert "联动技术研判" in _trace("600107", "discover").technical_reasoning
    assert "联动评分" in _trace("600107", "score").technical_reasoning


def test_list_filters_and_cache_invalidation():
    """list_traces 轻量列表（无长文本）+ 过滤；新写入后 flush 自动失效 L1 缓存"""
    lst = repo.list_traces(code="600107", date="2026-08-05")
    assert all(t["stock_code"] == "600107" and t["generate_date"] == "2026-08-05" for t in lst)
    assert all("technical_reasoning" not in t for t in lst)  # 轻量列表不含长文本

    # 触发新写入（同表），flush 后列表必须反映新数据（写后失效缓存）
    repo.upsert_score("600108", "测试股108", "2026-08-05", 66.0, "C",
                      {"技术趋势": {"comment": "缓存失效验证"}}, [])
    reasoning_trace.flush()
    lst2 = repo.list_traces(code="600108", date="2026-08-05")
    assert len(lst2) == 1

    full = repo.get_trace(lst2[0]["trace_id"])
    assert full["final_conclusion"] and "缓存失效验证" in full["technical_reasoning"]
    assert repo.get_trace(99999999) is None


def test_schema_rule_refs_field():
    """DiscoverCandidate 含 rule_refs（缺省空列表，旧输出兼容）"""
    c = DiscoverCandidate(
        stock_code="600109", stock_name="测试股109", reason="r", risk_notice="n",
        stock_type="拉升初期-突破型", confidence_tier="建议关注", confidence_pct=60,
        macro_view="m", meso_view="m", micro_view="m", volume_analysis="v",
        risks=["a", "b"], focus_type="低吸")
    assert c.rule_refs == []


def test_indexes_exist():
    """建表索引与唯一约束存在（联合唯一 + module_date 覆盖索引 + 单列索引）"""
    from sqlalchemy import inspect
    from app.db.session import engine

    insp = inspect(engine)
    idx = {i["name"]: i for i in insp.get_indexes("ai_reasoning_trace")}
    assert "ix_trace_module_date" in idx
    uniq = {u["name"]: u for u in insp.get_unique_constraints("ai_reasoning_trace")}
    assert "uq_trace_code_date_module" in uniq
