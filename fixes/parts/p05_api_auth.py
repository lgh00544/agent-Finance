# -*- coding: utf-8 -*-
'''p05_api_auth.py：M13 / M14 / M16 / M17 / M19

覆盖文件：
  backend/app/core/auth.py            M13 登录失败锁定（LoginGuard + client_ip）/ M16 配套（会话过期改用 _now()）
  backend/app/api/routes.py           M13 接入锁定 / M14 注册门槛 / M17 删除 if False 死代码
  backend/app/core/config.py          M14 新增 REGISTER_INVITE_CODE / REGISTER_REQUIRE_APPROVAL
  backend/app/db/repo.py              M14 create_user 支持 is_active=False（待审核）
  backend/app/db/models.py            M16 _now() 改为北京时间（naive，UTC+8）
  backend/app/services/chat_handlers.py  M17 删除同花顺 _fmt_pnl 的 if False 死代码
  backend/app/factors/data_adapter.py M19 板块名归一化 + 两级匹配（sector_dict.py 无既有工具可复用，未改动）

嵌入的代码片段一律用三单引号包裹（原文含三双引号 docstring）。
每个 old 均已在当前工作区文件中确认为「恰好出现一次」且逐字一致。
'''

NAME = "api_auth"

_FILE_AUTH = "backend/app/core/auth.py"
_FILE_ROUTES = "backend/app/api/routes.py"
_FILE_CONFIG = "backend/app/core/config.py"
_FILE_REPO = "backend/app/db/repo.py"
_FILE_MODELS = "backend/app/db/models.py"
_FILE_CHAT = "backend/app/services/chat_handlers.py"
_FILE_ADAPTER = "backend/app/factors/data_adapter.py"

