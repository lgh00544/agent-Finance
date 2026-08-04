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


# ================= 后台异步任务（提交即返回 + 状态查询 + 重试） =================
def submit_task(kind: str, params: dict | None = None) -> dict:
    """提交后台任务，立即返回 task_id（不阻塞页面，可切换页面继续操作）"""
    return _post("/api/tasks/submit", {"kind": kind, "params": params or {}})


def recent_tasks(limit: int = 8) -> list:
    """最近后台任务（最新在前，含状态/提交时间/失败原因）"""
    return _get("/api/tasks/recent", {"limit": limit})


def task_detail(tid: str) -> dict:
    """任务详情（状态/结果/失败原因）"""
    return _get(f"/api/tasks/{tid}")


def retry_task(tid: str) -> dict:
    """失败任务一键重试（复用原任务ID）"""
    return _post(f"/api/tasks/{tid}/retry")


def batch_import_knowledge(items: list[dict]) -> dict:
    """批量导入私有知识条目（异步提交，逐条落库）"""
    return _post("/api/knowledge/batch-import", {"items": items})


def run_discover() -> dict:
    return _post("/api/jobs/discover/run")


def job_status() -> dict:
    return _get("/api/jobs/status")


def system_status() -> dict:
    return _get("/api/system/status")


def llm_stats() -> dict:
    """LLM 运行统计（当日累计：请求次数/缓存命中 token/命中率/模型分布）"""
    return _get("/api/llm/stats")


def market_condition() -> dict | None:
    """当日市况评分（v2.0 前置步骤：总分/档位/候选池上限/五维/综述）"""
    return _get("/api/market-condition")


def market_indices() -> dict:
    """三大指数实时行情（上证指数/深证成指/创业板指 + 更新时间；失败含 error 标注）"""
    return _get("/api/market/indices")


def market_hot_sectors() -> dict:
    """今日涨幅前 5 行业板块 + 领涨龙头（代码+名称）+ 更新时间"""
    return _get("/api/market/hot-sectors")


def account_summary() -> dict:
    """账户核心资产摘要（双数据路径：有 OCR 账户基准用券商值，否则按总资金设定估算）"""
    return _get("/api/account/summary")


def save_account_baseline(body: dict) -> dict:
    """保存账户基准（OCR 识别结果经人工确认后调用）"""
    return _post("/api/account/baseline", body)


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


def holding_quotes() -> dict:
    """持仓列表视图：实时行情 + 参考止损/止盈 + 目标仓位%（只读；去重合并由前端展示层完成）"""
    return _get("/api/holdings/quotes")


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
