import sys, os, time
sys.path.insert(0, r"D:\self\backend")
import akshare as ak
out = []
for name, fn in (("stock_zh_a_spot(sina)", lambda: ak.stock_zh_a_spot()),
                 ("stock_zh_a_spot_em(em)", lambda: ak.stock_zh_a_spot_em())):
    for i in (1, 2):
        t0 = time.time()
        try:
            df = fn()
            out.append("%s try%d OK rows=%s %.1fs" % (name, i, len(df), time.time()-t0))
            break
        except Exception as e:
            out.append("%s try%d EXC %s: %s" % (name, i, type(e).__name__, str(e)[:90]))
            time.sleep(8)
# 直取腾讯实时快照（另一条可用链路）作为股票池
try:
    import requests
    r = requests.get("http://qt.gtimg.cn/q=sh600519", timeout=10)
    out.append("tencent quote http=%s bytes=%d" % (r.status_code, len(r.content)))
except Exception as e:
    out.append("tencent quote EXC %s" % type(e).__name__)
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_source_health.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))