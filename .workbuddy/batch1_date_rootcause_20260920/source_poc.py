import time, json, os, re
import requests
OUT = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
out = []
HDR = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
# A. 新浪日线历史：单请求多 symbol
for syms in (["sh600519"], ["sh600519", "sz000001"], ["sh600519", "sz000001", "sh601318"]):
    url = "https://hq.sinajs.cn/list=" + ",".join(syms)
    t0 = time.perf_counter()
    try:
        r = requests.get(url, headers=HDR, timeout=15)
        txt = r.content.decode("gbk", "replace")
        rows = len([l for l in txt.splitlines() if '="' in l])
        out.append("SINA hq list=%d -> http=%s rows=%d %.2fs bytes=%d" % (len(syms), r.status_code, rows, time.perf_counter()-t0, len(r.content)))
    except Exception as e:
        out.append("SINA hq list=%d EXC %s: %s" % (len(syms), type(e).__name__, str(e)[:120]))
# B. 新浪历史日线（klc_kl.js）单票 + 多票试探
base = "https://finance.sina.com.cn/realstock/company/%s/hisdata/klc_kl.js"
for sym in ("sh600519", "sz000001"):
    t0 = time.perf_counter()
    try:
        r = requests.get(base % sym, headers=HDR, timeout=20)
        txt = r.content.decode("gbk", "replace")
        m = re.search(r"\[(.*)\]", txt, re.S)
        n = len(m.group(1).split("],[")) if m else 0
        out.append("SINA klc_kl %s -> http=%s bars~%d %.2fs bytes=%d" % (sym, r.status_code, n, time.perf_counter()-t0, len(r.content)))
    except Exception as e:
        out.append("SINA klc_kl %s EXC %s: %s" % (sym, type(e).__name__, str(e)[:120]))
# C. 腾讯 K 线接口：250+ 根历史，多票试探
def tx(sym, n=320):
    u = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=%s,day,,,%d,qfq" % (sym, n))
    t0 = time.perf_counter()
    r = requests.get(u, headers={"User-Agent": HDR["User-Agent"]}, timeout=20)
    j = r.json()
    d = (j.get("data") or {}).get(sym) or {}
    arr = d.get("qfqday") or d.get("day") or []
    return r.status_code, len(arr), round(time.perf_counter()-t0, 2), (arr[:1], arr[-1:] if arr else [])
for sym in ("sh600519", "sz000001", "bj920001"):
    try:
        st, n, sec, sample = tx(sym)
        out.append("TENCENT fqkline %s -> http=%s bars=%d %.2fs first=%s last=%s" % (sym, st, n, sec, sample[0], sample[1]))
    except Exception as e:
        out.append("TENCENT fqkline %s EXC %s: %s" % (sym, type(e).__name__, str(e)[:140]))
# C2. 腾讯是否支持一次多票
for syms in (2, 5):
    many = ",".join(["sh6005%02d" % (19 + i) for i in range(syms)])
    try:
        st, n, sec, sample = tx("sh600519")
        out.append("TENCENT multi-probe(%d syms) skipped (接口 param 单票) ; 单票基准 bars=%d" % (syms, n))
        break
    except Exception as e:
        out.append("TENCENT multi-probe EXC %s" % type(e).__name__)
open(os.path.join(OUT, "_step_l_source_poc.txt"), "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))