"""Batch 3: chat router reads system map without changing dispatch behavior."""
from app.prompts.chat_router import RouteIntent
from app.services import chat_router


def test_route_intent_accepts_legacy_json():
    result = RouteIntent.model_validate({"intent": "chat"})
    assert result.target_agent == ""
    assert result.workflow_id == ""
    assert result.permission_note == ""


def test_route_map_failure_keeps_existing_intent(monkeypatch):
    monkeypatch.setattr(chat_router, "_route_regex", lambda text: None)
    monkeypatch.setattr(chat_router.system_map_registry, "get_system_map_summary",
                        lambda: (_ for _ in ()).throw(RuntimeError("map unavailable")))

    class _Result:
        intent = "score"
        params = type("Params", (), {"code": "600519", "name": "", "agent": ""})()
        target_agent = "score"
        workflow_id = "score"
        required_params = ["stock_code"]
        permission_note = ""
        reply_hint = ""

    monkeypatch.setattr(chat_router, "llm_call_json", lambda *args, **kwargs: _Result())
    intent, params, _ = chat_router.route("分析贵州茅台")
    assert intent == "score"
    assert params["code"] == "600519"


def test_score_route_uses_system_map_metadata():
    intent, params, hint = chat_router.route("分析 600519")
    assert intent == "score"
    assert params["target_agent"] == "score"
    assert params["workflow_id"] == "score"
    assert "权限" in hint


def test_unknown_capability_falls_back_to_chat(monkeypatch):
    monkeypatch.setattr(chat_router, "_route_regex", lambda text: None)

    class _Result:
        intent = "score"
        params = type("Params", (), {"code": "", "name": "", "agent": ""})()
        target_agent = "not_registered"
        workflow_id = "unknown_workflow"
        required_params = []
        permission_note = ""
        reply_hint = ""

    monkeypatch.setattr(chat_router, "llm_call_json", lambda *args, **kwargs: _Result())
    intent, _, hint = chat_router.route("调用未知能力")
    assert intent == "chat"
    assert "未注册能力" in hint


def test_route_and_execute_preserves_simple_command(monkeypatch):
    captured = {}
    monkeypatch.setattr(chat_router.chat_handlers, "dispatch",
                        lambda text, intent, params, hint, open_id: captured.update(
                            {"intent": intent, "params": params}) or "ok")
    assert chat_router.route_and_execute("查持仓", "", "ou_1") == "ok"
    assert captured["intent"] == "holdings"
