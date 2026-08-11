"""
麦蕊智数（mairui.club）增强数据源（可选，默认关闭）

与 akshare_source 并列的数据源实现：仅实现 v2.0 选股机制所需的高级资金面/股东面字段，
基础行情数据（快照/日K/新闻/行业/财务/日历）不在此实现，继续由 akshare 提供（东财→新浪双通道）。

调用策略（核心：按需调用、节省配额）：
  1. 仅在 MAIRUI_ENABLE=true 时由数据源工厂装配，默认关闭时系统行为与之前完全一致；
  2. 所有调用带当日缓存（同日同标的不重复请求，不二次消耗配额）；
  3. 请求失败 / 返回空 / 配额超限（返回 101）时抛 DataSourceError，
     由上层 FallbackSource 回退 akshare 现有字段，中文日志记录原因，不报错中断。

已核实的官方端点（licence 拼在 URL 末尾路径段，Get 请求，标准 JSON）：
  /hsmy/lscjt/{code}/{licence}   最近 10 天成交分布（超大单/大单/小单/散单净流入，拼音缩写字段）
  /hsmy/jddxt/{code}/{licence}   最近 10 天阶段主力动向（近 3/5/10 日主力净流入）
  /hscp/gdbh/{code}/{licence}    股东变化趋势（jzrq 截止日期 / gdhs 股东户数 / bh 比上期变化）
【刚性代码逻辑】只做数据采集与文本规整，不做任何市场判断；字段缺失一律降级不阻塞。
"""
import json
import logging
import re
import time
from typing import Any

import pandas as pd

from app.cache import cache
from app.core.config import settings
from app.datasource.base import DataSourceError
from app.datasource.http_client import get as http_get

logger = logging.getLogger(__name__)

# 已核实的官方端点（licence 由 _get_json 统一拼接）
_EP_LSCJT = "/hsmy/lscjt"   # 最近10天成交分布（超大单/大单/小单/散单净流入）
_EP_GDBH = "/hscp/gdbh"     # 股东变化趋势（jzrq 截止日期 / gdhs 股东户数 / bh 比上期变化）
_QUOTA_MARK = "101"         # 官方约定：当日请求次数超限标记
_RETRY_DELAYS = (1.5, 3.0, 6.0)  # 指数退避（与 akshare 源一致）
_TTL_DAY = 86400            # 当日缓存：同日同标的重复请求不二次调用

# 麦蕊成交分布字段为拼音缩写（实测确认，与 akshare 中文列名不同）：
#   t=日期  cddlr=超大单流入 cddjlr=超大单净流入  ddlr=大单流入 ddjlr=大单净流入
#   xdlr=小单流入 xdjlr=小单净流入  sdlr=散单流入 sdjlr=散单净流入  qbjlr=全部净流入
_LSCJT_FIELDS = {
    "date": "t",
    "super_large_net": "cddjlr",
    "large_net": "ddjlr",
    "small_net": "xdjlr",
}


def _fuzzy_key(row: dict, identity: str, *metric: str) -> str | None:
    """键名需包含 identity，且命中任意 metric 关键词（metric 为空则只匹配 identity）。
    找不到返回 None"""
    if not identity:
        return None
    for key in row.keys():
        s = str(key)
        if identity in s and (not metric or any(m in s for m in metric)):
            return key
    return None


def _row_value(row: dict, key: str | None) -> float | None:
    """按已解析出的精确键名取值并转 float；无键/值缺失/脏数据返回 None。
    不做二次模糊匹配：「大单净流入」是「超大单净流入」的子串，
    若再把键名交给 _fuzzy_key 会绕过排除逻辑误命中超大单列。"""
    if not key:
        return None
    try:
        value = row[key]
        if value is None or (isinstance(value, float) and value != value):  # NaN
            return None
        return float(value)
    except (TypeError, ValueError, KeyError):
        return None


def _parse_change_pct(value: Any) -> float | None:
    """把「比上期变化」文本规范化为带符号百分比数值（纯文本解析，非市场判断）"""
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace("％", "")
    if not text:
        return None
    neg = any(k in text for k in ("下降", "减少", "下跌", "负", "-"))
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if not m:
        return None
    num = float(m.group())
    if neg and num > 0:
        num = -num
    return round(num, 2)


