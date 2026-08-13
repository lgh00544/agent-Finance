# -*- coding: utf-8 -*-
"""验证 akshare_source 三个新方法：返回结构 + 降级行为（结果写 UTF-8 文件）"""
import json
import sys

sys.path.insert(0, ".")

from app.datasource.akshare_source import AkshareSource

out = {}
src = AkshareSource()

# 1) 隔夜美股
try:
    us = src.fetch_us_market_overnight()
    out["us_market"] = us
except Exception as e:
    out["us_market"] = {"exception": f"{type(e).__name__}: {e}"}

# 2) 两市量倍
try:
    tv = src.fetch_market_total_volume_ratio()
    out["total_ratio"] = tv
except Exception as e:
    out["total_ratio"] = {"exception": f"{type(e).__name__}: {e}"}

# 3) 板块箱位（东财当前不可达，预期全部数据缺失；用几个板块名测试）
try:
    bp = src.fetch_board_box_positions(["半导体", "通信设备", "光学光电子", "证券", "电子元件"])
    out["board_box"] = bp
except Exception as e:
    out["board_box"] = {"exception": f"{type(e).__name__}: {e}"}

with open("../scripts/_verify_new_methods.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1, default=str)
print("DONE")
