"""
Akshare 数据源实现（东财为主，新浪降级）
【刚性代码逻辑】仅做：数据采集、重试降级、列名规范化、缓存节流。
本层不做任何市场判断。

统一 fetch 封装：
  - 15s 超时（接口支持时传入 timeout 参数）
  - 失败后间隔 1-2s 重试 1 次（DATASOURCE_RETRY_TIMES/DELAY 可配），单次失败只打 DEBUG
  - 实时热点路径（tick/snapshot）接入断路器：连续失败 3 次进入临时降级 10 分钟，
    期间直接走备用源，冷却到期静默探测自动切回（切换才打 WARNING，日志不刷屏）
  - 非交易时段（午间休盘/盘前盘后/周末节假日）不请求实时接口，仅用收盘数据
  - 东财接口失败时按可降级映射尝试新浪/雪球/同花顺备选接口
  - 结果按 中文列名 → 英文标准列 规范化
  - Redis/内存缓存按接口设置 TTL，避免高频请求触发限流
"""
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable

import pandas as pd

from app.cache import cache
from app.core.config import settings
from app.datasource import market_hours
from app.datasource.base import DataSource, DataSourceError
from app.datasource.breaker import get_breaker
from app.datasource.http_client import get as http_get
from app.datasource.http_client import get_limiter, patch_requests_headers
from app.services import datasource_stats

logger = logging.getLogger(__name__)

try:
    import akshare as ak
except ImportError:  # pragma: no cover
    ak = None

# akshare 内部请求不传 headers，这里从 requests 层全局补浏览器 UA（一次性，见 http_client）
patch_requests_headers()


# ---------------- 列名规范化映射（中文 → 英文标准列） ----------------
_SPOT_COLS = {
    "代码": "code", "名称": "name", "最新价": "price", "涨跌幅": "change_pct",
    "涨跌额": "change_amount", "成交量": "volume", "成交额": "amount",
    "振幅": "amplitude", "最高": "high", "最低": "low", "今开": "open", "昨收": "pre_close",
    "量比": "volume_ratio", "换手率": "turnover_rate", "市盈率-动态": "pe_dynamic",
    "市净率": "pb", "总市值": "total_mv", "流通市值": "circ_mv",
    "60日涨跌幅": "pct_change_60d", "年初至今涨跌幅": "pct_change_ytd",
}
_KLINE_COLS = {
    "日期": "date", "开盘": "open", "收盘": "close", "最高": "high", "最低": "low",
    "成交量": "volume", "成交额": "amount", "振幅": "amplitude",
    "涨跌幅": "change_pct", "涨跌额": "change_amount", "换手率": "turnover_rate",
}
_FUND_FLOW_COLS = {
    "日期": "date",
    "主力净流入-净额": "main_net_inflow", "主力净流入-净占比": "main_net_pct",
    "超大单净流入-净额": "super_large_net", "超大单净流入-净占比": "super_large_pct",
    "大单净流入-净额": "large_net", "大单净流入-净占比": "large_pct",
    "中单净流入-净额": "medium_net", "中单净流入-净占比": "medium_pct",
    "小单净流入-净额": "small_net", "小单净流入-净占比": "small_pct",
}
_INST_COLS = {"证券代码": "code", "证券简称": "name", "机构数": "inst_count",
              "机构数变化": "inst_change", "持股比例": "hold_pct",
              "持股比例增幅": "hold_pct_change", "占流通股比例": "float_pct",
              "占流通股比例增幅": "float_pct_change"}
_FINANCIAL_SINA_COLS = {
    "日期": "report_date", "净资产收益率(%)": "roe", "净资产收益率-摊薄(%)": "roe_diluted",
    "主营业务收入增长率(%)": "revenue_yoy", "净利润增长率(%)": "profit_yoy",
    "资产负债率(%)": "debt_ratio", "销售净利率(%)": "net_margin",
    "销售毛利率(%)": "gross_margin",
}
_FINANCIAL_THS_COLS = {
    "报告期": "report_date", "营业总收入同比增长率(%)": "revenue_yoy",
    "净利润同比增长率(%)": "profit_yoy", "净资产收益率(%)": "roe",
    "资产负债率(%)": "debt_ratio", "销售毛利率(%)": "gross_margin",
}
_NEWS_COLS = {"关键词": "keyword", "新闻标题": "title", "新闻内容": "content",
              "发布时间": "published_at", "文章来源": "source", "新闻链接": "url"}
_NEWS_COLS_OLD = {"code": "code", "title": "title", "content": "content",
                  "public_time": "published_at", "url": "url"}
_INDEX_COLS = {"日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
               "最低": "low", "成交量": "volume", "成交额": "amount"}
_BOARD_COLS = {"板块名称": "board_name", "板块": "board_name",  # 东财/新浪列名变体
               "最新价": "price", "涨跌幅": "change_pct", "总市值": "total_mv",
               "换手率": "turnover_rate", "量比": "volume_ratio",  # 东财板块行情量比（缺失时不编造）
               "上涨家数": "up_count", "下跌家数": "down_count",
               "领涨股票": "leading_stock", "领涨股": "leading_stock", "股票名称": "leading_stock"}
_SUSPEND_COLS = {"代码": "code", "名称": "name", "停牌时间": "suspend_time",
                 "停牌原因": "reason", "预计复牌时间": "resume_time"}
_CONS_COLS = {"代码": "code", "名称": "name", "最新价": "price", "涨跌幅": "change_pct",
              "成交额": "amount", "换手率": "turnover_rate"}

# ---------------- 避险/进取板块归类（市场研判底座输入；纯关键词归类，客观不编造） ----------------
# 按板块名称关键词归属资金属性：防御/消费类 → 避险池；科技/进攻类 → 进取池
_DEFENSIVE_KW = ("地产", "房地产", "白酒", "消费", "农林牧渔", "农业", "食品", "医药", "银行",
                 "公用事业", "电力", "港口", "机场", "公路", "煤炭", "石油")
_AGGRESSIVE_KW = ("通信", "芯片", "半导体", "算力", "计算机", "电子", "软件", "人工智能", "AI",
                  "数字经济", "互联网", "新能源", "军工", "证券", "传媒", "游戏", "机器人")


