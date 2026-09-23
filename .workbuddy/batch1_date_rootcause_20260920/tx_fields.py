import requests, json
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
u = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600519,day,,,5,qfq"
j = requests.get(u, headers=UA, timeout=20).json()
d = j["data"]["sh600519"]
print("keys in data[sym]:", list(d.keys()))
for k, v in d.items():
    if isinstance(v, list):
        print("  %s: len=%d head=%s" % (k, len(v), v[:2]))
    elif isinstance(v, dict):
        print("  %s: dict keys=%s" % (k, list(v.keys())[:10]))
    else:
        print("  %s: %r" % (k, v))
print("--- 单根 bar 元素数 ---")
arr = d.get("qfqday") or d.get("day")
print("len(row)=%d row=%s" % (len(arr[0]), arr[0]))