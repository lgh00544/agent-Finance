"""同花顺真实账户采集器（ths_pnl）测试：不触网，_post 全部 mock

覆盖指令 §六 / 方案 §7.4：Cookie 归一化、凭证块读取、userid 提取、
payload 构造（fetch_pnl/fetch_index/discover_fund_key）、返回解析、失败容错
（网络/HTTP/解析/token 过期 → error 字段，不抛异常不伪造 0）、get_snapshot 合并、
repo upsert/get_latest/list 落库闭环。红线：所有断言不含 Cookie 明文。
"""
import pytest

from app.db import repo
from app.db.session import init_db
from app.services import ths_pnl


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    init_db()  # 建全部表（含 account_pnl_snapshot）


def _fake_post(result):
    """构造 _post 的 mock 返回 (ok, body|err, token_expired)"""

    def _post(url, payload, cookie, minimal=False):
        return result

    return _post


# ---------------- Cookie 归一化 / 凭证读取 / userid ----------------

def test_normalize_cookie_folds_yaml_lines():
    """YAML 多行折叠 → 单行：每段去空白后 '; ' 重连"""
    raw = ("a=1; b = 2 ;\n   c=3\n;  d=4")
    assert ths_pnl.normalize_cookie(raw) == "a=1; b=2; c=3; d=4"


def test_normalize_cookie_empty():
    assert ths_pnl.normalize_cookie("") == ""
    assert ths_pnl.normalize_cookie("   ") == ""


def test_read_cred_block_parses_inline_scalar():
    """真实凭证文件为 inline 标量（值在冒号同行，已实测确认无 >- 折叠标记）"""
    raw = ("refs:\n"
           "  STOCK_PNL_COOKIE: a=1; b = 2\n"
           "  STOCK_PNL_FUND_KEY: \"125118489\"\n"
           "  OTHER: x\n")
    assert ths_pnl._read_cred_block(raw, "STOCK_PNL_COOKIE") == "a=1; b = 2"
    assert ths_pnl._read_cred_block(raw, "STOCK_PNL_FUND_KEY") == '"125118489"'


def test_cookie_field_extract_userid():
    cookie = "sess_tk=abc; userid=765253304; other=1"
    assert ths_pnl._cookie_field(cookie, "userid") == "765253304"
    assert ths_pnl._cookie_field("a=1; b=2", "userid") == ""


def test_load_cookie_prefers_config_cookie(monkeypatch):
    monkeypatch.setattr(ths_pnl.settings, "ths_pnl_cookie", "  a=1 ; b = 2 ")
    assert ths_pnl.load_cookie() == "a=1; b=2"


def test_load_cookie_missing_file_empty(monkeypatch):
    monkeypatch.setattr(ths_pnl.settings, "ths_pnl_cookie", "")
    monkeypatch.setattr(ths_pnl.settings, "ths_pnl_cookie_file", r"Z:\no\such\file.yaml")
    assert ths_pnl.load_cookie() == ""


# ---------------- fetch_pnl：解析与失败容错 ----------------

def test_fetch_pnl_success(monkeypatch):
    body = {"error_code": "0", "ex_data": {"data": [
        {"time": 34200000, "zf": -0.2, "yk": -68.0},
        {"time": 34260000, "zf": -0.6, "yk": -204.0},
    ]}}
    monkeypatch.setattr(ths_pnl, "_post", _fake_post((True, body, False)))
    monkeypatch.setattr(ths_pnl, "load_fund_key", lambda: "125118489")
    r = ths_pnl.fetch_pnl("userid=765253304")
    assert r["error"] == ""
    assert r["pnl_yk"] == -204.0
    assert r["pnl_pct"] == -0.6
    assert r["chart_data"] == [{"t": 34200000, "v": -0.2}, {"t": 34260000, "v": -0.6}]
    assert r["token_expired"] is False


def test_fetch_pnl_api_rejected(monkeypatch):
    body = {"error_code": "-1", "error_msg": "账本拒绝请求"}
    monkeypatch.setattr(ths_pnl, "_post", _fake_post((True, body, False)))
    r = ths_pnl.fetch_pnl("userid=1")
    assert r["pnl_yk"] is None
    assert "账本拒绝请求" in r["error"]
    assert r["token_expired"] is False


