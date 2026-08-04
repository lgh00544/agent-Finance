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
from app.db import repo
from app.graph import router as graph_router
from app.scheduler import jobs as scheduler_jobs
from app.services import ocr as ocr_service
from app.services import status as status_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ================= 任务触发 =================
class CodeBody(BaseModel):
    stock_code: str = Field(description="6 位股票代码")
    stock_name: str = ""


@router.post("/jobs/discover/run")
def run_discover_job():
    """手动触发每日挖掘（discover → 候选打分）"""
    return graph_router.run_daily_pipeline()


@router.get("/jobs/status")
def job_status():
    return {"jobs": scheduler_jobs.job_status()}


@router.get("/system/status")
def system_status():
    """外部连接探活（数据源/LLM/数据库/向量库）+ 检测时间，供首页系统状态看板"""
    return status_service.system_status()


# ================= 候选池 / 评分 =================
@router.get("/candidates")
def list_candidates(date: Optional[str] = None, limit: int = 50):
    return repo.list_candidates(date, limit)


@router.get("/scores")
def list_scores(code: Optional[str] = None, date: Optional[str] = None, limit: int = 100):
    return repo.list_scores(code, date, limit)


@router.post("/score/{code}")
def trigger_score(code: str, body: Optional[CodeBody] = None):
    """手动触发单股打分"""
    name = body.stock_name if body else ""
    try:
        result = graph_router.run_score(code, name)
    except Exception as exc:  # noqa: BLE001
        logger.error("打分失败 %s: %s", code, exc)
        raise HTTPException(status_code=500, detail=f"打分失败: {exc}")
    return {"stock_code": code, "score_result": result.get("score_result")}


# ================= 建仓方案 =================
@router.post("/positions/plan")
def create_plan(body: CodeBody):
    try:
        result = graph_router.run_position(body.stock_code, body.stock_name)
    except Exception as exc:  # noqa: BLE001
        logger.error("建仓方案失败 %s: %s", body.stock_code, exc)
        raise HTTPException(status_code=500, detail=f"建仓方案生成失败: {exc}")
    return result.get("position_plan")


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

    result = {"holding_id": hid, "remain_shares": remain, "review_triggered": False}
    if remain == 0:
        repo.update_holding(hid, status="exited")
        try:
            graph_router.run_review(hid, body.trade_date)
            result["review_triggered"] = True
        except Exception as exc:  # noqa: BLE001
            logger.error("复盘触发失败 %s: %s", hid, exc)
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
    """立即生成一次卖出决策（SellAgent；决策仅供参考，卖出由人工执行）"""
    try:
        result = graph_router.run_sell_decision(hid)
    except Exception as exc:  # noqa: BLE001
        logger.error("卖出决策失败 %s: %s", hid, exc)
        raise HTTPException(status_code=500, detail=f"卖出决策失败: {exc}")
    return {"holding_id": hid, "decision": result.get("sell_decision")}


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
    try:
        result = llm_rethink_suggestion(rid, reason)
    except Exception as exc:  # noqa: BLE001
        logger.error("建议重思考失败 review_id=%s: %s", rid, exc)
        raise HTTPException(status_code=500, detail=f"重思考失败: {exc}")
    return {"rejected": True, "review_id": rid,
            "new_iteration": result["iteration"],
            "profile_suggestion": result["profile_suggestion"]}


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
