# 概览页模块 fragment 化（幂等）：每次运行先还原 .bak，再重新包裹。
# 支持单行/多行 fold_module 调用；ov_sectors（内部已有 fragment）除外；
# 模块1 在全局批量区（_m1 列行）前结束，批量区保留在页面级。
import io
import re
import shutil

P = r"D:\space\self\self\streamlit\pages\0_系统概览.py"
BAK = P + ".bak"

# 0) 幂等：先还原备份（首次运行创建备份，之后以备份为干净源）
if shutil.os.path.exists(BAK):
    shutil.copyfile(BAK, P)
else:
    shutil.copyfile(P, BAK)

src = io.open(P, encoding="utf-8").read()
lines = src.split("\n")

tab_idx = next(i for i, l in enumerate(lines) if l.startswith("with tab_overview:"))
# 单行：with render.fold_module("ov_x", ...)；多行：with render.fold_module(
mod_re = re.compile(r'^    with render\.fold_module\(')
NAME_RE = re.compile(r'"ov_(\w+)"')
EXCLUDE = {"sectors"}
FUNC = {
    "overview": "_module_overview",
    "market": "_module_market",
    "positions": "_module_positions",
    "alerts": "_module_alerts",
    "cands": "_module_cands",
    "reviews": "_module_reviews",
}
DOC = {
    "overview": "模块1：顶部数据概览组（5 张指标卡：候选/持仓/告警/盈亏/市况评分）",
    "market": "模块2：今日操作提示（市况五维，折叠后标题栏仍显示总分）",
    "positions": "模块3：持仓与操作建议（止盈仓位 4 模块卡片，与持仓监控页同源）",
    "alerts": "模块4：紧急告警日志（单条告警二级折叠项）",
    "cands": "模块6：今日候选与建仓机会",
    "reviews": "模块7：近期复盘动态",
}
# 页面级代码边界标记（扫描到即视为模块块结束）
PAGE_LEVEL = ("_m1, _m2, _m3 = st.columns",)


def block_name(lines, start):
    """从块起始两行内提取模块 scope 名"""
    for l in lines[start:start + 3]:
        m = NAME_RE.search(l)
        if m:
            return m.group(1)
    return None


# 1) 收集块区间
blocks = []
i = tab_idx + 1
while i < len(lines):
    if mod_re.match(lines[i]):
        name = block_name(lines, i)
        j = i + 1
        while j < len(lines):
            l = lines[j]
            if not l.strip():
                j += 1
                continue
            if any(mk in l for mk in PAGE_LEVEL):
                break
            if not l.startswith("    ") or (mod_re.match(l) and j != i):
                break
            j += 1
        blocks.append((name, i, j))
        i = j
    else:
        i += 1

# 2) 生成函数定义文本 + 调用替换
func_defs = []
repl = {}
for name, start, end in blocks:
    if name is None or name in EXCLUDE or name not in FUNC:
        continue
    body = [("    " + l) if l.strip() else l for l in lines[start:end]]
    fn = FUNC[name]
    doc = DOC.get(name, "")
    block = [
        "    @st.fragment",
        f"    def {fn}() -> None:",
        f'        """{doc}"""',
    ] + body
    func_defs.append("\n".join(block))
    repl[(start, end)] = f"    {fn}()"

# 3) 组装：函数定义插入 tab_overview 之后，原块替换为调用
out = lines[: tab_idx + 1]
out.append("    # ---- 一级模块（fragment 隔离：折叠/展开仅重跑自身模块，零网络请求） ----")
out.extend(func_defs)
out.append("")
i = tab_idx + 1
while i < len(lines):
    hit = None
    for (s, e), call in repl.items():
        if i == s:
            hit = (s, e, call)
            break
    if hit:
        out.append(hit[2])
        i = hit[1]
    else:
        out.append(lines[i])
        i += 1

io.open(P, "w", encoding="utf-8", newline="\n").write("\n".join(out))
print("blocks:", [(n, s, e) for n, s, e in blocks])
print("wrapped:", sorted(FUNC.keys()))
print("done")
