# -*- coding: utf-8 -*-
"""探测2：确认 index_us_stock_sina 签名 + 各东财接口实际可用性"""
import json
import inspect

import akshare as ak

out = {}

try:
    out["index_us_sig"] = str(inspect.signature(ak.index_us_stock_sina))
except Exception as e:
    out["index_us_sig"] = f"ERR {e}"

def probe(name, fn):
    try:
        df = fn()
        cols = list(df.columns)
        n = len(df)
        head = df.tail(3).to_dict(orient="records") if n else []
        out[name] = {"ok": True, "cols": cols, "n": n, "tail": head}
    except Exception as e:
        out[name] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:160]}"}

# 新浪美股指数（不传参看默认返回什么）
probe("us_sina_default", lambda: ak.index_us_stock_sina())
# 东财板块历史
probe("board_hist", lambda: ak.stock_board_industry_hist_em(
    symbol="半导体", period="日k", start_date="20260501", end_date="20260813", adjust=""))
# 东财板块名称（行业板块表）
probe("board_name_em", lambda: ak.stock_board_industry_name_em())
# 东财大盘日线
probe("index_daily_em", lambda: ak.stock_zh_index_daily_em(
    symbol="sh000001", start_date="20260701", end_date="20260813"))
# 东财全A快照
probe("spot_em", lambda: ak.stock_zh_a_spot_em())

with open("../scripts/_probe_ak_out2.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1, default=str)
print("DONE")
