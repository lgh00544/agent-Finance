"""
REST API：仅提供数据存取与手动触发任务（无任何二次判断逻辑）
面板等前端不内置研判，全部展示 LLM 输出结论与原始数据。
"""
import logging
import time
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.agents.review import llm_rethink_suggestion
from app.core.config import settings
from app.db import repo
from app.graph import router as graph_router
from app.scheduler import jobs as scheduler_jobs
from app.services import holding_view, market_view, ocr as ocr_service
from app.services import status as status_service, task_queue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ================= 后台异步任务（耗时操作提交即返回，不阻塞页面） =================
# 执行函数统一签名 fn(params: dict)；kind → (中文标签, 执行函数)
def _task_batch_import_knowledge(items: list[dict]) -> dict:
    """批量导入私有知识条目（逐条落库，存储抽象层不变）"""
    imported = 0
    for item in items:
        if item.get("title") and item.get("content"):
            repo.add_knowledge(str(item["title"]).strip(), str(item["content"]).strip(),
                               item.get("agent_tag") or "all")
            imported += 1
    return {"imported": imported}


_TASK_KINDS: dict[str, tuple[str, object]] = {
    "daily_pipeline": ("每日挖掘（Discover → 候选打分）",
                       lambda p: graph_router.run_daily_pipeline()),
    "score": ("单股评分",
              lambda p: graph_router.run_score(p.get("stock_code", ""), p.get("stock_name", ""))),
    "position": ("分批建仓方案",
                 lambda p: graph_router.run_position(p.get("stock_code", ""), p.get("stock_name", ""))),
    "sell_decision": ("卖出决策",
                      lambda p: graph_router.run_sell_decision(p.get("holding_id"))),
    "monitor_all": ("全量持仓实时监控",
                    lambda p: _task_monitor_all()),
    "review": ("卖出复盘",
               lambda p: graph_router.run_review(p.get("holding_id"), p.get("exit_date"))),
    "review_rethink": ("复盘建议重思考",
                       lambda p: llm_rethink_suggestion(p.get("review_id"), p.get("reason", ""))),
    "knowledge_import": ("知识库批量导入",
                         lambda p: _task_batch_import_knowledge(p.get("items") or [])),
}


def _task_monitor_all() -> dict:
    """全量持仓实时监控（前端「立即刷新监控」按钮用）；返回 JSON 安全摘要"""
    results = graph_router.run_monitor_all()
    return {"monitored": len(results),
            "signals": [{"code": r.get("stock_code"),
                         "action": ((r.get("holding_signal") or {}).get("action")),
                         "severity": ((r.get("holding_signal") or {}).get("severity"))}
                        for r in results]}


def _submit_task(kind: str, params: dict) -> dict:
    """提交后台任务：立即返回任务ID，页面可自由切换"""
    label, fn = _TASK_KINDS[kind]
    tid = task_queue.submit(kind, label, fn, params)
    return {"task_id": tid, "label": label, "status": "pending"}


class TaskSubmitBody(BaseModel):
    kind: str = Field(description="任务类型")
    params: dict = Field(default_factory=dict, description="任务参数")


@router.post("/tasks/submit")
def submit_task(body: TaskSubmitBody):
    if body.kind not in _TASK_KINDS:
        raise HTTPException(status_code=400, detail=f"未知任务类型: {body.kind}")
    return _submit_task(body.kind, body.params or {})


@router.get("/tasks/recent")
def recent_tasks(limit: int = 10):
    """最近后台任务（最新在前，含状态/提交时间/失败原因）"""
    return task_queue.recent_tasks(limit)


@router.get("/tasks/{tid}")
def task_detail(tid: str):
    task = task_queue.get(tid)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.post("/tasks/{tid}/retry")
def retry_task(tid: str):
    """失败任务一键重试（仅 failed 状态可重试，复用原任务ID）"""
    if not task_queue.retry(tid):
        raise HTTPException(status_code=400, detail="任务不存在或当前状态不可重试（仅失败任务可重试）")
    return {"task_id": tid, "status": "pending"}


# ================= 任务触发 =================
class CodeBody(BaseModel):
    stock_code: str = Field(description="6 位股票代码")
    stock_name: str = ""


