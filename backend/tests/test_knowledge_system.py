"""知识库完整沉淀配套测试：
分职能战法知识注入 / 知识版本指纹缓存失效 / 标的类型标识 Schema 强制落地 /
批量打分并行模式（大标的池自动切换，结果与单 Agent 一致）"""
import threading
import time

import pytest
from pydantic import ValidationError

from app.agents.schemas import DiscoverCandidate


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    from app.db.session import init_db
    init_db()


# ================= 分职能战法知识注入 =================

def test_agent_knowledge_text_loaded():
    """分职能战法知识库按 Agent 注入对应文件（discover 含漏斗/反例库，score 含评分细则）"""
    from app.agents.common import _agent_knowledge_text

    text = _agent_knowledge_text("discover")
    assert "选股漏斗" in text and "K8" in text and "威科夫" in text
    assert "亨通" in text and "立讯" in text  # 反例库单独成库并合并注入
    assert "吸筹末期-优选型" in text
    assert "参考权重" in text  # 全部落地为参考权重而非死条件

    score = _agent_knowledge_text("score")
    assert "5 维评分" in score and "决策阈值" in score

    monitor = _agent_knowledge_text("monitor")
    assert "派发期识别清单" in monitor and "止损止盈" in monitor

    review = _agent_knowledge_text("review")
    assert "复盘模板" in review and "失职根因" in review and "亨通" in review

    assert _agent_knowledge_text("position") == ""  # 无对应知识文件不注入


def test_agent_knowledge_version_fingerprint():
    """知识指纹入缓存键：不同 Agent 指纹不同，无知识文件为 a-"""
    from app.agents.common import _agent_knowledge_version

    v_discover = _agent_knowledge_version("discover")
    v_score = _agent_knowledge_version("score")
    assert v_discover.startswith("a") and len(v_discover) == 9
    assert v_discover != v_score
    assert _agent_knowledge_version("position") == "a-"


def test_agent_call_injects_knowledge_section(monkeypatch):
    """agent_call 拼接的 system prompt 含战法知识库段（段序在 Agent 专属 Prompt 之前，
    知识指纹入缓存键：编辑知识文件后 LLM 缓存自动失效）"""
    from app.agents.common import agent_call
    from app.agents.schemas import MarketConditionOutput

    captured = {}

    def _fake_call(agent, cache_key, system_prompt, user_prompt, schema, ttl_seconds, model_level):
        captured["sys"] = system_prompt
        captured["cache_key"] = cache_key
        return MarketConditionOutput(dim_index=5, dim_sector=5, dim_money=5,
                                     dim_sentiment=5, dim_risk=5, summary="测试")

    monkeypatch.setattr("app.agents.common.call_llm_cached", _fake_call)
    out = agent_call(agent="market_condition", cache_key="probe", system_prompt="专属段",
                     user_prompt="u", schema=MarketConditionOutput)
    assert "分职能战法知识库" in captured["sys"]
    assert "市况多维综合判定" in captured["sys"]  # market.md 内容
    assert captured["sys"].strip().endswith("专属段")  # 知识段在专属 Prompt 之前
    assert ":a" in captured["cache_key"]  # 知识指纹入缓存键
    assert out.summary == "测试"


def test_knowledge_section_explicit_reference_not_absolute():
    """知识段声明为参考权重：全部 Agent 的知识文本不得以绝对死条件表述"""
    from app.agents.common import _agent_knowledge_text

    for agent in ("discover", "score", "monitor", "sell", "review", "market_condition"):
        text = _agent_knowledge_text(agent)
        if text:
            assert ("参考权重" in text or "参考框架" in text or "动态参考" in text), agent


# ================= 标的类型标识（Schema 强制落地） =================

def _cand(stock_type: str) -> dict:
    return {
        "stock_code": "600519", "stock_name": "贵州茅台", "reason": "量价健康",
        "risk_notice": "估值偏高", "stock_type": stock_type,
        "confidence_tier": "建议关注", "confidence_pct": 72.0,
        "macro_view": "宏观判断", "meso_view": "中观判断", "micro_view": "微观判断",
        "volume_analysis": "主力小幅流入", "risks": ["风险A", "风险B"],
        "focus_type": "低吸",
    }