def test_fetch_pnl_login_expired_flag(monkeypatch):
    body = {"error_code": "-99", "error_msg": "登录已过期，请重新登录"}
    monkeypatch.setattr(ths_pnl, "_post", _fake_post((True, body, False)))
    r = ths_pnl.fetch_pnl("userid=1")
    assert r["token_expired"] is True


def test_fetch_pnl_http_401_token_expired(monkeypatch):
    monkeypatch.setattr(ths_pnl, "_post", _fake_post((False, "TOKEN_EXPIRED (HTTP 401)", True)))
    r = ths_pnl.fetch_pnl("userid=1")
    assert r["token_expired"] is True
    assert "401" in r["error"]


def test_fetch_pnl_redirect_not_expired(monkeypatch):
    monkeypatch.setattr(ths_pnl, "_post", _fake_post((False, "接口重定向未跟随 (HTTP 307)", False)))
    r = ths_pnl.fetch_pnl("userid=1")
    assert r["token_expired"] is False
    assert "307" in r["error"]


def test_fetch_pnl_network_error_no_crash(monkeypatch):
    monkeypatch.setattr(ths_pnl, "_post", _fake_post((False, "网络错误", False)))
    r = ths_pnl.fetch_pnl("userid=1")
    assert r["error"] == "网络错误"
    assert r["pnl_yk"] is None
    assert r["token_expired"] is False


def test_fetch_pnl_auto_discover_fund_key(monkeypatch):
    """fund_key 空时走 load_fund_key → discover_fund_key 兜底"""
    body = {"error_code": "0", "ex_data": {"data": [{"time": 1, "zf": 0.5, "yk": 1.0}]}}
    calls = {}

    def _post(url, payload, cookie, minimal=False):
        calls["payload"] = payload
        return (True, body, False)

    monkeypatch.setattr(ths_pnl, "_post", _post)
    monkeypatch.setattr(ths_pnl, "load_fund_key", lambda: "")
    monkeypatch.setattr(ths_pnl, "discover_fund_key", lambda c, u: "999888")
    r = ths_pnl.fetch_pnl("userid=7")
    assert r["error"] == ""
    assert "fund_key=999888" in calls["payload"]
    assert "userid=7" in calls["payload"]


# ---------------- fetch_index：解析与失败容错 ----------------

def test_fetch_index_success_sh_pct(monkeypatch):
    body = {"ex_data": [
        {"zqdm": "000001", "xianjia": 100, "zuoshou": 100},
        {"zqdm": "1A0001", "xianjia": 3210.5, "zuoshou": 3200.0},
    ]}
    monkeypatch.setattr(ths_pnl, "_post", _fake_post((True, body, False)))
    assert ths_pnl.fetch_index("userid=1") == 0.33  # round((3210.5-3200)/3200*100, 2)


def test_fetch_index_missing_returns_none(monkeypatch):
    monkeypatch.setattr(ths_pnl, "_post", _fake_post((True, {"ex_data": []}, False)))
    assert ths_pnl.fetch_index("userid=1") is None


def test_fetch_index_error_returns_none(monkeypatch):
    monkeypatch.setattr(ths_pnl, "_post", _fake_post((False, "网络错误", False)))
    assert ths_pnl.fetch_index("userid=1") is None


# ---------------- discover_fund_key ----------------

def test_discover_fund_key_first_valid(monkeypatch):
    body = {"ex_data": {"common": [
        {"fund_key": "", "manualname": "空"},
        {"fund_key": "125118489", "manualname": "主账户"},
        {"fund_key": "666", "manualname": "二账户"},
    ]}}
    monkeypatch.setattr(ths_pnl, "_post", _fake_post((True, body, False)))
    assert ths_pnl.discover_fund_key("userid=1") == "125118489"


def test_discover_fund_key_fail_empty(monkeypatch):
    monkeypatch.setattr(ths_pnl, "_post", _fake_post((False, "网络错误", False)))
    assert ths_pnl.discover_fund_key("userid=1") == ""


# ---------------- get_snapshot：合并与降级 ----------------