@router.post("/jobs/discover/run")
def run_discover_job():
    """手动触发每日挖掘（异步提交：discover → 候选打分 全流程后台执行）"""
    return _submit_task("daily_pipeline", {})


@router.get("/jobs/status")
def job_status():
    return {"jobs": scheduler_jobs.job_status()}


@router.get("/system/status")
def system_status():
    """外部连接探活（数据源/LLM/数据库/向量库）+ 检测时间，供首页系统状态看板"""
    return status_service.system_status()


@router.get("/llm/stats")
def llm_stats():
    """LLM 运行统计（当日累计：请求次数 / 缓存命中·未命中 token / 命中率 / 模型分布），
    供首页「系统运行状态」看板；数据来自调用层每次成功响应的 usage 记录"""
    from app.services import llm_stats as llm_stats_service

    return llm_stats_service.snapshot()


@router.get("/market-condition")
def market_condition():
    """当日市况评分（v2.0 前置步骤结果：总分/档位/候选池上限/五维/综述），供首页「今日操作提示」"""
    return repo.get_latest_market_condition()


# ================= 市场概览（顶部状态栏 / 首页热门板块，只读聚合） =================
@router.get("/market/indices")
def market_indices():
    """三大指数实时行情（上证指数/深证成指/创业板指，60s 缓存防限流）；
    数据源失败返回空列表 + error 标注（前端显示「数据加载中」或上次缓存值，不抛原始报错）"""
    return market_view.index_quotes()


@router.get("/market/hot-sectors")
def market_hot_sectors():
    """今日涨幅前 5 行业板块（客观排序）+ 领涨龙头（代码+名称）+ 更新时间，供首页看板"""
    return market_view.hot_sectors()


@router.get("/account/summary")
def account_summary():
    """账户核心资产摘要（双数据路径：有 OCR 账户基准用券商值，否则按总资金设定估算；
    纯数学计算，不落库不研判）"""
    return holding_view.build_account_summary()


class AccountBaselineBody(BaseModel):
    """账户基准（券商持仓截图 OCR 提取，人工确认后保存）"""
    total_asset: float = Field(gt=0, description="总资产（元）")
    available_cash: float = Field(ge=0, description="可用资金（元）")
    position_pct: float = Field(ge=0, le=100, description="整体仓位占比（%）")
    trade_date: str = Field(default="", description="基准日期（YYYY-MM-DD，留空取今天）")
    source: str = Field(default="ocr", description="来源：ocr / manual")


