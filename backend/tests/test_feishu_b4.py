# -*- coding: utf-8 -*-
"""飞书批4 增强：卡片回调确认/取消 / 群聊@过滤 / 日报组装（mock 服务不触网络）。"""
from types import SimpleNamespace

from app.services import feishu_bridge as fb


def _card(action, operator="ou_adm"):
    return SimpleNamespace(event=SimpleNamespace(
        operator=SimpleNamespace(open_id=operator),
        action=SimpleNamespace(value={"action": action})))


def test_card_confirm_applies(monkeypatch):
    fb._pending.clear()
    out = []
    monkeypatch.setattr(fb, "_reply", lambda oid, t: out.append(t))
    monkeypatch.setattr(fb, "_admin_open_ids", lambda: ["ou_adm"])
    def _mock_apply(oid, p):
        fb._pending.pop(oid, None)
        out.append("APPLIED")
        return "已保存"
    monkeypatch.setattr(fb, "_apply_pending", _mock_apply)
    fb._pending["ou_adm"] = {"result": {}, "expires": 10 ** 12}
    fb._on_card_action(_card("confirm"))
    assert "APPLIED" in out and not fb._pending


def test_card_cancel_discards(monkeypatch):
    fb._pending.clear()
    out = []
    monkeypatch.setattr(fb, "_reply", lambda oid, t: out.append(t))
    monkeypatch.setattr(fb, "_admin_open_ids", lambda: ["ou_adm"])
    fb._pending["ou_adm"] = {"result": {}, "expires": 10 ** 12}
    fb._on_card_action(_card("cancel"))
    assert "已取消" in out[0] and not fb._pending


def test_card_non_admin_ignored(monkeypatch):
    fb._pending.clear()
    out = []
    monkeypatch.setattr(fb, "_reply", lambda oid, t: out.append(t))
    monkeypatch.setattr(fb, "_admin_open_ids", lambda: ["ou_adm"])
    fb._pending["ou_evil"] = {"result": {}, "expires": 10 ** 12}
    fb._on_card_action(_card("confirm", operator="ou_evil"))
    assert out == [] and fb._pending
    fb._pending.clear()


def test_card_expired(monkeypatch):
    fb._pending.clear()
    out = []
    monkeypatch.setattr(fb, "_reply", lambda oid, t: out.append(t))
    monkeypatch.setattr(fb, "_admin_open_ids", lambda: ["ou_adm"])
    fb._pending["ou_adm"] = {"result": {}, "expires": 0.0}
    fb._on_card_action(_card("confirm"))
    assert "过期" in out[0] and not fb._pending


def test_group_mention_filter(monkeypatch):
    monkeypatch.setattr("app.services.feishu_sender.get_bot_open_id", lambda: "ou_bot")
    mk = lambda chat_type, mentions: SimpleNamespace(
        chat_type=chat_type, mentions=mentions, message_type="text",
        message_id="m", content='{"text":"hi"}')
    bot = SimpleNamespace(id=SimpleNamespace(open_id="ou_bot"))
    other = SimpleNamespace(id=SimpleNamespace(open_id="ou_other"))
    assert fb._is_mentioned_bot(mk("group", [bot])) is True
    assert fb._is_mentioned_bot(mk("group", [other])) is False
    assert fb._is_mentioned_bot(mk("group", [])) is False


def test_daily_report_assembly(monkeypatch):
    import app.services.ths_pnl as ths_mod

    from app.scheduler import jobs

    sent = []
    monkeypatch.setattr("app.services.feishu_sender.send_text", lambda oid, t: sent.append(t))
    monkeypatch.setattr(ths_mod, "get_snapshot", lambda: {"pnl_yk": 1234.5, "pnl_pct": 2.3})
    monkeypatch.setattr("app.services.holding_view.build_holding_view",
                        lambda: {"rows": [{"market_value": 100000.0, "pnl_amount": 5000.0}]})
    monkeypatch.setattr(jobs.repo, "list_candidates",
                        lambda d, n: [{"stock_code": "600519", "stock_name": "贵州茅台"}])
    monkeypatch.setattr(jobs.repo, "list_alerts",
                        lambda n: [{"created_at": "2026-08-28 10:00:00"}])
    monkeypatch.setattr(jobs, "_is_trading_day", lambda d: True)
    monkeypatch.setattr(jobs.settings, "feishu_daily_report", True)
    monkeypatch.setattr(jobs.settings, "feishu_admin_open_ids", "ou_adm")
    monkeypatch.setattr(jobs.time, "strftime", lambda *a, **k: "2026-08-28")
    jobs.feishu_daily_report_job()
    assert sent and "今日盈亏" in sent[0] and "告警 1 条" in sent[0]


def test_daily_report_disabled_noop(monkeypatch):
    import app.services.feishu_sender as fs

    from app.scheduler import jobs

    sent = []
    monkeypatch.setattr(fs, "send_text", lambda oid, t: sent.append(t))
    monkeypatch.setattr(jobs.settings, "feishu_daily_report", False)
    jobs.feishu_daily_report_job()
    assert sent == []  # 开关 false 直接 return 不发


def test_status_pending_count(monkeypatch):
    fb._pending.clear()
    fb._pending["ou_adm"] = {"result": {}, "expires": 10 ** 12}
    s = fb.status()
    assert s["pending_count"] == 1
    fb._pending.clear()
