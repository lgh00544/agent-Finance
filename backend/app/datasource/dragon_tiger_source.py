"""龙虎榜数据源：游资维度原始数据（T+1 抓取，落 lhb_original_flow 表）

职责边界（数据源层铁律）：只做「抓取 → 列名规范化 → 返回 DataFrame」，不做任何市场判断；
失败一律降级返回空表/空 dict，不抛异常打断主链路；中文日志记录原因。

数据分层（口径硬隔离，K227 防误读）：
- 股票级：当日上榜股票 + 龙虎榜净买额（东财 stock_lhb_detail_em / 新浪 stock_lhb_detail_daily_sina），
  用于多源校验（同(日期,标的,口径) ≥2 源且差值<10% 才采信）；
- 席位级：单股席位买卖明细（东财 stock_lhb_stock_detail_em，flag='1' 当日 / '3' 三日累计），
  用于游资-席位映射（seat_name → hot_money_profile）。

第二源现状（K227 诚实标注，不伪造第二源数据）：
- 新浪 stock_lhb_detail_daily_sina 仅返回"上榜原因列表"，无金额明细（已实测确认）→
  本批接入为"上榜确认第二源"：双源在榜采信升级（金额以东财为准），available 动态反映；
- 同花顺 data.10jqka.com.cn 直连需 JS 生成的 hexin-v token，本环境不可用（已实测确认）；
- 金额主源东财；新浪无净额列 → 仅作上榜确认标签，绝不合并进净买额。second_source_status()
  动态如实标注 available：双源在榜 confidence 升级 max(0.8,0.9)=0.9 采信，仅新浪在榜降 0.55
  仅参考（verify_net_buy 自身多源校验逻辑无需改动）。

实现对齐 MairuiSource 独立类模式：不继承 DataSource 协议，方法返回约定对齐
（失败 → 空表），低频 T+1 任务不接断路器（避免动 datasource_stats._KINDS 测试断言）。
"""
import logging

import pandas as pd

from app.core.config import settings
from app.datasource.base import DataSourceError

logger = logging.getLogger(__name__)

# 第二源可用性诚实标注（K227：无第二源不得假装采信；新浪上榜确认接入后动态反映）
_SECOND_SOURCE_ANNOTATION = "当前仅东财可用、采信待第二源"
_SECOND_SOURCE_CANDIDATES = {
    "eastmoney": "东财 datacenter 每日龙虎榜详情（股票级净买额，金额主源）",
    "ths": "同花顺 data.10jqka.com.cn 直连需 JS 生成的 hexin-v token（本环境不可用）",
    "sina": "新浪每日明细接口无金额明细（仅上榜确认，本批作上榜确认第二源参与采信）",
}


def second_source_status(sina_fetched: bool = False) -> dict:
    """第二龙虎榜数据源可用性（K227 诚实标注，零网络调用）：
    返回 {"available": bool, "main_source": str, "annotation": str, "candidates": {...}}。
    sina_fetched: 本批是否拉到新浪上榜确认数据（由抓取/调度端传入布尔，本函数不发请求）。
    True → available=True，双源采信（金额以东财为准）；False → 仅东财、采信待第二源。
    无参调用默认 False → 旧标注（向后兼容，jobs.py/hot_money.py 不传参仍按旧行为）。"""
    if sina_fetched:
        return {
            "available": True,
            "main_source": "eastmoney",
            "annotation": "双源：东财金额+新浪上榜确认（金额以主源为准）",
            "candidates": dict(_SECOND_SOURCE_CANDIDATES),
        }
    return {
        "available": False,
        "main_source": "eastmoney",
        "annotation": _SECOND_SOURCE_ANNOTATION,
        "candidates": dict(_SECOND_SOURCE_CANDIDATES),
    }

