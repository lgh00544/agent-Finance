"""
系统外部连接状态探活（首页「系统运行状态」看板数据源）
【刚性代码逻辑】只读探测各外部依赖连通性，不产生任何业务数据、不触发 Agent、不改存储。
时间统一北京时间（Asia/Shanghai，固定 UTC+8，无夏令时），格式 YYYY-MM-DD HH:mm。
"""
from datetime import datetime, timedelta, timezone

import requests

from app.core.config import settings

CN_TZ = timezone(timedelta(hours=8))


def now_min() -> str:
    """北京时间，精确到分钟"""
    return datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M")


_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _check_data_source() -> dict:
    """数据源探活：东财行情接口优先（3s 超时）；东财异常时探测新浪降级链路（业务同款降级）"""
    em_url = ("https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=1&po=1&np=1"
              "&fltt=2&invt=2&fid=f12&fs=m:0+t:6&fields=f12")
    try:
        resp = requests.get(em_url, timeout=3, headers=_UA)
        if resp.status_code == 200 and '"data"' in resp.text:
            return {"name": "数据源（akshare）", "ok": True, "detail": "东财接口正常"}
    except Exception:  # noqa: BLE001 继续走降级探测
        pass
    try:
        resp = requests.get("https://hq.sinajs.cn/list=sh600519", timeout=3,
                            headers={**_UA, "Referer": "https://finance.sina.com.cn"})
        if resp.status_code == 200 and "hq_str" in resp.text:
            return {"name": "数据源（akshare）", "ok": True, "detail": "东财不可达，新浪降级链路正常"}
        return {"name": "数据源（akshare）", "ok": False,
                "detail": f"东财与新浪降级均异常（HTTP {resp.status_code}）"}
    except Exception as exc:  # noqa: BLE001 只读探活，任何失败都视为不可用
        return {"name": "数据源（akshare）", "ok": False,
                "detail": f"东财与新浪降级均不可达：{str(exc)[:40]}"}


def _check_llm() -> dict:
    """LLM 探活：DeepSeek base_url 可达 + API Key 已配置（不消费 token）"""
    if not settings.deepseek_api_key:
        return {"name": "LLM（DeepSeek）", "ok": False, "detail": "未配置 API Key"}
    try:
        requests.get(settings.deepseek_base_url, timeout=3)
        return {"name": "LLM（DeepSeek）", "ok": True, "detail": "网络可达，API Key 已配置"}
    except Exception as exc:  # noqa: BLE001
        return {"name": "LLM（DeepSeek）", "ok": False, "detail": str(exc)[:60]}


def _check_db() -> dict:
    """数据库探活：SELECT 1"""
    from app.db.session import engine
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return {"name": "数据库", "ok": True, "detail": settings.db_backend.upper()}
    except Exception as exc:  # noqa: BLE001
        return {"name": "数据库", "ok": False, "detail": str(exc)[:60]}


def _check_vector() -> dict:
    """向量库探活：本地文件模式（dev 降级 SQL 检索）视为可用；server 模式探测 HTTP"""
    if settings.qdrant_mode != "server":
        return {"name": "向量库（Qdrant）", "ok": True, "detail": "本地模式（SQL 检索降级）"}
    try:
        resp = requests.get(f"{settings.qdrant_url}/collections", timeout=3)
        ok = resp.status_code == 200
        return {"name": "向量库（Qdrant）", "ok": ok,
                "detail": "服务正常" if ok else f"响应异常（HTTP {resp.status_code}）"}
    except Exception as exc:  # noqa: BLE001
        return {"name": "向量库（Qdrant）", "ok": False, "detail": str(exc)[:60]}


def _check_backend() -> dict:
    """后端服务自身探活：本进程即为服务本体，进程存活即正常"""
    return {"name": "后端服务", "ok": True,
            "detail": f"运行模式 {settings.app_env} · 进程存活"}


def system_status() -> dict:
    """五项外部连接/服务状态 + 统一检测时间（到分钟）"""
    checked_at = now_min()
    connections = [_check_backend(), _check_data_source(), _check_llm(),
                   _check_db(), _check_vector()]
    for conn in connections:
        conn["checked_at"] = checked_at
    return {
        "checked_at": checked_at,
        "connections": connections,
    }
