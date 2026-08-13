# -*- coding: utf-8 -*-
"""探针：确认 akshare 三个新方法所需接口是否存在（纯 ASCII 输出）"""
import akshare as ak

names = [
    "index_us_stock_sina",
    "stock_us_spot_em",
    "stock_us_daily",
    "stock_board_industry_hist_em",
    "stock_zh_index_spot_em",
    "stock_board_industry_name_em",
]
for n in names:
    print(n, "OK" if hasattr(ak, n) else "MISSING")

print("akshare", ak.__version__)