def classify_board_groups(board: pd.DataFrame) -> dict:
    """板块 → 避险池 / 进取池 资金归类（市场研判「风险偏好切换」维度输入）。

    【刚性代码逻辑】仅按板块名关键词归类 + 客观聚合（涨跌幅/量比/成交额均值），不做任何判断；
    板块表缺失量比/成交额列时该组指标标注 None（数据缺失如实标注，不编造）。
    返回: {"defensive": [板块名...], "aggressive": [...], "unclassified": [...],
           "stats": {"defensive": {...}, "aggressive": {...}}}"""
    if board is None or board.empty or "board_name" not in board.columns:
        return {"defensive": [], "aggressive": [], "unclassified": [],
                "stats": {"defensive": None, "aggressive": None, "note": "板块数据缺失"}}

    def _match(name: str, kws: tuple) -> bool:
        return any(k in str(name) for k in kws)

    groups = {"defensive": [], "aggressive": [], "unclassified": []}
    for _, row in board.iterrows():
        name = str(row.get("board_name") or "")
        if _match(name, _DEFENSIVE_KW):
            groups["defensive"].append(name)
        elif _match(name, _AGGRESSIVE_KW):
            groups["aggressive"].append(name)
        else:
            groups["unclassified"].append(name)

    def _stats(names: list[str]) -> dict | None:
        if not names:
            return None
        sub = board[board["board_name"].astype(str).isin(names)]
        st = {"count": int(len(sub))}
        for col, key in (("change_pct", "avg_change_pct"),
                         ("volume_ratio", "avg_volume_ratio")):
            if col in sub.columns:
                vals = pd.to_numeric(sub[col], errors="coerce").dropna()
                st[key] = round(float(vals.mean()), 3) if not vals.empty else None
            else:
                st[key] = None  # 源无该字段：如实标注缺失
        if "amount" in sub.columns:
            vals = pd.to_numeric(sub["amount"], errors="coerce").dropna()
            st["sum_amount"] = int(vals.sum()) if not vals.empty else None
        return st

    return {"defensive": groups["defensive"], "aggressive": groups["aggressive"],
            "unclassified": groups["unclassified"],
            "stats": {"defensive": _stats(groups["defensive"]),
                      "aggressive": _stats(groups["aggressive"])}}


