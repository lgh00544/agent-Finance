"""
OCR 持仓截图识别服务（引擎抽象：MiniMax M3 云端优先 + 本地 PaddleOCR 兜底）

【职责边界】只做两件事：
1. 文字识别：从券商持仓截图识别出 股票代码/名称/持仓数量/持仓成本/当前市价/持仓盈亏金额/持仓盈亏比例，
   以及截图顶部账户汇总（总资产/可用资金/整体仓位比例，识别不到则为 None）；
2. 数据回填：把识别结果作为「新增持仓表单」的预填值，供人工核对修正；
   账户汇总经人工确认后保存为账户基准（顶部状态栏双数据路径的权威值）。

【引擎选择链】MINIMAX_ENABLE=true（默认开启云端优先）时优先云端 MiniMax（识别准确率更高），
失败/无结果自动回退本地 PaddleOCR（离线、无 API 消耗），不阻塞录入流程；
MINIMAX_OCR_ENABLE=false 可强制仅用本地引擎。两个引擎输出结构完全一致（七字段），前端流程不变。

【调用优化】同一张截图 30 分钟内临时缓存识别结果，不重复识别、不重复消耗 API 调用次数。

本模块不做任何行情研判、交易决策——所有市场研判仍由 LLM 完成。
图片仅在内存/临时文件处理，识别完毕立即清理，不长期存储用户截图。

降级策略：OCR_ENABLE=false 或 paddleocr 未安装时，服务报告"未启用/不可用"，
返回清晰中文提示，不影响系统其他功能（手动录入始终可用）。
"""
import hashlib
import importlib.util
import json
import logging
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from app.cache import cache
from app.core.config import settings
from app.services.multimodal import MultimodalClient, get_multimodal_client

logger = logging.getLogger(__name__)

# 同一张截图识别结果的临时缓存时长（秒）：避免重复识别、重复消耗 MiniMax API 调用次数
_OCR_CACHE_TTL = 30 * 60

# MiniMax 云端识别提示词：纯结构化提取指令（字段名直接对齐统一输出格式，不含任何行情判断）
# 输出对象含 account（截图顶部账户汇总）与 holdings（持仓数组）；兼容性解析见 _parse_minimax
_MINIMAX_OCR_PROMPT = (
    "你是券商持仓截图的字段提取助手。请仔细识别图中持仓表格，把每只持仓整理为一条记录，"
    "并提取截图顶部的账户汇总信息。只输出一个 JSON 对象，结构如下："
    '{"account": {"total_asset": 总资产(元,数字), "available_cash": 可用资金(元,数字), '
    '"position_pct": 整体仓位比例(数字,如 40.5 表示 40.5%)}, '
    '"holdings": [{"stock_code": "6位数字股票代码", "stock_name": "股票全称", '
    '"shares": 持仓数量(整数,单位股), "cost_price": 持仓成本价(数字), '
    '"current_price": 当前市价(数字), "pnl_amount": 持仓盈亏金额(带正负号的数字,如 -1234.5), '
    '"pnl_pct": 持仓盈亏比例(数字,如 -3.2 表示 -3.2%)}]}。'
    "截图中没有的字段填 null，禁止编造；截图中没有账户汇总信息时 account 填 null。"
    "股票代码与股票名称必须成对出现，代码在前、名称在后。只输出 JSON 对象本身，"
    "不要任何解释、代码块标记或前后缀文字。"
)

# 模型输出 JSON 数组的稳健提取（容忍代码块围栏与前后说明文字）
_JSON_ARRAY_RE = re.compile(r"\[[\s\S]*\]")

# 允许上传的图片格式
ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 单张截图上限 10MB

STOCK_CODE_RE = re.compile(r"^\d{6}$")          # 6 位数字代码
STOCK_NAME_RE = re.compile(r"^[一-龥A-Za-z]{2,8}$")  # 中文/字母名称
NUMBER_RE = re.compile(r"^[+-]?[\d,]+(\.\d{1,3})?$")          # 数字（含千分位/小数）
INTEGER_RE = re.compile(r"^[\d,]+$")            # 整数（股数类）

