"""AI 研判推理链路留痕：异步批量写入 ai_reasoning_trace 表（零阻塞主流程）

一次生成、结构化入库、多端复用。写入完全脱离主研判同步流程：
后台单写线程攒批（满 5 条或间隔 1s）批量提交，失败重试 3 次，最终一致；
同 code+generate_date+source_module 保留最新（upsert 覆盖）。
写入失败绝不影响主业务流程（fire-and-forget + 失败仅日志）。

字段组装（从各模块现有落库参数映射，零 LLM 调用）：
  discover = snapshot/detail；score = detail 五维；position = batches/rationale；
  alert = signal；review = plan_vs_actual/lesson；sell = decision。
"""
import json
import logging
import queue
import threading
import time

from app.cache import cache
from app.db.models import AiReasoningTrace, _now
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

_BATCH_SIZE = 5          # 攒满 5 条即批量提交
_FLUSH_SECONDS = 1.0     # 兜底间隔：满 1 秒未凑满也提交
_MAX_RETRY = 3           # 批量写入失败重试次数（指数退避）

# upsert 列全集（trace_id 自增除外；create_time 冲突时刷新为本次写入时间）
_UP_COLS = ("stock_code", "stock_name", "source_module", "generate_date",
            "fact_basis", "technical_reasoning", "capital_reasoning",
            "fundamental_reasoning", "risk_reasoning", "rule_refs",
            "final_conclusion", "confidence", "data_source", "create_time", "ext_info")

_q: queue.Queue = queue.Queue()
_started = False
_start_lock = threading.Lock()
_DRAIN = object()  # 哨兵：flush 排空标记（(object, event) 元组，与 dict 载荷永不冲突）


def _now_str() -> str:
    return _now().strftime("%Y-%m-%d %H:%M")


def _start_worker() -> None:
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
        threading.Thread(target=_worker, name="trace-writer", daemon=True).start()


def submit(payload: dict) -> None:
    """提交一条留痕记录（fire-and-forget：任何异常都不抛给主流程）"""
    try:
        _start_worker()
        _q.put(payload)
    except Exception:  # noqa: BLE001
        logger.exception("trace 入队失败（忽略，不影响主流程）")


def flush(timeout: float = 15.0) -> None:
    """同步排空：提交哨兵并等待工作线程把此前全部记录落库后返回（幂等，可重复调用）。
    供进程退出前兜底与测试断言使用；等待超时仅告警不抛错（不阻塞主流程）。"""
    try:
        _start_worker()
        event = threading.Event()
        _q.put((_DRAIN, event))
        if not event.wait(timeout):
            logger.warning("trace 排空等待超时（%s 秒），部分记录可能仍在队列", timeout)
    except Exception:  # noqa: BLE001
        logger.exception("trace flush 异常（忽略）")


def _flush(batch: list[dict]) -> None:
    for attempt in range(1, _MAX_RETRY + 1):
        try:
            with SessionLocal() as db:
                for p in batch:
                    _upsert_one(db, p)
                db.commit()
            cache.delete_prefix("dbq:trace:")  # 写后失效 L1 读缓存
            return
        except Exception as exc:  # noqa: BLE001
            if attempt == _MAX_RETRY:
                logger.error("trace 批量写入失败（%d 条，重试 %d 次）: %s", len(batch), _MAX_RETRY, exc)
            else:
                time.sleep(0.5 * attempt)


def _upsert_one(db, payload: dict) -> None:
    """单条 upsert：方言原子 INSERT ... ON CONFLICT/DUPLICATE KEY（非 SELECT-先-INSERT）——
    同批内同键（如同日重复建仓/重复复盘）与多进程并发写同键均安全，后者覆盖前者。
    SELECT-先-INSERT 方案在 autoflush=False + 批内同键时会触发 UNIQUE 冲突整批丢弃（已踩坑）。"""
    values = {k: payload.get(k) for k in _UP_COLS}
    values["create_time"] = _now_str()
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
        stmt = insert(AiReasoningTrace).values(**values)
        db.execute(stmt.on_conflict_do_update(
            index_elements=["stock_code", "generate_date", "source_module"],
            set_={k: getattr(stmt.excluded, k) for k in _UP_COLS}))
    else:
        from sqlalchemy.dialects.mysql import insert
        stmt = insert(AiReasoningTrace).values(**values)
        db.execute(stmt.on_duplicate_key_update(
            **{k: getattr(stmt.inserted, k) for k in _UP_COLS}))


