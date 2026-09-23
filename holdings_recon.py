#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""实盘持仓对账（只读）：真实成交侧 CSV ↔ 系统侧 GET /holdings?status=holding。

差异容忍：shares 差 0 股；cost_price(每股成本，对齐系统 entry_price) 差 <= 0.001。
零写操作：只发 GET，不调 tradeable_view()，不改任何表；缺数据输出 None + reason，不估算（K227）。
"""
import argparse, csv, io, json, sys, urllib.request

BASE = "http://127.0.0.1:8000"
ALIAS = {"code": ("stock_code", "证券代码", "股票代码", "代码"),
         "name": ("stock_name", "证券名称", "股票名称", "名称"),
         "shares": ("shares", "股数", "持仓数量", "数量", "股票余额"),
         "cost": ("cost_price", "成本价", "成本单价", "entry_price", "持仓成本价")}
SHARE_TOLERANCE, COST_TOLERANCE = 0, 0.001

def pick(row, keys):
    for k in keys:
        if k in row and str(row[k]).strip() != "":
            return str(row[k]).strip()
    return None

def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def field_diff(code, name, hid, sval, rval, fname, tol, fix):
    if sval is None or rval is None:
        return [(code, name, fname, sval, rval, "-", "数据缺失")]
    if abs(sval - rval) <= tol:
        return []
    return [(code, name, fname, sval, rval, round(sval - rval, 4), "不一致"),
            (code, name, "修正动作", fix % hid, "-", "-", "待办")]

def read_csv(path):
    """读真实侧 CSV → {code: {name, shares, cost}}，允许 UTF-8 BOM/GBK"""
    raw, text = open(path, "rb").read(), None
    for enc in ("utf-8-sig", "gbk", "utf-8"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise SystemExit("CSV 解码失败（非 UTF-8/GBK）: %s" % path)
    rows = {}
    for row in csv.DictReader(io.StringIO(text)):
        code = pick(row, ALIAS["code"])
        if code:
            rows[code] = {"name": pick(row, ALIAS["name"]), "shares": pick(row, ALIAS["shares"]),
                          "cost": pick(row, ALIAS["cost"])}
    return rows

def fetch_system():
    """系统侧有效持仓（status=holding）；只读 GET，不触发 tradeable_view"""
    with urllib.request.urlopen(BASE + "/api/holdings?status=holding", timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return {r["stock_code"]: {"id": r.get("id"), "name": r.get("stock_name"),
                              "shares": r.get("shares"), "cost": r.get("entry_price"),
                              "dup": sum(x.get("stock_code") == r["stock_code"] for x in body) > 1}
            for r in body if r.get("stock_code")}

def compare(sysm, real):
    """逐票逐字段对账 → 差异行（code, 名称, 字段, 系统值, 真实值, 差额, 判定）"""
    rows = []
    for code in sorted(set(sysm) | set(real)):
        s, r = sysm.get(code), real.get(code)
        name = (s or r).get("name") or ""
        if not s or not r:
            rows += [(code, name, "整体", "有(id=%s)" % s["id"] if s else "None(无有效持仓)",
                      "CSV无" if s else "有", "-", "真实侧缺失" if s else "系统缺"),
                     (code, name, "修正动作", "POST /api/holdings 建仓" if not s else
                      "补 CSV 行；或 GET /api/holdings/%s/trades 核流水" % s["id"],
                      "-", "-", "待办")]
            continue
        rows += field_diff(code, name, s["id"], num(s["shares"]), num(r["shares"]), "shares",
                           SHARE_TOLERANCE,
                           "POST /api/holdings/%s/exit|add (price=真实成交价, shares=%s)")
        rows += field_diff(code, name, s["id"], num(s["cost"]), num(r["cost"]), "cost_price",
                           COST_TOLERANCE,
                           "POST /api/holdings/%s/cost (cost_price=%s, reason=对账修正)")
        if s["dup"]:
            rows.append((code, name, "重复持仓", "系统侧多条 status=holding", "-", "-",
                         "阻断：需先合并"))
    return rows

def main():
    ap = argparse.ArgumentParser(description="实盘持仓对账（只读）")
    ap.add_argument("csv", nargs="?", help="真实成交侧 CSV 路径")
    ap.add_argument("--dry", action="store_true", help="无真实 CSV：用系统值自比对，验证脚本本身")
    a = ap.parse_args()
    if not a.dry and not a.csv:
        raise SystemExit("用法: holdings_recon.py <csv路径>  |  holdings_recon.py --dry")
    sysm = fetch_system()
    if a.dry:
        real, mode = {c: dict(v, dup=False) for c, v in sysm.items()}, "DRY(系统值自比对)"
    else:
        real, mode = read_csv(a.csv), "CSV=%s" % a.csv
    diff = compare(sysm, real)
    out = ["对账模式: %s | 系统侧有效持仓 %d 只 | 真实侧 %d 只 | 容忍 shares差0股 cost_price差<=%s"
           % (mode, len(sysm), len(real), COST_TOLERANCE),
           "code | 名称 | 字段 | 系统值 | 真实值 | 差额 | 判定"]
    out += [" | ".join(str(x) for x in row) for row in diff] or ["(无差异)"]
    if a.dry and not sysm:
        out.append("NOTE: 系统侧 0 只有效持仓（status=holding）→ 口径已跑通，真实票对账需先有有效持仓；"
                   "缺数据不编造（K227）")
    text = "\n".join(out) + "\n"
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdout.write(text)
    if not sysm and not real:
        return 2
    return 1 if any(x[6] in ("不一致", "系统缺", "阻断：需先合并") for x in diff) else 0

if __name__ == "__main__":
    sys.exit(main())