def _normalize(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """中文列名 → 英文标准列；无法识别的列丢弃"""
    if df is None or df.empty:
        return df
    rename = {k: v for k, v in mapping.items() if k in df.columns}
    out = df.rename(columns=rename)
    keep = set(mapping.values()) & set(out.columns)
    return out[[c for c in out.columns if c in keep]]


def _to_json_safe(df: pd.DataFrame) -> pd.DataFrame:
    """NaN → None，便于 JSON 序列化落库"""
    return df.where(pd.notna(df), None)


_NEWS_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")


def _clean_em_tags(df: pd.DataFrame) -> pd.DataFrame:
    """清理东财高亮 <em> 标签与全角空格（纯清洗，不含任何判断）"""
    for col in ("新闻标题", "新闻内容"):
        if col not in df.columns:
            continue
        s = df[col].astype(str)
        df[col] = (s.str.replace(r"\(<em>", "", regex=True)
                   .str.replace(r"</em>\)", "", regex=True)
                   .str.replace("<em>", "", regex=False)
                   .str.replace("</em>", "", regex=False)
                   .str.replace("　", "", regex=False)  # 全角空格
                   .str.replace("\r\n", " ", regex=False))
    return df


def _stock_news_em_fixed(code: str) -> pd.DataFrame:
    """东财个股新闻（vendored 修复版）【刚性代码逻辑】
    上游 akshare 1.18.81 在 news_stock.py 用 `str.replace(r"\\u3000", regex=True)`
    清理全角空格，pandas 3 + pyarrow 字符串后端下 `\\u` 属非法正则，抛
    ArrowInvalid: Invalid regular expression: invalid escape sequence: \\u，
    导致个股新闻检索整体不可用。本函数为同接口等价实现，仅修正非法正则
    （全角空格/换行改为字面量替换，regex=False），清洗逻辑与上游一致。"""
    import json

    import requests

    url = "https://search-api-web.eastmoney.com/search/jsonp"
    inner_param = {
        "uid": "", "keyword": code, "type": ["cmsArticleWebOld"],
        "client": "web", "clientType": "web", "clientVersion": "curr",
        "param": {"cmsArticleWebOld": {"searchScope": "default", "sort": "default",
                                       "pageIndex": 1, "pageSize": 10,
                                       "preTag": "<em>", "postTag": "</em>"}},
    }
    params = {"cb": "jQuery_fixed_cb",
              "param": json.dumps(inner_param, ensure_ascii=False), "_": "1"}
    headers = {"user-agent": _NEWS_UA, "referer": f"https://so.eastmoney.com/news/s?keyword={code}"}
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    text = resp.text.strip()
    start, end = text.find("("), text.rfind(")")  # JSONP 包裹: jQueryxxx(...)
    if start < 0 or end <= start:
        raise DataSourceError(f"新闻接口响应格式异常: {text[:80]}")
    data = json.loads(text[start + 1:end])
    rows = (data.get("result") or {}).get("cmsArticleWebOld") or []
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if "code" in df.columns:
        df["新闻链接"] = "http://finance.eastmoney.com/a/" + df["code"].astype(str) + ".html"
    df = df.rename(columns={"date": "发布时间", "mediaName": "文章来源",
                            "title": "新闻标题", "content": "新闻内容"})
    df["关键词"] = code
    keep = [c for c in ("关键词", "新闻标题", "新闻内容", "发布时间", "文章来源", "新闻链接")
            if c in df.columns]
    return _clean_em_tags(df[keep])


def _stock_announcements(code: str) -> pd.DataFrame:
    """东财个股公告（搜索新闻接口失效时的降级源，2026-08 起搜索接口仅返回 profile 数据）【刚性代码逻辑】
    列表接口取最近公告，正文接口逐条取内容（最多 5 条正文，控制调用量）"""
    import requests

    headers = {"user-agent": _NEWS_UA, "referer": "https://data.eastmoney.com/"}
    ann = requests.get("https://np-anotice-stock.eastmoney.com/api/security/ann",
                       params={"sr": -1, "page_size": 10, "page_index": 1, "ann_type": "A",
                               "client_source": "web", "stock_list": code},
                       headers=headers, timeout=15).json()
    items = ((ann.get("data") or {}).get("list")) or []
    rows = []
    for it in items[:5]:
        art_code = str(it.get("art_code") or "")
        title = str(it.get("title") or "").strip()
        if not title or not art_code:
            continue
        content = ""
        try:
            detail = requests.get(
                "https://np-cnotice-stock.eastmoney.com/api/content/ann",
                params={"art_code": art_code, "client_source": "web", "page_index": 1},
                headers=headers, timeout=15).json()
            content = str(((detail.get("data") or {}).get("notice_content") or ""))
        except Exception as exc:  # noqa: BLE001 单条正文失败不阻塞
            logger.warning("公告 %s 正文拉取失败: %s", art_code, exc)
        rows.append({"新闻标题": title, "新闻内容": content,
                     "发布时间": str(it.get("notice_date") or "")[:10],
                     "文章来源": "东方财富-公告",
                     "新闻链接": f"https://data.eastmoney.com/notices/detail/{code}/{art_code}.html"})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["关键词"] = code
    return _clean_em_tags(df[["关键词", "新闻标题", "新闻内容", "发布时间", "文章来源", "新闻链接"]])


def _stock_news_fixed(code: str) -> pd.DataFrame:
    """东财个股新闻（vendored）：搜索接口为主，异常/空结果自动降级个股公告"""
    try:
        df = _stock_news_em_fixed(code)
    except Exception as exc:  # noqa: BLE001 搜索接口异常不阻塞，降级公告源
        logger.warning("个股新闻搜索接口失败，降级为个股公告源: %s (%s)", code, exc)
        df = pd.DataFrame()
    if not df.empty:
        return df
    logger.info("个股新闻搜索为空，降级为个股公告源: %s", code)
    return _stock_announcements(code)


def _cache_key(scope: str) -> str:
    """scope 需包含全部标识参数（如 'kline:600519:20240101:20240801:qfq'）"""
    return "ak:" + hashlib.md5(scope.encode()).hexdigest()


def _market_of(code: str) -> str:
    if code.startswith("6"):
        return "sh"
    if code.startswith(("4", "8", "9")):
        return "bj"
    return "sz"


class AkshareSource(DataSource):
    def __init__(self) -> None:
        if ak is None:
            raise DataSourceError("akshare 未安装")

    # ---------------- 统一 fetch 封装 ----------------
    def _fetch(self, scope: str, func_name: str, call: Callable, ttl_seconds: int,
               fallback: Callable | None = None, required: bool = True,
               normalize: Callable | None = None, kind: str | None = None) -> pd.DataFrame:
        """带缓存 + 重试 + 降级 + （kind 非空时）断路器/限流/统计的数据采集【刚性逻辑】。
        scope 必须包含全部标识参数（股票代码/日期等），作为缓存键。
        """
        key = _cache_key(scope)
        cached = cache.get(key)
        if cached:
            try:
                # pandas 3.x read_json 不解析 JSON 字符串（视为文件路径），改用 json.loads
                return pd.DataFrame(json.loads(cached))
            except (ValueError, TypeError):
                pass
        try:
            df = self._call_with_retry(func_name, call, fallback, kind=kind)
            if normalize is not None:
                df = normalize(df)
            if df is not None and not df.empty and "date" in df.columns:
                # 数据源日期类型不一（str/datetime.date/np.datetime64），统一为 YYYY-MM-DD
                df = df.copy()
                df["date"] = df["date"].astype(str).str.slice(0, 10)
            if ttl_seconds > 0 and df is not None and not df.empty:
                cache.set(key, df.to_json(orient="records", force_ascii=False), ttl_seconds)
            return df
        except DataSourceError:
            if not required:
                if kind is not None and get_breaker(kind).is_degraded:
                    # 降级期间的例行失败不刷屏（进入降级的 WARNING 已记录一次）
                    logger.debug("数据源 %s 失败，返回空表（降级期间，非必需数据）", func_name)
                else:
                    logger.warning("数据源 %s 失败，返回空表（非必需数据）", func_name)
                return pd.DataFrame()
            raise

    def _call_with_retry(self, func_name: str, call: Callable, fallback: Callable | None,
                         kind: str | None = None) -> pd.DataFrame:
        """主源重试 + 降级 + （kind 非空时）断路器/限流/统计。

        kind 用于实时热点路径（tick=实时行情 / snapshot=全市场快照）：
        - 断路器降级期间跳过主源直接走备用，不再打无效请求
        - 同类请求最小间隔限流（防高频触发对方限流）
        - 失败计数进断路器：连续失败达阈值进入临时降级（切换仅打一次 WARNING）
        - 单次失败只打 DEBUG（去重），最终失败由上层 WARNING 汇总
        """
        delay = settings.datasource_retry_delay
        if kind is not None:
            breaker = get_breaker(kind)
            if not breaker.should_try():

                datasource_stats.record_degraded(kind)
                logger.debug("数据源 %s 临时降级中，跳过主源直接走备用", func_name)
                if fallback is None:
                    raise DataSourceError(f"数据源 {func_name} 临时降级中且无备用源")
                return self._run_fallback(func_name, fallback)
            get_limiter(kind).wait()
        last_err: Exception | None = None
        for attempt in range(1, settings.datasource_retry_times + 2):
            if kind is not None:

                datasource_stats.record_request(kind)
            try:
                df = call()
                if kind is not None:
                    get_breaker(kind).record_success()
                return df
            except Exception as exc:  # noqa: BLE001 数据源异常类型繁多，统一捕获
                last_err = exc
                if kind is not None:
                    get_breaker(kind).record_failure()
                    datasource_stats.record_failure(kind)
                logger.debug("数据源 %s 第 %d 次失败: %s", func_name, attempt, exc)
                if fallback is not None:
                    try:
                        return self._run_fallback(func_name, fallback)
                    except Exception as f_exc:  # noqa: BLE001
                        last_err = f_exc
                if attempt <= settings.datasource_retry_times:
                    time.sleep(delay)
        raise DataSourceError(f"数据源 {func_name} 重试失败: {last_err}")

    def _run_fallback(self, func_name: str, fallback: Callable) -> pd.DataFrame:
        """执行备用接口；降级期间只打 DEBUG（切换时的 WARNING 已在断路器记录一次）"""
        try:
            df = fallback()
        except Exception as exc:  # noqa: BLE001
            logger.debug("数据源 %s 备用接口也失败: %s", func_name, exc)
            raise
        if isinstance(df, pd.DataFrame) and df.empty:
            logger.debug("数据源 %s 备用接口返回空表", func_name)
        else:
            logger.info("数据源 %s 已降级到备用接口", func_name)
        return df

    # ---------------- 全市场快照 ----------------
    def fetch_spot_universe(self) -> pd.DataFrame:
        if not market_hours.snapshot_allowed():
            cached = cache.get(_cache_key("spot_em"))
            if cached:
                try:
                    return pd.DataFrame(json.loads(cached))  # 复用收盘缓存
                except (ValueError, TypeError):
                    pass
            logger.info("非交易日（%s），全市场快照暂不请求实时接口，返回空表",
                        market_hours._now().strftime("%Y-%m-%d %A"))
            return pd.DataFrame(columns=list(_SPOT_COLS.values()))
        def primary():
            return self._call_with_timeout(ak.stock_zh_a_spot_em)
        def fallback():
            df = ak.stock_zh_a_spot()  # 新浪
            # 新浪代码列带前缀（sh600000），剥离前缀统一
            if "代码" in df.columns:
                df["代码"] = df["代码"].astype(str).str.replace(r"^(sh|sz|bj)", "", regex=True)
            return df
        df = self._fetch("spot_em", "spot_em", primary, ttl_seconds=60, fallback=fallback,
                         normalize=lambda d: _normalize(d, _SPOT_COLS), kind="snapshot")
        return _to_json_safe(df)

    # ---------------- 单股实时行情（持仓监控链路，60s 内缓存） ----------------
    def fetch_spot_quote(self, code: str) -> dict:
        """单股最新实时行情【刚性代码逻辑】：东财盘口 → 雪球单股 → 全市场快照匹配；
        TTL 30s 确保监控每次执行拿到最新价；全部失败返回 {}（调用方用日K收盘兜底并标注）。
        返回 {"code","name","price","change_pct","time"}，price/change_pct 解析失败为 None。
        非交易时段（午间休盘/盘前盘后）不请求实时接口，直接用收盘快照兜底。
        """
        if not market_hours.realtime_open():
            logger.debug("非交易时段（%s），%s 实时行情走收盘快照",
                         market_hours._now().strftime("%Y-%m-%d %H:%M"), code)
            return self._quote_from_universe(code)
        def parse_bid_ask(df: pd.DataFrame) -> pd.DataFrame:
            # 东财盘口 item/value 列（最新价/涨幅）；构造为标准单行；解析失败返回空表（不缓存坏数据）
            kv = {str(r["item"]): r["value"] for _, r in df.iterrows()}
            try:
                price = float(kv["最新"])
                change_pct = float(kv.get("涨幅") or kv.get("涨跌幅") or 0.0)
            except (TypeError, ValueError, KeyError):
                return pd.DataFrame()
            return pd.DataFrame([{"code": code, "name": kv.get("名称"), "price": price,
                                  "change_pct": change_pct,
                                  "time": kv.get("时间") or kv.get("最新时间") or ""}])

        def parse_xq(df: pd.DataFrame) -> pd.DataFrame:
            kv = {str(r["item"]): r["value"] for _, r in df.iterrows()}
            try:
                price = float(kv["现价"])
                change_pct = float(kv.get("涨幅") or 0.0)
            except (TypeError, ValueError, KeyError):
                return pd.DataFrame()
            return pd.DataFrame([{"code": code, "name": kv.get("名称"), "price": price,
                                  "change_pct": change_pct, "time": kv.get("时间") or ""}])

        def primary():
            return parse_bid_ask(self._call_with_timeout(ak.stock_bid_ask_em, symbol=code))

        def fallback():
            # 雪球单股（独立于东财/新浪的轻量实时源，请求开销低）
            prefix = "SH" if code.startswith("6") else ("BJ" if code.startswith(("4", "8", "9")) else "SZ")
            return parse_xq(ak.stock_individual_spot_xq(symbol=f"{prefix}{code}"))

        df = self._fetch(f"spot_quote:{code}", "spot_quote", primary, ttl_seconds=30,
                         fallback=fallback, required=False, kind="tick")
        if df is None or df.empty:
            quote = self._quote_from_universe(code)
        else:
            row = df.iloc[0]
            quote = {"code": code, "name": str(row.get("name") or ""),
                     "price": float(row["price"]),
                     "change_pct": float(row.get("change_pct") or 0.0),
                     "time": str(row.get("time") or "")}
        return quote

    def _quote_from_universe(self, code: str) -> dict:
        """第三级兜底：全市场快照匹配该股实时行情（快照本身东财→新浪双降级，缓存复用）"""
        try:
            df = self.fetch_spot_universe()
            if df is None or df.empty or "code" not in df.columns:
                return {}
            row = df[df["code"].astype(str) == code]
            if row.empty:
                return {}
            r = row.iloc[0]
            try:
                price = float(r.get("price"))
            except (TypeError, ValueError):
                price = None
            try:
                change_pct = float(r.get("change_pct"))
            except (TypeError, ValueError):
                change_pct = None
            return {"code": code, "name": str(r.get("name") or ""), "price": price,
                    "change_pct": change_pct, "time": ""}
        except Exception as exc:  # noqa: BLE001 兜底失败返回空，调用方走日K收盘
            logger.warning("快照匹配实时行情失败 %s: %s", code, exc)
            return {}

    # ---------------- 批量实时行情（监控全持仓一次获取） ----------------
    _BATCH_QUOTE_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"

    def fetch_spot_quotes_batch(self, codes: list[str],
                                force_realtime: bool = False) -> dict[str, dict]:
        """批量实时行情【刚性代码逻辑】：全持仓统一获取后再过滤，禁止循环内逐只请求。

        链路：东财 push2 ulist 批量（一次请求全部代码）→ 全市场快照过滤（收盘数据）
        → 仍缺的逐只 fetch_spot_quote 兜底（极少）；TTL 30s，key 按排序代码哈希。
        非交易时段不请求实时接口，直接走快照（收盘数据）。
        force_realtime=True：跳过 realtime_open 闸门直接走 ulist 实时接口
        （盘前集合竞价等场景，ulist 返回竞价撮合价；失败仍走快照兜底）。
        返回 {code: {"code","name","price","change_pct","time"}}，price 缺失置 None。
        """
        codes = sorted({str(c) for c in codes if c})
        if not codes:
            return {}
        key = _cache_key("batch_quote:" + ",".join(codes))
        cached = cache.get(key)
        if cached:
            try:
                return json.loads(cached)
            except (ValueError, TypeError):
                pass
        out: dict[str, dict] = {}
        if force_realtime or market_hours.realtime_open():
            try:
                out = self._batch_from_ulist(codes)
            except Exception as exc:  # noqa: BLE001 批量主源失败不阻塞，走快照降级
                logger.debug("批量行情主源失败，走快照降级: %s", exc)
        else:
            logger.debug("非交易时段，批量行情直接走收盘快照")
        # 仅对 ulist 未返回的代码兜底；已返回但字段缺失的保留 None（容错，不重复请求）
        missing = [c for c in codes if c not in out]
        if missing:
            out.update(self._batch_from_universe(missing))
        missing = [c for c in codes if c not in out]
        for c in missing:
            quote = self.fetch_spot_quote(c)  # 逐只兜底（自身断路器，极少触发）
            if quote:
                out[c] = quote
        if out:
            cache.set(key, json.dumps(out, ensure_ascii=False), 30)
        return out

    def _batch_from_ulist(self, codes: list[str]) -> dict[str, dict]:
        """东财 push2 ulist 批量行情（含断路器/限流/统计）"""

        breaker = get_breaker("tick")
        if not breaker.should_try():
            datasource_stats.record_degraded("tick")
            raise DataSourceError("tick 临时降级中，批量行情跳过主源")
        get_limiter("tick").wait()
        datasource_stats.record_request("tick")
        secids = ",".join(("1." if c.startswith("6") else "0.") + c for c in codes)
        try:
            resp = http_get(self._BATCH_QUOTE_URL, referer="eastmoney",
                            params={"secids": secids, "fields": "f12,f14,f2,f3,f124",
                                    "fltt": 2, "invt": 2, "np": 1, "pn": 1, "pz": len(codes)})
            resp.raise_for_status()
            data = (resp.json() or {}).get("data")
            if not data or not data.get("diff"):
                raise DataSourceError("东财批量行情 data 为空（限流或参数异常）")
            out: dict[str, dict] = {}
            for item in data["diff"]:
                code = str(item.get("f12") or "").zfill(6)
                if not code:
                    continue
                try:
                    price = float(item.get("f2"))
                except (TypeError, ValueError):
                    price = None
                try:
                    change_pct = float(item.get("f3"))
                except (TypeError, ValueError):
                    change_pct = None
                out[code] = {"code": code, "name": str(item.get("f14") or ""),
                             "price": price, "change_pct": change_pct,
                             "time": str(item.get("f124") or "")}
            breaker.record_success()
            return out
        except Exception as exc:  # noqa: BLE001 数据源异常类型繁多，统一捕获
            breaker.record_failure()
            datasource_stats.record_failure("tick")
            raise

    def _batch_from_universe(self, codes: list[str]) -> dict[str, dict]:
        """快照降级：单次全市场快照过滤全部缺失代码（快照本身东财→新浪双降级）"""
        out: dict[str, dict] = {}
        try:
            uni = self.fetch_spot_universe()
        except Exception as exc:  # noqa: BLE001 快照失败不阻塞
            logger.debug("批量快照降级失败: %s", exc)
            return out
        if uni is None or uni.empty or "code" not in uni.columns:
            return out
        rows = uni[uni["code"].astype(str).isin(codes)]
        for _, r in rows.iterrows():
            code = str(r["code"])
            try:
                price = float(r.get("price"))
            except (TypeError, ValueError):
                price = None
            try:
                change_pct = float(r.get("change_pct"))
            except (TypeError, ValueError):
                change_pct = None
            out[code] = {"code": code, "name": str(r.get("name") or ""),
                         "price": price, "change_pct": change_pct, "time": ""}
        return out

    def fetch_suspended(self) -> pd.DataFrame:
        today = time.strftime("%Y%m%d")
        def call():
            return self._call_with_timeout(ak.stock_tfp_em, date=today)
        df = self._fetch(f"tfp_em:{today}", "tfp_em", call, ttl_seconds=600,
                         normalize=lambda d: _normalize(d, _SUSPEND_COLS))
        return _to_json_safe(df)

    def fetch_index_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        def primary():
            return self._call_with_timeout(
                ak.stock_zh_index_daily_em,
                symbol=symbol, start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""))
        def fallback():
            # 新浪指数日K（东财限流降级），客户端按日期区间过滤
            df = ak.stock_zh_index_daily(symbol=symbol)
            df["date"] = df["date"].astype(str)
            df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
            keep = {"date", "open", "close", "high", "low", "volume"}
            return df[[c for c in df.columns if c in keep]]
        df = self._fetch(f"index_daily:{symbol}:{start_date}:{end_date}", "index_daily", primary,
                         ttl_seconds=3600, fallback=fallback,
                         normalize=lambda d: _normalize(d, _INDEX_COLS))
        return _to_json_safe(df)

    def fetch_index_volume_ratios(self, days: int = 6) -> pd.DataFrame:
        """上证指数近 N 日「量比」序列（市场研判底座·大盘连续量比维度输入）。

        东财指数日线接口无直接量比字段，按成交量比近似：量比 = 当日成交量 ÷ 前 5 日均量
        （口径在输出标注）；前 5 日不足 3 日的交易日标注 None（数据不足如实标注，不编造）。
        返回列: date / volume_ratio / close，最多最近 days 行。"""
        from datetime import datetime, timedelta

        today = time.strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")  # 前置窗口取 5 日均量
        df = self.fetch_index_daily("sh000001", start, today)
        if df is None or df.empty or "volume" not in df.columns:
            return pd.DataFrame(columns=["date", "volume_ratio", "close"])
        df = df.dropna(subset=["volume"]).reset_index(drop=True)
        vol = pd.to_numeric(df["volume"], errors="coerce")
        ratios: list = []
        for i in range(len(df)):
            base = vol[max(0, i - 5):i].dropna()
            if len(base) >= 3 and float(base.mean()) > 0:
                ratios.append(round(float(vol.iloc[i]) / float(base.mean()), 3))
            else:
                ratios.append(None)
        df["volume_ratio"] = ratios
        return _to_json_safe(df[["date", "volume_ratio", "close"]].tail(days))

    def fetch_index_spot(self) -> pd.DataFrame:
        """三大指数 + 沪深300 实时行情（东财指数快照：上证系列 + 深证系列 + 中证系列，60s 缓存防限流）；
        顶部状态栏使用，返回含 code/name/price/change_pct 的 DataFrame。
        非交易日不请求实时接口，返回空表（顶部状态栏隐藏）。"""
        if not market_hours.snapshot_allowed():
            logger.debug("非交易日，指数实时行情跳过（返回空表）")
            return pd.DataFrame(columns=["code", "name", "price", "change_pct"])
        def call():
            parts = [
                ak.stock_zh_index_spot_em(symbol="上证系列指数"),
                ak.stock_zh_index_spot_em(symbol="深证系列指数"),
                ak.stock_zh_index_spot_em(symbol="中证系列指数"),  # 沪深300 等宽基（跨市场，不在上证/深证系列）
            ]
            return pd.concat(parts, ignore_index=True)
        def fallback():
            # 新浪指数快照（东财限流/宕机降级）；代码列带 sh/sz 前缀，与东财格式一致，保留供下方 keep 过滤
            return ak.stock_zh_index_spot_sina()
        df = self._fetch("index_spot", "index_spot", call, ttl_seconds=60, fallback=fallback,
                         required=False, kind="snapshot",
                         normalize=lambda d: _normalize(d, _SPOT_COLS))
        if df is None or df.empty or "code" not in df.columns:
            return pd.DataFrame(columns=["code", "name", "price", "change_pct"])
        keep = {"sh000001", "sz399001", "sz399006", "sh000300"}  # 上证指数/深证成指/创业板指/沪深300
        out = df[df["code"].astype(str).isin(keep)]
        return _to_json_safe(out)

    # ---------------- 隔夜美股快照（催化传导链参考，60s 缓存） ----------------
    _US_INDEXES = [(".INX", "标普500"), (".IXIC", "纳斯达克"), (".DJI", "道琼斯")]
    # 关键 AI 链个股：东财美股快照优先（一次筛选），新浪个股日线兜底（前收对比）
    _US_AI_STOCKS = [("NVDA", "英伟达"), ("MU", "美光"), ("AVGO", "博通"),
                     ("AMD", "AMD"), ("TSM", "台积电(ADR)")]

    @staticmethod
    def _daily_change_pct(df: pd.DataFrame) -> float | None:
        """日K最后收盘相对前收涨跌幅（数据不足返回 None，不编造）"""
        if df is None or df.empty or "close" not in df.columns:
            return None
        closes = pd.to_numeric(df["close"], errors="coerce").dropna()
        if len(closes) < 2 or not closes.iloc[-2]:
            return None
        return round(float((closes.iloc[-1] / closes.iloc[-2] - 1) * 100), 2)

    def fetch_us_market_overnight(self) -> dict:
        """隔夜美股快照（为「隔夜催化传导链」提供数据源，60s 缓存）。

        指数：新浪美股指数日线（ak.index_us_stock_sina，标普/纳指/道指）；
        个股：东财美股实时快照一次筛选（ak.stock_us_spot_em），失败逐只降级
        新浪美股日线前收对比（ak.stock_us_daily）。全部指数失败返回
        {"available": False}（绝不编造）。返回
        {"date": "YYYY-MM-DD", "indices": [{"name", "change_pct"}],
         "stocks": [{"name", "code", "change_pct"}]}，单只缺失 change_pct 置 None。"""
        indices: list[dict] = []
        us_date = ""
        for sym, name in self._US_INDEXES:
            try:
                df = self._fetch(f"us_index:{sym}", "index_us_stock_sina",
                                 lambda s=sym: self._call_with_timeout(
                                     ak.index_us_stock_sina, symbol=s),
                                 ttl_seconds=60, required=False)
                pct = self._daily_change_pct(df)
                if pct is not None and not us_date and df is not None and not df.empty:
                    us_date = str(df["date"].astype(str).iloc[-1])[:10]
                indices.append({"name": name, "change_pct": pct})
            except Exception as exc:  # noqa: BLE001 单指数失败不阻塞整体
                logger.warning("隔夜美股指数 %s 数据缺失: %s", name, exc)
                indices.append({"name": name, "change_pct": None})

        # 关键个股：东财快照一次筛选
        spot_map: dict[str, dict] = {}
        try:
            sdf = self._fetch("us_spot_em", "us_spot_em",
                              lambda: self._call_with_timeout(ak.stock_us_spot_em),
                              ttl_seconds=60, required=False)
            if sdf is not None and not sdf.empty:
                code_col = "代码" if "代码" in sdf.columns else (
                    "symbol" if "symbol" in sdf.columns else None)
                name_col = "名称" if "名称" in sdf.columns else "name"
                pct_col = "涨跌幅" if "涨跌幅" in sdf.columns else (
                    "change_pct" if "change_pct" in sdf.columns else None)
                if code_col and pct_col:
                    for _, r in sdf.iterrows():
                        c = str(r.get(code_col) or "").upper()
                        if not c:
                            continue
                        try:
                            pct = float(r[pct_col]) if pd.notna(r[pct_col]) else None
                        except (TypeError, ValueError):
                            pct = None
                        spot_map[c] = {"name": str(r.get(name_col) or ""), "change_pct": pct}
        except Exception as exc:  # noqa: BLE001 快照失败降级新浪个股日线
            logger.debug("东财美股快照不可用，降级新浪个股日线: %s", exc)

        stocks: list[dict] = []
        for code, cn_name in self._US_AI_STOCKS:
            hit = spot_map.get(code)
            if hit and hit.get("change_pct") is not None:
                stocks.append({"name": cn_name, "code": code, "change_pct": hit["change_pct"]})
                continue
            try:
                df = self._fetch(f"us_daily:{code}", "stock_us_daily",
                                 lambda c=code: self._call_with_timeout(
                                     ak.stock_us_daily, symbol=c, adjust=""),
                                 ttl_seconds=60, required=False)
                stocks.append({"name": cn_name, "code": code,
                               "change_pct": self._daily_change_pct(df)})
            except Exception as exc:  # noqa: BLE001 单只缺失不阻塞整体
                logger.warning("隔夜美股个股 %s 数据缺失: %s", code, exc)
                stocks.append({"name": cn_name, "code": code, "change_pct": None})

        if not indices or all(i["change_pct"] is None for i in indices):
            return {"available": False, "note": "数据缺失"}
        return {"date": us_date, "indices": indices, "stocks": stocks}

    # ---------------- 两市总成交额量倍（结构性 vs 全面牛市判定输入，60s 缓存） ----------------
    def fetch_market_total_volume_ratio(self) -> dict:
        """两市总成交额量倍：量倍 = 当日两市成交额 ÷ 前 5 日均值（判断结构性行情 vs 全面牛市）。

        东财指数日线含成交额列 → 两市总成交额量倍（东财口径）；东财不可达降级新浪日线
        （新浪日线无成交额列，以成交量近似，口径标注清楚）。量倍分子分母取**同一日线序列**
        保证单位一致（绝不编造）。当日成交额（亿）来自指数快照展示。失败返回
        {"available": False}。返回 {"amount": 亿, "ratio": x.xx, "note": "口径说明"}。"""
        spot = self._fetch_total_amount_volume()
        amt_hist = self._fetch_index_total_history("amount")
        if amt_hist:
            ratio = self._total_ratio(amt_hist)
            amount_yi = round(float(amt_hist[-1]) / 1e8, 0)
            note = "两市总成交额量倍（东财口径，成交额求和）"
            return {"amount": amount_yi, "ratio": ratio, "note": note}

        vol_hist = self._fetch_index_total_history("volume")
        if vol_hist:
            ratio = self._total_ratio(vol_hist)
            amount_yi = round(spot["amount"] / 1e8, 0) if spot else None
            note = "两市总成交量量倍（新浪口径，日线缺成交额以成交量近似）"
            return {"amount": amount_yi, "ratio": ratio, "note": note}
        return {"available": False, "note": "数据缺失"}

    @staticmethod
    def _total_ratio(total: list[float]) -> float | None:
        """当日量倍 = 序列末值 ÷ 前 5 日均值（与 fetch_index_volume_ratios 口径一致）"""
        n = len(total)
        if n < 4:
            return None
        base = [v for v in total[max(0, n - 6):n - 1] if v is not None and v > 0]
        if len(base) < 3:
            return None
        today = total[-1]
        if not today:
            return None
        return round(today / (sum(base) / len(base)), 3)

    def _fetch_total_amount_volume(self) -> dict | None:
        """当日两市成交额/成交量（元/股）：东财指数快照优先，新浪快照兜底；失败返回 None"""
        try:
            parts: list[pd.DataFrame] = []
            for sym in ("上证系列指数", "深证系列指数"):
                df = self._fetch(f"idx_spot_total:{sym}", "idx_spot_total",
                                 lambda s=sym: self._call_with_timeout(
                                     ak.stock_zh_index_spot_em, symbol=s),
                                 ttl_seconds=60, required=False)
                if df is not None and not df.empty:
                    parts.append(df)
            if parts:
                row = self._filter_sh_sz(pd.concat(parts, ignore_index=True))
                if row is not None:
                    return row
        except Exception as exc:  # noqa: BLE001 东财失败降级新浪
            logger.debug("东财指数快照不可用，降级新浪: %s", exc)
        try:
            df = self._fetch("idx_spot_sina_total", "idx_spot_sina_total",
                             lambda: self._call_with_timeout(ak.stock_zh_index_spot_sina),
                             ttl_seconds=60, required=False)
            if df is not None and not df.empty:
                row = self._filter_sh_sz(df)
                if row is not None:
                    return row
        except Exception as exc:  # noqa: BLE001
            logger.warning("两市成交额快照获取失败: %s", exc)
        return None

    def _filter_sh_sz(self, df: pd.DataFrame) -> dict | None:
        """从指数快照中筛出上证指数+深证成指，返回 {amount 元, volume 股}；缺失返回 None"""
        df = _normalize(df, _SPOT_COLS)
        if df is None or df.empty or "code" not in df.columns or "amount" not in df.columns:
            return None
        row = df[df["code"].astype(str).isin(["sh000001", "sz399001"])]
        if row.empty:
            return None
        amt = float(pd.to_numeric(row["amount"], errors="coerce").sum())
        vol = (float(pd.to_numeric(row["volume"], errors="coerce").sum())
               if "volume" in row.columns else 0.0)
        return {"amount": amt, "volume": vol}

    def _fetch_index_total_history(self, key_col: str) -> list[float] | None:
        """近 90 日两市口径序列（sh000001+sz399001 按日期对齐求和，key_col: amount/volume）；
        任一指数历史缺失或不足 3 日返回 None"""
        start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        today = time.strftime("%Y-%m-%d")
        df1 = self.fetch_index_daily("sh000001", start, today)
        df2 = self.fetch_index_daily("sz399001", start, today)
        if (df1 is None or df1.empty or df2 is None or df2.empty
                or key_col not in df1.columns or key_col not in df2.columns):
            return None
        a = pd.DataFrame({"d": df1["date"].astype(str),
                          "v": pd.to_numeric(df1[key_col], errors="coerce")})
        b = pd.DataFrame({"d": df2["date"].astype(str),
                          "v": pd.to_numeric(df2[key_col], errors="coerce")})
        m = a.merge(b, on="d", how="inner", suffixes=("_a", "_b"))
        if m.empty:
            return None
        total = (m["v_a"] + m["v_b"]).dropna()
        return total.tolist()

    # ---------------- 个股日 K ----------------
    def fetch_daily_kline(self, code: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
        def primary():
            return self._call_with_timeout(
                ak.stock_zh_a_hist, symbol=code, period="daily",
                start_date=start_date.replace("-", ""), end_date=end_date.replace("-", ""), adjust=adjust)
        def fallback():
            # 新浪日K（东财限流/宕机降级；列名已是英文，仅保留标准列）
            df = ak.stock_zh_a_daily(symbol=f"{_market_of(code)}{code}",
                                     start_date=start_date.replace("-", ""),
                                     end_date=end_date.replace("-", ""), adjust=adjust)
            keep = {"date", "open", "close", "high", "low", "volume", "amount"}
            out = df[[c for c in df.columns if c in keep]].copy()
            out["change_pct"] = out["close"].pct_change() * 100  # 新浪无涨跌幅列，按收盘价补算
            return out
        df = self._fetch(f"kline:{code}:{start_date}:{end_date}:{adjust}", "kline", primary,
                         ttl_seconds=3600, fallback=fallback,
                         normalize=lambda d: _normalize(d, _KLINE_COLS))
        return _to_json_safe(df)

    # ---------------- 财务指标 ----------------
    def fetch_financial(self, code: str) -> pd.DataFrame:
        # 同花顺按单季度（主营收入同比/净利同比口径更准确），失败降级新浪
        def primary():
            return self._call_with_timeout(ak.stock_financial_abstract_ths, symbol=code, indicator="按单季度")
        def fallback():
            return self._call_with_timeout(ak.stock_financial_analysis_indicator, stock=code)
        df = self._fetch(f"fin:{code}", "fin", primary, ttl_seconds=86400, fallback=fallback,
                         normalize=lambda d: _normalize(
                             d, _FINANCIAL_THS_COLS if "报告期" in d.columns else _FINANCIAL_SINA_COLS))
        return _to_json_safe(df)

    # ---------------- 资金流向 ----------------
    def fetch_fund_flow(self, code: str) -> pd.DataFrame:
        market = _market_of(code)
        def call():
            return self._call_with_timeout(ak.stock_individual_fund_flow, stock=code, market=market)
        df = self._fetch(f"fundflow:{code}", "fundflow", call, ttl_seconds=1800,
                         normalize=lambda d: _normalize(d, _FUND_FLOW_COLS))
        return _to_json_safe(df)

    # ---------------- 个股增量数据（v2.0 候选富化） ----------------
    def fetch_stock_info(self, code: str) -> dict:
        """个股基本信息（item/value 两列 → dict，含 行业/上市时间等）；失败返回 {}"""
        def call():
            return self._call_with_timeout(ak.stock_individual_info_em, symbol=code)
        df = self._fetch(f"stockinfo:{code}", "stockinfo", call, ttl_seconds=86400, required=False)
        if df is None or df.empty or "item" not in df.columns:
            return {}
        return {str(k): v for k, v in zip(df["item"].astype(str), df["value"]) if k is not None}

    def fetch_shareholder_detail(self, code: str) -> dict:
        """股东户数最新一期（户数/较上期增减比例等）；失败返回 {}"""
        def call():
            return self._call_with_timeout(ak.stock_zh_a_gdhs_detail_em, symbol=code)
        df = self._fetch(f"gdhs:{code}", "gdhs", call, ttl_seconds=86400, required=False)
        if df is None or df.empty:
            return {}
        row = df.iloc[0]
        out: dict = {}
        for cn, key in [("股东户数统计截止日期", "report_date"), ("股东户数-本次", "holder_count"),
                        ("股东户数-上次", "holder_prev"), ("股东户数-增减", "holder_diff"),
                        ("股东户数-增减比例", "holder_change_pct")]:
            if cn in df.columns:
                out[key] = row[cn]
        return out

    def fetch_institute_hold_map(self) -> dict[str, dict]:
        """机构持股全景（全市场一次拉取，缓存 6 小时）→ {code: {hold_pct, float_pct}}；失败返回 {}"""
        def call():
            return ak.stock_institute_hold()
        df = self._fetch("inst_hold", "inst_hold", call, ttl_seconds=21600, required=False,
                         normalize=lambda d: _normalize(d, _INST_COLS))
        if df is None or df.empty or "code" not in df.columns:
            return {}
        return {str(r["code"]).zfill(6): {"hold_pct": r.get("hold_pct"),
                                          "float_pct": r.get("float_pct")}
                for _, r in df.iterrows()}

    def fetch_market_fund_flow(self) -> dict:
        """大盘资金流（东财）：最新一日各指数主力净流入/净占比摘要；失败返回 {}（非必需数据）"""
        def call():
            return ak.stock_market_fund_flow()
        df = self._fetch("mkt_flow", "mkt_flow", call, ttl_seconds=600, required=False)
        if df is None or df.empty:
            return {}
        row = df.iloc[-1]
        summary: dict = {"date": str(row.get("日期", ""))}
        for col in df.columns:
            if "主力净流入" in str(col):
                summary[str(col)] = row[col]
        return summary

    # ---------------- 新闻公告 ----------------
    def fetch_news(self, code: str) -> pd.DataFrame:
        def primary():
            # vendored 修复版：上游 1.18.81 非法正则 r"　" 在 pandas3+pyarrow 下抛
            # ArrowInvalid；搜索接口空结果时自动降级个股公告源
            return self._call_with_timeout(_stock_news_fixed, code)
        def fallback():
            return pd.DataFrame(columns=["title", "content", "published_at", "source", "url"])
        df = self._fetch(f"news:{code}", "news", primary, ttl_seconds=600, fallback=fallback,
                         normalize=lambda d: _normalize(
                             d, _NEWS_COLS if "新闻标题" in d.columns else _NEWS_COLS_OLD))
        return _to_json_safe(df)

    # ---------------- 行业板块 ----------------
    def fetch_industry_spot(self) -> pd.DataFrame:
        def primary():
            return self._call_with_timeout(ak.stock_board_industry_name_em)
        def fallback():
            # 新浪行业板块（东财限流降级，列名与东财差异经 _BOARD_COLS 兼容）
            return self._call_with_timeout(ak.stock_sector_spot, indicator="新浪行业")
        df = self._fetch("industry_spot", "industry_spot", primary, ttl_seconds=600, fallback=fallback,
                         normalize=lambda d: _normalize(d, _BOARD_COLS), kind="snapshot")
        return _to_json_safe(df)

    def fetch_industry_cons(self, board_name: str) -> pd.DataFrame:
        def call():
            return self._call_with_timeout(ak.stock_board_industry_cons_em, symbol=board_name)
        df = self._fetch(f"industry_cons:{board_name}", "industry_cons", call, ttl_seconds=3600,
                         normalize=lambda d: _normalize(d, _CONS_COLS), kind="snapshot")
        return _to_json_safe(df)

    # ---------------- 主线板块箱位（主箱位 × 60 日箱位双视角，≤10 个板块） ----------------
    def fetch_board_box_positions(self, board_names: list) -> dict:
        """主线板块箱位【刚性代码逻辑】：东财行业板块历史日K近 90 交易日 close →
        主箱位 = (close - 近10日最低) / (近10日最高 - 近10日最低)；60日箱位同理取近 60 日。

        只计算调用方传入的 ≤10 个板块（不做全市场循环，成本控制）；单板块失败标注
        「数据缺失」不中断整体；接口不可用则整体降级标注缺失（绝不编造）。
        返回 {"板块名": {"main_box_pct": xx, "box60_pct": xx, "note": ""}}。"""
        out: dict = {}
        end = time.strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
        for name in (board_names or [])[:10]:
            key = str(name)
            try:
                df = self._fetch(f"board_hist:{key}", "stock_board_industry_hist_em",
                                 lambda n=key: self._call_with_timeout(
                                     ak.stock_board_industry_hist_em, symbol=n, period="日k",
                                     start_date=start, end_date=end, adjust=""),
                                 ttl_seconds=3600, required=False,
                                 normalize=lambda d: _normalize(d, _KLINE_COLS))
                if df is None or df.empty or "close" not in df.columns:
                    out[key] = {"main_box_pct": None, "box60_pct": None, "note": "数据缺失"}
                    continue
                closes = pd.to_numeric(df["close"], errors="coerce").dropna()
                if len(closes) < 2:
                    out[key] = {"main_box_pct": None, "box60_pct": None, "note": "数据不足"}
                    continue
                last = float(closes.iloc[-1])

                def _box_pct(win: pd.Series) -> float | None:
                    hi, lo = float(win.max()), float(win.min())
                    return round(float((last - lo) / (hi - lo) * 100), 1) if hi > lo else None

                out[key] = {"main_box_pct": _box_pct(closes.tail(10)),
                            "box60_pct": _box_pct(closes.tail(60)),
                            "note": ""}
            except Exception as exc:  # noqa: BLE001 单板块失败不阻塞整体
                logger.warning("板块 %s 箱位数据缺失: %s", key, exc)
                out[key] = {"main_box_pct": None, "box60_pct": None, "note": "数据缺失"}
        return out

    # ---------------- 交易日历 ----------------
    def fetch_trade_calendar(self) -> list[str]:
        def call():
            df = ak.tool_trade_date_hist_sina()
            return df["trade_date"].astype(str).tolist()
        raw = cache.get("ak:trade_calendar")
        if raw:
            return raw.split(",")
        dates = self._call_with_retry("trade_calendar", call, None)
        cache.set("ak:trade_calendar", ",".join(dates), 86400)
        return dates

    def _call_with_timeout(self, func: Callable, *args, **kwargs):
        """优先传 timeout，接口签名不支持时降级不带超时调用"""
        try:
            return func(*args, **kwargs, timeout=settings.datasource_timeout)
        except TypeError:
            return func(*args, **kwargs)


def get_datasource() -> DataSource:
    return AkshareSource()