def _worker() -> None:
    batch: list[dict] = []
    while True:
        try:
            item = _q.get(timeout=_FLUSH_SECONDS)
        except queue.Empty:
            item = None
        if isinstance(item, tuple) and item and item[0] is _DRAIN:
            # 排空哨兵：先写掉手中批次，再通知调用方（保证此前提交全部落库）
            if batch:
                _flush(batch)
                batch.clear()
            item[1].set()
            continue
        if item is not None:
            batch.append(item)
        if batch and (len(batch) >= _BATCH_SIZE or item is None):
            _flush(batch)
            batch.clear()


# ==================== 各模块字段组装（纯字段映射，零判断逻辑） ====================

def _j(data) -> str:
    return json.dumps(data, ensure_ascii=False, default=str) if data else ""


def _line(*parts) -> str:
    return "\n".join(str(p) for p in parts if p)


def _dim_text(v: dict) -> str:
    """维度详情 → 留痕文本：v3.0 verdict/advice 优先，旧数据 comment 兜底"""
    if isinstance(v, dict):
        verdict = str(v.get("verdict") or "").strip()
        advice = str(v.get("advice") or "").strip()
        comment = str(v.get("comment") or "").strip()
        if verdict or advice:
            return _line(f"{verdict}：{advice}" if verdict and advice else (verdict or advice))
        return comment
    return ""


def trace_candidate(stock_code: str, stock_name: str, trade_date: str,
                    reasons: list, risk_notice: list, snapshot: dict,
                    detail: dict, created_at=None) -> None:
    """DiscoverAgent：事实=行情快照；技术=tech_view+中观；资金=量能+微观；基本面=宏观"""
    detail = detail or {}
    submit({
        "stock_code": stock_code, "stock_name": stock_name,
        "source_module": "discover", "generate_date": trade_date,
        "fact_basis": _j(snapshot),
        "technical_reasoning": _line(detail.get("tech_view"), detail.get("meso_view")),
        "capital_reasoning": _line(detail.get("volume_analysis"), detail.get("micro_view")),
        "fundamental_reasoning": detail.get("macro_view", ""),
        "risk_reasoning": _line(*(detail.get("risks") or []) + list(risk_notice or [])),
        "rule_refs": _rule_refs_text(detail.get("rule_refs")),
        "final_conclusion": _j({
            "stock_type": detail.get("stock_type", ""),
            "focus_type": detail.get("focus_type", ""),
            "price_levels": detail.get("price_levels", ""),
            "position_hint": detail.get("position_hint", ""),
            "confidence_tier": detail.get("confidence_tier", ""),
            "reasons": reasons,
            # v3.0 白盒维度归因：综合评估原文 + 各维度结论摘要（dim → verdict）
            "final_advice": detail.get("final_advice", ""),
            "dimensions": {d.get("dim", ""): d.get("verdict", "")
                           for d in (detail.get("dimensions") or []) if isinstance(d, dict)},
        }),
        "confidence": _conf(detail.get("confidence_pct")),
        "data_source": "行情快照 + LLM 研判",
        "ext_info": _j({"created_at": str(created_at) if created_at else ""}),
    })


def trace_score(stock_code: str, stock_name: str, trade_date: str,
                score: float, grade: str, detail: dict, risk_list: list) -> None:
    """ScoreAgent：五维分项研判 = dimensions[].verdict/advice（旧数据 comment 兜底），
    按维度归入技术/资金/基本面；v3.0 final_advice 进 final_conclusion"""
    detail = detail or {}
    by_name = {name: _dim_text(v) for name, v in detail.items() if isinstance(v, dict)}
    submit({
        "stock_code": stock_code, "stock_name": stock_name,
        "source_module": "score", "generate_date": trade_date,
        "fact_basis": _j(detail),
        "technical_reasoning": _line(by_name.get("技术趋势"), by_name.get("舆情风险")),
        "capital_reasoning": by_name.get("资金流向", ""),
        "fundamental_reasoning": _line(by_name.get("基本面"), by_name.get("行业景气")),
        "risk_reasoning": _line(*(risk_list or [])),
        "rule_refs": "",
        "final_conclusion": _j({"score": score, "grade": grade,
                                "final_advice": detail.get("final_advice", "")}),
        "confidence": 0.0,
        "data_source": "行情/财务/资金流/新闻原始数据 + LLM 五维打分",
        "ext_info": "",
    })


