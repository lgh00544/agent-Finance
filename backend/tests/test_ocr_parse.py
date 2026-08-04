"""OCR 结构化解析层测试（不依赖 PaddleOCR 真实推理，用合成文本行验证解析逻辑）

仅验证文字识别结果的【结构化提取与数据回填】正确性；
不做任何行情研判断言（那是 LLM 的职责）。
"""
import pytest

from app.services import ocr


def _line(text, x, y=0, w=70, h=20, conf=0.99):
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "conf": conf}


HEADER = [
    _line("证券代码", 30), _line("证券名称", 260), _line("持仓数量", 490),
    _line("成本价", 690), _line("市价", 880), _line("浮动盈亏", 1080),
]
ROW_1 = [
    _line("600519", 30, y=100), _line("贵州茅台", 260, y=100),
    _line("100", 490, y=100), _line("1520.00", 690, y=100),
    _line("1550.30", 880, y=100), _line("+3,030.00", 1080, y=100),
]
ROW_2 = [
    _line("300750", 30, y=170), _line("宁德时代", 260, y=170),
    _line("2,000", 490, y=170), _line("198.45", 690, y=170),
    _line("210.62", 880, y=170), _line("+24,340.00", 1080, y=170),
]


def test_parse_with_header_column_alignment():
    """表头模式：按列对齐提取代码/名称/股数/成本/市价"""
    rows = ocr.parse_lines(HEADER + ROW_1 + ROW_2)
    assert len(rows) == 2

    r1, r2 = rows[0], rows[1]
    assert r1["stock_code"] == "600519"
    assert r1["stock_name"] == "贵州茅台"
    assert r1["shares"] == 100
    assert r1["cost_price"] == 1520.0
    assert r1["current_price"] == 1550.3

    assert r2["stock_code"] == "300750"
    assert r2["stock_name"] == "宁德时代"
    assert r2["shares"] == 2000
    assert r2["cost_price"] == 198.45
    assert r2["current_price"] == 210.62


def test_parse_header_missing_fields_kept_none():
    """字段缺失时保留 None，由前端提示人工补全（不允许猜测填值）"""
    lines = HEADER + [
        _line("600519", 30, y=100), _line("贵州茅台", 260, y=100),
        # 缺 持仓数量/成本价，仅市价
        _line("1550.30", 880, y=100),
    ]
    rows = ocr.parse_lines(lines)
    assert len(rows) == 1
    r = rows[0]
    assert r["stock_code"] == "600519"
    assert r["shares"] is None
    assert r["cost_price"] is None
    assert r["current_price"] == 1550.3


def test_parse_heuristic_fallback_no_header():
    """无表头兜底：按代码行聚合，股数不应包含代码本身"""
    lines = [
        _line("持仓", 10, y=10, w=40),
        _line("600519", 10, y=50), _line("贵州茅台", 90, y=50, w=90),
        _line("100", 190, y=50, w=40), _line("1520.00", 240, y=50),
        _line("1550.30", 320, y=50),
    ]
    rows = ocr.parse_lines(lines)
    assert len(rows) == 1
    r = rows[0]
    assert r["stock_code"] == "600519"
    assert r["stock_name"] == "贵州茅台"
    assert r["shares"] == 100
    assert r["cost_price"] == 1520.0
    assert r["current_price"] == 1550.3


def test_parse_ignores_noise_rows():
    """无代码的行（标题/提示语）不产出持仓"""
    lines = [
        _line("您的持仓", 100, y=10, w=120),
        _line("行情有风险，投资需谨慎", 60, y=40, w=200),
        HEADER[0], HEADER[1], HEADER[2], HEADER[3], HEADER[4], HEADER[5],
    ]
    assert ocr.parse_lines(lines) == []


def test_recognize_disabled_raises(monkeypatch):
    """OCR_ENABLE=false 时调用识别应给出清晰中文错误"""
    monkeypatch.setattr(ocr.settings, "ocr_enable", False)
    with pytest.raises(RuntimeError, match="OCR 未启用"):
        ocr.recognize_holding(b"fake-image-bytes", "x.png")


def test_recognize_rejects_oversize(monkeypatch):
    """超限图片与非法格式给出清晰错误"""
    monkeypatch.setattr(ocr.settings, "ocr_enable", True)
    with pytest.raises(RuntimeError, match="图片过大"):
        ocr.recognize_holding(b"x" * (ocr.MAX_IMAGE_BYTES + 1), "x.png")
    with pytest.raises(RuntimeError, match="不支持的图片格式"):
        ocr.recognize_holding(b"x", "x.pdf")


class _FakeItem:
    """模拟 paddleocr 3.x 的 OCRResult.json 结构"""
    def __init__(self, texts):
        self._json = {"res": {"rec_texts": texts,
                              "rec_scores": [1.0] * len(texts),
                              "rec_polys": [[[10 + i, 10], [50 + i, 10],
                                             [50 + i, 30], [10 + i, 30]]
                                            for i in range(len(texts))]}}

    @property
    def json(self):
        return self._json


def test_normalize_lines_3x_result():
    """兼容 paddleocr 3.x 结果（外层包 res）"""
    result = [_FakeItem(["证券代码", "600519"])]
    lines = ocr._normalize_lines(result)
    assert [l["text"] for l in lines] == ["证券代码", "600519"]
    assert lines[0]["x"] == 10
    assert lines[1]["x"] == 11


def test_normalize_lines_2x_result():
    """兼容 paddleocr 2.x 结果（box + (text, conf) 元组列表）"""
    box = [[0, 0], [60, 0], [60, 20], [0, 20]]
    result = [[[box, ("600519", 0.98)], [box, ("贵州茅台", 0.97)]]]
    lines = ocr._normalize_lines(result)
    assert [l["text"] for l in lines] == ["600519", "贵州茅台"]
    assert abs(lines[0]["conf"] - 0.98) < 1e-6
