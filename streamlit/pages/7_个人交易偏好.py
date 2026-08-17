"""个人交易偏好档案：可视化编辑 + 导出/导入 JSON
保存立即生效（偏好版本号使 LLM 缓存自动失效），无需重启后端。
所有 Agent 调用 LLM 时自动注入这些偏好作为研判约束。
"""
import json

import streamlit as st

import api_client as api
import render

st.set_page_config(page_title="个人交易偏好", layout="wide")

# 全局深色科技感主题（卡片/徽章/溯源/数字等宽，全站唯一视觉体系）
render.apply_global_theme()

# 全局顶部常驻信息栏（北京时间/账户资产/三大指数，固定显示不随滚动消失）
render.top_status_bar()

# ===== 批次3：页面头部收敛为 page_header 单行范式 =====
render.page_header(
    "个人交易偏好档案（sys_trade_profile）",
    caption="偏好会在所有 Agent 调用 LLM 时自动注入研判上下文。保存立即生效，无需重启。"
            "字段可自由增删，支持导出/导入 JSON 备份迁移。",
)

try:
    profile = api.get_profile()
    content = dict(profile["content"])
    version = profile["version"]
except Exception as exc:
    render.error_card("偏好档案获取失败", "请确认后端服务运行正常后点击「重试」刷新。",
                      detail=exc, retry_key="retry_profile")
    st.stop()

st.markdown(f"当前版本：**v{version}**")

# ---------- 编辑表单 ----------
st.subheader("编辑偏好")
with st.form("profile_form"):
    field_names = list(content.keys())
    edited: dict = {}

    # 文本字段与数字字段通用渲染
    for i, key in enumerate(field_names):
        value = content[key]
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            edited[key] = st.number_input(key, value=float(value), step=1.0, key=f"num_{i}")
        elif isinstance(value, dict):
            edited[key] = st.text_area(key, value=json.dumps(value, ensure_ascii=False),
                                       key=f"dict_{i}")
        elif isinstance(value, list):
            edited[key] = st.text_area(key, value=json.dumps(value, ensure_ascii=False),
                                       key=f"list_{i}")
        else:
            edited[key] = st.text_input(key, value=str(value), key=f"str_{i}")

    st.markdown("**新增字段**（字段名:值，可留空）")
    new_field = st.text_input("新增字段名", key="new_key")
    new_value = st.text_input("新增字段值", key="new_val")

    submitted = st.form_submit_button("保存偏好（立即生效）")
    if submitted:
        final = {}
        for k, v in edited.items():
            if isinstance(v, str):
                # 尝试解析 JSON 结构（列表/字典）
                stripped = v.strip()
                try:
                    final[k] = json.loads(stripped)
                except json.JSONDecodeError:
                    final[k] = stripped
            else:
                final[k] = v
        if new_field.strip():
            try:
                final[new_field.strip()] = json.loads(new_value.strip())
            except json.JSONDecodeError:
                final[new_field.strip()] = new_value.strip()
        result = api.put_profile(final)
        st.success(f"已保存，版本 v{result['version']}（LLM 缓存已自动失效）")

# ---------- 导出 / 导入 ----------
st.subheader("导出 / 导入")
c1, c2 = st.columns(2)
with c1:
    if st.button("导出偏好 JSON（下载备份）"):
        data = api.export_profile()
        st.download_button("下载 JSON", json.dumps(data, ensure_ascii=False, indent=2),
                           file_name="trade_profile.json", mime="application/json")
with c2:
    uploaded = st.file_uploader("导入偏好 JSON（跨环境迁移）", type=["json"])
    if uploaded is not None:
        try:
            data = json.loads(uploaded.read().decode("utf-8"))
            if "content" not in data:
                render.msg_card("warn", "导入文件格式不符",
                                "JSON 需包含 content 字段（可由本页导出文件生成），请核对后重新上传。")
            else:
                result = api.import_profile(data["content"])
                st.success(f"导入成功，版本 v{result['version']}")
        except Exception as exc:
            render.msg_card("err", "导入失败", "未能导入该文件，请确认内容合法后重试。",
                            detail=exc)
