"""交易知识库：私有交易经验/战法管理（统一调教接口·知识注入）
各 Agent 每次启动任务时自动检索本库对应 agent_tag 的资料注入研判上下文，
保存/删除立即生效（知识版本号使 LLM 缓存自动失效），无需重启。
"""
import pandas as pd
import streamlit as st

import api_client as api

st.set_page_config(page_title="交易知识库", layout="wide")
st.title("交易知识库（统一调教·私有战法）")

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
