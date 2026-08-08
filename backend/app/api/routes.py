"""
REST API：仅提供数据存取与手动触发任务（无任何二次判断逻辑）
面板等前端不内置研判，全部展示 LLM 输出结论与原始数据。
"""
import logging
import os
import time
from pathlib import Path
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


def _task_daily_pipeline(params: dict) -> dict:
    """手动触发每日挖掘：先失效当日 LLM 结果缓存（初选/终选/市况），
    强制重新执行完整链路（硬过滤 → LLM 初选 → 新闻核验 → 最终确认 → 批量打分），
    保证手动触发绝不命中缓存、结果与已有数据不同也必然覆盖更新。"""
    from app.cache import cache

    date_key = time.strftime("%Y-%m-%d")
    for prefix in ("shortlist:v2:", "final:v2:", "market:v2:"):
        cache.delete_prefix(f"{prefix}{date_key}")
    result = graph_router.run_daily_pipeline()
    return {"candidates": result.get("candidates", 0),
            "scored": result.get("scored", 0),
            "date": date_key}


_TASK_KINDS: dict[str, tuple[str, object]] = {
    "daily_pipeline": ("每日挖掘（Discover → 候选打分）", _task_daily_pipeline),
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
    "chat_ask": ("Agent 对话·提问答疑", lambda p: _task_chat_ask(p)),
    "chat_rule": ("Agent 对话·规则调教", lambda p: _task_chat_rule(p)),
    "chat_learn": ("Agent 对话·图片学习", lambda p: _task_chat_learn(p)),
}


def _task_monitor_all() -> dict:
    """全量持仓实时监控（前端「立即刷新监控」按钮用）；返回 JSON 安全摘要"""
    results = graph_router.run_monitor_all()
    return {"monitored": len(results),
            "signals": [{"code": r.get("stock_code"),
                         "action": ((r.get("holding_signal") or {}).get("action")),
                         "severity": ((r.get("holding_signal") or {}).get("severity"))}
                        for r in results]}


def _task_chat_ask(params: dict) -> dict:
    """Agent 对话·文字提问答疑"""
    from app.services import agent_chat

    return agent_chat.ask_agent(str(params.get("agent", "")), str(params.get("question", "")))


def _task_chat_rule(params: dict) -> dict:
    """Agent 对话·规则调教校验（采纳自动沉淀知识库）"""
    from app.services import agent_chat

    return agent_chat.rule_feedback(str(params.get("agent", "")), str(params.get("proposal", "")))


def _task_chat_learn(params: dict) -> dict:
    """Agent 对话·多模态上传学习（识别+提炼，返回确认摘要；确认落库走独立接口）
    图片经临时文件传递（任务参数只含路径，避免二进制入任务表）；处理完毕立即清理"""
    import os

    from app.services import agent_chat

    tmp_path = params.get("tmp_path", "")
    try:
        with open(tmp_path, "rb") as f:
            image_bytes = f.read()
        return agent_chat.learn_from_image(str(params.get("agent", "")),
                                           image_bytes,
                                           str(params.get("filename", "upload.png")))
    finally:
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass


def _submit_task(kind: str, params: dict) -> dict:
    """提交后台任务：立即返回任务ID，页面可自由切换；
    同类型任务正在执行/排队时拒绝（重复触发防护，防脏数据与资源浪费）"""
    if task_queue.has_active(kind):
        raise HTTPException(status_code=409,
                            detail=f"已有同类任务（{_TASK_KINDS[kind][0]}）正在执行，"
                                   f"请等待其完成后重试")
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


@router.get("/datasource/stats")
def datasource_stats():
    """行情数据源状态（当日累计：主源调用/失败/降级/恢复次数、成功率、当前源状态），
    供首页「数据源状态」看板；数据来自数据源调用层与断路器"""
    from app.services import datasource_stats as datasource_stats_service

    return datasource_stats_service.snapshot()


@router.get("/dashboard")
def dashboard():
    """首页看板聚合：系统状态/LLM统计/市况/持仓与信号/候选评分方案/复盘与建议
    一次请求返回全部模块（内部并行执行），替代首页多次串行请求；
    单模块失败仅标注 error，不影响整体"""
    from app.services.dashboard import build_dashboard

    return build_dashboard()


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


@router.get("/candidates/dates")
def candidate_dates(limit: int = 30):
    """候选池可选日期（去重降序）：页面默认仅加载最新一天，切换日期再按需查询"""
    return {"dates": repo.list_candidate_dates(limit)}


@router.get("/scores")
def list_scores(code: Optional[str] = None, date: Optional[str] = None, limit: int = 100):
    return repo.list_scores(code, date, limit)


# ================= 推理留痕（可解释化展示数据源） =================
@router.get("/traces")
def list_traces(code: Optional[str] = None, date: Optional[str] = None,
                module: Optional[str] = None, limit: int = 50):
    """推理留痕轻量列表（不含长文本，毫秒级；详情按需单查）"""
    return repo.list_traces(code, date, module, limit)


