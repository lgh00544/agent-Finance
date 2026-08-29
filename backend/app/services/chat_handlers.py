"""intent→调用映射 + format：复用 routes.py 现有端点背后的实现，不新建业务逻辑。
长任务（score/sell/discover/trigger）先回执，task_queue 异步执行完成后直发结果。
【刚性约束】只做查询/分析/任务触发，不调用任何交易/落单接口。"""
import hashlib
import logging
import time

from app.agents import common
from app.core.config import settings
from app.db import repo
from app.graph import router as graph_router
from app.llm.structured import ModelLevel
from app.services import agent_chat, feishu_bridge, holding_view, market_view, status as status_service
from app.services import task_queue, ths_pnl

logger = logging.getLogger(__name__)

_LONG = {"score", "sell", "discover", "trigger"}
_LABEL = {"score": "飞书·单股评分", "sell": "飞书·卖出决策",
          "discover": "飞书·今日选股", "trigger": "飞书·手动选股"}
_NOTE = "\n（仅参考建议，交易需人工执行）"


def dispatch(text: str, intent: str, params: dict, hint: str, open_id: str) -> str:
    """分发：长任务异步提交回执，其余同步 format；任何异常回处理失败不崩溃"""
    if intent in _LONG:
        kind = f"feishu_{intent}"
        if not task_queue.has_active(kind):
            task_queue.submit(kind, _LABEL[intent],
                              lambda p, i=intent, o=open_id: _long_job(i, p, o), params)
            return "任务进行中，完成会通知你" + _NOTE
        return "同类任务正在执行中，请稍后再试"
    try:
        if intent == "draft":
            return _handle_draft(open_id, text)
        if intent == "teach":
            return _handle_teach(text, params, open_id)
        if intent in ("remember", "forget"):
            return _handle_memory(text, open_id, intent)
        if intent == "chat":
            return _fmt_chat(text, params)
        handler = _HANDLERS.get(intent, _fmt_help)
        return handler(params, hint)
    except Exception as exc:  # noqa: BLE001 单意图失败回处理失败，不崩溃
        logger.error("飞书意图 %s 执行失败: %s", intent, exc)
        return f"处理失败: {str(exc)[:120]}"


def _long_job(intent: str, params: dict, open_id: str) -> dict:
    """长任务执行体：跑真实 handler → 完成直发结果；失败回处理失败"""
    from app.services.feishu_sender import send_text

    try:
        send_text(open_id, _HANDLERS[intent](params, ""))
    except Exception as exc:  # noqa: BLE001 长任务失败回处理失败，不崩
        logger.error("飞书长任务 %s 失败: %s", intent, exc)
        send_text(open_id, f"处理失败: {str(exc)[:120]}")
    return {"replied": True}


def _fmt_holdings(params: dict, hint: str) -> str:
    """持仓摘要：持仓数/总市值/浮动盈亏/前 5 只"""
    view = holding_view.build_holding_view()
    rows = view["rows"]
    if not rows:
        return "当前无持仓"
    mv = sum(r["market_value"] or 0 for r in rows)
    pnl = sum(r["pnl_amount"] or 0 for r in rows)
    lines = [f"持仓 {len(rows)} 只 | 总市值 ¥{mv:,.0f} | 浮动盈亏 ¥{pnl:,.0f}"]
    for r in rows[:5]:
        pct = f"{r['pnl_pct']:+.2f}%" if r.get("pnl_pct") is not None else "—"
        lines.append(f"{r['stock_name'] or r['stock_code']} {r.get('current_price') or '—'}（{pct}）")
    if len(rows) > 5:
        lines.append(f"... 共 {len(rows)} 只")
    return "\n".join(lines)


def _fmt_pnl(params: dict, hint: str) -> str:
    """今日真实盈亏三态：未接入 / Cookie 过期 / 正常（¥与%）"""
    if not (settings.ths_pnl_enable and ths_pnl.load_cookie()):
        return "同花顺未接入（THS_PNL_ENABLE=false 或未配 Cookie）"
    snap = repo.get_latest_account_pnl() or {}
    if snap.get("token_expired"):
        return "同花顺 Cookie 过期，请到 DSH 插件重新登录"
    if snap.get("pnl_yk") is None:
        return f"今日盈亏获取失败：{snap.get('error') or '暂无数据'}"
    sh = f" 上证{snap['sh_pct']}%" if snap.get("sh_pct") is not None else ""
    return f"今日盈亏 ¥{snap['pnl_yk']:,.0f}（{snap.get('pnl_pct')}%）{sh}"


