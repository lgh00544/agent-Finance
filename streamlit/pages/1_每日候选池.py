"""每日候选池：DiscoverAgent 输出（候选理由/技术面研判/量价与资金/关键价位/风险点/操作建议）

纯展示层：评级筛选/排序/颜色仅为字段映射与展示，不含任何二次判断逻辑。
"""
import pandas as pd
import streamlit as st

import api_client as api
import render

st.set_page_config(page_title="每日候选池", layout="wide")

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("每日候选池（DiscoverAgent）")
st.caption("筛选标准由 LLM 综合量能/趋势/行业热度/基本面研判，每日 16:10 自动生成，也可手动触发。")

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

# 顶部手动触发每日挖掘（异步提交，立即返回，不阻塞页面）
if st.button("手动触发每日挖掘", type="primary", key="btn_run_discover"):
    api.submit_task("daily_pipeline")
    st.toast("每日挖掘任务已提交后台，可切换页面继续操作")

# 评级映射（LLM 信心度档位 → 展示评级；纯展示层转换，不含任何研判）
TIER_MAP = {"强烈推荐": "A", "建议关注": "B", "谨慎观察": "C"}
TIER_ICON = {"A": "🔴", "B": "🟠", "C": "🔵"}
TIER_LABEL = {"A": "A 强烈推荐", "B": "B 建议关注", "C": "C 谨慎观察"}
TIER_COLOR = {"A": "#F87171", "B": "#FBBF24", "C": "#60A5FA"}
_SORT = {"A": 0, "B": 1, "C": 2}

try:
    rows = api.candidates(limit=500)
    if not rows:
        st.info("暂无候选数据。可点击上方「手动触发每日挖掘」，或等待每日定时任务。")
        st.stop()

    # 同日同股按最新版本覆盖（created_at 最大），历史版本不参与渲染
    latest: dict[tuple, dict] = {}
    for r in rows:
        key = (r["stock_code"], r["trade_date"])
        if key not in latest or (r.get("created_at") or "") > (latest[key].get("created_at") or ""):
            latest[key] = r
    rows = list(latest.values())

    dates = sorted({r["trade_date"] for r in rows}, reverse=True)
    c1, c2 = st.columns([2, 3])
    with c1:
        date = st.selectbox("选择日期", dates, index=0)
    with c2:
        filter_opt = st.radio("评级筛选", ["全部", "可建仓 A+B", "仅观察 C"], horizontal=True)
    st.caption("评级：🔴 A 强烈推荐 ／ 🟠 B 建议关注 ／ 🔵 C 谨慎观察（LLM 信心度档位映射，纯展示）")

    day_rows = [r for r in rows if r["trade_date"] == date]

    def _tier(r: dict) -> str:
        t = ((r.get("detail") or {}).get("confidence_tier") or "")
        return TIER_MAP.get(t, "")

    if filter_opt == "可建仓 A+B":
        day_rows = [r for r in day_rows if _tier(r) in ("A", "B")]
    elif filter_opt == "仅观察 C":
        day_rows = [r for r in day_rows if _tier(r) == "C"]

    # ===== 板块行业筛选（来自首页「今日热门板块」点击跳转，query param 传递） =====
    sector = st.query_params.get("sector", "")
    if isinstance(sector, list):
        sector = sector[0] if sector else ""
    sector = str(sector or "").strip()
    if sector:
        st.info(f"行业筛选：**{sector}**（按候选详情行业字段子串匹配）")
        if st.button("清除行业筛选"):
            st.query_params.pop("sector", None)
            st.rerun()
        matched = []
        for r in day_rows:
            industry = str(((r.get("detail") or {}).get("enriched") or {}).get("industry") or "")
            if sector in industry or (industry and industry in sector):
                matched.append(r)
        if not matched:
            st.warning(f"当日候选池中没有行业包含「{sector}」的候选股"
                       f"（候选行业字段来自个股基本信息，可能与板块名称不完全一致）。")
        day_rows = matched

    # 可建仓置顶：A→B→C，组内按 rank 升序
    day_rows.sort(key=lambda r: (_SORT.get(_tier(r), 3), int(r.get("rank") or 999)))

    # 主表：评级（颜色区分）/股票/一句话核心理由/生成时间
    summary = pd.DataFrame([{
        "评级": TIER_LABEL.get(_tier(r), "未评级"),
        "股票": render.stock_label(r["stock_code"], r["stock_name"]),
        "核心理由": (r.get("reasons") or [""])[0] or ((r.get("detail") or {}).get("meso_view") or ""),
        "生成时间": str(r.get("created_at") or "")[:16],
    } for r in day_rows])
    styled = summary.style.map(
        lambda v: f"color: {TIER_COLOR.get(v, '#9CA3AF')}", subset=["评级"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    for r in day_rows:
        label = render.stock_label(r["stock_code"], r["stock_name"])
        detail = r.get("detail") or {}
        tier = _tier(r)
        focus = detail.get("focus_type", "")
        with st.expander(f"#{r.get('rank', '-')} {label}　{TIER_ICON.get(tier, '')}"
                         f"{TIER_LABEL.get(tier, '未评级')}"
                         + (f"　[{focus}]" if focus else "")):
            render.time_text("本轮挖掘执行时间", r.get("created_at"))

            st.markdown("**候选理由**")
            for i, reason in enumerate(r.get("reasons") or [], 1):
                st.markdown(f"{i}. {reason}")

            st.markdown("**技术面研判**（威科夫/量价/K线形态/谐波交叉验证，含体系支撑依据）")
            st.markdown(detail.get("tech_view") or detail.get("meso_view") or "（该轮未输出，可重新触发挖掘生成）")

            st.markdown("**量价与资金结论**（主力动向/量能结构）")
            st.markdown(detail.get("volume_analysis") or "（无）")

            st.markdown("**关键价位**（支撑位/压力位/建议关注区间）")
            st.markdown(detail.get("price_levels") or "（未输出）")

            st.markdown("**核心风险点**（≥2 项）")
            risks = detail.get("risks") or []
            if risks:
                for i, risk in enumerate(risks, 1):
                    st.markdown(f"{i}. {risk}")
            else:
                st.markdown("（无）")

            st.markdown("**操作建议**（关注类型 + 参考仓位）")
            hint = detail.get("position_hint") or ""
            st.markdown(f"- 关注类型：{focus or '观察'}")
            st.markdown(f"- 参考建议：{hint}" if hint else "- 参考建议：（该轮未输出）")

            with st.expander("三维分析（宏观/中观/微观）", expanded=False):
                st.markdown(f"- 宏观：{detail.get('macro_view', '（无）')}")
                st.markdown(f"- 中观：{detail.get('meso_view', '（无）')}")
                st.markdown(f"- 微观：{detail.get('micro_view', '（无）')}")
            st.markdown("**风险初判**")
            risk_notice = r.get("risk_notice") or []
            if risk_notice:
                for risk in risk_notice:
                    st.markdown(f"- {risk}")
            else:
                st.markdown("（无）")

            code, name = r["stock_code"], r["stock_name"]
            if st.button("生成建仓方案", key=f"plan_{code}_{r['trade_date']}"):
                api.submit_task("position", {"stock_code": code, "stock_name": name})
                st.toast("建仓方案生成任务已提交后台，可切换页面继续操作")
            render.raw_json_expander(
                {"reasons": r.get("reasons"), "risk_notice": r.get("risk_notice"),
                 "detail": detail},
                key=f"raw_cand_{code}_{r['trade_date']}")
except Exception as exc:
    st.error(f"候选池获取失败: {exc}")
