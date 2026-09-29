# -*- coding: utf-8 -*-
"""修复点自检（在 apply_fixes.py --apply 之后运行）

用法（项目根目录）：
    D:\\space\\self\\self\\.venv\\Scripts\\python.exe fixes\\verify_fixes.py

两类检查：
  [行为] —— 真正调用修复后的代码，断言可观测行为（强）
  [源码] —— 断言修复后的源码里存在/不存在某些构造（弱，作为回归护栏）
退出码 = 失败个数（0 表示全部通过）。
"""
from __future__ import annotations

import logging
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
BACKEND = PROJECT / "backend"
sys.path.insert(0, str(BACKEND))

RESULTS: list[tuple[str, str, str, str]] = []  # (编号, 类型, 状态, 说明)


def check(item: str, kind: str, ok, detail: str = "") -> None:
    RESULTS.append((item, kind, "PASS" if ok else "FAIL", detail))


def source(rel: str) -> str:
    return (PROJECT / rel).read_text(encoding="utf-8")


def skip(item: str, kind: str, detail: str) -> None:
    RESULTS.append((item, kind, "SKIP", detail))


# ---------------------------------------------------------------- P0-1
def p0_1() -> None:
    from app.services import signal_scan as ss

    cases = [
        (("300123", "ST Test", 19.8), (1, 1), "创业板 ST=20%"),
        (("300123", "ST Test", 5.10), (1, 0), "创业板 ST 不再是 5%"),
        (("301001", "ST Test", 19.8), (1, 1), "301 ST=20%"),
        (("688001", "ST Test", 19.8), (1, 1), "科创板 ST=20%"),
        (("689009", "ST Test", 19.8), (1, 1), "689 ST=20%"),
        (("900901", "B Share", 9.90), (0, 1), "沪 B 900xxx=10%"),
        (("200011", "B Share", 9.90), (0, 1), "深 B 200xxx=10%"),
        (("920001", "BJ", 29.8), (0, 1), "北交所 920=30%"),
        (("430047", "BJ", 29.8), (0, 1), "北交所 430=30%"),
        (("830799", "BJ", 29.8), (0, 1), "北交所 830=30%"),
        (("600000", "ST Test", 4.80), (1, 1), "主板 ST=5%（含 0.3% 容差）"),
        (("600000", "PuFa", 9.90), (0, 1), "主板=10%"),
        ((600000.0, "PuFa", 9.90), (0, 1), "float64 代码不失效"),
    ]
    bad = [label for args, want, label in cases if ss._flags(*args) != want]
    check("P0-1", "行为", not bad, "13 组涨跌幅用例；失败: %s" % (bad or "无"))


# ---------------------------------------------------------------- P0-2
def p0_2() -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.models import SignalTrigger
    from app.services import signal_scan as ss

    engine = create_engine("sqlite://")
    SignalTrigger.__table__.create(engine)
    original = ss.SessionLocal
    ss.SessionLocal = sessionmaker(bind=engine)
    row = dict(trade_date="2026-09-25", stock_code="600000", signal_id="s1", is_st=0,
               direction="buy", trigger_close=10.0, limit_up=0, dedup=0)
    try:
        first = ss._persist([dict(row), dict(row, signal_id="s2")])
        second = ss._persist([dict(row), dict(row, signal_id="s2")])
        propagated = False
        try:
            ss._persist([{"bogus_column": 1}])
        except Exception:  # noqa: BLE001 期望：非 IntegrityError 必须上抛
            propagated = True
        check("P0-2", "行为", first == 2 and second == 0 and propagated,
              "首轮写入=%s（期望 2）、幂等重跑=%s（期望 0）、非唯一约束异常上抛=%s（期望 True）"
              % (first, second, propagated))
    finally:
        ss.SessionLocal = original
        engine.dispose()


# ---------------------------------------------------------------- P0-3
def p0_3() -> None:
    from app.services import signal_scan as ss

    original = ss._scan_one
    ss._scan_one = lambda item, ctx: (time.sleep(1.0), ([], 0))[1]  # 每只 1s
    try:
        batch = [{"code": "%06d" % i} for i in range(8)]
        started = time.monotonic()
        rows, errors, dropped = ss._scan_batch(batch, {}, timeout=0.1)
        elapsed = time.monotonic() - started
        check("P0-3", "行为", elapsed < 0.6,
              "8 只各 1s、批超时 0.1s → 实际返回耗时 %.2fs（期望 <0.6s；旧实现约 1.0s+）" % elapsed)
    finally:
        ss._scan_one = original


