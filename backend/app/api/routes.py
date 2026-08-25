"""
REST API：仅提供数据存取与手动触发任务（无任何二次判断逻辑）
面板等前端不内置研判，全部展示 LLM 输出结论与原始数据。
"""
import difflib
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
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


def _task_experience_worker(params: dict) -> dict:
    """手动触发经验沉淀识别（强制跑 Worker 全流程，忽略积压门）"""
    from app.services.experience_worker import worker_run
    return worker_run(force=True)


_TASK_KINDS: dict[str, tuple[str, object]] = {
    "daily_pipeline": ("每日挖掘（Discover → 候选打分）", _task_daily_pipeline),
    "market_intel": ("市场研判（Market Intel）", lambda p: _task_market_intel()),
    "score": ("单股评分",
              lambda p: graph_router.run_score(p.get("stock_code", ""), p.get("stock_name", ""))),
    "position": ("分批建仓方案",
                 lambda p: graph_router.run_position(p.get("stock_code", ""), p.get("stock_name", ""),
                                                     source=p.get("source", "manual"))),
    "sell_decision": ("卖出决策",
                      lambda p: graph_router.run_sell_decision(p.get("holding_id"))),
    "monitor_all": ("全量持仓实时监控",
                    lambda p: _task_monitor_all()),
    "portfolio_sentinel": ("组合哨兵巡检",
                           lambda p: _task_portfolio_sentinel()),
    "review": ("卖出复盘",
               lambda p: graph_router.run_review(p.get("holding_id"), p.get("exit_date"))),
    "review_rethink": ("复盘建议重思考",
                       lambda p: llm_rethink_suggestion(p.get("review_id"), p.get("reason", ""))),
    "knowledge_import": ("知识库批量导入",
                         lambda p: _task_batch_import_knowledge(p.get("items") or [])),
    "chat_ask": ("Agent 对话·提问答疑", lambda p: _task_chat_ask(p)),
    "chat_rule": ("Agent 对话·规则调教", lambda p: _task_chat_rule(p)),
    "chat_learn": ("Agent 对话·图片学习", lambda p: _task_chat_learn(p)),
    "batch_ask": ("候选池批量验证对话", lambda p: _task_batch_ask(p)),
    "track_verify": ("候选池T+N验证", lambda p: _task_track_verify(False)),
    "track_backfill": ("候选池T+N历史回填", lambda p: _task_track_verify(True)),
    "track_suggest": ("选股验证建议生成", lambda p: _task_track_suggest()),
    "experience_worker": ("经验沉淀识别", lambda p: _task_experience_worker()),
}


def _task_market_intel() -> dict:
    """市场研判底座（手动入口）：聚合客观数据 → LLM 深度研判 → 落库 market_intel"""
    result = graph_router.run_market_intel()
    mi = result.get("market_intel") or {}
    return {"trade_date": mi.get("trade_date"),
            "phase": mi.get("phase"),
            "risk_appetite": mi.get("risk_appetite"),
            "summary": mi.get("summary"),
            "error": result.get("error")}


def _task_monitor_all() -> dict:
    """全量持仓实时监控（前端「立即刷新监控」按钮用）；返回 JSON 安全摘要"""
    results = graph_router.run_monitor_all()
    return {"monitored": len(results),
            "signals": [{"code": r.get("stock_code"),
                         "action": ((r.get("holding_signal") or {}).get("action")),
                         "severity": ((r.get("holding_signal") or {}).get("severity"))}
                        for r in results]}


def _task_portfolio_sentinel() -> dict:
    """组合哨兵巡检（手动入口）：聚合客观数据 → LLM 组合研判（LIGHT）→ 告警落库 + 飞书；
    返回 JSON 安全摘要；无持仓正常跳过（skipped）"""
    result = graph_router.run_portfolio_sentinel()
    ps = result.get("portfolio_sentinel") or {}
    if ps.get("skipped"):
        return {"skipped": True, "reason": ps.get("reason")}
    return {"trade_date": ps.get("trade_date"),
            "sector_alerts": len(ps.get("sector_alerts") or []),
            "time_stop_alerts": len(ps.get("time_stop_alerts") or []),
            "overall_assessment": ps.get("overall_assessment"),
            "error": result.get("error")}


def _task_track_verify(backfill: bool) -> dict:
    """候选池 T+N 验证（手动入口：每日 16:00 自动任务同链路，幂等）；
    返回 JSON 安全摘要（统计/建议不含超长文本）"""
    from app.services import track_verify

    result = track_verify.run_verify_chain(backfill=backfill)
    safe = {k: v for k, v in result.items() if k not in ("stats",)}
    suggestions = result.get("suggestions") or []
    if isinstance(suggestions, dict):  # 生成建议时返回 {suggestions, fallbacks, deduped, ...}
        safe["suggestion_count"] = (len(suggestions.get("suggestions", []))
                                    + len(suggestions.get("fallbacks", [])))
        safe["deduped"] = suggestions.get("deduped", 0)
    else:  # 无新增到期（finished_new=0 且非回填）→ 未触发建议生成
        safe["suggestion_count"] = len(suggestions)
        safe["deduped"] = 0
    return safe