# 表头关键词 → 字段名（兼容主流券商持仓界面；盈亏类字段需避开「盈亏比例」串匹配）
HEADER_FIELDS = [
    (re.compile(r"代码"), "stock_code"),
    (re.compile(r"名称"), "stock_name"),
    (re.compile(r"持仓(数量|总量)?|持股(数量|总量)?"), "shares"),
    (re.compile(r"成本"), "cost_price"),
    (re.compile(r"市价|现价|最新价"), "current_price"),
    (re.compile(r"(盈亏金额|浮动盈亏|累计盈亏|持仓盈亏(?!比例))"), "pnl_amount"),
    (re.compile(r"(盈亏比例|盈亏率|收益率|涨跌幅)"), "pnl_pct"),
]

_ocr = None
_ocr_lock = threading.Lock()


def get_status() -> dict:
    """OCR 功能状态（供前端展示开关与降级提示）"""
    minimax_ocr_enabled = get_multimodal_client() is not None and settings.minimax_ocr_enable
    if not settings.ocr_enable:
        return {"enabled": False, "available": False,
                "reason": "OCR 未启用（.env 设置 OCR_ENABLE=true 开启）",
                "minimax_ocr_enabled": minimax_ocr_enabled}
    try:
        _get_ocr()
        return {"enabled": True, "available": True, "reason": "",
                "minimax_ocr_enabled": minimax_ocr_enabled}
    except Exception as exc:  # noqa: BLE001
        return {"enabled": True, "available": False,
                "reason": f"PaddleOCR 初始化失败: {exc}",
                "minimax_ocr_enabled": minimax_ocr_enabled}


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
                        base_kwargs = dict(lang="ch", use_textline_orientation=True,
                                           engine=engine, device="gpu" if device == "gpu" else "cpu")
                        if settings.ocr_model_level.lower() == "light":
                            # 轻量模型（默认）：PP-OCRv4 mobile，体积小省空间；
                            # 模型名参数不被当前版本支持时自动回退默认模型
                            try:
                                _ocr = paddleocr.PaddleOCR(
                                    text_detection_model_name="PP-OCRv4_mobile_det",
                                    text_recognition_model_name="PP-OCRv4_mobile_rec",
                                    **base_kwargs)
                            except Exception as exc:  # noqa: BLE001
                                logger.warning("轻量模型加载失败，回退默认模型: %s", exc)
                                _ocr = paddleocr.PaddleOCR(**base_kwargs)
                        else:
                            # full=完整模型（精度略高，体积更大），需在 .env 显式设置
                            _ocr = paddleocr.PaddleOCR(**base_kwargs)
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


def _parse_pct_value(value: Any) -> float | None:
    """盈亏比例字段 → 数值（容忍 "-3.2%" / "-3.2" / "3.2%" 等显示形式；缺失/脏数据返回 None）"""
    if value is None:
        return None
    text = str(value).strip().rstrip("%").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


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
        elif field == "pnl_amount":
            val = _clean_number(token["text"])
            if val is not None:
                found.setdefault(field, val)
        elif field == "pnl_pct":
            val = _parse_pct_value(token["text"])
            if val is not None:
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
    """无表头时的兜底解析：按代码行聚合，同一行内取名称/股数/价格/盈亏"""
    results: list[dict] = []
    for row in rows:
        code = next((t["text"].strip() for t in row if STOCK_CODE_RE.match(t["text"].strip())), None)
        if not code:
            continue
        name = next((t["text"].strip() for t in row if STOCK_NAME_RE.match(t["text"].strip())), "")
        integers = [int(t["text"].replace(",", "")) for t in row
                    if INTEGER_RE.match(t["text"].strip())
                    and not STOCK_CODE_RE.match(t["text"].strip())]
        # 带 +/- 号的金额视为持仓盈亏（券商持仓界面惯例），百分号 token 视为盈亏比例；
        # 剔除后剩余小数才是成本价/当前市价，避免盈亏列污染价格取值
        sign_tokens = [t for t in row if t["text"].strip().startswith(("+", "-"))]
        prices = [v for t in row for v in [_clean_number(t["text"])]
                  if v is not None and "." in t["text"] and t not in sign_tokens]
        pnl_amount = next((_clean_number(t["text"]) for t in sign_tokens
                           if _clean_number(t["text"]) is not None), None)
        # 仅取带「%」后缀的 token，避免把代码等纯数字误判为盈亏比例
        pnl_pct = next((v for t in row if t["text"].strip().endswith("%")
                        for v in [_parse_pct_value(t["text"])] if v is not None), None)
        results.append(_complete_row(
            {"stock_code": code, "stock_name": name,
             "shares": max(integers) if integers else None,
             "cost_price": prices[0] if prices else None,
             "current_price": prices[-1] if prices else None,
             "pnl_amount": pnl_amount, "pnl_pct": pnl_pct}, row))
    return results