def _fmt_score(params: dict, hint: str) -> str:
    """单股评分（长任务）：复用 run_score"""
    code, name = params.get("code", ""), params.get("name", "")
    if not code:
        return "请给出 6 位股票代码（如 600519）"
    result = graph_router.run_score(code, name)
    sr = result.get("score_result") or {}
    if not sr:
        return f"评分失败：{result.get('error') or '无结果'}"
    risks = "；".join((sr.get("risk_list") or [])[:3]) or "无"
    return (f"分析 {code} {sr.get('stock_name') or name}：{sr.get('score')} 分 {sr.get('grade')} 级\n"
            f"建议: {(sr.get('final_advice') or '')[:200]}\n风险: {risks}")


def _fmt_sell(params: dict, hint: str) -> str:
    """卖出决策（长任务）：按 code 找持仓 hid → run_sell_decision"""
    code = params.get("code", "")
    holding = next((r for r in repo.list_holdings("holding")
                    if r["stock_code"] == code), None) if code else None
    if holding is None:
        return f"未找到持仓 {code or params.get('name') or ''}，无法生成卖出决策"
    result = graph_router.run_sell_decision(holding["id"])
    d = result.get("sell_decision") or {}
    if not d:
        return f"卖出决策失败：{result.get('error') or '无结果'}"
    action_map = {"hold": "继续持有", "partial": "部分减仓", "sell": "卖出清仓"}
    ratio = f" 建议减仓{d['reduce_ratio'] * 100:.0f}%" if d.get("reduce_ratio") else ""
    reasons = "；".join((d.get("reasons") or [])[:2]) or "—"
    return (f"卖出决策 {code} {holding.get('stock_name') or ''}：{action_map.get(d.get('action'), d.get('action'))}{ratio}\n"
            f"价格区间: {d.get('exit_price_zone') or '—'}\n依据: {reasons}\n"
            f"综合: {(d.get('final_advice') or '')[:150]}")


def _pipeline_summary(result: dict) -> str:
    """daily pipeline 统计摘要（discover/trigger 共用）"""
    return (f"候选 {result.get('candidates', 0)} 只，打分 {result.get('scored', 0)} 只，"
            f"建仓计划 {result.get('plans', 0)} 份")


def _fmt_discover(params: dict, hint: str) -> str:
    """今日选股摘要（长任务）：跑 daily pipeline 后列最新候选"""
    result = graph_router.run_daily_pipeline()
    rows = (repo.list_candidates(repo.list_candidate_dates(1)[0], 6)
            if repo.list_candidate_dates(1) else [])
    lines = ["选股完成：" + _pipeline_summary(result)]
    lines += [f"{r['stock_code']} {r['stock_name'] or ''}" for r in rows]
    return "\n".join(lines)


def _fmt_trigger(params: dict, hint: str) -> str:
    """手动触发选股（长任务）：跑 daily pipeline 出统计"""
    return f"选股执行完成：" + _pipeline_summary(graph_router.run_daily_pipeline()) + \
        f"（{time.strftime('%Y-%m-%d')}）"


def _fmt_market(params: dict, hint: str) -> str:
    """大盘：三大指数 + 板块轮动状态"""
    from app.services.sector_rotation_pattern import get_rotation_daily

    quotes = market_view.index_quotes()
    parts = [f"{it.get('name')} {it.get('price')}（{it.get('change_pct'):+.2f}%）"
             for it in quotes.get("indices", [])]
    rot = get_rotation_daily() or {}
    state = (rot.get("rotation_state") or {})
    if state.get("state"):
        parts.append(f"板块: {state['state']}")
    return "大盘：" + " | ".join(parts) if parts else "大盘数据获取失败"


def _fmt_monitor(params: dict, hint: str) -> str:
    """最新 N 条告警"""
    rows = repo.list_alerts(5)
    if not rows:
        return "暂无告警记录"
    lines = ["最近告警："]
    for a in rows:
        label = f"{a['stock_code']} {a['stock_name']}" if a.get("stock_name") else a["stock_code"]
        lines.append(f"{a.get('alert_type')} {label} [{a.get('severity')}] {(a.get('message') or '')[:70]}")
    return "\n".join(lines)


def _fmt_review(params: dict, hint: str) -> str:
    """最新复盘"""
    rows = repo.list_reviews(None, 3)
    if not rows:
        return "暂无复盘记录"
    lines = ["最近复盘："] + [f"{r['stock_name'] or r['stock_code']} {r.get('exit_date') or ''} "
                             f"盈亏{r.get('pnl_pct')}%" for r in rows]
    return "\n".join(lines)


