"""
OCR 持仓截图识别服务（本地 PaddleOCR 轻量版，离线识别）

【职责边界】只做两件事：
1. 文字识别：从券商持仓截图识别出 股票代码/名称/持仓数量/持仓成本/当前市价；
2. 数据回填：把识别结果作为「新增持仓表单」的预填值，供人工核对修正。

本模块不做任何行情研判、交易决策——所有市场研判仍由 LLM 完成。
图片仅在内存/临时文件处理，识别完毕立即清理，不长期存储用户截图。

降级策略：OCR_ENABLE=false 或 paddleocr 未安装时，服务报告"未启用/不可用"，
返回清晰中文提示，不影响系统其他功能（手动录入始终可用）。
"""
import importlib.util
import logging
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# 允许上传的图片格式
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 单张截图上限 10MB

STOCK_CODE_RE = re.compile(r"^\d{6}$")          # 6 位数字代码
STOCK_NAME_RE = re.compile(r"^[一-龥A-Za-z]{2,8}$")  # 中文/字母名称
NUMBER_RE = re.compile(r"^[+-]?[\d,]+(\.\d{1,3})?$")          # 数字（含千分位/小数）
INTEGER_RE = re.compile(r"^[\d,]+$")            # 整数（股数类）

# 表头关键词 → 字段名（兼容主流券商持仓界面）
HEADER_FIELDS = [
    (re.compile(r"代码"), "stock_code"),
    (re.compile(r"名称"), "stock_name"),
    (re.compile(r"持仓(数量|总量)?|持股(数量|总量)?"), "shares"),
    (re.compile(r"成本"), "cost_price"),
    (re.compile(r"市价|现价|最新价"), "current_price"),
]

_ocr = None
_ocr_lock = threading.Lock()


def get_status() -> dict:
    """OCR 功能状态（供前端展示开关与降级提示）"""
    if not settings.ocr_enable:
        return {"enabled": False, "available": False,
                "reason": "OCR 未启用（.env 设置 OCR_ENABLE=true 开启）"}
    try:
        _get_ocr()
        return {"enabled": True, "available": True, "reason": ""}
    except Exception as exc:  # noqa: BLE001
        return {"enabled": True, "available": False,
                "reason": f"PaddleOCR 初始化失败: {exc}"}


def _get_ocr():
    """惰性初始化 PaddleOCR 单例（首次调用自动下载识别模型）

    - 3.x（本机 Python 3.14 推荐）：无 paddlepaddle 时自动回退 onnxruntime 引擎；
    - 2.x（Docker 容器内可装 paddlepaddle 时）：经典 use_gpu 参数。
    """
    global _ocr
    if _ocr is None:
        with _ocr_lock:
            if _ocr is None:
                try:
                    import paddleocr
                except ImportError as exc:
                    raise RuntimeError(
                        "未安装 paddleocr 依赖：请执行 pip install paddleocr "
                        "（详见 backend/requirements.txt 的 OCR 可选依赖说明）") from exc
                # 压掉 paddlex / onnxruntime 的加载日志与警告，避免污染应用日志
                logging.getLogger("paddlex").setLevel(logging.WARNING)
                logging.getLogger("onnxruntime").setLevel(logging.ERROR)
                try:
                    device = settings.ocr_device.lower()
                    major = paddleocr.__version__.split(".")[0]
                    if major == "3":
                        # 3.x：无 paddlepaddle（如 Python 3.14）时自动回退 onnxruntime 引擎
                        engine = None if importlib.util.find_spec("paddle") else "onnxruntime"
                        _ocr = paddleocr.PaddleOCR(
                            lang="ch", use_textline_orientation=True,
                            engine=engine, device="gpu" if device == "gpu" else "cpu")
                    else:
                        _ocr = paddleocr.PaddleOCR(
                            use_angle_cls=True, lang="ch", show_log=False,
                            use_gpu=(device == "gpu"))
                except Exception as exc:  # noqa: BLE001
                    raise RuntimeError(f"PaddleOCR 初始化失败（设备: {settings.ocr_device}）: {exc}") from exc
    return _ocr


