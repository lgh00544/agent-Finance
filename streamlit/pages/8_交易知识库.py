"""交易知识库：私有交易经验/战法管理（统一调教接口·知识注入）
各 Agent 每次启动任务时自动检索本库对应 agent_tag 的资料注入研判上下文，
保存/删除立即生效（知识版本号使 LLM 缓存自动失效），无需重启。
"""
import pandas as pd
import streamlit as st

import api_client as api
import render

st.set_page_config(page_title="交易知识库", layout="wide")

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

st.title("交易知识库（统一调教·私有战法）")

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

st.caption("这里存放你的私有交易经验、战法、心得。六个 Agent（挖掘/评分/建仓/监控/卖出/复盘）"
           "每次启动任务都会自动检索对应标签的知识注入研判上下文；"
           "保存/删除立即生效（版本号使 LLM 缓存自动失效），无需重启服务。")

AGENTS = ["all", "discover", "score", "position", "monitor", "sell", "review"]

# ================= 新增知识 =================
st.subheader("新增知识条目")
with st.form("add_knowledge"):
    c1, c2 = st.columns([3, 1])
    with c1:
        title = st.text_input("标题 *", placeholder="如：放量突破战法的确认条件")
    with c2:
        agent_tag = st.selectbox("适用 Agent *", AGENTS,
                                 help="all=全部 Agent 通用；其余=仅对应 Agent 检索注入")
    content = st.text_area("正文 *（你的经验/战法/心得，可多行）",
                           placeholder="如：放量突破必须满足 ①换手率 5%-15% ②突破前缩量整理 ③...")
    submitted = st.form_submit_button("保存（立即生效）")
    if submitted:
        if not title.strip() or not content.strip():
            st.error("标题与正文为必填")
        else:
            result = api.add_knowledge(title.strip(), content.strip(), agent_tag)
            st.success(f"已保存（ID={result['id']}），对应 Agent 下次任务自动注入。")

st.divider()

# ================= 批量导入（异步提交） =================
st.subheader("批量导入知识")
with st.form("batch_knowledge"):
    batch_tag = st.selectbox("批量适用 Agent", AGENTS, key="batch_tag",
                             help="全部条目统一应用此标签，导入后可在列表里逐条修改")
    batch_text = st.text_area(
        "粘贴文本（空行分隔多条；每条第一行为标题，其余行为正文）",
        height=160,
        placeholder=("例如：\n"
                     "放量突破战法确认条件\n"
                     "①换手率 5%-15% ②突破前缩量整理 ③板块共振\n"
                     "\n"
                     "止损纪律\n"
                     "买入后跌破关键支撑位无条件离场，不补仓摊薄成本"))
    batch_submitted = st.form_submit_button("批量导入（异步执行）")
    if batch_submitted:
        items = []
        for block in (batch_text or "").splitlines():
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()
            title = lines[0].strip()
            content = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            if title and content:
                items.append({"title": title, "content": content, "agent_tag": batch_tag})
        if not items:
            st.error("未解析出有效条目：每条需至少包含标题行 + 正文行，且以空行分隔")
        else:
            result = api.batch_import_knowledge(items)
            st.success(f"已提交 {len(items)} 条知识批量导入任务（{result.get('task_id')}），"
                       "完成后顶部任务状态区会提示，无需等待本页刷新")

st.divider()

# ================= 知识列表 =================
st.subheader("知识条目")
try:
    rows = api.knowledge()
    if not rows:
        st.info("暂无知识条目。写入第一条战法后，各 Agent 即可自动引用。")
    else:
        filter_tag = st.selectbox("按适用 Agent 过滤", ["全部"] + AGENTS)
        if filter_tag != "全部":
            rows = [r for r in rows if r["agent_tag"] == filter_tag]

        df = pd.DataFrame([{
            "ID": r["id"], "标题": r["title"], "适用Agent": r["agent_tag"],
            "创建时间": r["created_at"][:16],
        } for r in rows])
        st.dataframe(df, width="stretch", hide_index=True)

        for r in rows:
            with st.expander(f"{r['title']}（适用 {r['agent_tag']}，{r['created_at'][:16]}）"):
                st.markdown(r["content"])
                if st.button("删除该条目", key=f"del_{r['id']}"):
                    api.delete_knowledge(r["id"])
                    st.success("已删除，对应 Agent 的缓存将自动失效。")
                    st.rerun()
except Exception as exc:
    st.error(f"知识库读取失败: {exc}")