def trace_plan(stock_code: str, stock_name: str, plan_date: str,
               total_pct: float, batches: list, stop_loss: float,
               take_profit: float, rationale: str, plan_id: int,
               detail: dict | None = None) -> None:
    """PositionAgent：结论=分批区间/止损止盈/总仓；推理=建仓逻辑说明；
    detail: v3.0 白盒（dimensions/final_advice/market_regime）"""
    detail = detail or {}
    submit({
        "stock_code": stock_code, "stock_name": stock_name,
        "source_module": "position", "generate_date": plan_date,
        "fact_basis": _j(batches),
        "technical_reasoning": rationale,
        "capital_reasoning": "",
        "fundamental_reasoning": "",
        "risk_reasoning": "",
        "rule_refs": "",
        "final_conclusion": _j({"total_pct": total_pct, "stop_loss": stop_loss,
                                "take_profit": take_profit, "plan_id": plan_id,
                                "final_advice": detail.get("final_advice", ""),
                                "dimensions": {d.get("dim", ""): d.get("verdict", "")
                                               for d in (detail.get("dimensions") or [])
                                               if isinstance(d, dict)}}),
        "confidence": 0.0,
        "data_source": "评分 + 大盘指数原始K线 + 资金约束 + LLM 方案",
        "ext_info": "",
    })


def trace_alert(stock_code: str, stock_name: str, trade_date: str,
                alert_type: str, severity: str, message: str,
                action: str, signal: dict) -> None:
    """MonitorAgent：事实=signal 全量；推理=研判依据 reasons；结论=动作/严重度"""
    signal = signal or {}
    submit({
        "stock_code": stock_code, "stock_name": stock_name,
        "source_module": "alert", "generate_date": trade_date,
        "fact_basis": _j(signal.get("key_levels") or {}),
        "technical_reasoning": _line(*(signal.get("reasons") or [])),
        "capital_reasoning": "",
        "fundamental_reasoning": "",
        "risk_reasoning": _line(*(signal.get("risks") or [])),
        "rule_refs": "",
        "final_conclusion": _j({"alert_type": alert_type, "severity": severity,
                                "action": action, "message": message}),
        "confidence": 0.0,
        "data_source": "实时行情/公告/指标 + LLM 信号研判",
        "ext_info": _j({k: v for k, v in signal.items()
                        if k not in ("reasons", "key_levels", "risks")}),
    })


def trace_review(stock_code: str, stock_name: str, exit_date: str,
                 plan_vs_actual: dict, lesson: str, feedback: dict) -> None:
    """ReviewAgent：事实=计划兑现对比；推理=经验教训；结论=反馈与偏好微调"""
    submit({
        "stock_code": stock_code, "stock_name": stock_name,
        "source_module": "review", "generate_date": exit_date,
        "fact_basis": _j(plan_vs_actual),
        "technical_reasoning": lesson,
        "capital_reasoning": "",
        "fundamental_reasoning": "",
        "risk_reasoning": "",
        "rule_refs": "",
        "final_conclusion": _j(feedback),
        "confidence": 0.0,
        "data_source": "建仓计划 + 全程行情 + 交易记录 + LLM 复盘",
        "ext_info": "",
    })


def trace_sell(stock_code: str, stock_name: str, trade_date: str, decision: dict) -> None:
    """SellAgent：推理=决策依据；结论=动作/置信度/离场区间 + v3.0 维度归因
    （final_advice 主结论 + dimensions dim→verdict 摘要；旧数据缺省为空）"""
    decision = decision or {}
    submit({
        "stock_code": stock_code, "stock_name": stock_name,
        "source_module": "sell", "generate_date": trade_date,
        "fact_basis": "",
        "technical_reasoning": _line(*(decision.get("reasons") or [])),
        "capital_reasoning": "",
        "fundamental_reasoning": "",
        "risk_reasoning": decision.get("risk_warning", ""),
        "rule_refs": "",
        "final_conclusion": _j({"action": decision.get("action", ""),
                                "confidence": decision.get("confidence", ""),
                                "exit_price_zone": decision.get("exit_price_zone", ""),
                                "check_list": decision.get("check_list", []),
                                "final_advice": decision.get("final_advice", ""),
                                "dimensions": {d.get("dim", ""): d.get("verdict", "")
                                               for d in (decision.get("dimensions") or [])
                                               if isinstance(d, dict)}}),
        "confidence": 0.0,
        "data_source": "持仓实时行情/近期监控信号 + LLM 卖出决策",
        "ext_info": "",
    })


def _rule_refs_text(raw) -> str:
    """rule_refs 兼容：list[str]（LLM 输出）或 逗号分隔字符串 → 逗号分隔文本"""
    if isinstance(raw, list):
        return ", ".join(str(x) for x in raw if x)
    return str(raw or "")


def _conf(pct):
    try:
        return float(pct) / 100.0 if pct is not None else 0.0
    except (TypeError, ValueError):
        return 0.0
