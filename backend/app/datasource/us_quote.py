"""美股行情数据源（新浪财经 hq.sinajs.cn，GBK 编码）

【刚性代码逻辑】只做行情拉取与字段解析，不做任何市场判断。
  - 复用 http_client 共享会话（浏览器头 + 连接/读取超时拆分 + 主机 Referer）
  - 新浪美股代码前缀 gb_（如 gb_nvda），响应为 GBK 编码，需 decode 后正则解析
  - 单只字段缺失/非数字 → 丢弃该只（不抛异常中断整批）；整批失败抛清晰异常
"""
import logging
import re

from app.datasource.http_client import get as http_get

logger = logging.getLogger(__name__)

_SINA_US_URL = "http://hq.sinajs.cn/list={symbols}"
# 新浪美股返回格式：var hq_str_gb_nvda="中文名,英文名,最新价,涨跌额,涨跌幅,..."
_US_RE = re.compile(r'hq_str_gb_([a-z0-9.]+)="([^"]*)"')
_SH_RE = re.compile(r'hq_str_sh000001="([^"]*)"')


def fetch_us_quotes(symbols: list[str]) -> list[dict]:
    """批量拉取美股行情（新浪 gb_ 前缀接口）。

    symbols 形如 "gb_nvda" / "nvda" 均可（自动补 gb_ 前缀，逗号拼接）。
    返回 [{symbol, name, price, change_pct}]；字段缺失/非数字的标的自动丢弃；
    请求失败/全部解析为空抛清晰异常（上层任务兜底，不静默返回空）。"""
    if not symbols:
        return []
    codes = [s.strip().lower() for s in symbols if s.strip()]
    codes = [c if c.startswith("gb_") else f"gb_{c}" for c in codes]
    if not codes:
        return []
    url = _SINA_US_URL.format(symbols=",".join(codes))
    resp = http_get(url, referer="sina")
    if resp.status_code != 200:
        raise RuntimeError(f"新浪美股行情请求失败 status={resp.status_code}")
    text = resp.content.decode("gbk", errors="ignore")
    quotes: list[dict] = []
    for code, body in _US_RE.findall(text):
        fields = body.split(",")
        if len(fields) < 5:
            continue
        try:
            price = float(fields[1])
            change_pct = float(str(fields[4]).strip().rstrip("%"))
        except (TypeError, ValueError):
            continue
        if change_pct != change_pct:  # NaN 兜底
            continue
        quotes.append({
            "symbol": f"gb_{code}",
            "name": fields[0],
            "price": price,
            "change_pct": change_pct,
        })
    if not quotes:
        raise RuntimeError(f"新浪美股行情解析为空 codes={codes}")
    return quotes


def fetch_sh_index_open_gap() -> float | None:
    """上证指数今日开盘缺口 %（今开 vs 昨收）。

    var hq_str_sh000001="名称,今开,昨收,最新价,最高,最低,..."
    返回 (open - prev_close) / prev_close * 100；请求失败/字段缺失返回 None
    （校验任务跳过本次，不抛异常中断调度）。"""
    try:
        resp = http_get("http://hq.sinajs.cn/list=sh000001", referer="sina")
    except Exception as exc:  # noqa: BLE001 网络异常不中断校验调度
        logger.warning("上证指数行情请求异常: %s", exc)
        return None
    if resp.status_code != 200:
        logger.warning("上证指数行情请求失败 status=%s", resp.status_code)
        return None
    text = resp.content.decode("gbk", errors="ignore")
    m = _SH_RE.search(text)
    if not m:
        logger.warning("上证指数行情解析失败: %s", text[:80])
        return None
    fields = m.group(1).split(",")
    if len(fields) < 3:
        return None
    try:
        open_px = float(fields[1])
        prev_close = float(fields[2])
    except (TypeError, ValueError):
        return None
    if prev_close <= 0:
        return None
    return round((open_px - prev_close) / prev_close * 100, 4)
