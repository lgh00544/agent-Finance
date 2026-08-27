# -*- coding: utf-8 -*-
"""同花顺投资账本真实账户采集器（P0 数据通道，默认 ths_pnl_enable=false 关闭）

链路：同花顺 time_share / getQuotes / account_list → 归一化 → account_pnl_snapshot 表。
红线（见 方案 §9）：Cookie/密钥只进内存与 HTTP 头，禁止 log/print/response 输出明文；
采集失败只写 error 字段，不抛异常、不伪造 0 值、不阻塞调度（token 失效标 token_expired）。

结构与 DSH 插件 dsh-ths-holdings 对齐（lib/index.js collectStats/postForm）：
  load_cookie / load_fund_key / discover_fund_key / fetch_pnl / fetch_index / get_snapshot
纯函数可单测（不触网路径全覆盖）；网络/解析异常一律转 error 返回，绝不抛给调用方。
"""
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from app.core.config import settings

_API_BASE = "https://tzzb.10jqka.com.cn/caishen_httpserver"
_PNL_URL = _API_BASE + "/tzzb/caishen_fund/pc/asset/v1/time_share"
_INDEX_URL = _API_BASE + "/tzzb/caishen_fund/invest/getQuotes"
_ACCOUNT_LIST_URL = _API_BASE + "/tzzb/caishen_fund/pc/account/v1/account_list"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")
_REFERER = "https://tzzb.10jqka.com.cn/pc/index.html"
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_CST = timezone(timedelta(hours=8))


def _now_str() -> str:
    return datetime.now(_CST).strftime("%Y-%m-%d %H:%M:%S")


def normalize_cookie(block: str) -> str:
    """Cookie 归一化：按 ; 拆分 → 去每段空白（含换行）→ '; ' 重连（处理 YAML 折叠换行）"""
    if not block:
        return ""
    parts = [re.sub(r"\s+", "", p) for p in re.split(r";\s*", block)]
    return "; ".join(p for p in parts if p)


def _read_cred_block(raw: str, key: str) -> str:
    """读凭证文件某 key 块（refs.STOCK_PNL_COOKIE / STOCK_PNL_FUND_KEY，YAML 多行折叠）"""
    m = re.search(re.escape(key) + r":\s*(.*?)(?=\n\s*[A-Za-z0-9_]+\s*:|\Z)", raw, re.S)
    return m.group(1).strip() if m else ""


def _cookie_field(cookie: str, name: str) -> str:
    m = re.search(r"(?:^|;\s*)%s=([^;]*)" % re.escape(name), cookie)
    return m.group(1).strip() if m else ""


def load_cookie() -> str:
    """取 Cookie：优先 ths_pnl_cookie（非空），否则读 ths_pnl_cookie_file 的 STOCK_PNL_COOKIE 块。
    只返回归一化字符串供内存/HTTP 头使用；绝不打印、绝不落日志。"""
    if settings.ths_pnl_cookie.strip():
        return normalize_cookie(settings.ths_pnl_cookie)
    try:
        with open(settings.ths_pnl_cookie_file, encoding="utf-8") as fh:
            return normalize_cookie(_read_cred_block(fh.read(), "STOCK_PNL_COOKIE"))
    except OSError:
        return ""


def load_fund_key() -> str:
    """取 fund_key：优先 ths_pnl_fund_key（非空），否则读凭证文件 STOCK_PNL_FUND_KEY 块"""
    if settings.ths_pnl_fund_key.strip():
        return settings.ths_pnl_fund_key.strip().strip('"').strip()
    try:
        with open(settings.ths_pnl_cookie_file, encoding="utf-8") as fh:
            return _read_cred_block(fh.read(), "STOCK_PNL_FUND_KEY").strip().strip('"').strip()
    except OSError:
        return ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