def test_get_snapshot_no_cookie_error(monkeypatch):
    monkeypatch.setattr(ths_pnl, "load_cookie", lambda: "")
    r = ths_pnl.get_snapshot()
    assert r["error"] == "未配置同花顺 Cookie"
    assert r["pnl_yk"] is None
    assert r["sh_pct"] is None
    assert r["token_expired"] is False


def test_get_snapshot_pnl_fail_skips_index(monkeypatch):
    monkeypatch.setattr(ths_pnl, "load_cookie", lambda: "userid=1")
    monkeypatch.setattr(ths_pnl, "fetch_pnl",
                        lambda c, u="", f="": {"pnl_yk": None, "pnl_pct": None, "chart_data": [],
                                               "updated_at": "x", "error": "网络错误",
                                               "token_expired": False})
    fetched = {"called": False}

    def _idx(c, u=""):
        fetched["called"] = True
        return 1.0

    monkeypatch.setattr(ths_pnl, "fetch_index", _idx)
    r = ths_pnl.get_snapshot()
    assert r["error"] == "网络错误"
    assert r["sh_pct"] is None
    assert fetched["called"] is False  # pnl 失败不继续拉指数


def test_get_snapshot_index_fail_honest_error(monkeypatch):
    pnl_ok = {"pnl_yk": -204.0, "pnl_pct": -0.6, "chart_data": [], "updated_at": "x",
              "error": "", "token_expired": False}
    monkeypatch.setattr(ths_pnl, "load_cookie", lambda: "userid=1")
    monkeypatch.setattr(ths_pnl, "fetch_pnl", lambda c, u="", f="": pnl_ok)
    monkeypatch.setattr(ths_pnl, "fetch_index", lambda c, u="": None)
    r = ths_pnl.get_snapshot()
    assert r["pnl_yk"] == -204.0           # pnl 值保留，不因指数失败丢弃
    assert r["sh_pct"] is None              # 不伪造 0
    assert r["error"] == "指数获取失败"


def test_get_snapshot_full_success(monkeypatch):
    pnl_ok = {"pnl_yk": -204.0, "pnl_pct": -0.6, "chart_data": [{"t": 1, "v": -0.2}],
              "updated_at": "x", "error": "", "token_expired": False}
    monkeypatch.setattr(ths_pnl, "load_cookie", lambda: "userid=1")
    monkeypatch.setattr(ths_pnl, "fetch_pnl", lambda c, u="", f="": pnl_ok)
    monkeypatch.setattr(ths_pnl, "fetch_index", lambda c, u="": 0.33)
    r = ths_pnl.get_snapshot()
    assert r["error"] == ""
    assert r["pnl_yk"] == -204.0
    assert r["sh_pct"] == 0.33


# ---------------- repo 落库闭环 ----------------

def test_repo_upsert_get_latest_history_roundtrip():
    date, ts = "2026-08-27", "10:05:00"
    rid = repo.upsert_account_pnl_snapshot(
        trade_date=date, ts=ts, pnl_yk=-204.0, pnl_pct=-0.6, sh_pct=0.33,
        chart_data=[{"t": 1, "v": -0.2}], error="", token_expired=False)
    assert isinstance(rid, int)

    # upsert 幂等：同一 (date, ts) 再次写入仍单行，字段整行替换
    rid2 = repo.upsert_account_pnl_snapshot(
        trade_date=date, ts=ts, pnl_yk=-300.0, pnl_pct=-0.9, sh_pct=0.5,
        chart_data=[{"t": 2, "v": -0.3}], error="")
    assert rid2 == rid

    latest = repo.get_latest_account_pnl()
    assert latest["trade_date"] == date
    assert latest["pnl_yk"] == -300.0      # 已被幂等更新
    assert latest["chart_data"] == [{"t": 2, "v": -0.3}]   # chart_data 同步替换

    # 失败快照：error 落库，token_expired 标记
    repo.upsert_account_pnl_snapshot(trade_date=date, ts="10:06:00",
                                     error="TOKEN_EXPIRED (HTTP 401)", token_expired=True)
    latest_err = repo.get_latest_account_pnl()
    assert latest_err["token_expired"] is True
    assert "401" in latest_err["error"]

    # 历史列表：近 30 天包含上面两行
    hist = repo.list_account_pnl_history(days=30)
    assert len(hist) >= 2
    assert all(h["trade_date"] == date for h in hist)