# 东财龙虎榜每日明细（股票级）：列名 → 标准列
_LHB_STOCK_COLS = {
    "代码": "stock_code", "名称": "stock_name", "上榜日": "trade_date",
    "龙虎榜净买额": "net_buy", "龙虎榜买入额": "buy_amt", "龙虎榜卖出额": "sell_amt",
    "上榜原因": "disclosure_reason",
}
# 新浪龙虎榜每日明细（股票级）：此接口仅为"上榜原因列表"（无金额明细），
# 代码/名称/指标（上榜原因）可作第二源的上榜确认；净买额缺失 → 多源校验标置信度不足（K227 单源不采信）
_LHB_SINA_COLS = {
    "股票代码": "stock_code", "股票名称": "stock_name",
    "指标": "disclosure_reason",
}
# 东财单股席位明细：列名 → 标准列
_LHB_SEAT_COLS = {
    "交易日期": "trade_date", "营业部名称": "seat_name",
    "买入金额": "buy_amt", "卖出金额": "sell_amt", "净买入金额": "net_buy",
}

# 官方源置信度 1.0 / 第三方（东财/新浪）0.8 / 社区 0.5
_CONF_OFFICIAL = 1.0
_CONF_THIRD = 0.8
_CONF_VERIFIED = 0.9      # 双源在榜采信（东财金额 + 新浪上榜确认，金额以东财为准）
_CONF_SINA_ONLY = 0.55    # 仅新浪上榜确认（无金额，置信度不足档，不参与金额采信）

try:
    import akshare as ak  # noqa: PLC0415 数据源层按需导入，缺失时整体降级
except Exception:  # noqa: BLE001
    ak = None

from app.datasource.http_client import get as http_get  # noqa: E402

# 东财 datacenter HTTP API（vendored 直连：akshare 1.18.81 的 stock_lhb_detail_em 真实环境报
# 'NoneType' object is not subscriptable，照 _batch_from_ulist 模式直连 + JSON 容错解析）
_EM_DATA_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_EM_STOCKS_REPORT = "RPT_DAILYBILLBOARD_DETAILSNEW"   # 每日龙虎榜详情（股票级，金额单位：元）
_EM_BUY_REPORT = "RPT_BILLBOARD_DAILYDETAILSBUY"      # 买入前五席位明细（单位：元）
_EM_SELL_REPORT = "RPT_BILLBOARD_DAILYDETAILSSELL"    # 卖出前五席位明细（单位：元）


def _em_json(report_name: str, params: dict) -> list:
    """东财 datacenter API 直连：GET → JSON 容错解析 → 数据列表；失败抛异常由调用方降级"""
    url = _EM_DATA_URL
    payload = {
        "reportName": report_name, "columns": "ALL",
        "filter": f"({params['filter']})", "pageSize": params.get("page_size", 500),
        "sortColumns": params.get("sort_columns", "SECURITY_CODE"),
        "sortTypes": params.get("sort_types", "1"),
        "source": "WEB", "client": "WEB",
    }
    resp = http_get(url, referer="eastmoney", params=payload,
                    timeout=settings.datasource_timeout)
    resp.raise_for_status()
    data = resp.json()
    result = (data or {}).get("result") or {}
    rows = result.get("data") or []
    return rows if isinstance(rows, list) else []


def _fetch_em_stocks(trade_date: str) -> pd.DataFrame:
    """东财每日龙虎榜详情（股票级，vendored 直连）"""
    rows = _em_json(_EM_STOCKS_REPORT,
                    {"filter": f"TRADE_DATE='{trade_date}'", "page_size": 500})
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    keep = {"SECURITY_CODE": "stock_code", "SECURITY_NAME_ABBR": "stock_name",
            "EXPLANATION": "disclosure_reason",
            "BILLBOARD_NET_AMT": "net_buy", "BILLBOARD_BUY_AMT": "buy_amt",
            "BILLBOARD_SELL_AMT": "sell_amt"}
    out = out.rename(columns=keep)
    keep_cols = [c for c in keep.values() if c in out.columns]
    out = out[keep_cols] if keep_cols else pd.DataFrame()
    for col in ("net_buy", "buy_amt", "sell_amt"):
        _to_float(out, col)
    out["trade_date"] = str(trade_date)
    out["lhb_type"] = "1d"
    out["source"] = "eastmoney"
    out["confidence"] = _CONF_THIRD
    return out


_SEATS_CACHE_TTL = 86400  # 当日席位明细缓存（T+1 数据当日不变）


