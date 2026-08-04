"""MiniMax M3 可选多模态能力测试（不触网：requests 全部 mock）：
1. 引擎工厂：默认关闭返回 None（零开销）/ 启用无密钥降级 / 启用返回 MiniMax 实现
2. MiniMax 请求格式：OpenAI 兼容端点 + Bearer 密钥 + base64 图片 + 关闭思考
3. 云端 OCR 引擎：JSON 解析 → 统一输出字段；失败/解析失败 → None（回退本地）
4. 识别降级链：云端优先 → 失败回退本地 PaddleOCR，不阻塞；同图缓存不二次调用
注意：每个用例使用独立图片字节，避免全局缓存键串扰。
"""
import json

import pytest

from app.core.config import settings
from app.services import multimodal, ocr
from app.services.multimodal import MiniMaxClient, get_multimodal_client
from app.services.ocr import (
    MiniMaxOcrEngine, _extract_account_local, _find_amount_after,
    _normalize_minimax_account, _normalize_minimax_row, _parse_minimax,
)


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _mock_post(monkeypatch, responder):
    """responder(url, **kwargs) -> 返回体 / 抛异常"""
    monkeypatch.setattr("requests.post",
                        lambda url, json=None, headers=None, timeout=15: responder(url, json, headers))


def _enable_minimax(monkeypatch, ocr_engine=False):
    monkeypatch.setattr(settings, "minimax_enable", True)
    monkeypatch.setattr(settings, "minimax_api_key", "test-minimax-key")
    monkeypatch.setattr(settings, "minimax_base_url", "https://api.minimax.test/v1")
    monkeypatch.setattr(settings, "minimax_model", "MiniMax-M3")
    monkeypatch.setattr(settings, "minimax_ocr_enable", ocr_engine)
    monkeypatch.setattr(multimodal, "_client", None)  # 工厂单例隔离


# ==================== 引擎工厂（默认关闭零开销） ====================

def test_factory_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "minimax_enable", False)
    assert get_multimodal_client() is None


def test_factory_enabled_without_key_returns_none(monkeypatch):
    _enable_minimax(monkeypatch)
    monkeypatch.setattr(settings, "minimax_api_key", "")
    assert get_multimodal_client() is None


def test_factory_enabled_returns_minimax_client(monkeypatch):
    _enable_minimax(monkeypatch)
    assert isinstance(get_multimodal_client(), MiniMaxClient)


def test_factory_disabled_zero_network(monkeypatch):
    """默认关闭时 analyze_image 不可能被调用（工厂恒为 None，零开销）"""
    monkeypatch.setattr(settings, "minimax_enable", False)
    assert get_multimodal_client() is None


# ==================== MiniMax 请求格式（OpenAI 兼容） ====================

def test_analyze_image_request_format(monkeypatch):
    _enable_minimax(monkeypatch)
    captured = {}

    def _responder(url, body, headers):
        captured["url"] = url
        captured["body"] = body
        captured["headers"] = headers
        return _FakeResp({"choices": [{"message": {"content": "识别结果"}}]})

    _mock_post(monkeypatch, _responder)
    out = MiniMaxClient().analyze_image(b"fake-png-bytes", "识别图中文字", max_tokens=1000)
    assert out == "识别结果"
    assert captured["url"].endswith("/chat/completions")       # OpenAI 兼容端点
    assert captured["headers"]["Authorization"] == "Bearer test-minimax-key"
    body = captured["body"]
    assert body["model"] == "MiniMax-M3"
    assert body["max_tokens"] == 1000
    assert body["thinking"] == {"type": "disabled"}            # OCR 直接作答，关闭思考
    parts = body["messages"][0]["content"]
    assert parts[0] == {"type": "text", "text": "识别图中文字"}
    img = parts[1]["image_url"]["url"]
    assert img.startswith("data:image/png;base64,")            # base64 内联图片
    assert img.count(";") == 1  # 仅 mime 与 base64 之间一个分号，密钥绝不混入图片体
    assert settings.minimax_api_key not in img


