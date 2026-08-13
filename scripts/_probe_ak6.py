# -*- coding: utf-8 -*-
"""探测5：新浪指数快照成分/新浪指数日线/新浪行业板块名与指数名映射（轻量）"""
import json
import akshare as ak

out = {}

try:
    df = ak.stock_zh_index_spot_sina()
    sub = df[df["代码"].isin(["sh000001", "sz399001", "sz399006"])]
    out["main_idx"] = sub.to_dict(orient="records")
    # 看行业类指数名（代码含 98 开头）
    sec = df[df["代码"].str.startswith("sz98")]
    out["sector_idx_n"] = len(sec)
    out["sector_idx_sample"] = sec[["代码", "名称"]].head(20).to_dict(orient="records")
    out["all_idx_names_sample"] = df[["代码", "名称"]].head(10).to_dict(orient="records")
except Exception as e:
    out["idx_spot_sina"] = f"ERR {type(e).__name__}: {str(e)[:120]}"

# 新浪指数日线（sh000001 / sz399001）—— 看是否含成交额/成交量、最新日期
try:
    d1 = ak.stock_zh_index_daily(symbol="sh000001")
    out["sh_daily_cols"] = list(d1.columns)
    out["sh_daily_tail"] = d1.tail(2).to_dict(orient="records")
except Exception as e:
    out["sh_daily"] = f"ERR {type(e).__name__}: {str(e)[:120]}"
try:
    d2 = ak.stock_zh_index_daily(symbol="sz399001")
    out["sz_daily_tail"] = d2.tail(2).to_dict(orient="records")
except Exception as e:
    out["sz_daily"] = f"ERR {type(e).__name__}: {str(e)[:120]}"

# 新浪行业板块名称（fetch_industry_spot 的 sina 降级源）
try:
    sp = ak.stock_sector_spot(indicator="新浪行业")
    out["sector_names"] = sp["板块"].tolist()
except Exception as e:
    out["sector_spot"] = f"ERR {type(e).__name__}: {str(e)[:120]}"

with open("../scripts/_probe_ak_out5.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1, default=str)
print("DONE")
