"""游资聚合服务：龙虎榜多源校验 + 席位-游资映射 + 注入文本组装

职责边界（【刚性代码逻辑】）：只做数据聚合/校验/格式化，不含任何市场判断；
所有游资研判（标向性/题材/骗局）在提示词层（global_base + 各 Agent 专属 Prompt）。

多源校验硬规则：同一(日期,标的,口径)的净买入，至少 2 个数据源 且 差值 < verify_threshold%
才采信（confidence 高）；不足 2 源或差值 ≥ 阈值 → confidence 标低 + "数据置信度不足"，
仅参考不纳入核心评分（对齐 global_base 游资红线铁律 3：置信度不足数据不纳入核心评分）。

注入 LLM 时字段强制带口径后缀（lhb_1d_net_buy / lhb_3d_net_buy），LLM 只能调用带后缀字段
（K227 字段误读防御，禁止 LLM 自行推导口径）。
"""
import logging

from app.core.config import settings
from app.db import repo
from app.services import reasoning_trace

logger = logging.getLogger(__name__)

# 采信置信度 / 置信度不足标记
_CONF_VERIFIED = 0.9
_CONF_WEAK = 0.5
_WEAK_NOTE = "数据置信度不足（多源校验未通过或单源），仅参考"


def second_source_hint() -> str:
    """第二源现状诚实标注（K227：无第二源不得假装采信；零网络调用）。
    当前仅东财可用 → 返回"当前仅东财可用、采信待第二源"；第二源接入后自动消失。"""
    try:
        from app.datasource.dragon_tiger_source import second_source_status
        return str(second_source_status().get("annotation") or "")
    except Exception:  # noqa: BLE001 标注失败不影响主链路
        return ""


def verify_net_buy(trade_date: str, stock_code: str, lhb_type: str = "1d") -> dict:
    """多源校验：同一(日期,标的,口径)按 source 分组的净买入，≥2 源且最大相对差值 < 阈值 → 采信。
    返回 {"verified": bool, "net_buy": float|None, "sources": [...], "confidence": float}"""
    rows = repo.list_lhb_flows(trade_date=trade_date, stock_code=stock_code, lhb_type=lhb_type)
    by_source: dict[str, list[dict]] = {}
    for r in rows:
        by_source.setdefault(r.get("source") or "unknown", []).append(r)

    net_by_source = {}
    for src, items in by_source.items():
        # 同源同口径多条（如席位明细聚合）取净买之和；股票级行（seat_name=''）直接取净买
        total = sum(float(i.get("net_buy") or 0.0) for i in items)
        net_by_source[src] = total

    if len(net_by_source) < 2:
        return {"verified": False, "net_buy": None, "sources": sorted(net_by_source),
                "confidence": _CONF_WEAK}
    vals = [abs(v) for v in net_by_source.values()]
    if not all(vals) or min(vals) <= 0:
        return {"verified": False, "net_buy": None, "sources": sorted(net_by_source),
                "confidence": _CONF_WEAK}
    diff_pct = (max(vals) - min(vals)) / max(vals) * 100
    threshold = float(settings.dragon_tiger_verify_threshold or 10.0)
    if diff_pct >= threshold:
        return {"verified": False, "net_buy": None, "sources": sorted(net_by_source),
                "confidence": _CONF_WEAK}
    # 采信：取两源均值（差值 <10% 时均值近似真实值）
    net = sum(net_by_source.values()) / len(net_by_source)
    return {"verified": True, "net_buy": round(net, 2), "sources": sorted(net_by_source),
            "confidence": _CONF_VERIFIED}


def map_seat_to_actor(seat_name: str) -> dict | None:
    """席位 → 游资档案（精确 → 包含模糊匹配）；未命中返回 None（candidate_actor 留给 LLM 研判，不写库）"""
    return repo.get_profile_by_seat(seat_name)


def _latest_lhb_date(stock_code: str, trade_date: str) -> str | None:
    """标的最近可用龙虎榜日期（≤ 目标日期）。
    T+1 语义：当日盘中尚无当日龙虎榜（数据按交易日落库），取该标的最接近的已上榜交易日；
    无任何记录返回 None。"""
    try:
        flows = repo.list_lhb_flows(stock_code=stock_code, limit=1000)
    except Exception:  # noqa: BLE001 查询失败按无数据处理，不阻塞主链路
        return None
    dates = sorted({f["trade_date"] for f in flows
                    if f.get("trade_date") and f["trade_date"] <= trade_date})
    return dates[-1] if dates else None


