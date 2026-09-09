"""Bounded public web evidence; external text is data, never an instruction."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import ipaddress
import re
import socket
import time
from urllib.parse import parse_qs, quote_plus, urljoin, urlsplit, urlunsplit

import urllib3

from app.db import repo

MAX_BYTES = 800_000
TIMEOUT = (5, 12)
TOTAL_TIMEOUT = 20
MAX_REDIRECTS = 3
_ZONE = timezone(timedelta(hours=8))


def _today() -> str:
    return datetime.now(_ZONE).date().isoformat()


def _require_live(trade_date: str) -> None:
    if trade_date != _today():
        raise ValueError("网页证据仅可用于当天实时模拟；历史重放禁止联网")


def _resolve_public(url: str) -> tuple[str, str, str, int]:
    if not isinstance(url, str) or len(url) > 4096 or any(ord(c) < 32 for c in url):
        raise ValueError("无效公网 URL")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("仅允许无凭证的 http/https 公网 URL")
    host = parsed.hostname.lower().rstrip(".").encode("idna").decode("ascii")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in {80, 443} or host in {"localhost", "localhost.localdomain"}:
        raise ValueError("禁止访问本机或非网页端口")
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
    try:
        addresses = future.result(timeout=TIMEOUT[0])
    except FutureTimeout as exc:
        raise TimeoutError("域名解析超时") from exc
    except socket.gaierror as exc:
        raise ValueError("域名解析失败") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    if not addresses:
        raise ValueError("域名没有可用地址")
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0].split("%")[0])
        if not ip.is_global or ip.is_multicast or ip.is_unspecified:
            raise ValueError("禁止访问内网、本机或保留地址")
    normalized = urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))
    return host, normalized, str(addresses[0][4][0]), port


def _public_host(url: str) -> tuple[str, str]:
    host, normalized, _, _ = _resolve_public(url)
    return host, normalized


def _open_public(url: str, remaining: float):
    """Pin the validated IP, including TLS hostname validation, to prevent DNS rebinding."""
    host, normalized, address, port = _resolve_public(url)
    parsed = urlsplit(normalized)
    timeout = urllib3.Timeout(connect=min(TIMEOUT[0], remaining),
                              read=min(TIMEOUT[1], remaining), total=remaining)
    if parsed.scheme == "https":
        pool = urllib3.HTTPSConnectionPool(address, port=port, timeout=timeout,
                                           assert_hostname=host, server_hostname=host,
                                           cert_reqs="CERT_REQUIRED")
    else:
        pool = urllib3.HTTPConnectionPool(address, port=port, timeout=timeout)
    target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    try:
        response = pool.urlopen("GET", target, headers={
            "Host": parsed.netloc, "User-Agent": "PaperResearch/1.0",
            "Accept": "text/html,text/plain,application/xhtml+xml", "Accept-Encoding": "identity",
        }, redirect=False, retries=False, preload_content=False)
    except Exception:
        pool.close()
        raise
    return response, pool, host, normalized


def _download(url: str) -> tuple[str, str, bytes, str, list[str]]:
    deadline = time.monotonic() + TOTAL_TIMEOUT
    visited = []
    for hop in range(MAX_REDIRECTS + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("网页读取总时限已到")
        response, pool, host, normalized = _open_public(url, remaining)
        visited.append(normalized)
        try:
            if response.status in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location or hop == MAX_REDIRECTS:
                    raise ValueError("网页重定向缺少目标或超过次数限制")
                url = urljoin(normalized, location)
                continue
            if not 200 <= response.status < 300:
                raise ValueError(f"网页 HTTP 状态 {response.status}")
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type.split(";")[0].strip() not in {"text/html", "text/plain", "application/xhtml+xml"}:
                raise ValueError("网页类型不支持")
            if response.headers.get("Content-Encoding", "identity").lower() not in {"", "identity"}:
                raise ValueError("拒绝压缩正文以控制解压资源")
            length = response.headers.get("Content-Length")
            if length and int(length) > MAX_BYTES:
                raise ValueError("网页正文超过大小限制")
            chunks, total = [], 0
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError("网页读取总时限已到")
                chunk = response.read(min(16_384, MAX_BYTES + 1 - total), decode_content=False)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("网页正文超过大小限制")
                chunks.append(chunk)
            charset = re.search(r"charset\s*=\s*['\"]?([a-zA-Z0-9_-]+)", content_type)
            encoding = charset.group(1) if charset else "utf-8"
            return host, normalized, b"".join(chunks), encoding, visited
        finally:
            response.close()
            pool.close()
    raise ValueError("网页重定向超过次数限制")


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts, self.parts, self.links = [], [], []
        self.hidden = 0
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        self.in_title = tag == "title" or self.in_title
        values = dict(attrs)
        if tag == "a" and "result__a" in (values.get("class") or "").split():
            self.links.append(values.get("href") or "")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
            if self.in_title:
                self.title_parts.append(data)


def _text(html: str) -> tuple[str, str]:
    page = _PageParser()
    page.feed(html)
    return (" ".join(" ".join(page.title_parts).split())[:512],
            " ".join(" ".join(page.parts).split())[:6000])


def fetch(account_id: int, trade_date: str, url: str, stock_code: str = "") -> dict:
    _require_live(trade_date)
    fetched_at = datetime.now(_ZONE).isoformat()
    values = {"url": str(url)[:4096], "domain": "", "title": "", "excerpt": "",
              "published_at": "", "fetched_at": fetched_at, "fact_as_of": fetched_at,
              "content_hash": "", "status": "error", "error": "",
              "trust": "external_evidence_only", "is_instruction": False}
    redirects = []
    try:
        host, normalized, content, encoding, redirects = _download(url)
        title, excerpt = _text(content.decode(encoding, errors="replace"))
        values.update(url=normalized, domain=host, title=title, excerpt=excerpt,
                      content_hash=hashlib.sha256(content).hexdigest(), status="ok")
    except Exception as exc:
        values["error"] = str(exc)[:256]
    evidence_id = repo.create_paper_web_evidence(account_id, trade_date, stock_code, values)
    return {"id": evidence_id, "account_id": account_id, "trade_date": trade_date,
            "stock_code": stock_code, "redirects": redirects, **values}


def search(account_id: int, trade_date: str, query: str, stock_code: str = "", limit: int = 5) -> dict:
    _require_live(trade_date)
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(str(query)[:120])}"
    try:
        _, normalized, content, encoding, _ = _download(search_url)
        parser = _PageParser()
        parser.feed(content.decode(encoding, errors="replace"))
        rows, seen = [], set()
        for link in parser.links:
            url = urljoin(normalized, link)
            parsed = urlsplit(url)
            if parsed.hostname in {"duckduckgo.com", "html.duckduckgo.com"}:
                url = (parse_qs(parsed.query).get("uddg") or [url])[0]
            if url in seen:
                continue
            seen.add(url)
            rows.append(fetch(account_id, trade_date, url, stock_code))
            if len(rows) >= max(1, min(int(limit), 5)):
                break
        return {"query": query, "results": rows, "status": "ok",
                "search_url": normalized, "search_hash": hashlib.sha256(content).hexdigest(),
                "trust": "external_evidence_only"}
    except Exception as exc:
        return {"query": query, "results": [], "status": "error", "error": str(exc)[:256]}