def _task_track_suggest() -> dict:
    """选股验证建议生成（手动入口：基于已存统计生成/兜底建议）"""
    from app.services import track_verify

    rows = repo.list_track_verify()
    stats = track_verify.compute_stats(rows, period="t5")
    anomalies = track_verify.detect_anomalies(stats)
    return track_verify.generate_suggestions(stats, anomalies)


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
                                           str(params.get("filename", "upload.png")),
                                           str(params.get("description", "")))
    finally:
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass


def _task_batch_ask(params: dict) -> dict:
    """候选池批量验证对话（只读分析 + 调整建议留痕；调整须人工确认生效）"""
    from app.services import batch_chat

    return batch_chat.ask_batch(str(params.get("scope", "all")),
                                params.get("codes") or [],
                                str(params.get("question", "")),
                                str(params.get("date", "") or time.strftime("%Y-%m-%d")),
                                operator=str(params.get("operator", "")))


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


@router.post("/tasks/{tid}/cancel")
def cancel_task(tid: str):
    """手动取消卡死任务（仅待执行/执行中可取消；取消后立即释放任务队列，
    新任务可提交，无需重启后端）"""
    if not task_queue.cancel(tid):
        raise HTTPException(status_code=400,
                            detail="任务不存在或当前状态不可取消（仅待执行/执行中可取消）")
    return {"task_id": tid, "status": "failed", "canceled": True}


# ================= 任务触发 =================
class CodeBody(BaseModel):
    stock_code: str = Field(description="6 位股票代码")
    stock_name: str = ""


@router.post("/jobs/discover/run")
def run_discover_job():
    """手动触发每日挖掘（异步提交：discover → 候选打分 全流程后台执行）"""
    return _submit_task("daily_pipeline", {})


# ================= 市场研判底座（market_intel：独立触发 + 独立查看） =================

@router.post("/market_intel/run")
def run_market_intel_job():
    """手动触发市场研判（异步提交：聚合数据 → LLM 深度研判 → 落库 market_intel）"""
    return _submit_task("market_intel", {})


# ================= 组合哨兵（portfolio_sentinel：组合级风控，与 MonitorAgent 零耦合） =================

@router.post("/portfolio_sentinel/run")
def run_portfolio_sentinel_job():
    """手动触发组合哨兵巡检（异步提交：组合数据聚合 → LLM 组合研判 → 告警落库 + 飞书）"""
    return _submit_task("portfolio_sentinel", {})


@router.get("/market_intel")
def get_market_intel(date: str | None = None):
    """当日/指定日期市场研判（无参数默认最新一日；不存在返回 404）"""
    row = (repo.get_market_intel(date) if date
           else repo.get_latest_market_intel())
    if row is None:
        raise HTTPException(status_code=404, detail="当日市场研判不存在（可手动触发生成）")
    return row


@router.get("/market_intel/dates")
def market_intel_dates(limit: int = 30):
    """已生成市场研判的日期列表（最新在前，页面选日期）。
    返回裸数组（原包裹 {"dates": [...]} 与前端期望 string[] 不一致，致 React SPA 黑屏）"""
    return repo.list_market_intel_dates(limit)


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
    """当日市况评分（v2.0 前置步骤结果：总分/档位/候选池上限/五维/综述），供首页「今日操作提示」。
    批次4：返回值追加 strictness（当日最终严格度，含 MarketIntel 修正；row 缺失/空 → None，前端降级）。"""
    from app.services.candidate_tradeable import _day_strictness
    row = repo.get_latest_market_condition()
    if not row:
        return {"strictness": None}
    td = row.get("trade_date")
    return {**row, "strictness": _day_strictness(str(td)) if td else None}


# ================= 市场概览（顶部状态栏 / 首页热门板块，只读聚合） =================
@router.get("/market/indices")
def market_indices():
    """三大指数实时行情（上证指数/深证成指/创业板指，60s 缓存防限流）；
    数据源失败返回空列表 + error 标注（前端显示「数据加载中」或上次缓存值，不抛原始报错）"""
    return market_view.index_quotes()


@router.get("/market/indices/history")
def market_indices_history(days: int = 90):
    """三大指数日线历史（只读，近 N 天）：change_pct 按收盘价回算（东财接口无涨跌幅列，
    与 discover 市况同口径）；数据源层 3600s 缓存；失败返回空 items + error 标注，不抛原始报错"""
    import pandas as pd
    from datetime import datetime, timedelta, timezone

    from app.datasource.akshare_source import get_datasource

    days = max(7, min(days, 250))
    now = datetime.now(timezone(timedelta(hours=8)))
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    items, err = [], None
    try:
        src = get_datasource()
        for code, name in market_view.INDEX_NAMES.items():
            df = src.fetch_index_daily(code, start, end)
            if df is None or df.empty:
                continue
            df = df.sort_values("date")
            df["change_pct"] = df["close"].pct_change() * 100
            for _, r in df.iterrows():
                if pd.notna(r["change_pct"]):
                    items.append({"date": r["date"], "code": code, "name": name,
                                  "change_pct": round(float(r["change_pct"]), 2)})
    except Exception as exc:  # noqa: BLE001
        err = f"指数历史获取失败（{type(exc).__name__}）"
    return {"items": items, "error": err}


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
    """候选池可选日期（去重降序）：页面默认仅加载最新一天，切换日期再按需查询。
    返回裸数组（原包裹 {"dates": [...]} 与前端期望 string[] 不一致，致 React SPA 黑屏）"""
    return repo.list_candidate_dates(limit)


