# -*- coding: utf-8 -*-
"""探测6：项目 http_client 访问东财 vs 新浪（判断代理层拦截范围）"""
import json
import sys

sys.path.insert(0, ".")
from app.datasource.http_client import get as http_get

out = {}

urls = {
    "eastmoney_kline": ("https://push2his.eastmoney.com/api/qt/stock/kline/get",
                        {"secid": "1.000001", "fields1": "f1,f2,f3", "fields2": "f51,f52,f53",
                         "klt": "101", "fqt": "0", "beg": "20260801", "end": "20260813"}),
    "eastmoney_spot": ("https://82.push2.eastmoney.com/api/qt/clist/get",
                       {"pn": 1, "pz": 5, "po": 1, "np": 1, "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                        "fltt": 2, "invt": 2, "fid": "f3", "fs": "m:1 t:1", "fields": "f1,f2,f3,f12,f14"}),
    "sina_spot": ("https://hq.sinajs.cn/list=sh000001",
                  {}),
}

for name, (url, params) in urls.items():
    try:
        resp = http_get(url, referer="eastmoney" if "eastmoney" in url else "sina",
                        params=params, timeout=(5, 15))
        out[name] = {"status": resp.status_code, "len": len(resp.text),
                     "head": resp.text[:120]}
    except Exception as e:
        out[name] = {"err": f"{type(e).__name__}: {str(e)[:140]}"}

with open("../scripts/_probe_http_out.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1, default=str)
print("DONE")