def test_stock_type_six_categories_valid():
    valid = ["吸筹末期-优选型", "拉升初期-突破型", "拉升中段-趋势型",
             "派发期-高风险型", "下跌期-反弹型", "观察期-蓄势型"]
    for t in valid:
        assert DiscoverCandidate(**_cand(t)).stock_type == t


def test_stock_type_required_and_rejected():
    data = _cand("吸筹末期-优选型")
    del data["stock_type"]
    with pytest.raises(ValidationError):  # 必填：强制落地
        DiscoverCandidate(**data)
    with pytest.raises(ValidationError):  # 非 6 类值拒绝
        DiscoverCandidate(**_cand("随便写的类型"))


# ================= 批量打分并行模式 =================

def test_daily_pipeline_parallel_large_batch(monkeypatch):
    """候选 ≥5 只自动切换并行：并发执行 + 全部落库 + 耗时显著低于串行"""
    import app.graph.router as router

    candidates = [{"stock_code": f"60000{i}", "stock_name": f"并行测试{i}"}
                  for i in range(1, 6)]
    state = {"n": 0, "max_active": 0, "done": 0}
    lock = threading.Lock()

    def _fake_discover(trade_date=None):
        return {"candidates": candidates}

    def _fake_run_score(code, stock_name="", trade_date=None):
        with lock:
            state["n"] += 1
            state["max_active"] = max(state["max_active"], state["n"])
        time.sleep(0.3)
        with lock:
            state["n"] -= 1
            state["done"] += 1
        return {"score_result": {"score": 88}}

    monkeypatch.setattr(router, "run_discover", _fake_discover)
    monkeypatch.setattr(router, "run_score", _fake_run_score)
    t0 = time.monotonic()
    result = router.run_daily_pipeline("2026-08-05")
    elapsed = time.monotonic() - t0

    assert result == {"candidates": 5, "scored": 5}
    assert state["done"] == 5
    assert state["max_active"] >= 2, "大标的池必须并发执行（并行模式未生效）"
    assert elapsed < 1.2, "并行应显著快于串行（5×0.3s 串行 ≥1.5s）"


def test_daily_pipeline_serial_small_batch(monkeypatch):
    """候选 <5 只保持单 Agent 串行模式（结果与并行模式同源一致）"""
    import app.graph.router as router

    candidates = [{"stock_code": "600001", "stock_name": "串行测试"},
                  {"stock_code": "600002", "stock_name": "串行测试2"}]
    state = {"n": 0, "max_active": 0}
    lock = threading.Lock()

    def _fake_discover(trade_date=None):
        return {"candidates": candidates}

    def _fake_run_score(code, stock_name="", trade_date=None):
        with lock:
            state["n"] += 1
            state["max_active"] = max(state["max_active"], state["n"])
        time.sleep(0.05)
        with lock:
            state["n"] -= 1
        return {"score_result": {"score": 80}}

    monkeypatch.setattr(router, "run_discover", _fake_discover)
    monkeypatch.setattr(router, "run_score", _fake_run_score)
    result = router.run_daily_pipeline("2026-08-05")
    assert result == {"candidates": 2, "scored": 2}
    assert state["max_active"] == 1, "小标的池保持串行（单 Agent 模式）"


def test_parallel_result_consistency(monkeypatch):
    """并行下输入输出映射无串扰：每只候选都经同一 run_score 独立打分（同 prompt/schema），
    代码/名称正确透传——结果与单 Agent 模式天然一致"""
    import app.graph.router as router

    candidates = [{"stock_code": f"60000{i}", "stock_name": f"一致性{i}"}
                  for i in range(1, 6)]
    seen = {}

    def _fake_discover(trade_date=None):
        return {"candidates": candidates}

    def _fake_run_score(code, stock_name="", trade_date=None):
        seen[code] = stock_name
        return {"score_result": {"score": 80}}

    monkeypatch.setattr(router, "run_discover", _fake_discover)
    monkeypatch.setattr(router, "run_score", _fake_run_score)
    result = router.run_daily_pipeline("2026-08-05")
    assert result == {"candidates": 5, "scored": 5}
    assert seen == {c["stock_code"]: c["stock_name"] for c in candidates}  # 无串扰
