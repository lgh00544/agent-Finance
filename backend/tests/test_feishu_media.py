# -*- coding: utf-8 -*-
"""飞书批3 多媒体：图片识别+人工确认落库 / 取消丢弃 / 双关路径 / video 收存 / 幂等 / 超限。
识别与下载均 mock（不触真实网络 / 不调 minimax / paddle）。"""
import tempfile
from pathlib import Path

from app.db import repo
from app.services import feishu_bridge as fb

_REAL_DEDUP = fb._dedup  # 幂等测试需真实实现（其他用例覆盖为恒 True）


def _run_image(fb_, content, download=lambda mid, fk, rt: b"\x89PNG\r\n\x1a\nfake"):
    out = []
    fb_._reply = lambda oid, t: out.append(t)
    fb_._download_resource = download
    fb_._pending.clear()
    fb_._recent_files.clear()
    fb_._dedup = lambda k: True
    fb_._handle_image("ou_t", "m", content)
    return out


def test_holding_preview_then_confirm_writes(monkeypatch):
    fb._recognize_holding_image = lambda data: {
        "recognized": [{"stock_code": "600519", "stock_name": "贵州茅台", "shares": 100,
                        "cost_price": 1800.0, "current_price": 1900.0, "pnl_pct": 5.5}],
        "account": None, "raw_text": ""}
    inserted = []
    monkeypatch.setattr(repo, "insert_holding", lambda *a, **k: inserted.append(a) or 1)
    out = _run_image(fb, '{"image_key":"k1"}')
    assert "确认" in out[0] and "600519" in out[0]
    r = fb._confirm_or_cancel("ou_t", "确认")
    assert "已保存 1 条" in r and len(inserted) == 1
    assert inserted[0][0] == "600519" and inserted[0][4] == 100


def test_cancel_discards_without_write(monkeypatch):
    fb._recognize_holding_image = lambda data: {
        "recognized": [{"stock_code": "600519", "stock_name": "贵州茅台", "shares": 100,
                        "cost_price": 1800.0, "current_price": 1900.0, "pnl_pct": 5.5}],
        "account": None, "raw_text": ""}
    inserted = []
    monkeypatch.setattr(repo, "insert_holding", lambda *a, **k: inserted.append(a) or 1)
    _run_image(fb, '{"image_key":"k2"}')
    r = fb._confirm_or_cancel("ou_t", "取消")
    assert "已取消" in r and not inserted and not fb._pending


def test_both_engines_off_replies_unable(monkeypatch):
    """MINIMAX_ENABLE=false + OCR_ENABLE=false → 明确回无法识别，不报错"""
    def _reject(data):
        raise RuntimeError("无可用识别引擎")
    fb._recognize_holding_image = _reject
    out = _run_image(fb, '{"image_key":"k3"}')
    assert "无法识别" in out[0]


def test_non_holding_image_described(monkeypatch):
    fb._recognize_holding_image = lambda data: {"recognized": [], "account": None, "raw_text": ""}
    fb._describe_image = lambda data: "K线图描述"
    out = _run_image(fb, '{"image_key":"k4"}')
    assert "K线图描述" in out[0]


def test_video_saved_to_media_dir(monkeypatch):
    media = Path(tempfile.mkdtemp())
    fb._media_dir = lambda: media
    out = []
    fb._reply = lambda oid, t: out.append(t)
    fb._dedup = lambda k: True
    fb._download_resource = lambda mid, fk, rt: b"\x00\x00\x00\x1Cftyp" + b"0" * 300
    fb._handle_file("ou_t", "m", '{"file_key":"f1","file_name":"clip.mp4"}')
    assert "已收到并保存" in out[0]
    assert any(f.name.endswith(".mp4") for f in media.iterdir())


def test_oversize_rejected():
    out = _run_image(fb, '{"image_key":"big"}',
                     download=lambda mid, fk, rt: b"x" * (10 * 1024 * 1024 + 1))
    assert "文件过大" in out[0]


def test_same_file_key_idempotent():
    fb._recent_files.clear()
    out = []
    fb._reply = lambda oid, t: out.append(t)
    fb._dedup = _REAL_DEDUP  # 用真实幂等
    fb._download_resource = lambda mid, fk, rt: b"small"
    fb._recognize_holding_image = lambda data: {"recognized": [], "account": None, "raw_text": ""}
    fb._handle_image("ou_t", "m", '{"image_key":"same"}')
    fb._handle_image("ou_t", "m", '{"image_key":"same"}')
    assert len(out) == 1, "同 file_key 第二次应幂等跳过"
    fb._recent_files.clear()


def test_pending_expired_no_confirm():
    fb._pending["ou_t"] = {"result": {"recognized": []}, "expires": 0.0}
    assert fb._confirm_or_cancel("ou_t", "确认") is None
    assert not fb._pending
