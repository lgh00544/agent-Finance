"""交易复盘建议「驳回迭代」闭环测试：
1. repo 层迭代流转：insert → reject 快照 → rethink 回写 → adopt 状态机
2. 旧结构表增量迁移（_ensure_review_result_columns 幂等补列不丢数据）
3. 复盘 Agent 的驳回原因/迭代历史注入文本格式"""
import pytest
from sqlalchemy import create_engine, select

from app.db import repo
from app.db.models import ReviewResult
from app.db.session import SessionLocal, _ensure_review_result_columns, init_db
from agent_prompts import review_prompt


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()


def _insert_review(feedback=None) -> int:
    return repo.insert_review(
        "601012", "测试股X", 77, "2026-08-01", 20, 5.5,
        {"入场逻辑": "回踩企稳", "兑现程度": "部分兑现"},
        "止盈应分批", feedback or {"偏好": "提高景气权重"})


def test_review_default_suggestion_state():
    """默认：待审核、第 1 版、无迭代历史"""
    rid = _insert_review()
    row = repo.get_review(rid)
    assert row.suggest_status == "pending"
    assert row.suggest_iteration == 1
    assert row.suggest_history == []
    assert row.reject_reason == ""


def test_reject_snapshots_history_and_sets_status():
    """驳回：当前建议快照 + 驳回原因写入 history，状态置已驳回"""
    rid = _insert_review(feedback={"偏好": "提高景气权重",
                                   "profile_suggestion": {"field": "风控容忍度",
                                                          "value": "单笔回撤容忍 6%",
                                                          "reason": "止损执行偏慢"}})
    repo.append_review_iteration(rid, "不认可该结论，止损已经够严了")

    row = repo.get_review(rid)
    assert row.suggest_status == "rejected"
    assert row.reject_reason == "不认可该结论，止损已经够严了"
    assert row.suggest_iteration == 1
    assert row.suggest_history == [{
        "iteration": 1,
        "suggestion": {"field": "风控容忍度", "value": "单笔回撤容忍 6%",
                       "reason": "止损执行偏慢"},
        "reject_reason": "不认可该结论，止损已经够严了",
    }]


def test_rethink_applies_new_suggestion_and_bumps_iteration():
    """重思考回写：新建议覆盖 feedback，迭代 +1，状态回待审核"""
    rid = _insert_review()
    repo.append_review_iteration(rid, "第一轮驳回")

    new_feedback = {"偏好": "更关注资金流向",
                    "profile_suggestion": {"field": "选股倾向", "value": "更重视主力资金流",
                                           "reason": "用户偏好资金面"}}
    repo.apply_rethink_suggestion(rid, new_feedback, 2)

    row = repo.get_review(rid)
    assert row.suggest_status == "pending"
    assert row.suggest_iteration == 2
    assert row.feedback["profile_suggestion"]["field"] == "选股倾向"
    assert len(row.suggest_history) == 1


def test_multi_round_iteration_trace_persisted():
    """多轮驳回：完整迭代轨迹持久化，按序可追溯"""
    rid = _insert_review(feedback={"profile_suggestion": {"field": "风控容忍度", "value": "6%",
                                                          "reason": "第一版"}})
    repo.append_review_iteration(rid, "太激进")
    repo.apply_rethink_suggestion(rid, {"profile_suggestion": {"field": "风控容忍度",
                                                               "value": "5%", "reason": "第二版"}}, 2)
    repo.append_review_iteration(rid, "还是太严")
    repo.apply_rethink_suggestion(rid, {"profile_suggestion": {"field": "仓位上限",
                                                               "value": "10%", "reason": "第三版"}}, 3)

    row = repo.get_review(rid)
    assert row.suggest_iteration == 3
    assert [h["iteration"] for h in row.suggest_history] == [1, 2]
    assert row.suggest_history[0]["reject_reason"] == "太激进"
    assert row.suggest_history[1]["reject_reason"] == "还是太严"
    assert row.suggest_history[1]["suggestion"]["value"] == "5%"


def test_adopt_sets_status_and_reject_history_feed():
    """采纳后状态已采纳；驳回历史扁平化输出供复盘 Agent 注入"""
    rid = _insert_review(feedback={"profile_suggestion": {"field": "风控容忍度", "value": "6%",
                                                          "reason": "止损慢"}})
    repo.append_review_iteration(rid, "规则过于严格")
    repo.apply_rethink_suggestion(rid, {"profile_suggestion": {"field": "风控容忍度",
                                                               "value": "7%", "reason": "折中"}}, 2)
    repo.update_review_suggestion_status(rid, "adopted")

    assert repo.get_review(rid).suggest_status == "adopted"

    hist = repo.get_review_reject_history(code="601012", limit=10)
    assert hist, "应有驳回历史"
    first = hist[0]
    assert first["iteration"] == 1
    assert first["field"] == "风控容忍度"
    assert first["value"] == "6%"
    assert first["suggest_reason"] == "止损慢"
    assert first["reject_reason"] == "规则过于严格"

    # 注入文本：含历史驳回记录，提醒避免重复同类建议
    section = review_prompt.build_reject_history_section(hist)
    assert "历史驳回记录" in section
    assert "规则过于严格" in section


def test_reject_history_section_empty_when_no_rows():
    assert review_prompt.build_reject_history_section([]) == ""


def test_rethink_user_prompt_contains_context():
    """重思考 prompt：原始结论 + 驳回原因 + 迭代轨迹齐全"""
    prompt = review_prompt.build_rethink_user_prompt(
        '{"plan_vs_actual": {}}', "不符合我的交易风格",
        [{"iteration": 1, "suggestion": {"field": "风控容忍度", "value": "6%"},
          "reject_reason": "不符合我的交易风格"}])
    assert "不符合我的交易风格" in prompt
    assert "历史迭代轨迹" in prompt
    assert "风控容忍度" in prompt
    assert "profile_suggestion 的 field 必须是用户偏好档案中真实存在的字段名" in prompt


def test_legacy_table_migration_adds_columns_idempotent(tmp_path):
    """旧结构 review_result（无 4 新列）→ 增量补列，数据不丢，可重复执行"""
    eng = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with eng.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE review_result ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "stock_code VARCHAR(16), stock_name VARCHAR(64), holding_id INTEGER, "
            "exit_date VARCHAR(10), hold_days INTEGER, pnl_pct FLOAT, "
            "plan_vs_actual JSON, lesson TEXT, feedback JSON, created_at DATETIME)")
        conn.exec_driver_sql(
            "INSERT INTO review_result (stock_code, stock_name, holding_id, exit_date, "
            "hold_days, pnl_pct, plan_vs_actual, lesson, feedback) "
            "VALUES ('601012', '隆基绿能', 1, '2026-07-20', 15, -3.2, '{}', '旧数据', '{}')")

    _ensure_review_result_columns(eng)
    _ensure_review_result_columns(eng)  # 幂等：第二次不报错

    with eng.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(review_result)")}
        for col in ("suggest_status", "reject_reason", "suggest_iteration", "suggest_history"):
            assert col in cols, f"迁移后缺少列 {col}"
        row = conn.exec_driver_sql("SELECT lesson, suggest_status, suggest_iteration "
                                   "FROM review_result").fetchone()
        assert row[0] == "旧数据", "迁移不应丢数据"
        assert row[1] == "pending", "迁移默认状态应为待审核"
        assert row[2] == 1, "迁移默认迭代次数应为 1"
