"""交易知识库：私有交易经验/战法管理（统一调教接口·知识注入）

顶部操作区用 Tab 划分二级功能（新增条目/批量导入），知识条目列表用企业级行范式：
左=信息色圆点+标题(加粗)+适用 Agent·创建时间(副标题)，右=创建时间+「查看详情」；
详情分区展示正文全文与删除操作。各 Agent 每次启动任务自动检索对应标签的知识注入
研判上下文；保存/删除立即生效（知识版本号使 LLM 缓存自动失效），无需重启。
"""
import streamlit as st

import api_client as api
import render

render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

# ===== 批次3：页面头部收敛为 page_header 单行范式 =====
render.page_header(
    "交易知识库（统一调教·私有战法）",
    caption="私有交易经验/战法/心得：六个 Agent 每次启动任务自动检索对应标签知识注入研判上下文；"
            "保存/删除立即生效（版本号使 LLM 缓存自动失效），无需重启服务。",
)

# 统一后台任务状态区（运行中提示/失败重试，任务全部结束自动消失）
render.task_status_area()

AGENTS = ["all", "discover", "score", "position", "monitor", "sell", "review"]

tab_add, tab_batch, tab_list = st.tabs(["新增条目", "批量导入", "知识条目"])

# ================= Tab 1：新增知识 =================
with tab_add:
    with st.form("add_knowledge"):
        c1, c2 = st.columns([3, 1])
        with c1:
            with st.container(key="fld_kb_title"):
                title = st.text_input("标题 *", placeholder="如：放量突破战法的确认条件")
            # 标题必填：原位标红 + 填写指引，不整段报错
            render.field_error("kb_title", render.get_field_error("kb_title"),
                               "标题不能为空，一句话概括本条知识")
        with c2:
            agent_tag = st.selectbox("适用 Agent *", AGENTS,
                                     help="all=全部 Agent 通用；其余=仅对应 Agent 检索注入")
        with st.container(key="fld_kb_content"):
            content = st.text_area("正文 *（你的经验/战法/心得，可多行）",
                                   placeholder="如：放量突破必须满足 ①换手率 5%-15% ②突破前缩量整理 ③...")
        render.field_error("kb_content", render.get_field_error("kb_content"),
                           "正文不能为空，请填写你的经验/战法/心得")
        render.field_summary(label_map={"kb_title": "标题", "kb_content": "正文"})
        submitted = st.form_submit_button("保存（立即生效）", type="primary")
        if submitted:
            errs = {}
            if not title.strip():
                errs["kb_title"] = "标题不能为空"
            if not content.strip():
                errs["kb_content"] = "正文不能为空"
            if errs:
                render.set_field_errors(errs)
            else:
                render.set_field_errors({})
                result = api.add_knowledge(title.strip(), content.strip(), agent_tag)
                st.success(f"已保存（ID={result['id']}），对应 Agent 下次任务自动注入。")

# ================= Tab 2：批量导入（异步提交） =================
with tab_batch:
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
        batch_submitted = st.form_submit_button("批量导入（异步执行）", type="primary")
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
                render.msg_card("warn", "未解析出有效条目",
                                "每条需至少包含标题行 + 正文行，且以空行分隔，可修改后重新导入。")
            else:
                result = api.batch_import_knowledge(items)
                st.success(f"已提交 {len(items)} 条知识批量导入任务（{result.get('task_id')}），"
                           "完成后顶部任务状态区会提示，无需等待本页刷新")

# ================= Tab 3：知识条目列表 =================
with tab_list:
    try:
        rows = api.knowledge()
        if not rows:
            render.empty_state("暂无知识条目。写入第一条战法后，各 Agent 即可自动引用。")
        else:
            filter_tag = st.selectbox("按适用 Agent 过滤", ["全部"] + AGENTS, key="_kb_filter")
            if filter_tag != "全部":
                rows = [r for r in rows if r["agent_tag"] == filter_tag]
            with render.fold_module(
                    "kb_list", "知识条目",
                    meta=f"共 {len(rows)} 条 · 保存/删除立即生效",
                    default_open=True,
                    batch=("kb", [f"kb_{r['id']}" for r in rows]) if rows else None):
                if not rows:
                    render.empty_state("当前过滤条件下无匹配条目。", icon="🔍")
                else:
                    def _kb_detail(r: dict, _i: int) -> None:
                        key = f"kb_{r['id']}"
                        if render.list_item_toggle(key, r["title"],
                                                   subtitle=f"适用 {r['agent_tag']} · "
                                                            f"{str(r.get('created_at') or '')[:16]}",
                                                   dot="info", meta=str(r.get("created_at") or "")[:16],
                                                   scope="kb"):
                            with st.container(border=True):
                                render.trace_line("创建时间", r.get("created_at"))
                                with st.container(border=True):
                                    render.section_title("知识正文")
                                    st.markdown(r["content"])
                                if st.button("删除该条目", key=f"del_{r['id']}"):
                                    api.delete_knowledge(r["id"])
                                    st.success("已删除，对应 Agent 的缓存将自动失效。")
                                    st.rerun()

                    render.record_list(rows, _kb_detail, batch=20, key=f"_kb_list_vis_{filter_tag}",
                                       empty_text="无匹配的知识条目。")
    except Exception as exc:
        render.dismissible_error("知识库读取失败", "请确认后端服务运行正常后点击「重试」刷新。",
                                 detail=exc, retry_key="retry_kb", dismiss_key="kb_list")
