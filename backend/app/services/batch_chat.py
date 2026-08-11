"""候选池全局批量对话验证服务（只读分析 + 调整留痕，调整须人工确认）

三类交互，全部复用现有底层能力（agent_call 固定段序注入 / 异步任务 / 对话历史）：
1. 批量验证对话（ask_batch）：按范围（全部/可建仓/A/B/C/手动 codes）注入候选上下文，
   LLM 按「总-分」结构输出（整体结论/共性分析/差异说明/调整建议 + adjust_plan 调整方案）；
   仅返回分析文本与调整建议，绝不自动修改任何业务数据；
2. 确认生效（apply_batch_adjust）：用户点「确认生效」后，将 adjust_plan 写入 candidate_adjust
   （覆盖表，不污染 detail JSON），batch 状态机 pending→applied，前后快照留痕；
3. 回滚（rollback_batch_adjust）：applied→rolled_back，删除本次覆盖恢复原判定并留原因。

【刚性代码逻辑】本模块只做：范围解析、上下文注入、LLM 调用、消息与调整留痕；
全部判定与调整方案由 LLM 结构化输出，是否生效由用户人工确认。
"""
import hashlib
import logging

from pydantic import BaseModel, Field

from app.agents import common
from app.db import repo
from app.llm.structured import ModelLevel
from app.services.candidate_tradeable import (_effective_tier, _latest_plan_for,
                                              ensure_tradeable, judge_tradeable)

logger = logging.getLogger(__name__)

# 单次批量注入候选上限（保护 token，超限截断并标注）
_SCOPE_CAP = 20
_VALID_SCOPES = ("all", "tradeable", "A", "B", "C", "manual")


class BatchAnswer(BaseModel):
    """批量验证对话「总-分」结构输出"""
    overall: str = Field(description="整体结论：对所选范围候选的一次性统一判断（是否建议建仓/当前侧重，1-2 段）")
    confidence: int = Field(default=60, description="信心度 0-100，数据充分且明确时取高值，存疑时取低值")
    sources: list[str] = Field(default_factory=list,
                               description="回答依据的来源清单（候选上下文/当日市况/知识库等）")
    common_points: list[str] = Field(default_factory=list,
                                     description="共性分析：范围内多只标的共同特征/共性风险/共同关注点")
    differences: list[str] = Field(default_factory=list,
                                   description="差异说明：范围内标的之间的关键差异与优先级排序")
    suggestions: list[str] = Field(default_factory=list,
                                   description="调整建议：针对评级/关注顺序的具体优化建议（仅建议，不自动生效）")
    adjust_plan: list[dict] = Field(default_factory=list,
                                    description="可落地的调整方案（每条：stock_code+new_tier+new_label+reason+evidence），"
                                                "仅限注入范围内标的，必须人工确认后才生效")


def _judged_rows(date: str) -> list[dict]:
    """当日全部候选 + 可建仓判定（effective_tier/现价/首仓区间/标签/原因），供范围过滤与上下文注入"""
    rows = repo.list_candidates(date=date, limit=300)
    adjusts = {a["stock_code"]: a for a in repo.list_candidate_adjusts(date)}
    out = []
    for cand in rows:
        code = cand.get("stock_code") or ""
        if not code:
            continue
        try:
            snapshot = repo.get_candidate_snapshot(code, date)
            plan = _latest_plan_for(code)
            tier = _effective_tier(cand, adjusts)
            res = judge_tradeable(cand, tier, plan, snapshot)
        except Exception as exc:  # noqa: BLE001 单标的判定异常不阻塞批量
            logger.warning("批量对话判定 %s@%s 失败: %s", code, date, exc)
            res = {"is_tradeable": 0, "label": "建议关注", "block_reason": "判定异常",
                   "price_zone": "", "current_price": None}
            tier = ""
        out.append({**cand, "effective_tier": tier, **res})
    return out


def resolve_scope(scope: str, codes: list | None, date: str) -> tuple[list[dict], str]:
    """范围解析：按所选范围过滤当日候选，截断至 _SCOPE_CAP；返回 (judged 行, 范围说明)"""
    if scope not in _VALID_SCOPES:
        raise ValueError(f"未知范围: {scope}（可选：{'/'.join(_VALID_SCOPES)}）")
    rows = _judged_rows(date)
    if scope == "tradeable":
        filtered = [r for r in rows if r.get("is_tradeable")]
    elif scope in ("A", "B", "C"):
        filtered = [r for r in rows if r.get("effective_tier") == scope]
    elif scope == "manual":
        wanted = {str(c) for c in (codes or [])}
        filtered = [r for r in rows if r.get("stock_code") in wanted]
    else:
        filtered = rows
    note = f"范围：{scope}，当日候选 {len(rows)} 只"
    if len(filtered) > _SCOPE_CAP:
        note += f"，单次注入上限 {_SCOPE_CAP} 只（已截断，其余未注入）"
    return filtered[:_SCOPE_CAP], note