@router.post("/account/baseline")
def save_account_baseline(body: AccountBaselineBody):
    """保存账户基准（仅人工确认后调用；每次插入一行保留历史，读取取最新）"""
    from datetime import datetime, timedelta, timezone

    trade_date = body.trade_date.strip() or datetime.now(
        timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    bid = repo.insert_account_baseline(trade_date, body.total_asset, body.available_cash,
                                       body.position_pct, body.source)
    return {"id": bid, "trade_date": trade_date, "saved": True}


@router.post("/db/maintenance")
def run_db_maintenance():
    """手动触发存储空间维护：超期新闻清理 + SQLite 真空收缩 + 向量库超期索引清理（低频操作）"""
    from app.services.vector_store import get_vector_store

    try:
        stats = repo.maintenance_db()
        cutoff = time.time() - settings.news_retention_days * 86400
        vector_removed = get_vector_store().cleanup_old_news(cutoff)
        return {**stats, "vector_removed": vector_removed}
    except Exception as exc:  # noqa: BLE001
        logger.error("空间维护失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"空间维护失败: {exc}")


# ================= 候选池 / 评分 =================
@router.get("/candidates")
def list_candidates(date: Optional[str] = None, limit: int = 50):
    return repo.list_candidates(date, limit)


@router.get("/scores")
def list_scores(code: Optional[str] = None, date: Optional[str] = None, limit: int = 100):
    return repo.list_scores(code, date, limit)


@router.post("/score/{code}")
def trigger_score(code: str, body: Optional[CodeBody] = None):
    """手动触发单股打分（异步提交，立即返回任务ID，不阻塞页面）"""
    name = body.stock_name if body else ""
    return _submit_task("score", {"stock_code": code, "stock_name": name})


# ================= 建仓方案 =================
@router.post("/positions/plan")
def create_plan(body: CodeBody):
    """手动触发分批建仓方案（异步提交，立即返回任务ID，不阻塞页面）"""
    return _submit_task("position", {"stock_code": body.stock_code, "stock_name": body.stock_name})


@router.get("/positions")
def list_plans(code: Optional[str] = None, limit: int = 50):
    return repo.list_plans(code, limit)


# ================= 持仓管理 =================
class HoldingBody(BaseModel):
    stock_code: str
    stock_name: str
    entry_date: str
    entry_price: float
    shares: int = Field(gt=0)
    cost: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    target_pct: float = 0.0
    plan_id: Optional[int] = None
    note: str = ""


class ExitBody(BaseModel):
    """人工卖出录入（系统不做任何下单，仅记录人工执行结果）"""
    price: float
    shares: int = Field(gt=0)
    trade_date: str
    note: str = ""


@router.get("/holdings")
def list_holdings(status: Optional[str] = None):
    return repo.list_holdings(status)


@router.get("/holdings/quotes")
def holding_quotes():
    """持仓列表视图：实时行情 + 参考止损/止盈 + 目标仓位%（只读，不落库；
    去重合并由前端展示层完成，数据库原始记录完整保留）"""
    return holding_view.build_holding_view()


@router.post("/holdings")
def add_holding(body: HoldingBody):
    """新增持仓（人工建仓后录入，触发创建后建议手动跑 monitor）"""
    hid = repo.insert_holding(body.stock_code, body.stock_name, body.entry_date,
                              body.entry_price, body.shares, body.cost or body.entry_price * body.shares,
                              body.stop_loss, body.take_profit, body.target_pct,
                              body.plan_id, body.note)
    return {"id": hid}


@router.post("/holdings/{hid}/exit")
def exit_holding(hid: int, body: ExitBody):
    """记录卖出：股数清零则标记 exited 并自动触发 ReviewAgent 复盘"""
    holding = repo.get_holding(hid)
    if holding is None or holding.status != "holding":
        raise HTTPException(status_code=404, detail="持仓不存在或已平仓")
    if body.shares > holding.shares:
        raise HTTPException(status_code=400, detail="卖出股数超过持仓")

    repo.add_trade(hid, holding.stock_code, "sell", body.price, body.shares,
                   body.trade_date, body.note)
    remain = holding.shares - body.shares
    repo.update_holding(hid, shares=remain)

    result = {"holding_id": hid, "remain_shares": remain, "review_task_id": None}
    if remain == 0:
        repo.update_holding(hid, status="exited")
        task = _submit_task("review", {"holding_id": hid, "exit_date": body.trade_date})
        result["review_task_id"] = task["task_id"]
    return result


@router.post("/holdings/{hid}/monitor")
def trigger_monitor(hid: int):
    """立即执行一次持仓监控"""
    try:
        result = graph_router.run_monitor(hid)
    except Exception as exc:  # noqa: BLE001
        logger.error("监控失败 %s: %s", hid, exc)
        raise HTTPException(status_code=500, detail=f"监控失败: {exc}")
    return {"holding_id": hid, "signal": result.get("holding_signal")}


@router.post("/holdings/{hid}/sell-decision")
def trigger_sell_decision(hid: int):
    """生成一次卖出决策（SellAgent；异步提交，决策仅供参考，卖出由人工执行）"""
    return _submit_task("sell_decision", {"holding_id": hid})


@router.get("/holdings/{hid}/sell-decisions")
def list_sell_decisions(hid: int, limit: int = 10):
    """读取该持仓的历史卖出决策记录（仅供参考）"""
    return repo.list_sell_decisions(hid, limit)


# ================= OCR 持仓截图识别 =================
@router.get("/ocr/status")
def ocr_status():
    """OCR 功能状态（前端据此显示可用性提示）"""
    return ocr_service.get_status()


@router.post("/ocr/holding")
async def ocr_holding(file: UploadFile = File(...)):
    """上传券商持仓截图 → OCR 识别持仓字段（仅识别与数据回填，不直接入库）

    识别结果必须经人工核对后，再通过 POST /api/holdings 创建持仓。
    图片仅在内存/临时文件处理，识别完毕立即清理。
    """
    try:
        image_bytes = await file.read()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"图片读取失败: {exc}") from exc
    try:
        result = ocr_service.recognize_holding(image_bytes, file.filename or "screenshot.png")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


# ================= 告警 / 复盘 =================
@router.get("/alerts")
def list_alerts(limit: int = 100):
    return repo.list_alerts(limit)


@router.get("/reviews")
def list_reviews(code: Optional[str] = None, limit: int = 50):
    return repo.list_reviews(code, limit)


class RejectReviewBody(BaseModel):
    reason: str = Field(min_length=1, description="驳回原因（必填，至少 1 个字符）")


@router.post("/reviews/{rid}/adopt")
def adopt_review_suggestion(rid: int):
    """采纳复盘给出的交易偏好优化建议 → 更新 sys_trade_profile"""
    review = repo.get_review(rid)
    if review is None:
        raise HTTPException(status_code=404, detail="复盘记录不存在")
    suggestion = (review.feedback or {}).get("profile_suggestion")

    if not suggestion:
        raise HTTPException(status_code=400, detail="该复盘无偏好优化建议")

    content = repo.get_trade_profile_content()
    content[suggestion["field"]] = suggestion["value"]
    version = repo.update_trade_profile(content)
    repo.update_review_suggestion_status(rid, "adopted")
    return {"adopted": True, "field": suggestion["field"], "version": version}


@router.post("/reviews/{rid}/reject")
def reject_review_suggestion(rid: int, body: RejectReviewBody):
    """驳回复盘建议（必填原因）→ 触发复盘 Agent 重思考，生成调整后的新建议再提交审核"""
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="驳回原因不能为空")
    review = repo.get_review(rid)
    if review is None:
        raise HTTPException(status_code=404, detail="复盘记录不存在")
    if review.suggest_status == "adopted":
        raise HTTPException(status_code=400, detail="该建议已采纳，不能再驳回")
    task = _submit_task("review_rethink", {"review_id": rid, "reason": reason})
    return {"rejected": True, "review_id": rid, "task_id": task["task_id"],
            "status": task["status"]}