def _fetch_em_seats(trade_date: str) -> pd.DataFrame:
    """东财当日全部席位明细（买入前五 + 卖出前五，vendored 直连；单位：元）。
    当日全量一次拉取（~600 行），按 SECURITY_CODE 过滤个股，避免逐股请求。"""
    from app.cache import cache

    cache_key = f"lhb:seats:{trade_date}"
    cached = cache.get(cache_key)
    if cached:
        try:
            import json as _json
            return pd.DataFrame(_json.loads(cached))
        except Exception:  # noqa: BLE001 缓存损坏忽略重新拉
            pass
    frames = []
    for report in (_EM_BUY_REPORT, _EM_SELL_REPORT):
        try:
            rows = _em_json(report, {"filter": f"TRADE_DATE='{trade_date}'", "page_size": 500})
            if rows:
                frames.append(pd.DataFrame(rows))
        except Exception as exc:  # noqa: BLE001 单报告失败降级
            logger.warning("东财席位明细 %s 拉取失败: %s", report, exc)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    keep = {"OPERATEDEPT_NAME": "seat_name", "BUY": "buy_amt", "SELL": "sell_amt",
            "NET": "net_buy", "SECURITY_CODE": "stock_code",
            "SECURITY_NAME_ABBR": "stock_name", "EXPLANATION": "disclosure_reason"}
    out = out.rename(columns=keep)
    keep_cols = [c for c in keep.values() if c in out.columns]
    out = out[keep_cols] if keep_cols else pd.DataFrame()
    for col in ("net_buy", "buy_amt", "sell_amt"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    out["trade_date"] = str(trade_date)
    out["lhb_type"] = "1d"
    out["source"] = "eastmoney"
    out["confidence"] = _CONF_THIRD
    if not out.empty:
        try:
            cache.set(cache_key, out.to_json(orient="records", force_ascii=False), _SEATS_CACHE_TTL)
        except Exception:  # noqa: BLE001 缓存失败不影响返回
            pass
    return out


def _norm(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """列名规范化：按映射 rename，未识别列丢弃"""
    df = df.rename(columns=mapping)
    keep = [c for c in mapping.values() if c in df.columns]
    return df[keep] if keep else pd.DataFrame()


def _to_float(df: pd.DataFrame, col: str) -> None:
    """金额列 NaN/文本 → float（东财返回文本型数值）"""
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def _num(v) -> float:
    """NaN/None 安全转 float（新浪等无金额列时 pandas iterrows 给出 NaN）"""
    try:
        f = float(v)
        return f if f == f else 0.0
    except (TypeError, ValueError):
        return 0.0


def _apply_second_source_credit(rows: pd.DataFrame, em: pd.DataFrame, sina: pd.DataFrame) -> None:
    """第二源上榜确认采信（K227：金额单源不伪造，in-place 打标/调置信度）。
    同(日期,标的)双源在榜 → 东财金额行 confidence 升级 max(0.8,0.9)=0.9 + multi_source_verified=True；
    仅新浪在榜（无金额，仅上榜确认）→ confidence=0.55，不置多源核验标志。
    金额列一律以东财为准，新浪无净额列绝不合并/覆盖进净买额。"""
    rows["multi_source_verified"] = False
    if em.empty:
        if not sina.empty:
            rows.loc[rows["source"] == "sina", "confidence"] = _CONF_SINA_ONLY
        return
    if sina.empty:
        return
    em_codes = set(em["stock_code"].astype(str))
    sina_codes = set(sina["stock_code"].astype(str))
    code_col = rows["stock_code"].astype(str)
    dual = em_codes & sina_codes
    if dual:
        dual_mask = (rows["source"] == "eastmoney") & code_col.isin(dual)
        rows.loc[dual_mask, "confidence"] = max(_CONF_THIRD, _CONF_VERIFIED)
        rows.loc[dual_mask, "multi_source_verified"] = True
    sina_only = (rows["source"] == "sina") & ~code_col.isin(em_codes)
    if sina_only.any():
        rows.loc[sina_only, "confidence"] = _CONF_SINA_ONLY


class DragonTigerSource:
    """龙虎榜数据源（东财主源 + 新浪备源；低频 T+1，失败降级不阻塞主链路）"""

    def __init__(self) -> None:
        if not settings.dragon_tiger_enable:
            logger.info("龙虎榜数据源未启用（DRAGON_TIGER_ENABLE=false），抓取方法返回空")

    def fetch_lhb_stocks(self, trade_date: str, source: str = "eastmoney") -> pd.DataFrame:
        """当日上榜股票列表（股票级，含龙虎榜净买额；多源校验用）。
        source: eastmoney（vendored 东财 datacenter 直连，akshare 兜底）/ sina（上榜原因列表，无金额）"""
        if not settings.dragon_tiger_enable:
            return pd.DataFrame()
        try:
            if source == "sina":
                if ak is None:
                    return pd.DataFrame()
                df = ak.stock_lhb_detail_daily_sina(date=trade_date.replace("-", ""))
                # 新浪此接口只有上榜原因列表（无金额明细），列名匹配失败时按原因表降级返回空
                out = _norm(df, _LHB_SINA_COLS)
                if out.empty:
                    logger.warning("龙虎榜 sina 列名未匹配（接口为原因列表，无金额），跳过: %s",
                                   trade_date)
                    return pd.DataFrame()
                for col in ("net_buy", "buy_amt", "sell_amt"):
                    _to_float(out, col)
                out["trade_date"] = str(trade_date)
                out["source"] = "sina"
                out["confidence"] = _CONF_THIRD
                out["lhb_type"] = "1d"
                return out
            # eastmoney：vendored 东财直连为主源（akshare 1.18.81 该接口真实环境报错）
            try:
                out = _fetch_em_stocks(trade_date)
                if not out.empty:
                    return out
                logger.warning("龙虎榜 eastmoney 直连无数据: %s", trade_date)
            except Exception as exc:  # noqa: BLE001 直连失败降级 akshare
                logger.warning("龙虎榜 eastmoney 直连失败，回退 akshare: %s", exc)
            if ak is None:
                return pd.DataFrame()
            df = ak.stock_lhb_detail_em(start_date=trade_date, end_date=trade_date)
            out = _norm(df, _LHB_STOCK_COLS)
            if out.empty:
                return pd.DataFrame()
            for col in ("net_buy", "buy_amt", "sell_amt"):
                _to_float(out, col)
            out["trade_date"] = str(trade_date)
            out["source"] = "eastmoney"
            out["confidence"] = _CONF_THIRD
            out["lhb_type"] = "1d"
            return out
        except Exception as exc:  # noqa: BLE001 单源失败降级，不抛
            logger.warning("龙虎榜 %s 股票级抓取失败: %s", source, exc)
            return pd.DataFrame()

    def fetch_lhb_seats(self, trade_date: str, stock_code: str,
                        lhb_type: str = "1d") -> pd.DataFrame:
        """单股席位买卖明细（席位级，游资-席位映射用）。
        东财当日全量明细（买入前五+卖出前五，当日缓存）按股过滤；3d 暂不支持返回空。"""
        if not settings.dragon_tiger_enable or lhb_type != "1d":
            return pd.DataFrame()
        try:
            all_seats = _fetch_em_seats(trade_date)
            if all_seats.empty:
                return pd.DataFrame()
            if str(stock_code) == "ALL":
                return all_seats.reset_index(drop=True)
            out = all_seats[all_seats["stock_code"] == str(stock_code)].copy()
            return out.reset_index(drop=True)
        except Exception as exc:  # noqa: BLE001 单股席位失败跳过该股，不阻塞整体
            logger.warning("龙虎榜席位明细抓取失败 %s/%s(%s): %s", trade_date, stock_code, lhb_type, exc)
            return pd.DataFrame()

    def fetch_and_merge(self, trade_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """抓取并合并：返回 (席位级流水, 股票级净买汇总)。
        席位级 = 当日全量买卖前五席位明细（东财一次拉取）；股票级 = 东财净买 + 新浪上榜确认。
        第二源按 DRAGON_TIGER_SECOND_SOURCE 开关聚合：新浪作上榜确认第二源，双源在榜
        采信升级（confidence 0.9 + multi_source_verified），金额以东财为准；仅新浪在榜
        降 0.55（无金额，仅上榜确认），second_source_status() 动态如实标注。
        全部失败返回两个空表。"""
        if not settings.dragon_tiger_enable:
            return pd.DataFrame(), pd.DataFrame()

        # 1) 股票级：东财（含净买额）+ 第二源（按开关；新浪作上榜确认第二源）
        em = self.fetch_lhb_stocks(trade_date, source="eastmoney")
        second = (settings.dragon_tiger_second_source or "auto").lower()
        sina = pd.DataFrame()
        if second != "none":
            sina = self.fetch_lhb_stocks(trade_date, source="sina")
        stock_rows = pd.concat([em, sina], ignore_index=True) if not (em.empty and sina.empty) \
            else pd.DataFrame()
        if not stock_rows.empty:
            _apply_second_source_credit(stock_rows, em, sina)

        # 2) 席位级：东财当日全量买卖前五席位明细（一次请求，当日缓存）
        seat_df = self.fetch_lhb_seats(trade_date, "ALL", lhb_type="1d") if not em.empty \
            else pd.DataFrame()
        if not seat_df.empty and not em.empty:
            name_map = dict(zip(em["stock_code"], em["stock_name"]))
            seat_df["stock_name"] = seat_df["stock_code"].map(
                lambda c: name_map.get(c, ""))
        return seat_df, stock_rows

    def fetch_dragon_tiger(self, trade_date: str) -> pd.DataFrame:
        """兼容接口名：返回席位级流水（主用途），失败空表"""
        seats, _ = self.fetch_and_merge(trade_date)
        return seats


def fetch_dragon_tiger(trade_date: str) -> pd.DataFrame:
    """模块级便捷入口（调度/脚本用）：拉取并落库一次龙虎榜"""
    from app.db import repo

    src = DragonTigerSource()
    seats, stocks = src.fetch_and_merge(trade_date)
    # 席位级流水落库（游资-席位映射数据）
    rows = []
    if not seats.empty:
        for _, r in seats.iterrows():
            rows.append({
                "trade_date": r.get("trade_date") or trade_date,
                "stock_code": str(r.get("stock_code") or ""),
                "stock_name": str(r.get("stock_name") or ""),
                "lhb_type": str(r.get("lhb_type") or "1d"),
                "disclosure_reason": str(r.get("disclosure_reason") or ""),
                "seat_name": str(r.get("seat_name") or ""),
                "buy_amt": _num(r.get("buy_amt")),
                "sell_amt": _num(r.get("sell_amt")),
                "net_buy": _num(r.get("net_buy")),
                "confidence": _num(r.get("confidence")) or _CONF_THIRD,
                "source": str(r.get("source") or "eastmoney"),
            })
    n = repo.insert_lhb_flows(rows) if rows else 0
    # 股票级净买（东财/新浪）也落库：多源校验与"无席位但上榜"标的覆盖
    stock_rows = []
    if not stocks.empty:
        for _, r in stocks.iterrows():
            stock_rows.append({
                "trade_date": r.get("trade_date") or trade_date,
                "stock_code": str(r.get("stock_code") or ""),
                "stock_name": str(r.get("stock_name") or ""),
                "lhb_type": str(r.get("lhb_type") or "1d"),
                "disclosure_reason": str(r.get("disclosure_reason") or ""),
                "seat_name": "",  # 股票级行：席位为空，净买为股票级龙虎榜净买额
                "buy_amt": _num(r.get("buy_amt")),
                "sell_amt": _num(r.get("sell_amt")),
                "net_buy": _num(r.get("net_buy")),
                "confidence": _num(r.get("confidence")) or _CONF_THIRD,
                "source": str(r.get("source") or "eastmoney"),
                "multi_source_verified": bool(r.get("multi_source_verified") or False),
            })
    n2 = repo.insert_lhb_flows(stock_rows) if stock_rows else 0
    logger.info("龙虎榜落库 %s: 席位级 %s 条 / 股票级 %s 条", trade_date, n, n2)
    # 第二源上榜确认采信状态如实标注（K227 诚实：sina 拉到上榜确认 → available=True 动态反映，
    # 金额仍以东财为准；未拉到则如实标"采信待第二源"）
    sina_fetched = bool(not stocks.empty and (stocks["source"] == "sina").any())
    ss = second_source_status(sina_fetched=sina_fetched)
    logger.info("龙虎榜第二源状态: available=%s（%s）", ss.get("available"), ss.get("annotation"))
    return seats