def _complete_row(data: dict, row: list[dict]) -> dict:
    """统一输出结构：七个字段齐全，缺失值用 None（由前端提示人工补全）"""
    return {
        "stock_code": data.get("stock_code") or "",
        "stock_name": data.get("stock_name") or "",
        "shares": data.get("shares"),
        "cost_price": data.get("cost_price"),
        "current_price": data.get("current_price"),
        "pnl_amount": data.get("pnl_amount"),
        "pnl_pct": data.get("pnl_pct"),
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


# 账户汇总关键词（本地引擎关键词扫描，兼容主流券商持仓界面顶部汇总栏）
_ACCOUNT_KEYWORDS = [
    ("总资产", "total_asset"),
    ("可用资金", "available_cash"),
    ("可用余额", "available_cash"),
    ("资金余额", "available_cash"),
]
_POSITION_PCT_KEYWORDS = ["仓位", "持仓比例", "总仓位"]


def _find_amount_after(text: str, keyword: str) -> float | None:
    """关键词之后的金额（容忍千分位/万亿/亿/万/元单位）：'总资产 12.3万' → 123000"""
    idx = text.find(keyword)
    if idx < 0:
        return None
    tail = text[idx + len(keyword):]
    m = re.search(r"([+-]?[\d,]+(?:\.\d+)?)\s*(万亿|亿|万|元)?", tail)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = m.group(2) or ""
    if "万亿" in unit:
        num *= 1e12
    elif "亿" in unit:
        num *= 1e8
    elif "万" in unit:
        num *= 1e4
    return num


def _extract_account_local(lines: list[dict]) -> dict | None:
    """本地引擎：按关键词从文本行扫描账户汇总（总资产/可用资金/仓位比例）。

    仅做数值提取，识别不到对应字段则不返回该键；全部字段均缺失返回 None。
    结果仍需人工核对后才保存为账户基准。
    """
    account: dict = {}
    for line in lines:
        text = line["text"]
        for keyword, key in _ACCOUNT_KEYWORDS:
            if key not in account and keyword in text:
                value = _find_amount_after(text, keyword)
                if value is not None:
                    account[key] = round(value, 2)
        if "position_pct" not in account and any(k in text for k in _POSITION_PCT_KEYWORDS):
            idx = min((text.find(k) for k in _POSITION_PCT_KEYWORDS if k in text))
            m = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", text[idx:])
            if m:
                account["position_pct"] = float(m.group(1))
    return account or None


def _recognize_local(image_bytes: bytes, filename: str = "screenshot.png") -> dict:
    """本地 PaddleOCR 引擎（默认）：离线识别，无 API 消耗"""
    ocr = _get_ocr()
    suffix = Path(filename).suffix.lower() or ".png"
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
        account = _extract_account_local(lines)
        logger.info("本地 OCR 识别完成：文本行 %d，提取持仓 %d 条%s",
                    len(lines), len(recognized), "，账户汇总已识别" if account else "")
        return {"recognized": recognized, "raw_text": raw_text, "account": account}
    finally:
        try:
            os.unlink(tmp_path)  # 临时文件立即清理，不长期存储截图
        except OSError:
            pass


def _to_float(value: Any) -> float | None:
    """模型字段 → float（容忍千分位/字符串数字）；缺失/脏数据返回 None"""
    if value is None or str(value).strip() in ("", "null", "None"):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    """模型字段 → int（股数类）；缺失/脏数据返回 None"""
    f = _to_float(value)
    if f is None:
        return None
    return int(f)


def _first(row: dict, *keys: str) -> Any:
    """按序取第一个非空字段值（容忍英文键名与中文别名混用；0 视为有效值）"""
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip() not in ("", "null", "None"):
            return value
    return None


def _parse_minimax(text: str) -> tuple[list, dict | None]:
    """模型输出 → (持仓行列表, 账户汇总原始 dict|None)

    兼容两种输出形态：新版对象 {"account": {...}, "holdings": [...]} 与旧版纯数组；
    容忍代码块围栏与前后说明文字。
    """
    candidates = [text]
    m = _JSON_ARRAY_RE.search(text)
    if m:
        candidates.append(m.group())
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            rows = data.get("holdings")
            if not isinstance(rows, list):
                rows = []
            acc = data.get("account")
            return rows, (acc if isinstance(acc, dict) else None)
        if isinstance(data, list):
            return data, None
    return [], None


def _normalize_minimax_account(acc: dict | None) -> dict | None:
    """账户汇总字段规范化（容忍中英键名）；无有效总资产返回 None（前端提示人工补全）"""
    if not isinstance(acc, dict):
        return None
    total = _to_float(_first(acc, "total_asset", "总资产"))
    cash = _to_float(_first(acc, "available_cash", "可用资金"))
    pct = _parse_pct_value(_first(acc, "position_pct", "仓位比例", "仓位"))
    if total is None:
        return None
    out: dict = {"total_asset": total}
    if cash is not None:
        out["available_cash"] = cash
    if pct is not None:
        # 模型可能把 40.5% 输出为 0.405 小数形式，统一为百分比
        if 0 < pct <= 1:
            pct *= 100
        out["position_pct"] = round(pct, 2)
    return out


def _normalize_minimax_row(row: dict) -> dict:
    """模型 JSON 行 → 统一输出结构（字段与本地 _complete_row 完全一致，前端流程不变）"""
    code = str(_first(row, "stock_code", "股票代码") or "").strip()
    name = str(_first(row, "stock_name", "股票名称") or "").strip()
    shares = _to_int(_first(row, "shares", "持仓数量"))
    cost = _to_float(_first(row, "cost_price", "持仓成本", "成本"))
    price = _to_float(_first(row, "current_price", "当前市价", "市价"))
    pnl_amount = _to_float(_first(row, "pnl_amount", "持仓盈亏金额", "盈亏金额",
                                  "浮动盈亏", "持仓盈亏"))
    pnl_pct = _parse_pct_value(_first(row, "pnl_pct", "持仓盈亏比例", "盈亏比例", "收益率"))
    return {
        "stock_code": code if STOCK_CODE_RE.match(code) else "",
        "stock_name": name if STOCK_NAME_RE.match(name) else "",
        "shares": shares,
        "cost_price": cost,
        "current_price": price,
        "pnl_amount": pnl_amount,
        "pnl_pct": pnl_pct,
        # 云端识别无逐字置信度，给保守固定值，由人工核对修正（与本地引擎语义一致）
        "confidence": 0.9,
        "source_line": " ".join(filter(None, (code, name,
                                              str(shares or ""), str(cost or ""), str(price or "")))),
    }


class MiniMaxOcrEngine:
    """云端 OCR 引擎：MiniMax M3 多模态识别持仓截图（开启后使用，识别准确率更高）

    输出与本地 PaddleOCR 完全一致的结构化字段；识别失败/解析失败返回 None，
    由上层回退本地 PaddleOCR，不阻塞录入流程。
    """

    def __init__(self, client: MultimodalClient) -> None:
        self._client = client

    def recognize(self, image_bytes: bytes, filename: str = "screenshot.png") -> dict | None:
        try:
            text = self._client.analyze_image(image_bytes, _MINIMAX_OCR_PROMPT)
        except Exception as exc:  # noqa: BLE001 云端失败统一回退本地
            logger.warning("MiniMax 云端识别失败，回退本地 PaddleOCR: %s", exc)
            return None
        rows, account_raw = _parse_minimax(text)
        if not rows and account_raw is None:
            logger.warning("MiniMax 识别结果解析失败，回退本地 PaddleOCR")
            return None
        recognized = [_normalize_minimax_row(r) for r in rows if isinstance(r, dict)]
        account = _normalize_minimax_account(account_raw)
        logger.info("MiniMax 云端识别完成：提取持仓 %d 条%s",
                    len(recognized), "，账户汇总已识别" if account else "")
        return {"recognized": recognized, "raw_text": text, "account": account}


def recognize_holding(image_bytes: bytes, filename: str = "screenshot.png") -> dict:
    """识别持仓截图 → 结构化持仓字段列表 + 账户汇总（引擎选择链 + 同图临时缓存）

    引擎选择：MINIMAX_ENABLE + MINIMAX_OCR_ENABLE 同时开启时优先云端 MiniMax，
    失败/无结果自动回退本地 PaddleOCR；默认（未开启云端）仅走本地引擎，行为与之前完全一致。
    同一张截图 30 分钟内命中临时缓存直接返回，不重复识别、不重复消耗 API 调用次数。

    返回: {"recognized": [...], "raw_text": "...", "account": {"total_asset", "available_cash", "position_pct"}|None}
    账户汇总识别不到时为 None（前端不展示保存入口）；识别结果一律需人工核对后才落库。
    识别失败抛 RuntimeError（中文信息），调用方转为 400/错误提示。
    """
    if not settings.ocr_enable:
        raise RuntimeError("OCR 未启用：请在 .env 设置 OCR_ENABLE=true 后重启后端服务")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise RuntimeError(f"图片过大（{len(image_bytes) / 1024 / 1024:.1f}MB），上限 {MAX_IMAGE_BYTES // 1024 // 1024}MB")
    suffix = Path(filename).suffix.lower() or ".png"
    if suffix not in ALLOWED_EXT:
        raise RuntimeError(f"不支持的图片格式 {suffix}，支持: {', '.join(sorted(ALLOWED_EXT))}")

    cache_key = f"ocr:{hashlib.md5(image_bytes).hexdigest()}"
    cached = cache.get(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except (ValueError, TypeError):
            pass

    engines: list[tuple[str, Callable[[bytes, str], dict | None]]] = []
    client = get_multimodal_client()
    if client is not None and settings.minimax_ocr_enable:
        engines.append(("MiniMax 云端识别", MiniMaxOcrEngine(client).recognize))
    engines.append(("本地 PaddleOCR", _recognize_local))

    last_err: Exception | None = None
    for name, engine in engines:
        try:
            result = engine(image_bytes, filename)
            if result is None:
                continue
            # 云端未提取到持仓行 → 回退下一引擎；末位引擎（本地）空结果按原行为返回，不报错
            if not result["recognized"] and len(engines) > 1 and name != engines[-1][0]:
                logger.warning("%s 未提取到持仓行，回退下一引擎", name)
                continue
            cache.set(cache_key, json.dumps(result, ensure_ascii=False), _OCR_CACHE_TTL)
            logger.info("OCR 识别完成（%s）：提取持仓 %d 条", name, len(result["recognized"]))
            return result
        except Exception as exc:  # noqa: BLE001 单引擎失败不阻塞整体流程
            last_err = exc
            logger.warning("%s 识别失败，回退下一引擎: %s", name, exc)
    raise RuntimeError(f"持仓截图识别失败：{last_err or '无可用识别引擎'}")