def _post(url: str, payload: str, cookie: str, minimal: bool = False) -> tuple[bool, object, bool]:
    """POST 表单到同花顺账本 API（不跟随重定向）。返回 (ok, body|error, token_expired)。

    minimal=True 只带 Content-Type/UA/Cookie：account_list 网关会拒绝多余浏览器头
    （插件 lib/index.js listPortfolios 注释）。Cookie 仅经 HTTP 头传输，错误信息不含明文。"""
    req = urllib.request.Request(url, data=payload.encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if not minimal:
        req.add_header("Accept", "application/json, text/plain, */*")
        req.add_header("Accept-Language", "zh-CN,zh;q=0.9")
        req.add_header("Referer", _REFERER)
    req.add_header("User-Agent", _UA)
    req.add_header("Cookie", cookie)
    try:
        with urllib.request.build_opener(_NoRedirect()).open(req, timeout=25) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code in _REDIRECT_STATUSES:
            return False, "接口重定向未跟随 (HTTP %s)" % exc.code, False
        if exc.code in (401, 403):
            return False, "TOKEN_EXPIRED (HTTP %s)" % exc.code, True
        return False, "HTTP %s" % exc.code, False
    except Exception:
        return False, "网络错误", False
    try:
        return True, json.loads(body), False
    except ValueError:
        return False, "响应解析失败", False


def discover_fund_key(cookie: str, user_id: str = "") -> str:
    """调 account_list 自动发现第一个有效 fund_key；任何失败返回空串（由调用方走 error）"""
    uid = user_id or _cookie_field(cookie, "userid")
    payload = "terminal=1&version=0.0.0&userid=%s&user_id=%s" % (uid, uid)
    ok, body, _ = _post(_ACCOUNT_LIST_URL, payload, cookie, minimal=True)
    if not ok:
        return ""
    for item in ((body or {}).get("ex_data") or {}).get("common") or []:
        fk = str(item.get("fund_key") or "").strip()
        if fk:
            return fk
    return ""


def fetch_pnl(cookie: str, user_id: str = "", fund_key: str = "") -> dict:
    """POST time_share → 归一化今日盈亏。返回 dict 含 error/token_expired，不抛异常。

    成功：pnl_yk/pnl_pct 取当日曲线最后一点 {zf, yk}；chart_data=[{t, v}]。
    token 失效：error_msg 含「登录/过期」或 HTTP 401/403 → token_expired=true。"""
    uid = user_id or _cookie_field(cookie, "userid")
    if not fund_key:
        fund_key = load_fund_key()
    if not fund_key:
        fund_key = discover_fund_key(cookie, uid)
    payload = ("terminal=1&version=0.0.0&userid=%s&user_id=%s&manual_id=&fundid=&"
               "fund_key=%s&rzrq_fund_key=&custid=") % (uid, uid, fund_key)
    ok, body, token_expired = _post(_PNL_URL, payload, cookie)
    if not ok:
        return {"pnl_yk": None, "pnl_pct": None, "chart_data": [], "updated_at": _now_str(),
                "error": str(body), "token_expired": token_expired}
    if str((body or {}).get("error_code")) != "0":
        msg = str((body or {}).get("error_msg") or "账本拒绝请求")
        return {"pnl_yk": None, "pnl_pct": None, "chart_data": [], "updated_at": _now_str(),
                "error": msg, "token_expired": ("登录" in msg) or ("过期" in msg)}
    points = ((body or {}).get("ex_data") or {}).get("data") or []
    chart = [{"t": int(p.get("time") or 0), "v": p.get("zf")}
             for p in points if isinstance(p, dict)]
    last = points[-1] if points else {}
    return {"pnl_yk": last.get("yk"), "pnl_pct": last.get("zf"), "chart_data": chart,
            "updated_at": _now_str(), "error": "", "token_expired": False}


def fetch_index(cookie: str, user_id: str = "") -> float | None:
    """POST getQuotes → 上证指数（zqdm=1A0001）涨跌幅 %；失败返回 None（不伪造 0）"""
    uid = user_id or _cookie_field(cookie, "userid")
    payload = ("terminal=1&version=0.0.0&userid=%s&user_id=%s&code=2%%3A1A0001&date="
               % (uid, uid))
    ok, body, _ = _post(_INDEX_URL, payload, cookie)
    if not ok:
        return None
    ex_data = (body or {}).get("ex_data") or []
    if not isinstance(ex_data, list):
        return None
    for item in ex_data:
        if str(item.get("zqdm")) != "1A0001":
            continue
        price = item.get("xianjia")
        prev = item.get("zuoshou")
        try:
            if not price or not prev or float(prev) == 0:
                return None
            return round((float(price) - float(prev)) / float(prev) * 100, 2)
        except (TypeError, ValueError):
            return None
    return None


def get_snapshot(cookie: str = "", user_id: str = "", fund_key: str = "") -> dict:
    """合并「今日盈亏 + 上证指数」归一化快照；失败写 error，不抛异常、不伪造 0。

    pnl 失败 → 只返回 error（sh_pct 保持 None）；pnl 成功但指数失败 →
    pnl 值保留、error 记指数失败（诚实降级，指数为可选补充）。"""
    cookie = cookie or load_cookie()
    if not cookie:
        return {"pnl_yk": None, "pnl_pct": None, "sh_pct": None, "chart_data": [],
                "updated_at": _now_str(), "error": "未配置同花顺 Cookie", "token_expired": False}
    pnl = fetch_pnl(cookie, user_id, fund_key)
    if pnl["error"]:
        return {**pnl, "sh_pct": None}
    sh_pct = fetch_index(cookie, user_id)
    if sh_pct is None:
        return {**pnl, "sh_pct": None, "error": "指数获取失败"}
    return {**pnl, "sh_pct": sh_pct}
