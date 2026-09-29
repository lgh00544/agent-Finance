"""轻量认证与请求级用户上下文。

多人开关关闭时完全兼容旧单用户入口；开启后除登录/健康检查外均要求
Bearer session token。授权只从认证上下文读取，不信任请求体中的 user_id。
"""
from contextvars import ContextVar
from datetime import datetime, timedelta
import hashlib
import hmac
import secrets
import threading
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.db import repo
from app.db.models import _now  # M16 配套：会话过期与库内时间戳必须同一时钟

_current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)
_current_user_role: ContextVar[str | None] = ContextVar("current_user_role", default=None)
_current_user_username: ContextVar[str | None] = ContextVar("current_user_username", default=None)


def current_user_id() -> int | None:
    return _current_user_id.get()


def current_user_role() -> str | None:
    return _current_user_role.get()


def current_user_username() -> str | None:
    return _current_user_username.get()


def current_user_is_admin() -> bool:
    return current_user_role() == "admin"


def set_user_context(user_id: int | None, role: str | None = None):
    """为后台线程显式设置请求等价的用户上下文，返回可用于 reset 的 token。"""
    return _current_user_id.set(user_id), _current_user_role.set(role), _current_user_username.set(None)


def reset_user_context(tokens) -> None:
    user_token, role_token, username_token = tokens
    _current_user_id.reset(user_token)
    _current_user_role.reset(role_token)
    _current_user_username.reset(username_token)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
    return f"pbkdf2_sha256$120000${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(),
                                     int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


class LoginGuard:
    """M13：登录失败锁定（进程内实现，按「用户名 + 客户端 IP」维度计数）。

    阈值依据：连续失败 5 次锁定 15 分钟 —— 等价于单键每小时最多约 20 次尝试，
    远低于撞库/弱口令穷举所需量级；正常用户手误 4 次内仍可登录，成功即清零。
    维度取舍：键里带客户端 IP，攻击者只能锁死「自己 IP + 目标用户名」这一组合，
    不会因为恶意失败把真实用户从其他 IP 登录也一并锁掉（避免锁定型 DoS）。
    实现取舍：项目当前是单进程 uvicorn 部署，用 threading.Lock 保护的进程内字典最简单
    可靠；将来若多进程/多实例部署，需把 _entries 迁到 app.cache（Redis）才能全局生效。
    """

    def __init__(self, max_failures: int = 5, lock_seconds: int = 900,
                 window_seconds: int = 900) -> None:
        self.max_failures = max(1, int(max_failures))
        self.lock_seconds = max(1, int(lock_seconds))
        self.window_seconds = max(1, int(window_seconds))
        self._lock = threading.Lock()
        # key -> [连续失败次数, 锁定截止(monotonic 秒), 最后一次失败时间(monotonic 秒)]
        self._entries: dict[str, list] = {}

    def _prune(self, now: float) -> None:
        """滑动窗口清理：锁定已过期且超出窗口期的条目删除，防止字典无限增长（内存 DoS）。"""
        stale = [k for k, v in self._entries.items()
                 if now >= v[1] and now - v[2] > self.window_seconds]
        for key in stale:
            self._entries.pop(key, None)

    def check(self, key: str) -> int:
        """返回剩余锁定秒数（向上取整，最后一秒不提前放行）；0 表示未锁定。"""
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            entry = self._entries.get(key)
            if not entry or now >= entry[1]:
                return 0
            return int(entry[1] - now) + 1

    def record_failure(self, key: str) -> int:
        """记一次失败（窗口内累加）；达到阈值即锁定，返回剩余锁定秒数（0=未锁定）。"""
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            failures, locked_until, _last = self._entries.get(key, [0, 0.0, now])
            failures += 1
            if failures >= self.max_failures:
                locked_until = now + self.lock_seconds
            self._entries[key] = [failures, locked_until, now]
            return int(locked_until - now) if locked_until > now else 0

    def reset(self, key: str) -> None:
        """登录成功清零失败计数。"""
        with self._lock:
            self._entries.pop(key, None)

    def failures(self, key: str) -> int:
        """当前窗口内连续失败次数（仅用于提示文案/日志，不参与判定）。"""
        with self._lock:
            entry = self._entries.get(key)
            return int(entry[0]) if entry else 0


login_guard = LoginGuard()


def client_ip(request: Request) -> str:
    """登录失败计数用的客户端标识：只取 TCP 对端 IP。

    刻意不信任 X-Forwarded-For：该头可被客户端随意伪造，若用它做计数维度，
    攻击者只要每次换一个头就能永久绕过失败锁定（反代场景的 IP 维度应由 nginx 层限流承担）。
    """
    client = getattr(request, "client", None)
    return str(getattr(client, "host", "") or "unknown")


def issue_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    # M16 配套：expires_at 必须与 models._now() 用同一时钟（北京时间 naive）。
    # 否则 TZ=UTC 容器里 expires_at 落在 UTC 口径、repo.get_user_by_token 用北京口径
    # 比较，24h 会话实际 16h 就失效（repo 里较多 datetime.now() 与库列混用，详见修复报告）。
    expires_at = _now() + timedelta(hours=max(1, settings.auth_session_ttl_hours))
    repo.create_user_session(user_id, token, expires_at)
    return token


def authenticate_token(token: str) -> dict | None:
    return repo.get_user_by_token(token)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request.headers.get("Authorization", "")
        bearer = token[7:].strip() if token.lower().startswith("bearer ") else ""
        user = authenticate_token(bearer) if bearer else None
        user_id = user["id"] if user else None
        role = user["role"] if user else None
        username = user["username"] if user else None
        reset_id = _current_user_id.set(user_id)
        reset_role = _current_user_role.set(role)
        reset_username = _current_user_username.set(username)
        try:
            # SPA shell and compiled assets must remain public so an unauthenticated
            # browser can load the login screen; only API routes are gated.
            public = (not request.url.path.startswith("/api/") or request.url.path in {
                "/api/auth/login", "/api/auth/register", "/api/auth/status", "/api/health", "/health",
            })
            if settings.multi_user_enabled and not public and user is None:
                return JSONResponse(status_code=401, content={"detail": "需要有效的 Bearer 会话令牌"})
            if (settings.multi_user_enabled and role == "viewer"
                    and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}):
                return JSONResponse(status_code=403, content={"detail": "viewer 仅允许只读访问"})
            response = await call_next(request)
            return response
        finally:
            _current_user_id.reset(reset_id)
            _current_user_role.reset(reset_role)
            _current_user_username.reset(reset_username)


def require_user() -> int:
    """服务层授权入口；单用户模式返回默认用户。"""
    user_id = current_user_id()
    if user_id is not None:
        return user_id
    if settings.multi_user_enabled:
        raise HTTPException(status_code=401, detail="未认证")
    return repo.ensure_default_user()


def require_write_access() -> None:
    """写操作授权入口；多人模式下 viewer 只能读。"""
    require_user()
    if settings.multi_user_enabled and current_user_role() == "viewer":
        raise HTTPException(status_code=403, detail="viewer 仅允许只读访问")
