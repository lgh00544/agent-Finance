# -*- coding: utf-8 -*-
"""探测3：新浪系备选接口可用性（美股个股/新浪指数快照/新浪板块历史）"""
import json
import inspect

import akshare as ak

out = {}

def sig(name):
    try:
        out[name + "_sig"] = str(inspect.signature(getattr(ak, name)))
    except Exception as e:
        out[name + "_sig"] = f"ERR {e}"

def probe(name, fn):
    try:
        df = fn()
        out[name] = {"ok": True, "cols": list(df.columns), "n": len(df),
                     "tail": df.tail(3).to_dict(orient="records")}
    except Exception as e:
        out[name] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:140]}"}

for n in ["stock_us_daily", "stock_us_zh_spot", "stock_zh_index_spot_sina",
          "stock_sector_spot", "stock_sector_hist", "index_us_stock_sina"]:
    sig(n)

# 新浪美股个股日线（需先确认 symbol 格式，用英伟达 NVDA）
probe("us_daily_nvda", lambda: ak.stock_us_daily(symbol="NVDA", adjust=""))
# 新浪美股中文快照（可能含代码/名称/涨跌幅）
probe("us_zh_spot", lambda: ak.stock_us_zh_spot())
# 新浪指数快照（看是否含成交额字段，两市量倍候选）
probe("idx_spot_sina", lambda: ak.stock_zh_index_spot_sina())
# 新浪行业板块快照
probe("sector_spot", lambda: ak.stock_sector_spot(indicator="新浪行业"))
# 新浪板块历史（半导体）
if hasattr(ak, "stock_sector_hist"):
    probe("sector_hist", lambda: ak.stock_sector_hist(symbol="半导体"))
# 美股指数：纳指 / 道指 / 标普
probe("us_ixic", lambda: ak.index_us_stock_sina(symbol=".IXIC"))
probe("us_dji", lambda: ak.index_us_stock_sina(symbol=".DJI"))

with open("../scripts/_probe_ak_out3.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1, default=str)
print("DONE")