def test_analyze_image_mime_guess(monkeypatch):
    captured = {}
    _mock_post(monkeypatch, lambda url, body, headers: (captured.update(url=url, body=body),
                                                        _FakeResp({"choices": [{"message": {"content": "x"}}]}))[1])
    jpg = b"\xff\xd8\xff\xe0" + b"a" * 10
    MiniMaxClient().analyze_image(jpg, "p")
    url = captured["body"]["messages"][0]["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")


def test_analyze_image_retries_then_raises(monkeypatch):
    calls = {"n": 0}

    def _boom(url, body, headers):
        calls["n"] += 1
        raise ConnectionError("网络不可达")

    _mock_post(monkeypatch, _boom)
    with pytest.raises(RuntimeError, match="MiniMax 多模态请求失败"):
        MiniMaxClient().analyze_image(b"img", "p")
    assert calls["n"] == 2  # 首试 + 1 次退避重试


def test_analyze_image_oversize_rejected(monkeypatch):
    calls = {"n": 0}
    _mock_post(monkeypatch, lambda url, body, headers: (calls.__setitem__("n", calls["n"] + 1), _FakeResp({"choices": []}))[1])
    with pytest.raises(RuntimeError, match="图片过大"):
        MiniMaxClient().analyze_image(b"x" * (multimodal.MAX_IMAGE_BYTES + 1), "p")
    assert calls["n"] == 0  # 超限直接拒绝，不发起请求


# ==================== 云端 OCR 引擎解析（对齐统一输出字段） ====================

class _FakeClient:
    """模拟 MultimodalClient：返回预设文本或抛异常"""

    def __init__(self, text=None, exc=None):
        self._text = text
        self._exc = exc
        self.calls = []

    def analyze_image(self, image_bytes, prompt, max_tokens=2048):
        self.calls.append(len(image_bytes))
        if self._exc is not None:
            raise self._exc
        return self._text


def _valid_json_text():
    return json.dumps([
        {"stock_code": "600519", "stock_name": "贵州茅台", "shares": 100,
         "cost_price": 1520.0, "current_price": 1550.3,
         "pnl_amount": 3030.0, "pnl_pct": -1.9},
        {"stock_code": "300750", "stock_name": "宁德时代", "shares": 2000,
         "cost_price": 198.45, "current_price": 210.62,
         "pnl_amount": 24340.0, "pnl_pct": 6.13},
    ], ensure_ascii=False)


def test_minimax_engine_parse_unified_fields():
    client = _FakeClient(text=_valid_json_text())
    result = MiniMaxOcrEngine(client).recognize(b"img-a1", "x.png")
    assert result is not None
    rows = result["recognized"]
    assert len(rows) == 2
    r1 = rows[0]
    # 与本地引擎 _complete_row 完全一致的统一输出结构（七字段）
    assert set(r1) == {"stock_code", "stock_name", "shares", "cost_price",
                       "current_price", "pnl_amount", "pnl_pct",
                       "confidence", "source_line"}
    assert r1["stock_code"] == "600519"
    assert r1["stock_name"] == "贵州茅台"
    assert r1["shares"] == 100
    assert r1["cost_price"] == 1520.0
    assert r1["current_price"] == 1550.3
    assert r1["pnl_amount"] == 3030.0
    assert r1["pnl_pct"] == -1.9
    assert "600519" in r1["source_line"]
    assert isinstance(result["raw_text"], str)


def test_minimax_engine_tolerates_fence_and_prefix():
    """模型输出带 ```json 围栏/前后说明文字时仍能提取 JSON 数组"""
    text = "以下是识别结果：\n```json\n" + _valid_json_text() + "\n```\n请核对"
    result = MiniMaxOcrEngine(_FakeClient(text=text)).recognize(b"img-a2", "x.png")
    assert result is not None and len(result["recognized"]) == 2


def test_minimax_engine_bad_fields_normalized():
    """非法字段值 → 置空/None（由前端提示人工补全，不编造）"""
    client = _FakeClient(text=json.dumps([
        {"stock_code": "ABC123", "stock_name": "!!!", "shares": "1,000",
         "cost_price": "abc", "current_price": 12.34,
         "pnl_amount": "+1,234.5", "pnl_pct": "-3.2%"}]))
    rows = MiniMaxOcrEngine(client).recognize(b"img-a3", "x.png")["recognized"]
    r = rows[0]
    assert r["stock_code"] == ""        # 非 6 位数字代码 → 置空
    assert r["stock_name"] == ""
    assert r["shares"] == 1000          # 千分位字符串转 int
    assert r["cost_price"] is None      # 脏数据 → None
    assert r["current_price"] == 12.34
    assert r["pnl_amount"] == 1234.5    # 带号千分位金额
    assert r["pnl_pct"] == -3.2         # 百分比文本 → 数值