@router.get("/traces/{trace_id}")
def get_trace(trace_id: int):
    """推理留痕完整详情（结论卡 + 分层推理全文）"""
    trace = repo.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="留痕记录不存在")
    return trace


@router.get("/stocks/names")
def stock_names(codes: str = ""):
    """批量补名（只读）：基于行情源实时名称反查，不写库、不动任务体系。
    查不到/异常返回 {}；name 为空或等于代码的项丢弃（缺省键）。"""
    code_list = sorted({c.strip() for c in codes.split(",")
                        if c.strip() and len(c.strip()) == 6})[:50]
    if not code_list:
        return {}
    from app.datasource.fallback import get_datasource

    try:
        quotes = get_datasource().fetch_spot_quotes_batch(code_list)
    except Exception as exc:  # noqa: BLE001 数据源异常（断路器/限流）静默降级
        logger.warning("批量补名失败: %s", exc)
        return {}
    out = {}
    for code, q in quotes.items():
        name = (q.get("name") or "").strip()
        if name and name != code:
            out[code] = name
    return out


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
    """记录卖出：股数清零则标记 exited 并自动触发 ReviewAgent 复盘。
    流水与持仓更新单事务写入（K223 留痕与事实一致）。"""
    holding = repo.get_holding(hid)
    if holding is None or holding.status != "holding":
        raise HTTPException(status_code=404, detail="持仓不存在或已平仓")
    if body.shares % 100 != 0:
        raise HTTPException(status_code=400, detail="卖出股数必须为 100 的整数倍")
    if body.shares > holding.shares:
        raise HTTPException(status_code=400, detail="卖出股数超过持仓")

    remain = holding.shares - body.shares
    fields = {"shares": remain}
    if remain == 0:
        fields["status"] = "exited"
    repo.record_holding_trade(hid, side="sell", price=body.price, shares=body.shares,
                              trade_date=body.trade_date, note=body.note,
                              before_shares=holding.shares, after_shares=remain,
                              holding_fields=fields)

    result = {"holding_id": hid, "remain_shares": remain, "review_task_id": None}
    if remain == 0:
        task = _submit_task("review", {"holding_id": hid, "exit_date": body.trade_date})
        result["review_task_id"] = task["task_id"]
    return result


class AddSharesBody(BaseModel):
    """手动加仓录入（系统不做任何下单，仅记录人工执行结果）"""
    price: float = Field(gt=0)
    shares: int = Field(gt=0)
    trade_date: str
    note: str = ""


class CostAdjustBody(BaseModel):
    """手动成本修正（人工核对实盘成本后录入，原因必填留痕）"""
    cost_price: float = Field(gt=0)
    reason: str


@router.post("/holdings/{hid}/add")
def add_shares(hid: int, body: AddSharesBody):
    """手动加仓：加权成本重算 + C3 止损（成本×0.92，知识库红线）联动 + buy 流水留痕。
    流水与持仓更新单事务写入。"""
    holding = repo.get_holding(hid)
    if holding is None or holding.status != "holding":
        raise HTTPException(status_code=404, detail="持仓不存在或已平仓")
    if body.shares % 100 != 0:
        raise HTTPException(status_code=400, detail="加仓股数必须为 100 的整数倍")

    old_shares = holding.shares
    new_shares = old_shares + body.shares
    new_entry = round((holding.entry_price * old_shares + body.price * body.shares)
                      / new_shares, 4)
    new_stop = round(new_entry * 0.92, 2)
    repo.record_holding_trade(hid, side="buy", price=body.price, shares=body.shares,
                              trade_date=body.trade_date, note=body.note,
                              before_shares=old_shares, after_shares=new_shares,
                              holding_fields={"shares": new_shares, "entry_price": new_entry,
                                              "cost": round(new_entry * new_shares, 2),
                                              "stop_loss": new_stop})
    return {"holding_id": hid, "shares": new_shares, "cost_price": new_entry,
            "stop_loss": new_stop, "added_shares": body.shares}


@router.post("/holdings/{hid}/cost")
def adjust_cost(hid: int, body: CostAdjustBody):
    """手动成本修正：成本联动 C3 止损重算，adjust 流水留痕（原因必填）。
    流水与持仓更新单事务写入。"""
    holding = repo.get_holding(hid)
    if holding is None or holding.status != "holding":
        raise HTTPException(status_code=404, detail="持仓不存在或已平仓")
    if not (body.reason or "").strip():
        raise HTTPException(status_code=400, detail="成本修正必须填写原因")

    new_stop = round(body.cost_price * 0.92, 2)
    repo.record_holding_trade(hid, side="adjust", price=body.cost_price,
                              shares=holding.shares, trade_date=time.strftime("%Y-%m-%d"),
                              note=f"成本修正：{body.reason.strip()}",
                              before_shares=holding.shares, after_shares=holding.shares,
                              holding_fields={"entry_price": body.cost_price,
                                              "cost": round(body.cost_price * holding.shares, 2),
                                              "stop_loss": new_stop})
    return {"holding_id": hid, "cost_price": body.cost_price, "stop_loss": new_stop}


