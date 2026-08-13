# -*- coding: utf-8 -*-
"""探测4：同花顺行业指数/新浪美股快照/美股历史 备选接口"""
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
        out[name] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:160]}"}

for n in ["stock_board_industry_index_ths", "stock_board_industry_name_ths",
          "stock_us_spot", "stock_us_hist", "stock_sector_detail"]:
    sig(n)

# 同花顺行业指数历史（半导体）
probe("ths_index_hist", lambda: ak.stock_board_industry_index_ths(
    symbol="半导体", start_date="20260101", end_date="20260813"))
# 新浪美股实时快照（含涨跌幅）
probe("us_spot_sina", lambda: ak.stock_us_spot())
# 美股历史（看数据源）
probe("us_hist", lambda: ak.stock_us_hist(symbol="105.NVDA", period="daily",
      start_date="20260101", end_date="20260813", adjust=""))
# 同花顺行业板块名称
probe("ths_board_name", lambda: ak.stock_board_industry_name_ths())
# 新浪板块明细（半导体，某日）—— 可能用于成分股兜底，先看结构
probe("sector_detail", lambda: ak.stock_sector_detail(symbol="半导体", date="20260813"))

with open("../scripts/_probe_ak_out4.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1, default=str)
print("DONE")