def test_minimax_engine_chinese_alias_fields():
    """模型输出中文别名键名时同样归一（盈亏金额/盈亏比例）"""
    client = _FakeClient(text=json.dumps([
        {"股票代码": "600519", "股票名称": "贵州茅台", "持仓数量": 100,
         "持仓成本": 1520.0, "当前市价": 1550.3,
         "持仓盈亏金额": "+3,030.00", "持仓盈亏比例": "-1.9%"}]))
    r = MiniMaxOcrEngine(client).recognize(b"img-a3b", "x.png")["recognized"][0]
    assert r["stock_code"] == "600519"
    assert r["stock_name"] == "贵州茅台"
    assert r["shares"] == 100
    assert r["pnl_amount"] == 3030.0
    assert r["pnl_pct"] == -1.9


def test_minimax_engine_failure_returns_none():
    client = _FakeClient(exc=ConnectionError("云端不可达"))
    assert MiniMaxOcrEngine(client).recognize(b"img-a4", "x.png") is None


def test_minimax_engine_unparseable_returns_none():
    client = _FakeClient(text="抱歉，无法识别图片内容")
    assert MiniMaxOcrEngine(client).recognize(b"img-a5", "x.png") is None


def test_parse_minimax_variants():
    """兼容两种输出形态：旧版纯数组 / 新版 {account, holdings} 对象"""
    rows, account = _parse_minimax('[{"a": 1}]')
    assert rows == [{"a": 1}] and account is None
    rows, _ = _parse_minimax("前缀 [{ }] 后缀")
    assert rows is not None
    rows, account = _parse_minimax("无数组内容")
    assert rows == [] and account is None
    rows, account = _parse_minimax('{"account": {"total_asset": 100}, "holdings": [{"a": 1}]}')
    assert rows == [{"a": 1}] and account == {"total_asset": 100}
    # 对象里 holdings 为空但含 account → 保留 account（前端仍可保存基准）
    rows, account = _parse_minimax('{"holdings": [], "account": {"total_asset": 50}}')
    assert rows == [] and account == {"total_asset": 50}


def test_normalize_minimax_account_variants():
    """账户汇总字段规范化：中英键名/小数比例 ×100/缺字段处理"""
    acc = _normalize_minimax_account({"total_asset": "123456.78", "available_cash": "40000",
                                      "position_pct": "40.5"})
    assert acc["total_asset"] == 123456.78
    assert acc["available_cash"] == 40000.0
    assert acc["position_pct"] == 40.5

    acc = _normalize_minimax_account({"总资产": 888888.0, "可用资金": 0, "仓位比例": "0.405"})
    assert acc["total_asset"] == 888888.0
    assert acc["position_pct"] == 40.5  # 小数形式统一为百分比

    assert _normalize_minimax_account(None) is None
    assert _normalize_minimax_account({}) is None          # 无总资产 → None
    assert _normalize_minimax_account({"available_cash": 1}) is None
    acc = _normalize_minimax_account({"total_asset": 1000, "position_pct": "40%"})
    assert acc == {"total_asset": 1000.0, "position_pct": 40.0}  # 缺可用资金不伪造


def test_minimax_engine_object_output_with_account():
    """新版对象输出（含账户汇总）→ 持仓行 + account 同时归一"""
    text = json.dumps({
        "account": {"total_asset": "1234567.89", "available_cash": "456789.01",
                    "position_pct": "63.0"},
        "holdings": [
            {"stock_code": "600519", "stock_name": "贵州茅台", "shares": 100,
             "cost_price": 1520.0, "current_price": 1550.3,
             "pnl_amount": 3030.0, "pnl_pct": -1.9},
        ],
    }, ensure_ascii=False)
    result = MiniMaxOcrEngine(_FakeClient(text=text)).recognize(b"img-a6", "x.png")
    assert result is not None
    assert result["recognized"][0]["stock_code"] == "600519"
    assert result["account"] == {"total_asset": 1234567.89,
                                 "available_cash": 456789.01, "position_pct": 63.0}