def _fmt_amt(value) -> str:
    """金额友好格式（元 → 亿/万）；None/非数值 → ''（纯展示格式化，不含判断）"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if abs(v) >= 1e8:
        return f"{v / 1e8:.2f}亿"
    if abs(v) >= 1e4:
        return f"{v / 1e4:.1f}万"
    return f"{v:.0f}"


def _fund_direction_text(enriched: dict) -> str:
    """候选资金方向文本（透传 detail.enriched 主力/大单净额等字段，严格当日有效）；
    无当日资金数据 → 统一标注「当日资金数据暂不可用」，不携带任何历史/占位值"""
    parts = []
    for label, key in (("主力3日", "main_net_3d"), ("主力5日", "main_net_5d"),
                       ("主力10日", "main_net_10d"), ("超大单", "super_large_net"),
                       ("大单", "large_net")):
        val = _fmt_amt((enriched or {}).get(key))
        if val:
            parts.append(f"{label}={val}")
    if not parts:
        return "当日资金数据暂不可用"
    inst = (enriched or {}).get("inst_hold_pct")
    if inst not in (None, ""):
        parts.append(f"机构持股={inst}%")
    ind = (enriched or {}).get("industry")
    if ind:
        parts.append(f"行业={ind}")
    return "；".join(parts)


def _candidate_table_text(judged: list[dict]) -> str:
    """候选上下文压缩为紧凑文本（代码/名称/评级/现价/首仓区间/判定标签/资金方向/原因/风险前2）"""
    if not judged:
        return "（范围内无候选）"
    lines = []
    for r in judged:
        price = f"{r['current_price']:.2f}" if r.get("current_price") else "—"
        risks = [str(x) for x in ((r.get("detail") or {}).get("risks") or [])[:2]]
        risks = risks or [str(x) for x in (r.get("risk_notice") or [])[:2]]
        fund = _fund_direction_text((r.get("detail") or {}).get("enriched") or {})
        lines.append(
            f"- {r.get('stock_name')}({r.get('stock_code')}) | 评级={r.get('effective_tier') or '—'} "
            f"| 现价={price} | 首仓区间={r.get('price_zone') or '无方案'} "
            f"| 判定={r.get('label') or '—'} | 原因={r.get('block_reason') or '—'} "
            f"| 资金方向={fund} | 风险={('; '.join(risks)) or '—'}")
    return "\n".join(lines)


def _market_context_text() -> str:
    """市况上下文（复用已落库的 market_condition，不调实时行情，保证批量对话不卡）"""
    mc = repo.get_latest_market_condition()
    if not mc:
        return "（暂无市况数据）"
    dims = mc.get("dims") or {}
    dim_txt = "，".join(f"{k}:{v}" for k, v in dims.items()) if dims else "—"
    return (f"市况日期={mc.get('trade_date')} | 总分={mc.get('total_score')} "
            f"| 分档={mc.get('band')} | 候选池上限={mc.get('cap')} "
            f"| 维度={dim_txt} | 摘要={mc.get('summary') or ''}")


def ask_batch(scope: str, codes: list | None, question: str, date: str,
              operator: str = "") -> dict:
    """批量验证对话：注入范围候选上下文 + 市况 → LLM「总-分」结构化回答 → 留痕两条对话消息
    返回 task_queue 安全标量 dict；adjust_plan 完整走历史 meta 取（前端确认生效用）。"""
    if not question or not question.strip():
        raise ValueError("问题不能为空")
    judged, scope_note = resolve_scope(scope, codes, date)
    from agent_prompts import batch_chat_prompt
    user_prompt = (f"【提问范围与规模】{scope_note}\n\n"
                   f"【候选上下文】\n{_candidate_table_text(judged)}\n\n"
                   f"【当日市况】\n{_market_context_text()}\n\n"
                   f"用户提问：\n{question}")
    key = (f"batch:v2:{date}:{scope}:"
           f"{hashlib.md5(question.strip().encode('utf-8')).hexdigest()[:10]}")
    answer = common.agent_call(
        agent="discover", cache_key=key,
        system_prompt=batch_chat_prompt.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        schema=BatchAnswer, ttl_seconds=0, model_level=ModelLevel.DEEP)
    adjust_plan = [p for p in (answer.adjust_plan or [])
                   if p.get("stock_code") and p.get("stock_code") in
                   {r.get("stock_code") for r in judged}]
    meta = {"scope": scope, "date": date, "count": len(judged), "scope_note": scope_note,
            "adjust_plan": adjust_plan, "common_points": answer.common_points,
            "differences": answer.differences, "suggestions": answer.suggestions,
            "confidence": answer.confidence, "sources": answer.sources}
    user_mid = repo.add_chat_message("discover", "user", question.strip(), "batch", meta=meta)
    assistant_mid = repo.add_chat_message("discover", "assistant", answer.overall, "batch",
                                          meta={**meta, "user_msg_id": user_mid})
    if adjust_plan:
        # 落一条 batch 调整留痕（pending，供确认生效/回滚）
        batch_id = repo.add_batch_adjust(scope, [r.get("stock_code") for r in judged],
                                         question.strip(), date, adjust_plan,
                                         _before_snapshot(judged), assistant_mid, operator)
    else:
        batch_id = 0
    return {"user_msg_id": user_mid, "assistant_msg_id": assistant_mid,
            "batch_id": batch_id, "scope": scope, "date": date, "count": len(judged),
            "answer": answer.overall, "confidence": answer.confidence,
            "sources": "；".join(s for s in (answer.sources or []) if s) or "",
            "scope_note": scope_note}


def _before_snapshot(judged: list[dict]) -> dict:
    """生效前快照：范围内标的名 + 当前 effective_tier/label（回滚对比用）"""
    return {"items": [{"stock_code": r.get("stock_code"), "stock_name": r.get("stock_name"),
                       "tier": r.get("effective_tier") or "", "label": r.get("label") or ""}
                      for r in judged]}


def _apply_adjust(batch: dict, names: dict[str, str]) -> list[dict]:
    """将 batch.adjust_plan 写入 candidate_adjust（tier_override）；返回已写入明细"""
    applied = []
    for p in batch.get("adjust_plan") or []:
        code = str(p.get("stock_code") or "")
        tier = str(p.get("new_tier") or "").strip().upper()
        if code not in names or tier not in ("A", "B", "C"):
            continue
        label = str(p.get("new_label") or "").strip()
        reason = f"[批量验证] {str(p.get('reason') or '').strip()}"
        repo.upsert_candidate_adjust(code, names[code], batch.get("trade_date") or "",
                                     tier, label, reason, operator=batch.get("operator") or "")
        applied.append({"stock_code": code, "stock_name": names[code],
                        "tier_override": tier, "label_override": label, "reason": reason})
    return applied


def apply_batch_adjust(batch_id: int) -> dict:
    """确认生效：pending→applied，adjust_plan 写入 candidate_adjust；返回生效明细"""
    batch = repo.get_batch_adjust(batch_id)
    if batch is None:
        raise ValueError(f"批量调整记录不存在: {batch_id}")
    if batch.get("status") != "pending":
        raise ValueError(f"当前状态 {batch.get('status')} 不可确认生效（仅 pending 可）")
    rows = repo.list_candidates(date=batch.get("trade_date") or "", limit=300)
    names = {r.get("stock_code"): r.get("stock_name") or "" for r in rows}
    applied = _apply_adjust(batch, names)
    after = {"items": applied}
    repo.update_batch_adjust_status(batch_id, "applied", after_snapshot=after)
    # 立即按 effective_tier 重判落库，保证前端计数/标签/筛选同步（幂等覆盖）
    ensure_tradeable(batch.get("trade_date") or "")
    return {"batch_id": batch_id, "status": "applied", "applied": applied, "count": len(applied)}


def rollback_batch_adjust(batch_id: int, reason: str = "") -> dict:
    """回滚：applied→rolled_back，删除本次覆盖恢复原判定；留原因与时间"""
    batch = repo.get_batch_adjust(batch_id)
    if batch is None:
        raise ValueError(f"批量调整记录不存在: {batch_id}")
    if batch.get("status") == "rolled_back":
        raise ValueError("该批次已回滚，不可重复操作")
    trade_date = batch.get("trade_date") or ""
    codes = [p.get("stock_code") for p in (batch.get("adjust_plan") or [])]
    removed = []
    for code in codes:
        if code and repo.delete_candidate_adjust(code, trade_date):
            removed.append(code)
    from datetime import datetime
    repo.update_batch_adjust_status(batch_id, "rolled_back",
                                    rollback_reason=reason.strip(),
                                    rollback_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    # 删除覆盖后立即重判落库，恢复原判定（幂等）
    ensure_tradeable(trade_date)
    return {"batch_id": batch_id, "status": "rolled_back", "removed": removed,
            "count": len(removed), "reason": reason}