def _fmt_help(params: dict, hint: str) -> str:
    """帮助 + 系统状态"""
    s = status_service.system_status()
    parts = [f"{c['name']}{'✓' if c['ok'] else '✗'}" for c in s["connections"]]
    return ("可用指令：查持仓 / 今日盈亏 / 分析 600519 / 卖出 600519 / 今日选股\n"
            "大盘怎么样 / 最新告警 / 最新复盘 / 跑一次选股\n"
            "系统状态：" + " | ".join(parts))


def _fmt_chat(text: str, params: dict) -> str:
    """知识库问答兜底（无把握指令不瞎执行）"""
    agent = params.get("agent") or "discover"
    if agent not in agent_chat.AGENT_TAGS:
        agent = "discover"
    try:
        payload = agent_chat.ask_agent(agent, text)
        return f"{payload.get('answer', '')}\n（置信 {payload.get('confidence', '')}）"
    except Exception as exc:  # noqa: BLE001 兜底失败回处理失败
        return f"处理失败: {str(exc)[:120]}"


# ==================== teach/remember/forget（教机器人，web 调教通路复用） ====================
_TEACH_SYNC_MAX = 50  # proposal>50 字符走异步
_HARD_MOD, _THRESHOLD = ("改成", "设为", "改为"), ("止损", "止盈", "仓位", "风控", "红线", "硬规则")
_AGENT_KW = (("sell", ("卖出", "减仓", "止盈", "止损")), ("monitor", ("监控", "告警", "盘中")),
             ("review", ("复盘", "反思", "迭代")), ("score", ("评分", "选股", "候选")))
_MEM = {"remember": ("记住", "别忘了"), "forget": ("忘掉", "删掉", "不要再说")}
_DRAFT_START = ("教·存草稿", "教 存草稿", "存草稿", "先存着", "开始草稿")
_DRAFT_APPEND = ("补一条", "继续", "记住", "教")
_DRAFT_PREFIX = _DRAFT_START + _DRAFT_APPEND


def _teach_agent(text: str) -> str:
    for agent, kws in _AGENT_KW:  # 领域识别；默认 score（核心研判捕获最广）
        if any(k in text for k in kws):
            return agent
    return "score"


def _strip_prefix(text: str, kws: tuple) -> str:
    t = text.strip()
    for kw in kws:
        if t.startswith(kw):
            return t[len(kw):].strip(" ，,：:")
    return t


def _guard_hard(text: str) -> str | None:
    if any(k in text for k in _HARD_MOD) and any(k in text for k in _THRESHOLD):  # 明确改阈值→硬拒
        return "该项属于硬规则，只读不可教"
    return None


def _draft_body(text: str) -> str:
    return _strip_prefix(text, _DRAFT_PREFIX).replace("不存了", "").strip(" ，,：:")


def _draft_piece(raw: str, body: str) -> dict:
    is_rule = (raw.strip().startswith("教") or any(k in body for k in _THRESHOLD)
               or any(k in body for k in ("教战法", "新规则", "以后都", "永远")))
    return {"content": body, "agent_tag": _teach_agent(body), "piece_type": "rule" if is_rule else "fact"}


def _handle_draft(open_id: str, text: str) -> str:
    t = text.strip()
    draft = feishu_bridge._drafts.get(open_id)
    if t.startswith("放弃"):
        n = len(draft.pieces) if draft else 0
        feishu_bridge._drafts.pop(open_id, None)
        return f"已丢弃 {n} 条"
    if t in ("完成", "教 完成", "教·完成"):
        if not draft or not draft.pieces:
            feishu_bridge._drafts.pop(open_id, None)
            return "草稿为空，无可提交"
        pieces = draft.pieces[:]
        feishu_bridge._drafts.pop(open_id, None)
        lines = []
        for i, piece in enumerate(pieces, 1):
            if piece["piece_type"] == "fact":
                content = repo.get_trade_profile_content()
                content[piece["content"]] = piece["content"]
                repo.update_trade_profile(content)
                result = f"已记住：{piece['content']}"
            else:
                result = _handle_teach(piece["content"], {"agent": piece["agent_tag"]}, open_id, True)
            lines.append(f"{i}. {piece['piece_type']}：{result}")
        return "草稿已提交：\n" + "\n".join(lines)
    if any(k in t for k in _DRAFT_START):
        if draft:
            return f"已有 {len(draft.pieces)} 条草稿，继续/放弃？"
        draft = feishu_bridge.DraftState()
        feishu_bridge._drafts[open_id] = draft
        body = _draft_body(t)
        if not body:
            return "已开启草稿，请继续发「补一条 内容」或「完成」"
    else:
        if not draft:
            return "还没有草稿，先发「教·存草稿」开草稿"
        if "不存了" in t:
            return f"已取消本条，草稿仍有 {len(draft.pieces)} 条"
        body = _draft_body(t)
        if not body:
            return f"草稿已有 {len(draft.pieces)} 条，请继续发「补一条 内容」或「完成」"
    draft.pieces.append(_draft_piece(t, body))
    return f"已存第 {len(draft.pieces)} 条（{draft.pieces[-1]['piece_type']}）"