def test_find_amount_after_units():
    """金额文本解析：千分位/万亿/亿/万/元 单位"""
    assert _find_amount_after("总资产 1,234,567.89", "总资产") == 1234567.89
    assert _find_amount_after("总资产：12.3万", "总资产") == 123000.0
    assert _find_amount_after("总资产 8.9亿", "总资产") == 890000000.0
    assert _find_amount_after("总资产 1.5万亿元", "总资产") == 1.5e12
    assert _find_amount_after("可用资金 567890元", "可用资金") == 567890.0
    assert _find_amount_after("持仓市值 0.00", "持仓市值") == 0.0
    assert _find_amount_after("无金额", "总资产") is None


def test_extract_account_local_keyword_scan():
    """本地引擎关键词扫描：总资产/可用资金/仓位比例（同一行多字段也可提取）"""
    lines = [
        {"text": "总资产 12.3万", "x": 0, "y": 0, "w": 10, "h": 5, "conf": 1.0},
        {"text": "可用资金 45678.90 仓位比例 40.5%", "x": 0, "y": 20, "w": 10, "h": 5, "conf": 1.0},
    ]
    acc = _extract_account_local(lines)
    assert acc == {"total_asset": 123000.0, "available_cash": 45678.9, "position_pct": 40.5}


def test_extract_account_local_none_when_missing():
    """无账户汇总关键词 → None"""
    lines = [{"text": "600519 贵州茅台 100", "x": 0, "y": 0, "w": 10, "h": 5, "conf": 1.0}]
    assert _extract_account_local(lines) is None


# ==================== 识别降级链（云端优先 → 本地兜底） ====================

class _FakeOcr:
    """模拟 paddleocr 3.x 的 predict 结果（_FakeItem 同构，产出合成文本行）"""

    def predict(self, path):
        return [self._item(["证券代码", "证券名称", "持仓数量", "成本价", "市价"]),
                self._item(["600519", "贵州茅台", "100", "1520.00", "1550.30"])]

    def _item(self, texts):
        boxes = [[[10 + i * 80, 10], [70 + i * 80, 10], [70 + i * 80, 30], [10 + i * 80, 30]]
                 for i in range(len(texts))]
        return type("R", (), {"json": {"res": {"rec_texts": texts,
                                                "rec_scores": [1.0] * len(texts),
                                                "rec_polys": boxes}}})()  # noqa: BLE001


def _enable_local_ocr(monkeypatch):
    monkeypatch.setattr(settings, "ocr_enable", True)
    monkeypatch.setattr(ocr, "_get_ocr", lambda: _FakeOcr())


def test_recognize_minimax_success_skips_local(monkeypatch):
    """云端识别成功 → 不调用本地引擎"""
    _enable_minimax(monkeypatch, ocr_engine=True)
    _enable_local_ocr(monkeypatch)

    def _boom_local(image_bytes, filename):
        raise AssertionError("云端成功时不应调用本地引擎")

    monkeypatch.setattr(ocr, "_recognize_local", _boom_local)
    monkeypatch.setattr(ocr, "MiniMaxOcrEngine",
                        lambda client: type("E", (), {"recognize": lambda self, b, f: {
                            "recognized": [{"stock_code": "600519", "stock_name": "贵州茅台",
                                            "shares": 100, "cost_price": 1520.0,
                                            "current_price": 1550.3, "confidence": 0.9,
                                            "source_line": "600519 贵州茅台 100"}]}})())
    result = ocr.recognize_holding(b"img-b1", "shot.png")
    assert result["recognized"][0]["stock_code"] == "600519"


def test_recognize_cloud_failure_falls_back_to_local(monkeypatch):
    """云端失败（抛异常）→ 自动回退本地 PaddleOCR，不阻塞录入"""
    _enable_minimax(monkeypatch, ocr_engine=True)
    _enable_local_ocr(monkeypatch)
    monkeypatch.setattr(ocr, "MiniMaxOcrEngine", lambda client: MiniMaxOcrEngine(_FakeClient(exc=ConnectionError("超时"))))
    result = ocr.recognize_holding(b"img-b2", "shot.png")
    assert result["recognized"][0]["stock_code"] == "600519"  # 来自本地合成行


