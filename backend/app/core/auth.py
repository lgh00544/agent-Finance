"""轻量认证与请求级用户上下文。

多人开关关闭时完全兼容旧单用户入口；开启后除登录/健康检查外均要求
Bearer session token。授权只从认证上下文读取，不信任请求体中的 user_id。
"""
from contextvars import ContextVar
from datetime import datetime, timedelta
import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.db import repo

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


def issue_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=max(1, settings.auth_session_ttl_hours))
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
                "/api/auth/login", "/api/auth/status", "/api/health", "/health",
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