# ================= 个人交易偏好档案 =================
@router.get("/profile")
def get_profile():
    row = repo.get_trade_profile()
    return {"version": row.version, "content": row.content}


@router.put("/profile")
def put_profile(body: dict):
    """整体更新偏好档案（保存立即生效，无需重启）"""
    if not isinstance(body, dict) or "content" not in body:
        raise HTTPException(status_code=400, detail="body 需包含 content 对象")
    version = repo.update_trade_profile(body["content"])
    return {"version": version, "content": repo.get_trade_profile_content()}


@router.post("/profile/import")
def import_profile(body: dict):
    """导入偏好 JSON（跨环境迁移）"""
    if not isinstance(body, dict) or "content" not in body:
        raise HTTPException(status_code=400, detail="body 需包含 content 对象")
    version = repo.update_trade_profile(body["content"])
    return {"version": version, "content": repo.get_trade_profile_content()}


@router.get("/profile/export")
def export_profile():
    """导出偏好 JSON（备份/迁移）"""
    row = repo.get_trade_profile()
    return {"version": row.version, "content": row.content}


# ================= 私有知识库（统一调教接口·知识注入） =================
class KnowledgeBody(BaseModel):
    title: str = Field(min_length=1, description="知识标题")
    content: str = Field(description="知识正文")
    agent_tag: str = Field(default="all",
                           description="适用 Agent：discover/score/position/monitor/sell/review/all")


@router.get("/knowledge")
def list_knowledge(agent_tag: Optional[str] = None):
    """私有交易经验/战法列表（全部或按 Agent 过滤）"""
    rows = repo.list_knowledge(agent_tag)
    return [{"id": r.id, "title": r.title, "content": r.content, "agent_tag": r.agent_tag,
             "created_at": str(r.created_at)} for r in rows]