# ---------------------------------------------------------------- P0-4
def p0_4() -> None:
    from app.datasource.http_client import RateLimiter

    interval = 0.05
    limiter = RateLimiter(interval)
    started = time.monotonic()
    threads = [threading.Thread(target=limiter.wait) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.monotonic() - started
    serialized = interval * 8
    check("P0-4", "行为", elapsed < serialized * 0.6,
          "8 线程 min_interval=%.2fs → %.3fs（旧实现串行 %.2fs）" % (interval, elapsed, serialized))


# ---------------------------------------------------------------- P0-6 (4)
def p0_6_4() -> None:
    from app.factors.data_adapter import latest

    items = [{"report_date": "2025-12-31", "roe": 10.0},
             {"report_date": "2026-03-31", "roe": 12.0}]
    legacy = latest(items)                       # 无 as_of：向后兼容，取最新一期
    early = latest(items, as_of="2026-04-01")    # 年报(120天)/一季报(30天)均未到披露截止
    on_deadline = latest(items, as_of="2026-04-30")   # 一季报法定披露截止日
    late = latest(items, as_of="2026-05-31")     # 一季报已披露（旧的统一 120 天规则会误判为不可得）
    check("P0-6-4", "行为",
          legacy.get("report_date") == "2026-03-31"
          and early == {}
          and on_deadline.get("report_date") == "2026-03-31"
          and late.get("report_date") == "2026-03-31",
          "无 as_of=%s（兼容）、as_of=2026-04-01=%s（前视被拦应空）、"
          "as_of=2026-04-30=%s（截止日当天可用）、as_of=2026-05-31=%s（分类缓冲，非统一 120 天）"
          % (legacy.get("report_date"), early or "{}",
             on_deadline.get("report_date"), late.get("report_date")))


# ---------------------------------------------------------------- M2
def m2() -> None:
    from app.datasource import market_hours
    from app.services import signal_scan as ss

    original_cal, original_session = market_hours._load_calendar, ss.SessionLocal
    warnings: list[str] = []

    class _Handler(logging.Handler):
        def emit(self, record):
            warnings.append(record.getMessage())

    handler = _Handler()
    logger = logging.getLogger("app.services.signal_scan")
    logger.addHandler(handler)
    market_hours._load_calendar = lambda: set()

    class _Query:
        def filter(self, *args, **kwargs):
            return self

        def all(self):
            return []

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def query(self, *args):
            return _Query()

    ss.SessionLocal = _Session
    try:
        ss._load_keys("2026-02-25")
        hit = any("冷却窗口显式放宽" in message for message in warnings)
        check("M2", "行为", hit,
              "日历为空时是否显式告警并放宽窗口: %s" % ("是" if hit else "否"))
    finally:
        market_hours._load_calendar, ss.SessionLocal = original_cal, original_session
        logger.removeHandler(handler)


# ---------------------------------------------------------------- M3
def m3() -> None:
    from app.services.signal_scan import _code6

    cases = {600000.0: "600000", "600000.SH": "600000", "000001": "000001",
             "600000.0": "600000", "300123": "300123"}
    bad = {k: _code6(k) for k, want in cases.items() if _code6(k) != want}
    check("M3", "行为", not bad, "失败: %s" % (bad or "无"))


# ---------------------------------------------------------------- M16
def m16() -> None:
    from app.db.models import _now

    delta = abs((_now() - datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)).total_seconds())
    check("M16", "行为", delta < 5 and _now().tzinfo is None,
          "与北京时间墙钟差 %.1fs，naive=%s（要求 <5s 且不带 tzinfo）" % (delta, _now().tzinfo is None))


# ---------------------------------------------------------------- M19
def m19() -> None:
    from app.factors.data_adapter import DataAdapter

    rows = [{"board_name": "半导体行业", "sector_5d": 3.2}, {"board_name": "银行", "sector_5d": 1.0}]
    fuzzy = DataAdapter(extra={"industry": "半导体", "as_of": "2026-04-01"}, sectors=rows).sector()
    exact = DataAdapter(extra={"industry": "半导体行业"}, sectors=rows).sector()
    missing = DataAdapter(extra={"industry": "不存在板块"}, sectors=rows).sector()
    check("M19", "行为",
          bool(fuzzy) and bool(exact) and missing == {},
          "后缀差异命中=%s、精确命中=%s、无匹配仍返回空=%s"
          % (bool(fuzzy), bool(exact), missing == {}))