@router.get("/candidates/tradeable")
def candidates_tradeable(date: Optional[str] = None, limit: int = 200):
    """当日可建仓判定视图（只读；当日缺判定记录时懒补算）：
    {date, count(可建仓数), plan_candidate_count(可自动生成建仓计划数), total, items}"""
    from app.services import candidate_tradeable

    trade_date = date or time.strftime("%Y-%m-%d")
    return candidate_tradeable.tradeable_view(trade_date, limit)


@router.get("/candidate/concentration")
def candidate_concentration(date: Optional[str] = None):
    """候选行业集中度（只读 detail.enriched.industry）：
    {total, groups, max_concentration, max_industry, coverage}；coverage<50% 时前端不展示集中度"""
    from app.services import pre_market_screen

    return pre_market_screen.candidate_industry_concentration(date)


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


class RejectSuggestionBody(BaseModel):
    reason: str = Field(default="", description="驳回原因（审核留痕，可空以兼容旧客户端）")


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
             "hit_count": r.hit_count, "last_used_at": str(r.last_used_at) if r.last_used_at else None,
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
             "reject_reason": s.reject_reason or "",
             "priority": s.priority or "medium", "rule_type": s.rule_type or "soft",
             "problem_desc": s.problem_desc or "", "rule_text": s.rule_text or "",
             "expected_effect": s.expected_effect or "", "risk_note": s.risk_note or "",
             "file_path": s.file_path or "", "insert_position": s.insert_position or "",
             "conflict_note": s.conflict_note or "", "dedup_note": s.dedup_note or "",
             "suggestion_source": s.suggestion_source or "llm",
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
    prompt/规则类建议 → 请走 POST /agent-suggestions/{sid}/adopt 一键采纳自动落地。"""
    suggestion = repo.get_agent_suggestion(sid)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="建议不存在")
    if suggestion.status != "pending":
        raise HTTPException(status_code=400, detail=f"该建议已处理（{suggestion.status}）")
    if suggestion.target_kind != "profile":
        raise HTTPException(
            status_code=400,
            detail="该建议为规则类（prompt），请走 /agent-suggestions/{sid}/adopt 一键采纳自动落地")

    content = repo.get_trade_profile_content()
    content[suggestion.rule_name] = _coerce_value(suggestion.suggested_value)
    version = repo.update_trade_profile(content)
    repo.update_agent_suggestion_status(sid, "approved")
    return {"approved": True, "suggestion_id": sid, "applied": "profile",
            "profile_version": version}


@router.post("/agent-suggestions/{sid}/reject")
def reject_agent_suggestion(sid: int, body: RejectSuggestionBody | None = None):
    """人工审核：驳回建议（不修改任何配置）；reason 为驳回原因，落库留痕（审核可追溯）"""
    suggestion = repo.get_agent_suggestion(sid)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="建议不存在")
    if suggestion.status != "pending":
        raise HTTPException(status_code=400, detail=f"该建议已处理（{suggestion.status}）")
    reason = (body.reason if body else "") or ""
    repo.update_agent_suggestion_status(sid, "rejected", reason=reason)
    return {"rejected": True, "suggestion_id": sid, "reason": reason}


# ================= 一键采纳自动落地（规则存库 + agent_call 动态注入，绝不写源码文件） =================

_WEAKEN_VERBS = ("放宽", "允许", "取消", "豁免", "解除", "不设", "绕过")


class AdoptSuggestionBody(BaseModel):
    confirm: bool = Field(default=False, description="硬规则二次确认（rule_type=hard 时必须为 True）")


class RollbackRuleBody(BaseModel):
    reason: str = Field(min_length=1, description="回滚原因（必填，至少 1 个字符）")


def _normalize_rule(text: str) -> str:
    """规则文本归一化（空白折叠 + 去尾部标点），供去重/冲突比对"""
    return re.sub(r"\s+", "", str(text or "")).strip("。；;，,！!？? \t")


def _validate_adopt(suggestion) -> tuple[bool, str, str]:
    """确定性二次校验（双保险第二层，纯函数可单测）：
    1) 与已生效规则比对：完全相同/高度相似 → 去重拦截；
    2) 与人工硬性规则比对：疑似放宽/绕过的冲突 → 冲突拦截；相同/相似 → 去重拦截；
    3) rule_name 命中偏好档案字段 → 引导改走 profile 通道。
    返回 (通过, conflict_note, dedup_note)；conflict/dedup 任一非空即拦截。"""
    from app.agents.common import HARD_RULES

    norm = _normalize_rule(suggestion.rule_text)
    if not norm:
        return False, "", "规则正文为空，无法采纳"
    for r in repo.get_active_rules():
        rn = _normalize_rule(r.get("rule_text", ""))
        if not rn:
            continue
        if rn == norm:
            return False, "", (f"规则已存在：与生效规则 #{r['id']}「{r.get('rule_name', '')}」完全相同，"
                               "无需重复采纳")
        if difflib.SequenceMatcher(None, rn, norm).ratio() >= 0.85:
            return False, "", (f"与生效规则 #{r['id']}「{r.get('rule_name', '')}」高度相似"
                               "（相似度 ≥85%），请勿重复采纳")
    for i, hard in enumerate(HARD_RULES, 1):
        hn = _normalize_rule(hard)
        if not hn:
            continue
        if difflib.SequenceMatcher(None, hn, norm).ratio() >= 0.85:
            if any(v in norm for v in _WEAKEN_VERBS):
                return False, (f"与人工硬性规则 #{i} 冲突：该建议疑似放宽/绕过硬性底线"
                               f"（规则原文：{hard[:60]}…）"), ""
            return False, "", f"与人工硬性规则 #{i} 内容相同或高度相似，规则已存在"
    try:
        profile_keys = set(repo.get_trade_profile_content().keys())
    except Exception:  # noqa: BLE001 偏好读取失败不阻塞校验
        profile_keys = set()
    if suggestion.rule_name in profile_keys:
        return False, "该规则名命中个人交易偏好档案字段，请改为 profile 类建议在偏好档案中修改", ""
    return True, "", ""


@router.post("/agent-suggestions/{sid}/adopt")
def adopt_agent_suggestion(sid: int, body: AdoptSuggestionBody | None = None):
    """一键采纳自动落地（⚠️ 仅人工触发；系统禁止自动、无监督修改任何策略参数）：
    校验通过后写入 rule_change 表（status=active）→ agent_call 管道动态注入全部 Agent
    → 版本指纹入缓存键，LLM 缓存自动失效；硬规则需二次确认（confirm=True）。
    文件路径/插入位置仅作展示元数据，绝不写入源码文件。"""
    confirm = (body.confirm if body else False)
    suggestion = repo.get_agent_suggestion(sid)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="建议不存在")
    if suggestion.status != "pending":
        raise HTTPException(status_code=400, detail=f"该建议已处理（{suggestion.status}）")
    if suggestion.target_kind == "profile":
        raise HTTPException(status_code=400, detail="profile 类建议请走 /approve 采纳")
    if not (suggestion.rule_text or "").strip():
        raise HTTPException(status_code=400,
                            detail="该建议为旧版规则建议（无落地规则正文），不支持一键采纳；"
                                   "可驳回后由 AI 重新生成")
    if (suggestion.rule_type or "soft") == "hard" and not confirm:
        raise HTTPException(status_code=400,
                            detail="该规则为硬性规则（底层约束，全局生效），请确认后重试")

    ok, conflict_note, dedup_note = _validate_adopt(suggestion)
    if not ok:
        repo.update_agent_suggestion_notes(sid, conflict_note, dedup_note)
        raise HTTPException(status_code=409, detail=conflict_note or dedup_note)

    change_id = repo.adopt_rule_suggestion(sid, operator="本机用户")
    if not change_id:
        raise HTTPException(status_code=400, detail="该建议已处理（并发冲突）")
    return {"adopted": True, "suggestion_id": sid, "rule_change_id": change_id,
            "applied": "injected",
            "rule_type": suggestion.rule_type or "soft",
            "rule_name": suggestion.rule_name,
            "detail": "规则已写入生效表，全部 Agent 下次任务自动携带（LLM 缓存已失效）"}


@router.get("/rule-changes")
def list_rule_changes(status: Optional[str] = None, target_agent: Optional[str] = None,
                      suggestion_id: Optional[int] = None, limit: int = 50):
    """规则变更记录（一键采纳/回滚全量留痕，时间倒序；记录页数据源；
    suggestion_id 过滤供复盘页回显某条建议的生效记录）"""
    return repo.list_rule_changes(status, target_agent, suggestion_id, limit)


@router.get("/rule-changes/{rid}")
def get_rule_change_detail(rid: int):
    """规则变更完整详情（变更前后对比/落地元数据/回滚原因）"""
    row = repo.get_rule_change(rid)
    if row is None:
        raise HTTPException(status_code=404, detail="规则变更记录不存在")
    return row


@router.post("/rule-changes/{rid}/rollback")
def rollback_rule_change(rid: int, body: RollbackRuleBody):
    """一键回滚：恢复变更前状态（status → rolled_back，原因/时间留痕，全程可追溯）"""
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(status_code=400, detail="回滚原因不能为空")
    ok = repo.rollback_rule_change(rid, reason)
    if not ok:
        raise HTTPException(status_code=404, detail="规则变更记录不存在或已回滚")
    return {"rolled_back": True, "rule_change_id": rid, "reason": reason}


# ================= 持仓止盈/仓位管理计划（独立计算服务，与持仓监控页同源） =================
@router.get("/holdings/take-profit-plan")
def take_profit_plan(force: bool = False):
    """全部持仓的分档止盈 + 阶梯止损 + 仓位管理计划（纯计算，零 LLM 调用）。
    行情/参考止损止盈来自 build_holding_view()（与持仓监控页同一函数）100% 同源；
    结果按 代码+日期 缓存 10 分钟，force=true 击穿（手动刷新）；
    每次计算自动写推理留痕（source_module='position_monitor'），并顺带检查
    「接近止盈/止盈触发」告警（独立去重通道，不改监控循环）。"""
    from app.services.take_profit import build_plans
    return build_plans(force=force)


# ================= 派发期判定（6 维自动判定；每日 15:30 落库，此端点实时查 / force 击穿） =================
@router.get("/distribution_phase/{stock_code}")
def distribution_phase(stock_code: str, force: bool = False):
    """单只标的派发期自动判定：完整 6 维 + phase + confidence + missing_data（纯计算零 LLM）。
    结果按 代码+日期 缓存 86400s，force=true 删除缓存键后重算（手动击穿）；
    缺维返回 null + missing_data 标注，不补零不补均值。"""
    from app.cache import cache
    from app.services.distribution_phase import compute_distribution_phase
    trade_date = time.strftime("%Y-%m-%d")
    if force:
        cache.delete(f"distribution_phase:{trade_date}:{stock_code}")
    try:
        return compute_distribution_phase(stock_code, trade_date)
    except Exception as exc:  # noqa: BLE001 判定失败报 502，前端提示可稍后重试
        logger.warning("派发期判定失败 %s: %s", stock_code, exc)
        raise HTTPException(status_code=502, detail=f"派发期判定失败: {exc}")


# ================= 资本视图（游资/龙虎榜/资金流三维 + K189 对倒 + 30日统计；批次E） =================
@router.get("/capital_view/{stock_code}")
def capital_view(stock_code: str, force: bool = False):
    """单只标的资本视图（最近 30 个上榜交易日）：recent_actors/coordination/wash_suspect(K189 纯代码)/
    stats_30d/theme_resonance + dragon_tiger_rows·capital_flow_rows 三维表。
    结果 86400s 缓存，force=true 删除缓存键后重算；30 日无数据 → coordination="数据不足"（绝不写"无动作"）；
    单源必标 source="sse_only"（K227 诚实）。"""
    from app.cache import cache
    from app.services.capital_view import compute_capital_view
    trade_date = time.strftime("%Y-%m-%d")
    if force:
        cache.delete(f"capital_view:{trade_date}:{stock_code}")
    try:
        return compute_capital_view(stock_code, trade_date)
    except Exception as exc:  # noqa: BLE001 计算失败报 502，前端提示可稍后重试
        logger.warning("资本视图失败 %s: %s", stock_code, exc)
        raise HTTPException(status_code=502, detail=f"资本视图失败: {exc}")


# ================= 持仓红线扫描（批次G）：C1/C2/C3/C4 + K139/K226/K189 事实层 =================
def _fetch_day_lows(codes: list) -> dict:
    """每只持仓当日最低价（日K最新一根 low）；失败/停牌 → 不收录（C2 缺数据显式 null）"""
    lows: dict[str, float] = {}
    if not codes:
        return lows
    from app.datasource.fallback import get_datasource
    end = time.strftime("%Y-%m-%d")
    start = time.strftime("%Y-%m-%d", time.localtime(time.time() - 45 * 86400))
    for code in codes:
        try:
            kl = get_datasource().fetch_daily_kline(code, start, end)
            if kl is not None and not kl.empty:
                lows[code] = float(kl.iloc[-1]["low"])
        except Exception as exc:  # noqa: BLE001 单只失败不影响其余
            logger.warning("红线扫描·当日 low 取数失败 %s: %s", code, exc)
    return lows


def _red_line_holdings() -> tuple[list, dict]:
    """红线扫描输入：build_holding_view() 行情行（100% 与持仓监控页同源）+ 每只 high_price（repo 读取）"""
    view = holding_view.build_holding_view()
    holdings = []
    for r in view["rows"]:
        high_price = None
        if r.get("id"):
            try:
                h = repo.get_holding(r["id"])
                high_price = getattr(h, "high_price", None)
            except Exception:  # noqa: BLE001 单只 high_price 失败不阻塞（C4 缺数据 → null）
                high_price = None
        holdings.append({"stock_code": r["stock_code"], "entry_price": r.get("entry_price"),
                         "cost": r.get("cost"), "shares": r.get("shares"),
                         "high_price": high_price})
    return holdings, view


@router.get("/red_line_check")
def red_line_check():
    """全部持仓红线扫描：C1 占比 / C2 日内回撤 / C3 止损 / C4 突破 + K139 SOP / K226 派发期 / K189 对倒。
    纯计算 + 复用 D/E 缓存；缺数据字段显式 null；K139/K226 为参考权重（LLM 一票否决）。"""
    from app.services.red_line_check import account_total_asset, compute_red_line
    holdings, view = _red_line_holdings()
    prices = {r["stock_code"]: r["current_price"] for r in view["rows"] if r.get("current_price") is not None}
    lows = _fetch_day_lows(list(prices))
    total_asset = account_total_asset()
    result = compute_red_line(holdings, prices, total_asset, lows=lows)
    return {"rows": result, "trade_date": time.strftime("%Y-%m-%d"),
            "total_asset": total_asset, "quote_time": view.get("quote_time")}


@router.get("/red_line_check/{stock_code}")
def red_line_check_single(stock_code: str):
    """单只持仓红线扫描（取数管道与全量一致）；无该持仓 → 404"""
    from app.services.red_line_check import account_total_asset, compute_red_line
    holdings, view = _red_line_holdings()
    row = next((r for r in view["rows"] if r["stock_code"] == stock_code), None)
    if row is None:
        raise HTTPException(status_code=404, detail=f"无该持仓: {stock_code}")
    h = next((x for x in holdings if x["stock_code"] == stock_code), None)
    prices = {stock_code: row["current_price"]} if row.get("current_price") is not None else {}
    lows = _fetch_day_lows([stock_code])
    result = compute_red_line([h] if h else [], prices, account_total_asset(), lows=lows)
    return result[0] if result else {"stock_code": stock_code, "red_line": None}


# ================= 复盘反哺选股（批次H）：组合归因 / 周期复利 =================
@router.get("/portfolio_attribution")
def portfolio_attribution(days: int = 30):
    """组合归因（纯计算，零 LLM）：组合盈亏曲线 + 各持仓贡献度瀑布 + 最大拖累者。
    口径写死在 track_verify.build_portfolio_attribution（单测锁定）；days 默认 30，上限 365。"""
    from app.services.track_verify import build_portfolio_attribution
    days = max(1, min(days, 365))
    return build_portfolio_attribution(days)


@router.get("/stock_cycle_attribution/{stock_code}")
def stock_cycle_attribution(stock_code: str):
    """单股周期复利（纯计算，零 LLM）：历史多次操作的汇总（总盈亏/平均持仓/最佳最差周期/胜率拖累率）。
    无持仓记录 → has_history=False；供 Score 历史胜率加分/扣分 + 复盘页周期表。"""
    from app.services.track_verify import build_stock_cycle_attribution
    return build_stock_cycle_attribution(stock_code)


# ================= 游资追踪（游资档案 / 龙虎榜流水 / 留痕 / 权重迭代） =================
@router.get("/hot-money/profiles")
def hot_money_profiles(q: str = "", tier: str = ""):
    """游资档案列表（名称/席位/梯队/风格/擅长题材/5日胜率），
    q=名称或席位模糊搜索、tier=档位过滤；纯读不写"""
    rows = repo.list_hot_money_profiles()
    q = (q or "").strip()
    tier = (tier or "").strip()
    if q:
        rows = [p for p in rows if q in (p.get("actor_name") or "")
                or q in (p.get("seat_code") or "")]
    if tier:
        rows = [p for p in rows if p.get("tier") == tier]
    return rows


@router.get("/hot-money/flows")
def hot_money_flows(date: Optional[str] = None, code: Optional[str] = None,
                    lhb_type: str = "1d", limit: int = 500):
    """龙虎榜原始流水（按日/标的/口径筛选），游资追踪页数据源（纯读）"""
    return repo.list_lhb_flows(trade_date=date, stock_code=code,
                               lhb_type=lhb_type, limit=limit)


@router.get("/hot-money/traces")
def hot_money_traces(code: Optional[str] = None, limit: int = 50):
    """游资研判留痕（source_module='hot_money'，跨模块联查一次拿到全研判）"""
    return repo.list_traces(code=code, module="hot_money", limit=limit)


@router.post("/hot-money/win-rate-iteration")
def hot_money_win_rate_iteration():
    """游资胜率迭代（代码侧统计 + 建议生成，需真实行情回溯，耗时较长）：
    ⚠️ 只生成建议（agent_suggestion 落 pending）与统计事实（win_rate_5d/last_review_at），
    任何降/升档与权重调整必须经人工审核确认后才生效。"""
    from app.services import hot_money_review

    return hot_money_review.run_win_rate_iteration()


class TierApplyBody(BaseModel):
    suggestion_id: int


@router.post("/hot-money/tier/apply")
def hot_money_tier_apply(body: TierApplyBody):
    """人工审核确认后应用游资档位建议（仅 approved 状态可执行，代码绝不自动改权重生效）"""
    from app.services import hot_money_review

    try:
        return hot_money_review.apply_tier_suggestion(body.suggestion_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ================= 候选池 T+N 验证（选股效果闭环） =================
@router.get("/track/verify/list")
def track_verify_list(select_date: str = "", rating: str = "", status: str = "",
                      limit: int = 200):
    """追踪验证行列表（默认全部；status: all/tracking/finished；纯读）"""
    finished = None
    if status == "tracking":
        finished = 0
    elif status == "finished":
        finished = 1
    return repo.list_track_verify(select_date=select_date, rating=rating,
                                  is_finished=finished, limit=limit)


@router.get("/track/verify/dates")
def track_verify_dates(limit: int = 30):
    """追踪验证可选日期（去重降序，页面日期筛选）"""
    return repo.list_track_verify_dates(limit=limit)


@router.get("/track/verify/stats")
def track_verify_stats(period: str = "t5"):
    """周期统计（从已存验证行纯计算，非实时行情；period: t3/t5/t10）"""
    from app.services import track_verify

    if period not in ("t3", "t5", "t10"):
        period = "t5"
    rows = repo.list_track_verify()
    stats = track_verify.compute_stats(rows, period=period)
    stats["anomalies"] = track_verify.detect_anomalies(stats)
    return stats


class TrackVerifyRunBody(BaseModel):
    backfill: bool = Field(default=False,
        description="True=历史回填（幂等，重复执行安全）；False=常规验证")


@router.post("/track/verify/run")
def track_verify_run(body: TrackVerifyRunBody | None = None):
    """手动触发候选 T+N 验证（每日 16:00 自动任务同链路；提交任务即返回，
    结果保存后可随时查询；同类型任务执行中拒绝重复提交）"""
    backfill = bool(body.backfill) if body is not None else False
    return _submit_task("track_backfill" if backfill else "track_verify", {})


@router.post("/track/verify/suggest")
def track_verify_suggest():
    """手动触发选股验证建议生成（LLM 为主 + 模板兜底，来源强制标记；
    建议落 pending 走人工审核闭环）"""
    return _submit_task("track_suggest", {})


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
def chat_history(agent: str, limit: int = 50, message_type: Optional[str] = None):
    """某 Agent 的对话历史（最新在前，可回溯每次提问/调教/学习/批量对话）"""
    if agent not in chat_service.AGENT_TAGS:
        raise HTTPException(status_code=400,
                            detail=f"未知 Agent: {agent}（可选：{'/'.join(chat_service.AGENT_TAGS)}）")
    return repo.list_chat_messages(agent, limit, message_type)


class ChatAskBody(BaseModel):
    agent: str = Field(description="目标 Agent：discover/score/position/monitor/sell/review")
    question: str = Field(min_length=1, description="问题内容")


@router.post("/agent-chat/ask")
def chat_ask(body: ChatAskBody):
    """文字提问答疑（异步：提交任务后轮询结果；答案标注依据来源与信心度）"""
    return _submit_task("chat_ask", {"agent": body.agent, "question": body.question})


class BatchAskBody(BaseModel):
    scope: str = Field(description="提问范围：all/tradeable/A/B/C/manual")
    codes: list[str] = Field(default_factory=list, description="manual 范围时的标的代码列表")
    question: str = Field(min_length=1, description="批量验证问题")
    date: str = Field(default="", description="候选日期（留空取今日）")


@router.post("/agent-chat/batch-ask")
def batch_ask(body: BatchAskBody):
    """候选池批量验证对话（异步）：按范围注入候选上下文 →「总-分」结构化回答 + 调整建议；
    仅分析不改数据，调整须人工「确认生效」后写入 candidate_adjust。"""
    return _submit_task("batch_ask", {"scope": body.scope, "codes": body.codes,
                                      "question": body.question, "date": body.date})


class BatchAdjustApplyBody(BaseModel):
    batch_id: int = Field(description="批量调整记录 id")
    operator: str = Field(default="", description="操作人")


@router.post("/agent-chat/batch-adjust/apply")
def batch_adjust_apply(body: BatchAdjustApplyBody):
    """确认生效：pending→applied，将 adjust_plan 写入 candidate_adjust（覆盖展示层判定，可回滚）"""
    from app.services import batch_chat

    try:
        return batch_chat.apply_batch_adjust(body.batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class BatchAdjustRollbackBody(BaseModel):
    reason: str = Field(default="", description="回滚原因")


@router.post("/agent-chat/batch-adjust/{batch_id}/rollback")
def batch_adjust_rollback(batch_id: int, body: BatchAdjustRollbackBody):
    """回滚：applied→rolled_back，删除本次覆盖恢复原判定；留原因与时间"""
    from app.services import batch_chat

    try:
        return batch_chat.rollback_batch_adjust(batch_id, body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class ChatRuleBody(BaseModel):
    agent: str = Field(description="目标 Agent")
    proposal: str = Field(min_length=1, description="规则修改/新增提案")


@router.post("/agent-chat/rules")
def chat_rule(body: ChatRuleBody):
    """规则调教校验（异步）：按验证流程给「采纳/部分采纳/维持原规则」结论；
    采纳/部分采纳自动沉淀到对应 Agent 知识库；硬性规则与核心方法论只读。"""
    return _submit_task("chat_rule", {"agent": body.agent, "proposal": body.proposal})


@router.post("/agent-chat/learn")
async def chat_learn(agent: str, file: UploadFile = File(...),
                     description: str = Form(default="")):
    """多模态上传学习（异步）：MiniMax 识别（失败降级 PaddleOCR）→ 提炼知识点与标签
    → 返回确认摘要（未落库）；确认/修正标签后调用 learn/confirm 落库。
    可选辅助文本描述（≤500字，图片为主、文字为辅），空描述完全兼容旧行为。"""
    import tempfile

    if agent not in chat_service.AGENT_TAGS:
        raise HTTPException(status_code=400,
                            detail=f"未知 Agent: {agent}（可选：{'/'.join(chat_service.AGENT_TAGS)}）")
    if len(description) > 500:
        raise HTTPException(status_code=400, detail="补充说明过长（上限 500 字）")
    image_bytes = await file.read()
    if len(image_bytes) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片过大（上限 15MB）")
    suffix = Path(file.filename or "upload.png").suffix.lower() or ".png"
    fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="chat_learn_")
    with os.fdopen(fd, "wb") as f:
        f.write(image_bytes)
    return _submit_task("chat_learn", {"agent": agent, "tmp_path": tmp_path,
                                       "filename": file.filename or "upload.png",
                                       "description": description})


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


# ==================== 经验沉淀闭环 API（M1-M5 前端数据源） ====================

class ExperienceReviewBody(BaseModel):
    action: str = Field(description="approve=批准 / reject=驳回")
    note: str = Field(default="", description="驳回原因必填（留痕）")


class ExperienceConfigBody(BaseModel):
    config: dict = Field(description="key-value 配置（key 须为 DEFAULTS 已知项）")


@router.get("/experience/pending")
def experience_pending(status: str | None = None, stage: str | None = None, limit: int = 50):
    """M1 沉淀队列（只读看板；pending 灰·processing 蓝·done 绿，按阶段筛选）"""
    return repo.list_pending_experience(status=status, stage=stage, limit=limit)


@router.post("/experience/worker/run")
def experience_worker_run():
    """M1 立即触发识别（异步后台任务；同类型活跃时 409 拒绝防并发）"""
    return _submit_task("experience_worker", {})


@router.get("/experience/list")
def experience_list(status: str | None = None, stage: str | None = None,
                    auto_merged: int | None = None, limit: int = 100):
    """M4 经验库列表（按状态/阶段/自动合并筛选）"""
    return repo.list_experience(status=status, stage=stage, auto_merged=auto_merged, limit=limit)


@router.get("/experience/search")
def experience_search(stage: str | None = None, query: str | None = None, k: int = 5):
    """经验检索（FTS5/LIKE，仅 active；供 M4 搜索框与注入联查）"""
    return repo.search_experience(stage=stage, query=query, k=k)

@router.get("/experience/config")
def experience_config_get():
    """M5 设置读取（当前生效值 = DB experience_config 覆盖 + 默认）"""
    from app.services.experience_worker import DEFAULTS, _cfg
    return {k: _cfg(k) for k in DEFAULTS}


@router.post("/experience/config")
def experience_config_set(body: ExperienceConfigBody):
    """M5 设置写入（key-value 热加载，无需重启；key 须为 DEFAULTS 已知项）"""
    from app.services.experience_worker import DEFAULTS
    invalid = [k for k in body.config if k not in DEFAULTS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"未知配置项: {invalid}")
    for k, v in body.config.items():
        repo.set_config(k, str(v))
    return {"ok": True, "config": {k: str(v) for k, v in body.config.items()}}


@router.get("/experience/{eid}")
def experience_detail(eid: int):
    """单条经验（含来源 pending 摘要）"""
    item = repo.get_experience(eid)
    if item is None:
        raise HTTPException(status_code=404, detail="经验不存在")
    return item


@router.post("/experience/{eid}/review")
def experience_review(eid: int, body: ExperienceReviewBody):
    """M2/M3 审核：approve→active；reject→rejected（原因必填留痕）。仅 pending_review 可操作。"""
    item = repo.get_experience(eid)
    if item is None:
        raise HTTPException(status_code=404, detail="经验不存在")
    if item["status"] != "pending_review":
        raise HTTPException(status_code=409,
                            detail=f"仅待审核条目可审核（当前 {item['status']}）")
    if body.action == "approve":
        repo.update_experience_status(eid, "active", reviewer="sir",
                                      action="approve", note=body.note or "")
        return {"id": eid, "status": "active"}
    if body.action == "reject":
        if not (body.note or "").strip():
            raise HTTPException(status_code=400, detail="驳回必须填写原因（留痕可追溯）")
        repo.update_experience_status(eid, "rejected", reviewer="sir",
                                      action="reject", note=body.note)
        return {"id": eid, "status": "rejected"}
    raise HTTPException(status_code=400, detail="action 仅支持 approve/reject")


@router.post("/experience/{eid}/rollback")
def experience_rollback(eid: int):
    """M4 回滚：仅「已生效且自动合并」可回滚 → rolled_back + review_log(rollback)；
    回滚后 status 过滤使检索不再命中（误合并可恢复）。"""
    item = repo.get_experience(eid)
    if item is None:
        raise HTTPException(status_code=404, detail="经验不存在")
    if item["status"] != "active" or item["auto_merged"] != 1:
        raise HTTPException(status_code=409,
                            detail="仅「已生效且自动合并」的经验可回滚（误合并恢复入口）")
    repo.update_experience_status(eid, "rolled_back", reviewer="sir",
                                  action="rollback", note="M4 人工回滚")
    return {"id": eid, "status": "rolled_back"}