@router.post("/knowledge")
def create_knowledge(body: KnowledgeBody):
    """新增知识条目（保存后自动进入对应 Agent 的检索注入，无需重启）"""
    kid = repo.add_knowledge(body.title, body.content, body.agent_tag)
    return {"id": kid}


@router.post("/knowledge/{kid}/delete")
def remove_knowledge(kid: int):
    ok = repo.delete_knowledge(kid)
    if not ok:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    return {"deleted": True}


class KnowledgeBatchBody(BaseModel):
    items: list[KnowledgeBody] = Field(min_length=1, description="批量知识条目（至少 1 条）")


@router.post("/knowledge/batch-import")
def batch_import_knowledge(body: KnowledgeBatchBody):
    """批量导入私有知识（异步提交：逐条落库，立即返回任务ID，不阻塞页面）"""
    items = [{"title": it.title, "content": it.content, "agent_tag": it.agent_tag}
             for it in body.items]
    return _submit_task("knowledge_import", {"items": items})


# ================= 策略闭环·Agent 优化建议（人工审核） =================
@router.get("/agent-suggestions")
def list_agent_suggestions(status: Optional[str] = None, target_agent: Optional[str] = None):
    """复盘进化Agent 提出的各 Agent 规则/参数优化建议（默认全部；可过滤）"""
    suggestions = repo.get_agent_suggestions(status=status)
    if target_agent:
        suggestions = [s for s in suggestions if s.target_agent == target_agent]
    return [{"id": s.id, "review_id": s.review_id, "target_agent": s.target_agent,
             "target_kind": s.target_kind, "rule_name": s.rule_name,
             "current_value": s.current_value, "suggested_value": s.suggested_value,
             "reason": s.reason, "evidence": s.evidence, "status": s.status,
             "created_at": str(s.created_at)} for s in suggestions]


def _coerce_value(raw: str):
    """建议值字符串 → 合理类型（数字/布尔/列表原样，其余保留字符串）"""
    import json

    if raw is None or raw == "":
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


@router.post("/agent-suggestions/{sid}/approve")
def approve_agent_suggestion(sid: int):
    """人工审核：采纳建议（⚠️ 仅人工触发；系统禁止自动、无监督修改任何策略参数）
    profile 类建议 → 直接写入个人交易偏好档案（版本号+1 全部 Agent 生效）；
    prompt 类建议 → 仅标记已采纳，并提示人工修改 agent_prompts/ 对应文件。"""
    suggestion = repo.get_agent_suggestion(sid)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="建议不存在")
    if suggestion.status != "pending":
        raise HTTPException(status_code=400, detail=f"该建议已处理（{suggestion.status}）")

    applied = "none"
    version = None
    if suggestion.target_kind == "profile":
        content = repo.get_trade_profile_content()
        content[suggestion.rule_name] = _coerce_value(suggestion.suggested_value)
        version = repo.update_trade_profile(content)
        applied = "profile"
    repo.update_agent_suggestion_status(sid, "approved")
    result = {"approved": True, "suggestion_id": sid, "applied": applied}
    if version is not None:
        result["profile_version"] = version
    if applied == "none":
        result["hint"] = ("该建议为提示词/硬性规则类，请人工在 agent_prompts/ 对应文件或 "
                          "common.py 的 HARD_RULES 中按 suggested_value 修改后生效")
    return result


@router.post("/agent-suggestions/{sid}/reject")
def reject_agent_suggestion(sid: int):
    """人工审核：驳回建议（不修改任何配置）"""
    suggestion = repo.get_agent_suggestion(sid)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="建议不存在")
    if suggestion.status != "pending":
        raise HTTPException(status_code=400, detail=f"该建议已处理（{suggestion.status}）")
    repo.update_agent_suggestion_status(sid, "rejected")
    return {"rejected": True, "suggestion_id": sid}


# ================= 其他 =================
@router.get("/health")
def health():
    return {"status": "ok", "time": time.strftime("%Y-%m-%d %H:%M:%S"), "env": __import__("app.core.config", fromlist=["settings"]).settings.app_env}
