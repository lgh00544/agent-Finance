import sys, requests, pandas as pd, statistics
sys.path.insert(0, r"D:\self\backend")
from app.datasource.fallback import get_datasource
from concurrent.futures import ThreadPoolExecutor
ua = {"User-Agent": "Mozilla/5.0"}
def txf(code, n=420):
    sym = ("sh" if code.startswith("6") else ("bj" if code.startswith(("4","8","9")) else "sz")) + code
    u = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,qfq" % (sym, n)
    try:
        d = (requests.get(u, headers=ua, timeout=20).json().get("data") or {}).get(sym) or {}
        return code, d.get("qfqday") or d.get("day") or [], None
    except Exception as e:
        return code, [], type(e).__name__
CODES = ["600519","000001","601318","600036","000002","601398","600030","000063","601888","600276",
         "002415","300750","600887","000858","601166","600028","601288","000651","600585","002594",
         "600050","601857","600900","000333","002304","600048","601628","300059","002142","600438"]
src = get_datasource()
rows = []
with ThreadPoolExecutor(max_workers=8) as p:
    tx_res = {c: arr for c, arr, err in p.map(lambda c: txf(c), CODES)}
for code in CODES:
    arr = tx_res.get(code) or []
    if len(arr) < 250:
        rows.append((code, -1, -1, len(arr))); continue
    t = {str(x[0])[:10]: float(x[2]) for x in arr if len(x) >= 6}
    try:
        a = src.fetch_daily_kline(code, "2025-07-25", "2026-09-18").copy()
        a["date"] = a["date"].astype(str).str.slice(0, 10)
        am = {r["date"]: float(r["close"]) for _, r in a.iterrows()}
    except Exception:
        rows.append((code, -2, -2, len(t))); continue
    common = sorted(set(t) & set(am))
    if not common:
        rows.append((code, -3, -3, len(t))); continue
    devs = [abs(t[d]-am[d])/am[d]*100 for d in common if am[d]]
    rows.append((code, statistics.median(devs), max(devs), len(common)))
ok = [r for r in rows if r[1] >= 0]
med = sorted(r[1] for r in ok)
print("样本=%d 可对账=%d" % (len(rows), len(ok)))
print("全窗口 close 偏差：中位=%.4f%%  p90=%.4f%%  最大=%.4f%%" % (statistics.median(med), med[int(0.9*(len(med)-1))], med[-1]))
print("偏差>1%% 的只数=%d/%d   >0.5%% 的只数=%d" % (sum(1 for r in ok if r[1] > 1), len(ok), sum(1 for r in ok if r[1] > 0.5)))
print("明细（偏差降序 top10）:")
for r in sorted(ok, key=lambda x: -x[1])[:10]:
    print("  %s 中位=%.4f%% 最大=%.4f%% 共同日=%d" % r)