def aggregate_for_stock(stock_code: str, stock_name: str, trade_date: str, trace: bool = True) -> dict | None:
    """聚合单标的游资数据 → 注入 dict（无数据返回 None，LLM 保持"无游资席位数据标中性"）。
    字段名强制带口径后缀（lhb_1d_net_buy / lhb_3d_net_buy），LLM 只能调用带后缀字段。
    目标日期无流水时自动回退到 ≤ 目标日期的最近龙虎榜交易日（T+1 数据注入打通）。"""
    flows = repo.list_lhb_flows(trade_date=trade_date, stock_code=stock_code)
    lhb_date = trade_date
    if not flows:
        latest = _latest_lhb_date(stock_code, trade_date)
        if latest is None:
            return None
        flows = repo.list_lhb_flows(trade_date=latest, stock_code=stock_code)
        lhb_date = latest

    by_type: dict[str, list[dict]] = {}
    for f in flows:
        by_type.setdefault(f.get("lhb_type") or "1d", []).append(f)

    agg: dict = {
        "actor": None, "tier": None, "seat_name": None,
        "lhb_1d_net_buy": None, "lhb_3d_net_buy": None,
        "confidence": None, "multi_source_verified": False,
        "sources": [], "candidate_actor": None, "note": "",
        "lhb_date": lhb_date,  # 实际生效的龙虎榜交易日（T+1 回退后为最近交易日）
    }
    # 口径隔离：每个口径独立多源校验（K227 禁止跨口径推导；校验用实际龙虎榜日期）
    for lhb_type in ("1d", "3d"):
        key = f"lhb_{lhb_type}_net_buy"
        if lhb_type not in by_type:
            continue
        verify = verify_net_buy(lhb_date, stock_code, lhb_type=lhb_type)
        if verify["verified"]:
            agg[key] = verify["net_buy"]
            agg["multi_source_verified"] = True
            agg["sources"] = sorted(set(agg["sources"]) | set(verify["sources"]))
        else:
            # 校验未通过：口径净买不纳入核心评分，但注明确信度不足（仍展示席位信息供参考）
            agg["note"] = _WEAK_NOTE
            agg["confidence"] = _CONF_WEAK
            # 如实标注第二源现状（K227 诚实：无金额第二源时标注"当前仅东财可用、
            # 采信待第二源"；第二源接入后 hint 自动为空，不再标注）
            hint = second_source_hint()
            if hint:
                agg["second_source"] = hint

    # 席位级 → 游资映射（仅采信口径或含席位明细的行）
    seat_flows = [f for f in flows if f.get("seat_name")]
    seen_actors: dict[str, dict] = {}
    for f in seat_flows:
        profile = map_seat_to_actor(f.get("seat_name") or "")
        if profile:
            seen_actors.setdefault(profile["actor_name"], profile)
    if seen_actors:
        first = next(iter(seen_actors.values()))
        agg["actor"] = first["actor_name"]
        agg["tier"] = first["tier"]
        agg["seat_name"] = first["seat_code"]

    if trace:
        # 留痕：命中游资或有流水时写 ai_reasoning_trace（source_module='hot_money'，跨模块联查）
        try:
            reasoning_trace.trace_hot_money(
                stock_code, stock_name, trade_date,
                flows=[{"seat": f.get("seat_name"), "type": f.get("lhb_type"),
                        "net_buy": f.get("net_buy"), "source": f.get("source")} for f in flows],
                agg=agg)
        except Exception:  # noqa: BLE001 留痕失败不影响主链路
            logger.warning("hot_money 留痕失败: %s/%s", stock_code, trade_date)
    return agg


def build_hot_money_context(code_aggs: dict, trade_date: str) -> str:
    """组装注入文本段（对齐阶段1四层结构：核心结论/事实数据/推理逻辑/风险提示）。
    code_aggs: {stock_code: aggregate_for_stock 返回的 dict}；无有效数据返回 ""（LLM 保持标中性）。"""
    valid = {k: v for k, v in (code_aggs or {}).items() if v}
    if not valid:
        return ""
    lines = ["【候选游资聚合数据】（口径硬隔离：字段带后缀 lhb_1d/lhb_3d，LLM 不得自行推导口径；"
             "仅作平行维度补充加权，不压倒其他四维）"]
    for code, agg in valid.items():
        if not agg:
            continue
        parts = [f"- {code}" + (f"（龙虎榜 {agg['lhb_date']}）" if agg.get("lhb_date") else "")]
        if agg.get("actor"):
            parts.append(f"  核心结论：游资[{agg['actor']}（{agg.get('tier') or '观察'}梯队）]"
                         f"席位 {agg.get('seat_name')} 上榜")
        else:
            parts.append("  核心结论：无已知游资席位命中（未强行归类，可自行研判候选游资）")
        facts = []
        if agg.get("lhb_1d_net_buy") is not None:
            facts.append(f"lhb_1d_net_buy={agg['lhb_1d_net_buy']:,.0f}元（单日）")
        if agg.get("lhb_3d_net_buy") is not None:
            facts.append(f"lhb_3d_net_buy={agg['lhb_3d_net_buy']:,.0f}元（三日累计）")
        if facts:
            parts.append(f"  事实数据：{('；'.join(facts))}"
                         f"　置信度={agg.get('confidence') or '—'}　"
                         f"多源验证={'通过' if agg.get('multi_source_verified') else '未通过'}"
                         f"　数据源={agg.get('sources') or '—'}")
        note_parts = [agg["note"]] if agg.get("note") else []
        if agg.get("second_source"):
            note_parts.append(agg["second_source"])  # K227 诚实标注第二源现状
        if note_parts:
            parts.append(f"  风险提示：{'　'.join(note_parts)}")
        lines.append("\n".join(parts))
    return "\n".join(lines)
