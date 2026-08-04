"""
Streamlit → backend API 客户端
面板只做展示与人工数据录入，不内置任何二次判断逻辑。
"""
import os

import requests

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")


def _get(path: str, params: dict | None = None) -> dict | list:
    resp = requests.get(f"{API_BASE}{path}", params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, json: dict | None = None) -> dict | list:
    resp = requests.post(f"{API_BASE}{path}", json=json or {}, timeout=600)
    resp.raise_for_status()
    return resp.json()


def _put(path: str, json: dict | None = None) -> dict | list:
    resp = requests.put(f"{API_BASE}{path}", json=json or {}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def health() -> dict:
    return _get("/api/health")


def run_discover() -> dict:
    return _post("/api/jobs/discover/run")


def job_status() -> dict:
    return _get("/api/jobs/status")


def system_status() -> dict:
    return _get("/api/system/status")


def candidates(date: str | None = None, limit: int | None = None) -> list:
    params = {"date": date} if date else {}
    if limit is not None:
        params["limit"] = limit
    return _get("/api/candidates", params or None)


def scores(code: str | None = None, date: str | None = None, limit: int | None = None) -> list:
    params = {}
    if code:
        params["code"] = code
    if date:
        params["date"] = date
    if limit is not None:
        params["limit"] = limit
    return _get("/api/scores", params or None)


def trigger_score(code: str) -> dict:
    return _post(f"/api/score/{code}", {"stock_code": code})


def plans(code: str | None = None, limit: int | None = None) -> list:
    params = {"code": code} if code else {}
    if limit is not None:
        params["limit"] = limit
    return _get("/api/positions", params or None)


def create_plan(code: str, name: str = "") -> dict:
    return _post("/api/positions/plan", {"stock_code": code, "stock_name": name})


def holdings(status: str | None = None) -> list:
    return _get("/api/holdings", {"status": status} if status else None)


def add_holding(body: dict) -> dict:
    return _post("/api/holdings", body)


def ocr_status() -> dict:
    """OCR 功能状态（是否启用/可用），前端据此提示"""
    return _get("/api/ocr/status")


def ocr_holding(image_bytes: bytes, filename: str) -> dict:
    """上传持仓截图 → OCR 识别持仓字段（仅回填表单，不直接入库）"""
    resp = requests.post(f"{API_BASE}/api/ocr/holding",
                         files={"file": (filename, image_bytes, "image/png")}, timeout=180)
    resp.raise_for_status()
    return resp.json()


def exit_holding(hid: int, body: dict) -> dict:
    return _post(f"/api/holdings/{hid}/exit", body)


def monitor_holding(hid: int) -> dict:
    return _post(f"/api/holdings/{hid}/monitor")


def sell_decision(hid: int) -> dict:
    """生成一次卖出决策（SellAgent；仅供参考，卖出人工执行）"""
    return _post(f"/api/holdings/{hid}/sell-decision")


def sell_decisions(hid: int) -> list:
    return _get(f"/api/holdings/{hid}/sell-decisions")


def agent_suggestions(status: str | None = None, target_agent: str | None = None) -> list:
    params = {}
    if status:
        params["status"] = status
    if target_agent:
        params["target_agent"] = target_agent
    return _get("/api/agent-suggestions", params or None)


def approve_suggestion(sid: int) -> dict:
    return _post(f"/api/agent-suggestions/{sid}/approve")


def reject_suggestion(sid: int) -> dict:
    return _post(f"/api/agent-suggestions/{sid}/reject")


def knowledge() -> list:
    return _get("/api/knowledge")


def add_knowledge(title: str, content: str, agent_tag: str) -> dict:
    return _post("/api/knowledge", {"title": title, "content": content, "agent_tag": agent_tag})


def delete_knowledge(kid: int) -> dict:
    return _post(f"/api/knowledge/{kid}/delete")


def alerts(limit: int | None = None) -> list:
    return _get("/api/alerts", {"limit": limit} if limit is not None else None)


def reviews(code: str | None = None, limit: int | None = None) -> list:
    params = {"code": code} if code else {}
    if limit is not None:
        params["limit"] = limit
    return _get("/api/reviews", params or None)


def adopt_review(rid: int) -> dict:
    return _post(f"/api/reviews/{rid}/adopt")


def reject_review(rid: int, reason: str) -> dict:
    return _post(f"/api/reviews/{rid}/reject", {"reason": reason})


def get_profile() -> dict:
    return _get("/api/profile")


def put_profile(content: dict) -> dict:
    return _put("/api/profile", {"content": content})


def export_profile() -> dict:
    return _get("/api/profile/export")


def import_profile(content: dict) -> dict:
    return _post("/api/profile/import", {"content": content})
