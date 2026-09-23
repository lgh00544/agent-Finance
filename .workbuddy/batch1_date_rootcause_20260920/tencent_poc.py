import time, json, os, sys, statistics
sys.path.insert(0, r"D:\self\backend")
import requests
from concurrent.futures import ThreadPoolExecutor
OUT = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
out = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
def tx(sym, n=320):
    u = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,qfq" % (sym, n)
    r = requests.get(u, headers=UA, timeout=20)
    j = r.json()
    d = (j.get("data") or {}).get(sym) or {}
    arr = d.get("qfqday") or d.get("day") or []
    return arr
# 1) 质量对账：腾讯 qfq vs 本项目 fetch_daily_kline（新浪/东财链）逐日收盘
from app.datasource.fallback import get_datasource
src = get_datasource()
CODES = ["600519", "000001", "601318"]
out.append("=== 质量对账（沪深主板各 1-2 只，close 相对偏差）===")
for code in CODES:
    sym = ("sh" if code.startswith("6") else "sz") + code
    try:
        t = {str(r[0]): float(r[2]) for r in tx(sym)}
    except Exception as e:
        out.append("  %s tx EXC %s" % (code, type(e).__name__)); continue
    df = src.fetch_daily_kline(code, "2025-07-25", "2026-09-18")
    a = {str(r["date"])[:10]: float(r["close"]) for _, r in df.iterrows()}
    common = sorted(set(t) & set(a))[-60:]
    diffs = [abs(t[d] - a[d]) / a[d] * 100 for d in common if a[d]]
    if diffs:
        out.append("  %s 共同交易日=%d 相对偏差 中位=%.4f%% 最大=%.4f%%" % (code, len(common), statistics.median(diffs), max(diffs)))
    else:
        out.append("  %s 无共同交易日" % code)
# 2) 吞吐：20 只 × 8 并发
CODES20 = ["600519","000001","601318","600036","000002","601398","600030","000063","601888","600276",
           "002415","300750","600887","000858","601166","600028","601288","000651","600585","002594"]
def one(c):
    sym = ("sh" if c.startswith("6") else ("bj" if c.startswith(("4","8","9")) else "sz")) + c
    t0 = time.perf_counter()
    try:
        arr = tx(sym); return c, len(arr), round(time.perf_counter()-t0, 2), ""
    except Exception as e:
        return c, 0, round(time.perf_counter()-t0, 2), type(e).__name__
t0 = time.perf_counter()
with ThreadPoolExecutor(max_workers=8) as p:
    res = list(p.map(one, CODES20))
wall = time.perf_counter() - t0
ok = [r for r in res if r[1] >= 250]
out.append("")
out.append("=== 吞吐（8 并发 × %d 只）===" % len(CODES20))
out.append("  wall=%.1fs  成功(>=250根)=%d/%d  等效吞吐=%.2f 只/s" % (wall, len(ok), len(res), len(res)/wall))
out.append("  根数分布=%s" % sorted(r[1] for r in res))
out.append("  单只耗时 中位=%.2fs 最大=%.2fs" % (statistics.median([r[2] for r in res]), max(r[2] for r in res)))
out.append("  失败=%s" % [r[0] for r in res if r[3]])
out.append("  推算：5564 只 / %.2f 只/s = %.1f 分钟（8 并发）" % (len(res)/wall, 5564/(len(res)/wall)/60))
open(os.path.join(OUT, "_step_m_tencent_quality.txt"), "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))