@router.get("/holdings/{hid}/trades")
def holding_trades(hid: int):
    """操作流水（只读）：加仓/减仓/清仓/成本修正记录，最新在前（K223 可追溯）；
    before/after_shares 为操作前后持仓股数（旧数据为 None，展示层兼容）"""
    rows = repo.get_trades(hid)
    rows.sort(key=lambda r: (r.created_at, r.id), reverse=True)
    return [{"id": r.id, "holding_id": r.holding_id, "stock_code": r.stock_code,
             "side": r.side, "price": r.price, "shares": r.shares,
             "amount": r.amount, "trade_date": r.trade_date, "note": r.note,
             "before_shares": r.before_shares, "after_shares": r.after_shares,
             "created_at": str(r.created_at)} for r in rows]


@router.post("/holdings/{hid}/monitor")
def trigger_monitor(hid: int):
    """立即执行一次持仓监控（仅限当前有效持仓；已清仓标的不再监控）"""
    holding = repo.get_holding(hid)
    if holding is None or holding.status != "holding":
        raise HTTPException(status_code=404, detail="持仓不存在或已平仓")
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


# ================= Agent 专属对话（提问答疑 / 规则调教 / 多模态学习） =================
# 交互全程复用：agent_call 统一知识注入 + 双模型路由 + 异步任务 + 知识库沉淀；
# 硬性规则与核心方法论只读，对话无权修改（校验由 LLM 强制 + 代码无写入路径）。
from app.services import agent_chat as chat_service


@router.get("/agent-chat/agents")
def chat_agents():
    """六 Agent 对话元信息（页面标注名称/职责范围/知识库来源）"""
    return [{"agent": k, **v} for k, v in chat_service.AGENT_CHAT_META.items()]


@router.get("/agent-chat/history")
def chat_history(agent: str, limit: int = 50):
    """某 Agent 的对话历史（最新在前，可回溯每次提问/调教/学习）"""
    if agent not in chat_service.AGENT_TAGS:
        raise HTTPException(status_code=400,
                            detail=f"未知 Agent: {agent}（可选：{'/'.join(chat_service.AGENT_TAGS)}）")
    return repo.list_chat_messages(agent, limit)


class ChatAskBody(BaseModel):
    agent: str = Field(description="目标 Agent：discover/score/position/monitor/sell/review")
    question: str = Field(min_length=1, description="问题内容")


@router.post("/agent-chat/ask")
def chat_ask(body: ChatAskBody):
    """文字提问答疑（异步：提交任务后轮询结果；答案标注依据来源与信心度）"""
    return _submit_task("chat_ask", {"agent": body.agent, "question": body.question})


class ChatRuleBody(BaseModel):
    agent: str = Field(description="目标 Agent")
    proposal: str = Field(min_length=1, description="规则修改/新增提案")


@router.post("/agent-chat/rules")
def chat_rule(body: ChatRuleBody):
    """规则调教校验（异步）：按验证流程给「采纳/部分采纳/维持原规则」结论；
    采纳/部分采纳自动沉淀到对应 Agent 知识库；硬性规则与核心方法论只读。"""
    return _submit_task("chat_rule", {"agent": body.agent, "proposal": body.proposal})


@router.post("/agent-chat/learn")
async def chat_learn(agent: str, file: UploadFile = File(...)):
    """多模态上传学习（异步）：MiniMax 识别（失败降级 PaddleOCR）→ 提炼知识点与标签
    → 返回确认摘要（未落库）；确认/修正标签后调用 learn/confirm 落库。"""
    import tempfile

    if agent not in chat_service.AGENT_TAGS:
        raise HTTPException(status_code=400,
                            detail=f"未知 Agent: {agent}（可选：{'/'.join(chat_service.AGENT_TAGS)}）")
    image_bytes = await file.read()
    if len(image_bytes) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片过大（上限 15MB）")
    suffix = Path(file.filename or "upload.png").suffix.lower() or ".png"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="chat_learn_")
    with os.fdopen(fd, "wb") as f:
        f.write(image_bytes)
    return _submit_task("chat_learn", {"agent": agent, "tmp_path": tmp_path,
                                       "filename": file.filename or "upload.png"})


class ChatLearnConfirmBody(BaseModel):
    agent: str = Field(description="目标 Agent")
    entries: list[dict] = Field(min_length=1, description="确认的知识点列表（可含修正后的标签）")


@router.post("/agent-chat/learn/confirm")
def chat_learn_confirm(body: ChatLearnConfirmBody):
    """确认多模态学习结果：将知识点写入对应 Agent 知识库（同步，立即生效）"""
    try:
        result = chat_service.confirm_learn(body.agent, body.entries)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result
