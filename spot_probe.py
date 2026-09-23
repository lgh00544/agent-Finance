"""spot 源原始可用性探针（只读、零副作用）：绕开 akshare 与断路器，直打 HTTP。

用途：判定 fetch_spot_universe 失败是「源真的挂了」还是「应用层断路器打开」。
用法: D:/self/.venv/Scripts/python.exe D:/self/spot_probe.py
"""
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import requests  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Referer": "https://quote.eastmoney.com/"}

TARGETS = [
    ("东财 push2 clist（spot_em 主源）",
     "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=5&po=1&np=1&fltt=2&invt=2"
     "&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
     "&fields=f2,f3,f12,f14", UA),
    ("新浪 Market_Center（spot 备源）",
     "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
     "Market_Center.getHQNodeData?page=1&num=5&sort=symbol&asc=1&node=hs_a&symbol=&_s_r_a=page", {}),
    ("新浪 hq 基线（已知可通）",
     "https://hq.sinajs.cn/list=sh600519", {"Referer": "https://finance.sina.com.cn"}),
]

for name, url, headers in TARGETS:
    t = time.time()
    try:
        r = requests.get(url, headers=headers, timeout=15)
        body = r.text[:160].replace("\n", " ")
        print("[%s] status=%s ct=%s len=%d elapsed=%.1fs"
              % (name, r.status_code, r.headers.get("Content-Type", "-"), len(r.text), time.time() - t))
        print("      head=%s" % body)
    except Exception as exc:  # noqa: BLE001
        print("[%s] EXC %s: %s (%.1fs)" % (name, type(exc).__name__, exc, time.time() - t))

print("== akshare 直调（绕开本项目断路器） ==")
try:
    import akshare as ak
    t = time.time()
    try:
        df = ak.stock_zh_a_spot()
        print("  ak.stock_zh_a_spot (新浪) OK rows=%d elapsed=%.1fs" % (len(df), time.time() - t))
    except Exception as exc:  # noqa: BLE001
        print("  ak.stock_zh_a_spot (新浪) FAIL %s: %s (%.1fs)" % (type(exc).__name__, exc, time.time() - t))
except Exception as exc:  # noqa: BLE001
    print("  akshare import FAIL:", exc)

print("== 本项目断路器状态 ==")
try:
    sys.path.insert(0, r"D:/self/backend")
    from app.datasource import breaker as brk  # noqa: E402
    for kind in ("snapshot", "spot_em", "kline"):
        try:
            b = brk.get_breaker(kind)
            print("  breaker %-9s = %s" % (kind, {k: v for k, v in vars(b).items() if not k.startswith("_")}))
        except Exception as exc:  # noqa: BLE001
            print("  breaker %-9s = <err> %s" % (kind, exc))
except Exception as exc:  # noqa: BLE001
    print("  breaker 模块读取失败:", exc)