def test_recognize_cloud_empty_falls_back_to_local(monkeypatch):
    """云端解析无结果 → 回退本地"""
    _enable_minimax(monkeypatch, ocr_engine=True)
    _enable_local_ocr(monkeypatch)
    monkeypatch.setattr(ocr, "MiniMaxOcrEngine", lambda client: MiniMaxOcrEngine(_FakeClient(text="无法识别")))
    result = ocr.recognize_holding(b"img-b3", "shot.png")
    assert result["recognized"][0]["stock_code"] == "600519"


def test_recognize_default_only_local(monkeypatch):
    """默认关闭云端 → 仅走本地引擎，行为与之前完全一致"""
    monkeypatch.setattr(settings, "minimax_enable", False)
    _enable_local_ocr(monkeypatch)
    result = ocr.recognize_holding(b"img-b4", "shot.png")
    assert result["recognized"][0]["stock_code"] == "600519"


# ==================== 同图临时缓存（不重复消耗 API 调用次数） ====================

def test_same_image_cached_no_second_api_call(monkeypatch):
    """同一张截图 30 分钟内只识别一次：二次调用直接命中缓存，云端零调用"""
    _enable_minimax(monkeypatch, ocr_engine=True)
    monkeypatch.setattr(settings, "ocr_enable", True)
    engine = MiniMaxOcrEngine(_FakeClient(text=_valid_json_text()))
    monkeypatch.setattr(ocr, "MiniMaxOcrEngine", lambda client: engine)
    monkeypatch.setattr(ocr, "_get_ocr", lambda: _FakeOcr())
    image = b"img-b5-same-screenshot"
    first = ocr.recognize_holding(image, "shot.png")
    second = ocr.recognize_holding(image, "shot.png")
    assert first == second
    assert len(engine._client.calls) == 1  # 云端只调用一次


def test_different_images_separate_cache(monkeypatch):
    """不同截图互不影响（各自识别一次）"""
    _enable_minimax(monkeypatch, ocr_engine=True)
    monkeypatch.setattr(settings, "ocr_enable", True)
    engine = MiniMaxOcrEngine(_FakeClient(text=_valid_json_text()))
    monkeypatch.setattr(ocr, "MiniMaxOcrEngine", lambda client: engine)
    monkeypatch.setattr(ocr, "_get_ocr", lambda: _FakeOcr())
    ocr.recognize_holding(b"img-b6-1", "a.png")
    ocr.recognize_holding(b"img-b6-2", "b.png")
    assert len(engine._client.calls) == 2


# ==================== 状态接口（附加云端信息，前端既有键不变） ====================

def test_status_reports_minimax_flag(monkeypatch):
    monkeypatch.setattr(settings, "ocr_enable", True)
    _enable_local_ocr(monkeypatch)
    _enable_minimax(monkeypatch, ocr_engine=True)
    st = ocr.get_status()
    assert st["enabled"] is True and st["minimax_ocr_enabled"] is True

    monkeypatch.setattr(settings, "minimax_ocr_enable", False)
    st = ocr.get_status()
    assert st["minimax_ocr_enabled"] is False


def test_normalize_minimax_row_shared_shape():
    """归一化行与本地 _complete_row 键集合完全一致（前端录入流程不变）"""
    data = {"stock_code": "600519", "stock_name": "贵州茅台",
            "shares": 100, "cost_price": 1520.0, "current_price": 1550.3,
            "pnl_amount": 3030.0, "pnl_pct": -1.9}
    local_row = ocr._complete_row(data, [{"conf": 0.99, "text": "600519 贵州茅台 100"}])
    cloud_row = _normalize_minimax_row(data)
    assert set(cloud_row) == set(local_row)
    for key in ("stock_code", "stock_name", "shares", "cost_price",
                "current_price", "pnl_amount", "pnl_pct"):
        assert cloud_row[key] == local_row[key] == data[key]