# ------------------------------------------------------- 源码级护栏
# 说明：这些是「弱断言」—— 只证明修复后的代码里存在/不存在某构造，不证明行为正确；
# 行为正确性由上面的 [行为] 检查与用户侧的 pytest 回归共同保证。
SOURCE_GUARDS = [
    # --- signal_scan.py ---
    ("M1", "backend/app/services/signal_scan.py", r"信号扫描落库失败", True,
     "_persist 已移入 try 并单独 catch"),
    ("M4", "backend/app/services/signal_scan.py", r"exc_info=True", True, "异常日志带堆栈"),
    ("M5", "backend/app/services/signal_scan.py", r"eligible = max\(0,", True, "eligible 下夹紧到 0"),
    ("P0-1", "backend/app/services/signal_scan.py", r"def _limit_pct", True, "涨跌幅按号段+ST 规则"),
    ("P0-3", "backend/app/services/signal_scan.py",
     r"pool\.shutdown\(wait=False, cancel_futures=True\)\s*\n\s*return rows, errors, dropped", True,
     "批超时后显式不等待（无 with 二次 shutdown）"),
    # --- scheduler/jobs.py ---
    ("P0-5", "backend/app/scheduler/jobs.py",
     r'cache\.get_lock_owner\("scheduler:leader"\) == _leader_owner', True,
     "任务执行前 leader fencing 校验"),
    ("P0-5", "backend/app/scheduler/jobs.py", r"def _leader_demote", True, "失租统一降级"),
    ("M6", "backend/app/scheduler/jobs.py", r"def _today_cn", True, "统一上海时间 helper"),
    ("M7", "backend/app/scheduler/jobs.py",
     r'acquire_lock_owner\("kline_ingest"', True, "kline_ingest 锁带 owner + 收窄 TTL"),
    ("M9", "backend/app/scheduler/jobs.py", r"def _add_job", True, "add_job 统一包装 + 异常降级"),
    ("M15", "backend/app/scheduler/jobs.py", r"def _purge_expired_sessions", True, "过期会话清理"),
    ("M17", "backend/app/scheduler/jobs.py", r"if False", False, "jobs.py 无裸 if False 死代码"),
    # --- datasource / db ---
    ("P0-4", "backend/app/datasource/http_client.py",
     r"start = max\(now, self\._last \+ self\._min_interval\)", True,
     "锁内预约 + 锁外 sleep（不持锁 sleep）"),
    ("M10", "backend/app/datasource/http_client.py", r"raise_for_status: bool = True", True,
     "默认校验 HTTP 状态码（保留逃生口）"),
    ("M11", "backend/app/datasource/http_client.py", r"HTTPAdapter", True, "共享会话连接池 + 重试"),
    ("M12", "backend/app/db/session.py", r"db_pool_size", True, "连接池容量可配（默认 20/20）"),
    ("M12", "backend/app/core/config.py", r"db_pool_size", True, "连接池配置字段"),
    # --- auth / api / models ---
    ("M13", "backend/app/core/auth.py", r"class LoginGuard", True, "登录失败锁定"),
    ("M13", "backend/app/api/routes.py", r"login_guard\.check", True, "登录接口接入锁定"),
    ("M14", "backend/app/core/config.py", r"register_invite_code", True, "注册邀请码配置"),
    ("M14", "backend/app/core/config.py", r"register_require_approval", True, "注册人工审核配置"),
    ("M14", "backend/app/api/routes.py", r"settings\.register_invite_code", True, "注册门槛接入"),
    ("M16", "backend/app/db/models.py", r"datetime\.now\(_CN_TZ\)\.replace\(tzinfo=None\)", True,
     "_now() 取上海时间且保持 naive"),
    ("M17", "backend/app/api/routes.py", r"if False", False, "routes.py 无裸 if False 死代码"),
    ("M17", "backend/app/services/chat_handlers.py", r"if False", False,
     "chat_handlers.py 无裸 if False 死代码"),
    # --- factors ---
    ("P0-6-4", "backend/app/factors/data_adapter.py", r"DISCLOSURE_LAG_DAYS", True,
     "财报披露滞后缓冲常数"),
    ("P0-6-3", "backend/app/services/factor_ic.py", r"KLINE_ADJUST", True, "复权口径门禁"),
    ("M19", "backend/app/factors/data_adapter.py", r"def _norm_sector", True, "板块名归一化"),
    ("M20", "backend/app/factors/data_adapter.py", r"_KEY_SOURCES", True, "跨源来源白名单"),
    ("M20", "backend/app/factors/data_adapter.py", r"def find_in", True, "显式指定来源取数"),
    ("P0-7", "backend/app/services/factor_ic.py", r"exclude_codes", True, "ST/退市整票剔除"),
    ("P0-7", "backend/app/services/factor_ic.py", r"def _is_limit_board", True, "一字板/停牌样本剔除"),
]


def guards() -> None:
    for item, rel, pattern, want, note in SOURCE_GUARDS:
        try:
            text = source(rel)
        except OSError as exc:
            skip("%s[源码]" % item, "源码", "%s 读取失败: %s" % (rel, exc))
            continue
        found = re.search(pattern, text, re.S) is not None
        check(item, "源码", found == want, "%s（%s）" % (note, rel))


def main() -> int:
    for name, func in (("P0-1", p0_1), ("P0-2", p0_2), ("P0-3", p0_3), ("P0-4", p0_4),
                       ("P0-6-4", p0_6_4), ("M2", m2), ("M3", m3), ("M16", m16), ("M19", m19)):
        try:
            func()
        except Exception as exc:  # noqa: BLE001 自检脚本本身不得因单项失败中断
            check(name, "行为", False, "检查执行异常: %s: %s" % (type(exc).__name__, exc))
    guards()

    width = max(len(item) for item, _, _, _ in RESULTS)
    for item, kind, status, detail in RESULTS:
        print("%-*s | %-4s | %-4s | %s" % (width, item, kind, status, detail))
    failed = sum(1 for _, _, status, _ in RESULTS if status == "FAIL")
    print("\n合计 %d 项：PASS %d / FAIL %d / SKIP %d"
          % (len(RESULTS),
             sum(1 for _, _, s, _ in RESULTS if s == "PASS"),
             failed,
             sum(1 for _, _, s, _ in RESULTS if s == "SKIP")))
    return failed


if __name__ == "__main__":
    sys.exit(main() if __package__ is None else 0)
