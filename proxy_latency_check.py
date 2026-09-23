"""数据源延迟归因：隔离「本机代理」vs「源本身慢」（只读、零副作用）

动机：09-18 生产跑实测 284 只 / 625s（8 并发 → 有效 ~17.6s/只），DSH 三轮测得中位 15–27s/只。
两者量级一致，但 DSH 的异常原文里出现
  HTTPSConnection(host='127.0.0.1', port=7897)  ← 数据源请求走了本机代理
故必须先判定：15s 是「代理绕路」造成，还是「源本身慢」。若是代理，则解法是 bypass，而不是把预算提 32×。

用法: D:/self/.venv/Scripts/python.exe D:/self/proxy_latency_check.py
"""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

import requests  # noqa: E402

URLS = [
    ("新浪日线(备用源, DSH异常原文同路径)",
     "https://finance.sina.com.cn/realstock/company/sh600519/hisdata_klc2/klc_kl.js"),
    ("东财日线(主源 push2his)",
     "https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.600519"
     "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57"
     "&klt=101&fqt=1&end=20500101&lmt=5"),
    ("新浪 hq 基线(已知可通)",
     "https://hq.sinajs.cn/list=sh600519"),
]
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
       "Referer": "https://finance.sina.com.cn/"}

print("== 代理相关环境变量 ==")
found = {k: v for k, v in os.environ.items() if "proxy" in k.lower()}
print("  ", found or "<none>")
print("== requests 自动探测到的代理 ==")
print("  ", requests.utils.getproxies())

N = 3
for name, url in URLS:
    for mode in ("经代理(默认)", "直连(trust_env=False)"):
        s = requests.Session()
        s.trust_env = mode.startswith("直连")
        samples, err = [], None
        for _ in range(N):
            t = time.time()
            try:
                r = s.get(url, headers=HDR, timeout=30)
                samples.append((time.time() - t) * 1000)
            except Exception as exc:  # noqa: BLE001
                err = "%s: %s" % (type(exc).__name__, str(exc)[:110])
                break
        if samples:
            samples.sort()
            print("[%s] %-34s %s  ms=%s"
                  % (mode, name, ("n=%d" % len(samples)), [round(x) for x in samples]))
        else:
            print("[%s] %-34s FAIL %s" % (mode, name, err))
