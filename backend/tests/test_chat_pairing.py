"""Agent 对话历史「问答配对」算法测试（chat_cards.pair_messages 纯函数，不触网）：

1. meta.user_msg_id 精确配对（qa/rule 标准路径，后端已落库的绑定字段）
2. 旧数据无 user_msg_id → 相邻顺序配对 fallback（user 在前、assistant 紧随）
3. learn 确认追加记录（孤儿 assistant）并入最近同类单元
4. 孤儿 user 独立成卡（status=orphan，无回答）
5. user_msg_id 指向不存在的记录 → 游离 assistant 独立成卡
6. 单元排序：最新在前（max_id 降序）
7. 空列表返回空
"""
import sys
from pathlib import Path

_STREAMLIT_DIR = str(Path(__file__).resolve().parents[2] / "streamlit")
if _STREAMLIT_DIR not in sys.path:
    sys.path.insert(0, _STREAMLIT_DIR)

from chat_cards import pair_messages  # noqa: E402


def _msg(i: int, role: str, mtype: str = "qa", user_msg_id: int | None = None,
         verdict: str = "", kid: int | None = None, meta: dict | None = None) -> dict:
    """构造一条对话消息记录（字段对齐 repo.list_chat_messages 返回结构）"""
    m = {"id": i, "agent": "discover", "role": role, "message_type": mtype,
         "content": f"内容{i}", "verdict": verdict, "knowledge_id": kid,
         "meta": meta or {}, "created_at": f"2026-08-09 10:00:0{i % 10}"}
    if user_msg_id is not None:
        m["meta"]["user_msg_id"] = user_msg_id
    return m


def test_pairs_by_user_msg_id():
    """标准路径：assistant.meta.user_msg_id 精确绑定 user"""
    msgs = [_msg(2, "assistant", meta={"user_msg_id": 1, "confidence": 80}),
            _msg(1, "user")]  # 后端返回格式：id 降序
    units = pair_messages(msgs)
    assert len(units) == 1
    u = units[0]
    assert u["user"]["id"] == 1
    assert [a["id"] for a in u["answers"]] == [2]
    assert u["status"] == "ok"
    assert u["kind"] == "qa"


def test_fallback_adjacent_pairing_for_legacy():
    """旧数据无 user_msg_id：按 id 相邻顺序配对（user 在前、assistant 紧随）"""
    msgs = [_msg(10, "assistant"), _msg(9, "user")]
    units = pair_messages(msgs)
    assert len(units) == 1
    assert units[0]["user"]["id"] == 9
    assert units[0]["answers"][0]["id"] == 10
    assert units[0]["status"] == "ok"


def test_learn_confirm_record_merged_into_unit():
    """learn：上传 user + 摘要 assistant + 确认追加 assistant（无 user_msg_id）并入同一单元"""
    msgs = [_msg(7, "assistant", "learn", meta={"saved": [{"title": "战法A", "agent_tag": "all"}]}),
            _msg(6, "assistant", "learn", meta={"point_count": 2,
                                                "points": [{"title": "P1"}, {"title": "P2"}]}),
            _msg(5, "user", "learn")]
    units = pair_messages(msgs)
    assert len(units) == 1
    u = units[0]
    assert u["user"]["id"] == 5
    assert [a["id"] for a in u["answers"]] == [6, 7]  # 摘要在前、确认在后（时序保持）
    assert u["kind"] == "learn"
    assert u["status"] == "ok"


def test_orphan_user_standalone_card():
    """孤儿 user（无任何回答记录）独立成卡，status=orphan"""
    units = pair_messages([_msg(3, "user")])
    assert len(units) == 1
    assert units[0]["user"]["id"] == 3
    assert units[0]["answers"] == []
    assert units[0]["status"] == "orphan"


def test_dangling_assistant_standalone_card():
    """user_msg_id 指向不存在的记录 → 游离 assistant 独立成卡（不丢记录）"""
    units = pair_messages([_msg(8, "assistant", "rule", meta={"user_msg_id": 999})])
    assert len(units) == 1
    assert units[0]["user"] is None
    assert units[0]["answers"][0]["id"] == 8
    assert units[0]["kind"] == "rule"


def test_multi_exchanges_sorted_newest_first():
    """多轮对话互不串扰，单元按最新 id 降序（最新对话在最顶部）"""
    msgs = [_msg(20, "assistant", meta={"user_msg_id": 19}),
            _msg(19, "user"),
            _msg(11, "assistant", meta={"user_msg_id": 10}),
            _msg(10, "user")]
    units = pair_messages(msgs)
    assert [u["max_id"] for u in units] == [20, 11]
    assert units[0]["user"]["id"] == 19
    assert units[1]["user"]["id"] == 10


def test_mixed_legacy_and_linked_records():
    """同一会话内 精确配对 + 相邻 fallback 混合：不重不漏"""
    msgs = [_msg(30, "assistant", meta={"user_msg_id": 29}),   # 精确配对
            _msg(29, "user"),
            _msg(22, "assistant"),                             # 旧数据 fallback
            _msg(21, "user")]
    units = pair_messages(msgs)
    assert len(units) == 2
    assert [u["max_id"] for u in units] == [30, 22]
    assert units[0]["answers"][0]["id"] == 30
    assert units[1]["answers"][0]["id"] == 22


def test_empty_list():
    assert pair_messages([]) == []