def _normalize_lines(result: Any) -> list[dict]:
    """兼容 paddleocr 2.x（ocr.ocr 返回元组列表）与 3.x（predict 返回 OCRResult 对象）"""
    lines: list[dict] = []

    def append(text: str, box: Any, conf: float) -> None:
        try:
            xs = [float(p[0]) for p in box]
            ys = [float(p[1]) for p in box]
        except (TypeError, ValueError):
            return
        lines.append({
            "text": text, "x": min(xs), "y": min(ys),
            "w": max(xs) - min(xs), "h": max(ys) - min(ys),
            "conf": float(conf),
        })

    # 2.x：result = [[[box, (text, conf)], ...], ...]（外层列表通常仅一张图）
    if isinstance(result, list) and result and isinstance(result[0], list):
        for line in result[0]:
            if len(line) == 2:
                box, (text, conf) = line
                append(text, box, conf)
        return lines

    # 3.x：result = [OCRResult, ...]（OCRResult 的 json 属性为 dict，内容包在 'res' 键下）
    for item in result:
        if hasattr(item, "json"):
            res = item.json
        else:
            res = item
        if isinstance(res, dict) and "res" in res:
            res = res["res"]
        texts = res.get("rec_texts") or []
        scores = res.get("rec_scores") or [1.0] * len(texts)
        boxes = res.get("rec_polys") or res.get("rec_boxes") or []
        for text, score, box in zip(texts, scores, boxes):
            append(text, box, score)
    return lines


def _cluster_rows(lines: list[dict]) -> list[list[dict]]:
    """按 y 坐标聚类成行（同一行文字的 y 中心差小于行高一半视为同行）"""
    rows: list[list[dict]] = []
    for line in sorted(lines, key=lambda l: l["y"]):
        placed = False
        for row in rows:
            ref = row[0]
            dy = abs((line["y"] + line["h"] / 2) - (ref["y"] + ref["h"] / 2))
            if dy <= max(ref["h"], line["h"]) * 0.75:
                row.append(line)
                placed = True
                break
        if not placed:
            rows.append([line])
    return [sorted(r, key=lambda l: l["x"]) for r in rows]


def _is_header_row(row: list[dict]) -> bool:
    return any(re.search(r"代码|名称", t["text"]) for t in row)


def _column_map(header: list[dict]) -> dict[str, float]:
    """表头行 → {字段名: 该列中心 x 坐标}"""
    mapping: dict[str, float] = {}
    for token in header:
        for pattern, field in HEADER_FIELDS:
            if pattern.search(token["text"]):
                mapping[field] = token["x"] + token["w"] / 2
                break
    return mapping


def _clean_number(text: str) -> float | None:
    if not NUMBER_RE.match(text.strip()):
        return None
    return float(text.replace(",", ""))


def _assign_by_column(tokens: list[dict], mapping: dict[str, float]) -> dict:
    """按「token 中心 x 与表头列中心最近」规则把 token 分配给对应字段"""
    found: dict = {}
    for token in tokens:
        center = token["x"] + token["w"] / 2
        field, dist = None, float("inf")
        for f, cx in mapping.items():
            d = abs(center - cx)
            if d < dist:
                field, dist = f, d
        if field is None:
            continue
        if field == "stock_code" and STOCK_CODE_RE.match(token["text"].strip()):
            found[field] = token["text"].strip()
        elif field == "stock_name" and STOCK_NAME_RE.match(token["text"].strip()):
            found[field] = token["text"].strip()
        elif field == "shares" and INTEGER_RE.match(token["text"].strip()):
            found[field] = int(token["text"].replace(",", ""))
        elif field in ("cost_price", "current_price"):
            val = _clean_number(token["text"])
            if val is not None and "." in token["text"]:  # 价格必带小数点
                found.setdefault(field, val)
    return found