def _handle_memory(text: str, open_id: str, mode: str) -> str:
    if mode == "remember" and open_id in feishu_bridge._drafts:
        return _handle_draft(open_id, text)
    hard = _guard_hard(text)  # remember=事实直写（阈值类降级 teach 待审）；forget=删键
    if hard:
        return hard
    fact = _strip_prefix(text, _MEM[mode])
    if not fact:
        return f"请说明要{'记住' if mode == 'remember' else '忘掉'}的内容（如：{_MEM[mode][0]} 我持有 600519）"
    if mode == "remember" and any(k in fact for k in _THRESHOLD):
        return _teach_validate(fact, _teach_agent(fact), open_id)  # P1 修复：降级待审不硬拒
    content = repo.get_trade_profile_content()
    if mode == "forget":
        keys = [k for k in content if fact == k or fact in k]
        if not keys:
            return "无匹配偏好可删"
        for k in keys:
            content.pop(k, None)
    else:
        content[fact] = fact
    repo.update_trade_profile(content)
    return f"已{'删除' if mode == 'forget' else '记住'}：{fact}" + ("（下次对话生效）" if mode == "remember" else "")


def _handle_teach(text: str, params: dict, open_id: str, draft_bypass: bool = False) -> str:
    if not draft_bypass and open_id in feishu_bridge._drafts:
        return _handle_draft(open_id, text)
    hard = _guard_hard(text)
    if hard:
        return hard
    proposal = _strip_prefix(text, ("教", "帮我", "请"))
    if not proposal:
        return "请说明要教的规则（如：教 以后都追涨停）"
    agent = params.get("agent") or "score"
    if len(proposal) > _TEACH_SYNC_MAX:
        task_queue.submit("feishu_teach", "飞书·规则教学",
                          lambda p, a=agent, o=open_id, g=not draft_bypass: _teach_job(a, p, o, g),
                          {"proposal": proposal})
        return "已提交处理中，完成会通知你"
    return _teach_validate(proposal, agent, open_id, guide=not draft_bypass)


def _teach_job(agent: str, params: dict, open_id: str, guide: bool = True) -> dict:
    from app.services.feishu_sender import send_text

    try:
        send_text(open_id, _teach_validate(params.get("proposal", ""), agent, open_id, guide=guide))
    except Exception as exc:  # noqa: BLE001 长任务失败回处理失败，不崩
        send_text(open_id, f"处理失败: {str(exc)[:120]}")
    return {"replied": True}


def _teach_validate(proposal: str, agent: str, open_id: str, guide: bool = True) -> str:
    """自组装 LLM 校验（复用 agent_chat 提示词/schema，不调 rule_feedback 避免双写绕过）"""
    meta = agent_chat._require_agent(agent)
    fb = common.agent_call(
        agent=agent, cache_key=f"teach:{agent}:{hashlib.md5(proposal.encode()).hexdigest()[:10]}",
        system_prompt=agent_chat._RULE_SYSTEM_PROMPT,
        user_prompt=agent_chat._rule_user_prompt(agent, proposal, meta),
        schema=agent_chat.RuleFeedback, ttl_seconds=0, model_level=ModelLevel.DEEP)
    if fb.verdict not in ("adopted", "partial"):
        msg = f"维持原规则：{fb.reason or '与现有硬性规则/方法论冲突'}"
        return msg + ("\n如需多轮教，先发「教·存草稿」开草稿" if guide else "")
    if not (fb.rule_title and fb.rule_content):
        return f"校验结论：{agent_chat._VERDICT_LABELS[fb.verdict]}，但缺少可沉淀正文，未提交"
    repo.add_pending_experience(
        f"feishu:{open_id}:{int(time.time())}", "feishu_tutoring", f"{fb.rule_title}\n{fb.reason}",
        {"open_id": open_id, "source": "feishu", "agent": agent, "verdict": fb.verdict,
         "rule_content": fb.rule_content, "conflict_note": fb.conflict_note})
    return f"已提交待审核：{fb.rule_title}（审核页确认后生效）"


_HANDLERS = {
    "holdings": _fmt_holdings, "pnl": _fmt_pnl, "score": _fmt_score,
    "sell": _fmt_sell, "discover": _fmt_discover, "market": _fmt_market,
    "monitor": _fmt_monitor, "review": _fmt_review, "trigger": _fmt_trigger,
    "help": _fmt_help,
}