ITEMS = [
    {
        "id": "M13",
        "file": _FILE_AUTH,
        "summary": "登录失败锁定：新增线程安全的 LoginGuard（5 次失败锁 15 分钟）与 client_ip",
        "edits": [
            ('''import secrets''',
             '''import secrets
import threading
import time'''),
            ('''def issue_token(user_id: int) -> str:''',
             '''class LoginGuard:
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


def issue_token(user_id: int) -> str:'''),
        ],
    },
    {
        "id": "M13",
        "file": _FILE_ROUTES,
        "summary": "登录接口接入失败锁定（429 / 401 + 成功清零），补 Request 与 client_ip/login_guard 导入",
        "edits": [
            ('''from pydantic import BaseModel, Field''',
             '''from pydantic import BaseModel, Field
from starlette.requests import Request  # M13：登录失败锁定需要读取客户端 IP'''),
            ('''    current_user_is_admin,''',
             '''    client_ip,
    current_user_is_admin,'''),
            ('''    issue_token,''',
             '''    issue_token,
    login_guard,'''),
            ('''@router.post("/auth/login")
def auth_login(body: LoginBody):
    user = repo.get_user_by_credentials(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {**user, "access_token": issue_token(user["id"]), "token_type": "bearer"}''',
             '''@router.post("/auth/login")
def auth_login(body: LoginBody, request: Request):
    """登录。M13：连续失败 5 次锁定 15 分钟（用户名 + 客户端 IP 维度，成功登录清零）。"""
    guard_key = f"{body.username.strip().lower()}|{client_ip(request)}"
    locked = login_guard.check(guard_key)
    if locked > 0:
        raise HTTPException(
            status_code=429,
            detail=f"登录失败次数过多，已临时锁定，请 {max(1, locked // 60)} 分钟后再试")
    user = repo.get_user_by_credentials(body.username, body.password)
    if user is None:
        if login_guard.record_failure(guard_key) > 0:
            # 第 5 次失败即锁定：本次直接回 429，明确告知锁定窗口（避免前端只看到 401 反复重试）
            raise HTTPException(
                status_code=429,
                detail=f"登录失败次数过多，已临时锁定 {login_guard.lock_seconds // 60} 分钟")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    login_guard.reset(guard_key)
    return {**user, "access_token": issue_token(user["id"]), "token_type": "bearer"}'''),
        ],
    },
    {
        "id": "M14",
        "file": _FILE_CONFIG,
        "summary": "新增注册门槛配置项：REGISTER_INVITE_CODE（默认空=关闭）与 REGISTER_REQUIRE_APPROVAL（默认 False）",
        "edits": [
            ('''    auth_default_username: str = "legacy"
    auth_default_password: str = ""''',
             '''    auth_default_username: str = "legacy"
    auth_default_password: str = ""
    # M14：自助注册门槛（两项默认全关 = 与旧行为完全一致，既有测试语义不变）
    register_invite_code: str = ""            # REGISTER_INVITE_CODE：非空时注册必须携带匹配邀请码，否则 403
    register_require_approval: bool = False   # REGISTER_REQUIRE_APPROVAL：true 时新用户 is_active=False，待管理员审核'''),
        ],
    },
    {
        "id": "M14",
        "file": _FILE_REPO,
        "summary": "create_user 增加关键字参数 is_active（默认 True），支持「待审核」用户落库为未激活",
        "edits": [
            ('''def create_user(username: str, password: str, role: str = "researcher") -> dict:
    if role not in {"admin", "researcher", "viewer"}:
        raise ValueError("角色仅支持 admin/researcher/viewer")''',
             '''def create_user(username: str, password: str, role: str = "researcher", *,
                is_active: bool = True) -> dict:
    """创建用户；is_active=False 用于 M14「注册需人工审核」：先落库为未激活，待管理员审核。

    默认 True，保持既有调用方（自助注册 / 管理员建号 / 测试）语义完全不变。
    """
    if role not in {"admin", "researcher", "viewer"}:
        raise ValueError("角色仅支持 admin/researcher/viewer")'''),
            ('''        row = User(username=username.strip(), password_hash=hash_password(password),
                   role=role, is_active=True)''',
             '''        row = User(username=username.strip(), password_hash=hash_password(password),
                   role=role, is_active=bool(is_active))'''),
        ],
    },
    {
        "id": "M14",
        "file": _FILE_ROUTES,
        "summary": "注册接口接入邀请码校验与人工审核（默认关闭，默认行为不变）",
        "edits": [
            ('''class LoginBody(BaseModel):
    username: str
    password: str''',
             '''class LoginBody(BaseModel):
    username: str
    password: str
    # M14：注册邀请码（仅注册接口使用）。默认空串 —— REGISTER_INVITE_CODE 未配置时不校验。
    invite_code: str = ""'''),
            ('''@router.post("/auth/register")
def auth_register(body: LoginBody):
    """Self-service researcher registration for first-time local users."""
    username = body.username.strip()
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少需要 2 个字符")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="密码至少需要 8 个字符")
    try:
        user = repo.create_user(username, body.password, "researcher")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**user, "access_token": issue_token(user["id"]), "token_type": "bearer"}''',
             '''@router.post("/auth/register")
def auth_register(body: LoginBody):
    """Self-service researcher registration for first-time local users.

    M14：多用户模式下自助注册无门槛（任何匿名者都能拿到 researcher 账号），
    增加两道可配置门槛：邀请码（REGISTER_INVITE_CODE）与人工审核
    （REGISTER_REQUIRE_APPROVAL）。两项默认关闭时，本函数行为与旧版逐行等价。
    """
    username = body.username.strip()
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少需要 2 个字符")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="密码至少需要 8 个字符")
    if settings.register_invite_code and body.invite_code.strip() != settings.register_invite_code:
        raise HTTPException(status_code=403, detail="邀请码无效")
    pending = bool(settings.register_require_approval)
    try:
        # 需人工审核时先落库为未激活（is_active=False）：此时签发的 token 也过不了
        # repo.get_user_by_token 的 is_active 过滤，故下面不签发 token，只回待审核状态。
        user = repo.create_user(username, body.password, "researcher", is_active=not pending)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if pending:
        return {**user, "pending_approval": True,
                "message": "注册已提交，等待管理员审核通过后即可登录"}
    return {**user, "access_token": issue_token(user["id"]), "token_type": "bearer"}'''),
        ],
    },
    {
        "id": "M16",
        "file": _FILE_MODELS,
        "summary": "_now() 改为北京时间（UTC+8）朴素时间，不再取服务器本地时区",
        "edits": [
            ('''from datetime import datetime''',
             '''from datetime import datetime, timedelta, timezone

# M16：全库时间列都是 naive DateTime，而调度（cron 按北京时间）、行情（交易所时间）
# 与前端展示全部按 Asia/Shanghai（UTC+8）口径。原 `datetime.now()` 取服务器本地时区，
# 容器 TZ=UTC 时落库时间整体偏早 8 小时（与行情/调度对不上）。
# 这里显式取 UTC+8 后 **去掉 tzinfo**，保持 naive DateTime 列契约不变
# （给 MySQL DATETIME / SQLite 交 aware datetime 会被静默截断或报错，代价更大）。
_CN_TZ = timezone(timedelta(hours=8))'''),
            ('''def _now() -> datetime:
    return datetime.now()''',
             '''def _now() -> datetime:
    """当前北京时间（naive，UTC+8）：与调度/行情/展示口径一致（M16）。"""
    return datetime.now(_CN_TZ).replace(tzinfo=None)'''),
        ],
    },
    {
        "id": "M16",
        "file": _FILE_AUTH,
        "summary": "会话过期时间改用与 models._now() 同一北京时间时钟，避免 UTC 容器里 TTL 少 8 小时",
        "edits": [
            ('''from app.db import repo''',
             '''from app.db import repo
from app.db.models import _now  # M16 配套：会话过期与库内时间戳必须同一时钟'''),
            ('''def issue_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=max(1, settings.auth_session_ttl_hours))''',
             '''def issue_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    # M16 配套：expires_at 必须与 models._now() 用同一时钟（北京时间 naive）。
    # 否则 TZ=UTC 容器里 expires_at 落在 UTC 口径、repo.get_user_by_token 用北京口径
    # 比较，24h 会话实际 16h 就失效（repo 里较多 datetime.now() 与库列混用，详见修复报告）。
    expires_at = _now() + timedelta(hours=max(1, settings.auth_session_ttl_hours))'''),
        ],
    },
    {
        "id": "M17",
        "file": _FILE_ROUTES,
        "summary": "删除同花顺已下线接口里不可达的 if False 死代码，只留显式 410",
        "edits": [
            ('''@router.get("/account/pnl")
def account_pnl():
    """同花顺真实盈亏【已下线 2026-09-16】返回 410；原逻辑保留于 if False。"""
    raise HTTPException(status_code=410, detail="同花顺真实盈亏已下线（账本登录态不可用）")
    if False:  # === DISABLED 2026-09-16 ===
        if not settings.ths_pnl_enable:
            return {"configured": False}
        from app.services import ths_pnl as ths_pnl_service

        if not ths_pnl_service.load_cookie():
            return {"configured": False}
        return {"configured": True,
                "snapshot": ths_pnl_service.refresh_snapshot_if_needed(
                    user_id=_request_user_id(), is_admin=current_user_role() == "admin")}''',
             '''# M17：同花顺账本已于 2026-09-16 下线（登录态不可用，原因见 同花顺模块下线_方案.md）。
# 原实现在 raise 之后用 `if False:` 包住旧逻辑：永远不可达，却仍会被静态检查/阅读
# 当作活代码。这里直接删除死代码，只保留显式 410 语义；需要恢复时按方案文档的
# 解注释路径重新实现（旧实现可从 git 历史取回）。
@router.get("/account/pnl")
def account_pnl():
    """同花顺真实盈亏【已下线 2026-09-16】返回 410。"""
    raise HTTPException(status_code=410, detail="同花顺真实盈亏已下线（账本登录态不可用）")'''),
            ('''@router.post("/account/pnl/refresh")
def account_pnl_refresh():
    """同花顺凭证刷新【已下线 2026-09-16】返回 410；原逻辑保留于 if False。"""
    raise HTTPException(status_code=410, detail="同花顺真实盈亏已下线（账本登录态不可用）")
    if False:  # === DISABLED 2026-09-16 ===
        if not settings.ths_pnl_enable:
            return {"configured": False}
        from app.services import ths_pnl as ths_pnl_service

        if not ths_pnl_service.load_cookie():
            return {"configured": False}
        return {"configured": True,
                "snapshot": ths_pnl_service.refresh_snapshot_if_needed(
                    force=True, user_id=_request_user_id(),
                    is_admin=current_user_role() == "admin")}''',
             '''# M17：同花顺模块已下线（见 同花顺模块下线_方案.md），删除不可达的 `if False:` 死代码。
@router.post("/account/pnl/refresh")
def account_pnl_refresh():
    """同花顺凭证刷新【已下线 2026-09-16】返回 410。"""
    raise HTTPException(status_code=410, detail="同花顺真实盈亏已下线（账本登录态不可用）")'''),
        ],
    },
    {
        "id": "M17",
        "file": _FILE_CHAT,
        "summary": "删除同花顺 _fmt_pnl 里 return 之后的 if False 死代码",
        "edits": [
            ('''def _fmt_pnl(params: dict, hint: str) -> str:
    """今日真实盈亏【已下线 2026-09-16】改走推算口径。"""
    return "同花顺真实盈亏已下线（账本登录态不可用）"
    if False:  # === DISABLED 2026-09-16 ===
        if not (settings.ths_pnl_enable and ths_pnl.load_cookie()):
            return "同花顺未接入（THS_PNL_ENABLE=false 或未配 Cookie）"
        snap = repo.get_latest_account_pnl(
            params.get("user_id"), is_admin=params.get("user_role") == "admin") or {}
        if snap.get("token_expired"):
            return "同花顺 Cookie 过期，请到 DSH 插件重新登录"
        if snap.get("pnl_yk") is None:
            return f"今日盈亏获取失败：{snap.get('error') or '暂无数据'}"
        sh = f" 上证{snap['sh_pct']}%" if snap.get("sh_pct") is not None else ""
        return f"今日盈亏 ¥{snap['pnl_yk']:,.0f}（{snap.get('pnl_pct')}%）{sh}"''',
             '''def _fmt_pnl(params: dict, hint: str) -> str:
    """今日真实盈亏【已下线 2026-09-16】：改走推算口径，原同花顺实现已删除。

    M17：下线原因见 同花顺模块下线_方案.md；旧实现在 return 之后用 `if False:` 包住，
    永远不可达却仍会被静态检查/阅读当作活代码，故直接删除（恢复路径见方案文档）。
    """
    return "同花顺真实盈亏已下线（账本登录态不可用）"'''),
        ],
    },
    {
        "id": "M19",
        "file": _FILE_ADAPTER,
        "summary": "板块名归一化 + 「归一化精确 → 唯一子串」两级匹配，不再因空格/后缀/全半角静默返回 {}",
        "edits": [
            # 注：`import unicodedata` 由 p04_factors.py 针对同一文件的 import 区 edit 一并加入
            # （本片段只用 unicodedata）。同一行被两个片段改会让补丁应用顺序敏感 —— 先执行的
            # 那个会把后执行者的锚点吃掉 —— 故 import 区只由 p04 单方修改。
            ('''class DataAdapter:''',
             '''_SECTOR_SUFFIXES = ("行业", "板块", "概念", "指数", "产业")


def _norm_sector(name: Any) -> str:
    """板块名归一化键：去全部空白 + NFKC（全角转半角）+ 小写 + 去尾部业务后缀。

    M19：东财行业快照的 board_name 与个股 industry 字段常只差后缀/空格/全半角
    （"半导体" vs "半导体行业" vs "半导体 "），原实现用 == 精确比较，
    任一差异都静默返回 {}，让 f22-f25 四个板块因子退化成 data_missing。
    复用说明：services/sector_dict.py 里只有内联的「去空白」处理（未导出为工具函数），
    且 factors 层直接依赖 services 层会引入 DB 侧依赖链，故在因子层本地实现。
    """
    text = unicodedata.normalize("NFKC", str(name or ""))
    # str.split() 按 Unicode 空白切分：覆盖半角/全角空格、NBSP、制表符等全部空白
    text = "".join(text.split()).lower()
    for suffix in _SECTOR_SUFFIXES:
        if len(text) > len(suffix) and text.endswith(suffix):
            return text[: -len(suffix)]      # 只剥一层，避免「行业板块」这类反复剥离
    return text


class DataAdapter:'''),
            ('''        industry = self.industry()
        matches = [r for r in self.sector_rows() if str(r.get("board_name") or r.get("sector_name") or "") == industry]
        return matches[0] if len(matches) == 1 else {}''',
             '''        industry = self.industry()
        key = _norm_sector(industry)
        if not key:
            self.extra["sector_match"] = "no_industry"
            return {}
        board_rows = self.sector_rows()
        # M19：两级匹配 —— ① 归一化后精确相等；② 唯一子串（"半导体" ⊂ "半导体及元件"）。
        # 仍不唯一/无匹配则返回 {}：宁缺勿错，错配的板块因子比缺失更危险。
        exact = [r for r in board_rows
                 if _norm_sector(r.get("board_name") or r.get("sector_name")) == key]
        if len(exact) == 1:
            self.extra["sector_match"] = "normalized"
            return exact[0]
        if exact:
            self.extra["sector_match"] = "ambiguous:%d" % len(exact)
            return {}
        fuzzy = [r for r in board_rows
                 if key in _norm_sector(r.get("board_name") or r.get("sector_name"))]
        if len(fuzzy) == 1:
            self.extra["sector_match"] = "substring"
            return fuzzy[0]
        # 原因只记在 extra（不影响返回结构与调用方签名）：无匹配 vs 多义可区分排查
        self.extra["sector_match"] = "no_match" if not fuzzy else "ambiguous_substring:%d" % len(fuzzy)
        return {}'''),
        ],
    },
]