def _parse_with_header(rows: list[list[dict]], header: list[dict]) -> list[dict]:
    mapping = _column_map(header)
    if not mapping:
        return []
    header_y = header[0]["y"]
    results: list[dict] = []
    for row in rows:
        if row is header or row[0]["y"] <= header_y + max(r["h"] for r in header) * 0.75:
            continue
        data = _assign_by_column(row, mapping)
        if not data.get("stock_code"):
            continue
        results.append(_complete_row(data, row))
    return results


def _parse_heuristic(rows: list[list[dict]]) -> list[dict]:
    """无表头时的兜底解析：按代码行聚合，同一行内取名称/股数/价格"""
    results: list[dict] = []
    for row in rows:
        code = next((t["text"].strip() for t in row if STOCK_CODE_RE.match(t["text"].strip())), None)
        if not code:
            continue
        name = next((t["text"].strip() for t in row if STOCK_NAME_RE.match(t["text"].strip())), "")
        integers = [int(t["text"].replace(",", "")) for t in row
                    if INTEGER_RE.match(t["text"].strip())
                    and not STOCK_CODE_RE.match(t["text"].strip())]
        prices = [v for t in row for v in [_clean_number(t["text"])]
                  if v is not None and "." in t["text"]]
        results.append(_complete_row(
            {"stock_code": code, "stock_name": name,
             "shares": max(integers) if integers else None,
             "cost_price": prices[0] if prices else None,
             "current_price": prices[-1] if prices else None}, row))
    return results


def _complete_row(data: dict, row: list[dict]) -> dict:
    """统一输出结构：五个字段齐全，缺失值用 None（由前端提示人工补全）"""
    return {
        "stock_code": data.get("stock_code") or "",
        "stock_name": data.get("stock_name") or "",
        "shares": data.get("shares"),
        "cost_price": data.get("cost_price"),
        "current_price": data.get("current_price"),
        "confidence": round(sum(t["conf"] for t in row) / len(row), 3),
        "source_line": " ".join(t["text"] for t in row),
    }


def parse_lines(lines: list[dict]) -> list[dict]:
    """从 OCR 文本行提取持仓字段（纯结构化数据提取，不含任何行情判断）

    优先策略：定位表头行 → 按表头列名与 token x 坐标做列对齐（兼容主流券商界面）；
    无表头时退化为按代码行启发式解析。缺失字段保留 None，由前端提示人工补全。
    """
    rows = _cluster_rows(lines)
    header = next((r for r in rows if _is_header_row(r)), None)
    if header:
        parsed = _parse_with_header(rows, header)
        if parsed:
            return parsed
    return _parse_heuristic(rows)


def recognize_holding(image_bytes: bytes, filename: str = "screenshot.png") -> dict:
    """识别持仓截图 → 结构化持仓字段列表

    返回: {"recognized": [...], "raw_text": "..."}
    识别失败抛 RuntimeError（中文信息），调用方转为 400/错误提示。
    """
    if not settings.ocr_enable:
        raise RuntimeError("OCR 未启用：请在 .env 设置 OCR_ENABLE=true 后重启后端服务")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise RuntimeError(f"图片过大（{len(image_bytes) / 1024 / 1024:.1f}MB），上限 {MAX_IMAGE_BYTES // 1024 // 1024}MB")
    suffix = Path(filename).suffix.lower() or ".png"
    if suffix not in ALLOWED_EXT:
        raise RuntimeError(f"不支持的图片格式 {suffix}，支持: {', '.join(sorted(ALLOWED_EXT))}")

    ocr = _get_ocr()
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(image_bytes)
        # 注意：必须等写句柄关闭后 PaddleOCR 才能可靠读取文件（Windows 下尤其重要）
        # 2.x 与 3.x 均有 predict()；cls 参数仅 2.x 支持，统一走 predict 免分支
        result = ocr.predict(tmp_path)
        lines = _normalize_lines(result)
        recognized = parse_lines(lines)
        raw_text = "\n".join(l["text"] for l in lines)
        logger.info("OCR 识别完成：文本行 %d，提取持仓 %d 条", len(lines), len(recognized))
        return {"recognized": recognized, "raw_text": raw_text}
    finally:
        try:
            os.unlink(tmp_path)  # 临时文件立即清理，不长期存储截图
        except OSError:
            pass
