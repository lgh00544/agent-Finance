# -*- coding: utf-8 -*-
"""实际调用探测：美股快照 / 美股指数 / 板块历史 / 指数快照（结果写入 UTF-8 文件，避免控制台 GBK 乱码）"""
import json
import inspect

import akshare as ak

out = {}

# 1) 板块历史接口签名
try:
    sig = inspect.signature(ak.stock_board_industry_hist_em)
    out["board_hist_sig"] = str(sig)
except Exception as e:
    out["board_hist_sig"] = f"ERR {e}"

# 2) 美股指数（新浪）
try:
    df = ak.index_us_stock_sina()
    out["us_index_cols"] = list(df.columns)
    out["us_index_n"] = len(df)
    out["us_index_head"] = df.head(8).to_dict(orient="records")
except Exception as e:
    out["us_index"] = f"ERR {type(e).__name__}: {e}"

# 3) 美股个股实时快照（东财）
try:
    df2 = ak.stock_us_spot_em()
    out["us_spot_cols"] = list(df2.columns)
    out["us_spot_n"] = len(df2)
    out["us_spot_head"] = df2.head(3).to_dict(orient="records")
except Exception as e:
    out["us_spot"] = f"ERR {type(e).__name__}: {e}"

# 4) 东财指数快照（上证+深证），用于两市成交额
try:
    df3 = ak.stock_zh_index_spot_em(symbol="上证系列指数")
    out["sh_index_cols"] = list(df3.columns)
    out["sh_index_head"] = df3.head(5).to_dict(orient="records")
except Exception as e:
    out["sh_index"] = f"ERR {type(e).__name__}: {e}"

with open("../scripts/_probe_ak_out.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1, default=str)
print("DONE")
