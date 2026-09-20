"""买卖点信号 · 本地日线仓库 · 当日增量（批1.5 容量修复）

数据源：`hq.sinajs.cn/list=`（明文 CSV，逗号拼接多只；实测 50 只/1.41s ≈36 只/s）。
字段映射（34 字段）：1 今开、2 昨收、3 现价、4 最高、5 最低、8 成交量(股)、9 成交额、30 日期。
⚠️ 快照为**当日不复权**；与 qfq 历史在「当日」等价（核验结论 v2 §11.4 已验证）。
除权检测：快照昨收(2) 与本地前收不等（>0.5%）⇒ 该票 qfq 历史基准漂移，须重建其历史段。
"""
import time

import requests

from app.services import kline_store as store

SNAPSHOT_URL = "https://hq.sinajs.cn/list="
HEADERS = {"Referer": "https://finance.sina.com.cn"}
DEFAULT_BATCH = 100
EX_DIV_TOL = 0.005
_F = {"open": 1, "pre_close": 2, "close": 3, "high": 4, "low": 5, "volume": 8, "amount": 9, "date": 30}


def _chunks(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _prefix(code: str) -> str:
    if code.startswith("6"):
        return "sh"
    if code.startswith(("4", "8", "9")):
        return "bj"
    return "sz"


def fetch_snapshot(codes: list[str], batch: int = DEFAULT_BATCH, timeout: int = 15,
                   session: requests.Session | None = None) -> tuple[dict, list]:
    """分批拉快照 → ({纯6位代码: fields}, [失败批次描述])；单批失败不阻断其他批"""
    out: dict[str, list[str]] = {}
    errors: list = []
    sess = session or requests.Session()
    for part in _chunks(list(codes), max(1, batch)):
        symbols = ",".join(f"{_prefix(c)}{c}" for c in part)
        try:
            resp = sess.get(SNAPSHOT_URL + symbols, headers=HEADERS, timeout=timeout)
            if resp.status_code != 200:
                errors.append(f"http{resp.status_code}:{len(part)}只")
                continue
            for line in resp.content.decode("gbk", "replace").splitlines():
                if '="' not in line:
                    continue
                key = line.split("=")[0].split("_")[-1]
                fields = line.split('"')[1].split(",")
                if len(fields) > _F["date"]:
                    out[key[2:] if len(key) > 6 else key] = fields
        except Exception as exc:  # noqa: BLE001 单批失败不阻断
            errors.append(f"{type(exc).__name__}:{len(part)}只:{str(exc)[:60]}")
    return out, errors


def parse_bar(code: str, fields: list[str], fallback_date: str) -> dict | None:
    """快照字段 → 日线 bar；价格全 0/空（停牌或无效）返回 None"""
    def num(idx: int):
        try:
            return float(fields[idx])
        except (IndexError, TypeError, ValueError):
            return None

    close, open_ = num(_F["close"]), num(_F["open"])
    if not close or close <= 0:
        return None
    trade_date = (fields[_F["date"]] or fallback_date).strip() or fallback_date
    return {"stock_code": code, "trade_date": trade_date, "open": open_ or close, "high": num(_F["high"]) or close,
            "low": num(_F["low"]) or close, "close": close, "volume": num(_F["volume"]),
            "amount": num(_F["amount"]), "source": "hq_snapshot", "adjust": "none"}


def ingest_today(trade_date: str | None = None, codes: list[str] | None = None,
                 path: str | None = None, batch: int = DEFAULT_BATCH) -> dict:
    """当日增量落库 + 除权检出；返回 {trade_date, batches, bars, skipped, ex_div_codes, errors, seconds}

    codes 为空时取 `fetch_spot_universe()`；两者皆空则不写任何行（不猜 universe）。
    """
    started = time.time()
    summary = {"trade_date": trade_date or "", "batches": 0, "bars": 0, "skipped": 0,
               "ex_div_codes": [], "errors": [], "seconds": 0.0, "reason": ""}
    if not codes:
        try:
            from app.datasource.fallback import get_datasource
            spot = get_datasource().fetch_spot_universe()
            codes = [str(c) for c in spot["code"].tolist()] if spot is not None and not spot.empty else []
        except Exception as exc:  # noqa: BLE001 股票池失败：不落任何行
            summary["reason"] = "error:universe"
            summary["errors"].append(f"{type(exc).__name__}: {str(exc)[:80]}")
            summary["seconds"] = round(time.time() - started, 1)
            return summary
    if not codes:
        summary["reason"] = "empty_universe"
        summary["seconds"] = round(time.time() - started, 1)
        return summary

    fallback_date = trade_date or time.strftime("%Y-%m-%d")
    snapshot, errors = fetch_snapshot(codes, batch=batch)
    summary["batches"] = (len(codes) + batch - 1) // batch
    summary["errors"] = errors
    bars, ex_div, skipped = [], [], 0
    for code in codes:
        fields = snapshot.get(code)
        if fields is None:
            skipped += 1
            continue
        bar = parse_bar(code, fields, fallback_date)
        if bar is None:
            skipped += 1
            continue
        bars.append(bar)
        prev = store.prev_close(code, bar["trade_date"], path)
        if prev and prev > 0:
            try:
                pre_close = float(fields[_F["pre_close"]])
            except (IndexError, TypeError, ValueError):
                pre_close = 0.0
            if pre_close > 0 and abs(pre_close - prev) / prev > EX_DIV_TOL:
                ex_div.append(code)
    written = store.upsert_bars(bars, path)
    summary.update(bars=written, skipped=skipped, ex_div_codes=ex_div,
                   trade_date=(bars[0]["trade_date"] if bars else summary["trade_date"]))
    summary["reason"] = "ok"
    summary["seconds"] = round(time.time() - started, 1)
    return summary