class MairuiSource:
    """麦蕊智数数据源：v2.0 富化所需的高级资金面/股东面字段"""

    def __init__(self) -> None:
        if not settings.mairui_licence:
            raise DataSourceError("麦蕊证书未配置：请在 .env 设置 MAIRUI_LICENCE 后重启后端")

    # ---------------- 统一请求封装（缓存 + 重试 + 配额识别） ----------------
    def _get_json(self, endpoint: str, code: str) -> list:
        """GET 麦蕊接口 → JSON 列表；当日缓存；失败抛 DataSourceError（中文原因）"""
        cache_key = f"mairui:{endpoint}:{code}"
        cached = cache.get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except (ValueError, TypeError):
                pass
        url = f"{settings.mairui_base_url.rstrip('/')}{endpoint}/{code}/{settings.mairui_licence}"
        last_err: Exception | None = None
        for attempt, delay in enumerate(_RETRY_DELAYS, 1):
            try:
                # 共享连接池 + 浏览器请求头（与 akshare 源同款请求加固，降被限流概率）
                resp = http_get(url, referer=settings.mairui_base_url,
                                timeout=settings.datasource_timeout)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, str) and _QUOTA_MARK in data:
                    raise DataSourceError("麦蕊当日请求次数超限（101），本次回退 akshare 数据")
                if not isinstance(data, list) or not data:
                    raise DataSourceError(f"麦蕊 {endpoint}/{code} 返回数据为空")
                cache.set(cache_key, json.dumps(data, ensure_ascii=False), _TTL_DAY)
                return data
            except DataSourceError:
                raise
            except Exception as exc:  # noqa: BLE001 网络/JSON 异常统一重试
                last_err = exc
                logger.warning("麦蕊 %s/%s 第 %d 次请求失败: %s", endpoint, code, attempt, exc)
                if attempt < len(_RETRY_DELAYS):
                    time.sleep(delay)
        raise DataSourceError(f"麦蕊 {endpoint}/{code} 请求失败: {last_err}")

    # ---------------- 资金流（对齐 akshare 标准列，供 v2.0 富化与打分） ----------------
    def fetch_fund_flow(self, code: str) -> pd.DataFrame:
        """最近 10 天成交分布 → 标准列 DataFrame：
        date/super_large_net/large_net/medium_net(None)/small_net/main_net_inflow。
        主力净流入 = 超大单 + 大单（纯算术，两桶均有效才计算，缺失不填 0）；
        近 3/5/10 日累计由调用方 tail 求和（以当日为锚点）。
        字段缺失时返回空表（上层回退 akshare / 标注当日不可用），不抛异常。
        """
        try:
            rows = self._get_json(_EP_LSCJT, code)
        except Exception as exc:  # noqa: BLE001
            logger.warning("麦蕊资金流 %s 不可用，回退 akshare: %s", code, exc)
            return pd.DataFrame()
        records: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            super_net = _row_value(row, _LSCJT_FIELDS["super_large_net"])
            large_net = _row_value(row, _LSCJT_FIELDS["large_net"])
            small_net = _row_value(row, _LSCJT_FIELDS["small_net"])
            if super_net is None and large_net is None and small_net is None:
                continue  # 该行无任何资金桶 → 不可用（不填占位）
            records.append({
                "date": str(row.get(_LSCJT_FIELDS["date"], ""))[:10],
                "super_large_net": super_net,
                "large_net": large_net,
                "medium_net": None,   # 麦蕊无中单桶（四桶为超大/大/小/散），保持缺失
                "small_net": small_net,
            })
        if not records:
            logger.warning("麦蕊成交分布 %s 无可用字段（字段名可能已变更），回退 akshare", code)
            return pd.DataFrame()
        df = pd.DataFrame(records)
        # 主力净流入 = 超大单 + 大单；任一元桶缺失 → NaN（不伪造 0，防历史/缺失冒充当日）
        df["main_net_inflow"] = df.apply(
            lambda r: r["super_large_net"] + r["large_net"]
            if pd.notna(r["super_large_net"]) and pd.notna(r["large_net"])
            else float("nan"), axis=1)
        df = df.dropna(subset=["date"]).reset_index(drop=True)
        return df

    # ---------------- 股东户数（对齐 akshare 返回键） ----------------
    def fetch_shareholder_detail(self, code: str) -> dict:
        """股东户数最新一期 → {report_date/holder_count/holder_change_pct}；失败返回 {}（回退 akshare）"""
        try:
            rows = self._get_json(_EP_GDBH, code)
            latest = rows[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning("麦蕊股东户数 %s 不可用，回退 akshare: %s", code, exc)
            return {}
        out: dict = {}
        if (key := _fuzzy_key(latest, "jzrq")) is not None:
            out["report_date"] = str(latest[key])[:10]
        if (key := _fuzzy_key(latest, "gdhs")) is not None:
            out["holder_count"] = latest[key]
        if (key := _fuzzy_key(latest, "bh")) is not None:
            change = _parse_change_pct(latest[key])
            if change is not None:
                out["holder_change_pct"] = change
        return out
