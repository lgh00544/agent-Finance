"""买卖点信号体系 · C 段定点抽样干跑（零写入）

为什么定点抽样：WorkBuddy 沙箱注入代理 → 东财 push2 ProxyError、新浪 456 反爬，
沙箱内 fetch_spot_universe() 必失败（后端自身环境无此问题）。故 universe 改用跨板块
定点抽样，用于验证：① 22 个信号函数在真实日线上是否全部可执行 ② 单只耗时与
540s 总预算风险。

零写入：只调 _scan_batch（signal_scan.py:100，不落库），不调 scan_signal_triggers/_persist。
用法: D:/self/.venv/Scripts/python.exe D:/self/signal_dryrun_sample.py [YYYY-MM-DD] [budget_s]
"""
import sys
import time
from collections import Counter
from datetime import datetime, timedelta

sys.path.insert(0, r"D:/self/backend")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from app.services import signal_scan as ss  # noqa: E402
from app.services.signal_registry import list_all  # noqa: E402
from app.datasource.fallback import get_datasource  # noqa: E402

DAY = sys.argv[1] if len(sys.argv) > 1 else "2026-09-17"
BUDGET = float(sys.argv[2]) if len(sys.argv) > 2 else 240.0

SAMPLE = """
600519 600036 601318 600030 601988 601857 600028 601398 601288 600887
600276 600309 600585 601012 601899 600438 603259 603288 603501 605117
000001 000002 000063 000333 000651 000725 000858 000876 002027 002142
002230 002304 002415 002475 002594 002714 002812 002916 003816 002007
300015 300059 300122 300124 300142 300274 300308 300316 300347 300394
300450 300496 300502 300628 300661 300750 300760 300782 301236 301269
688008 688012 688036 688111 688169 688180 688256 688271 688396 688499 688981
920000 920001 920002
""".split()
# 注（2026-09-20 修）：原样例含 430047/830799/832735/836077/839680 五只北交所**老段**代码，
# 会稳定抛 `No value to decode`，把固定噪声混进 errors（曾致 09-19 实测被误读为环境问题）。
# 经 DSH 实测 `ak.stock_info_bj_name_code()`：北交所 344 只**全部在 920 段**，43/83 段 0 只
# ⇒ 老段在真实 universe 中不存在，故改用 920 段（新浪可取，rows=282）。

defs = list_all()
ctx = {
    "trade_date": DAY, "defs": defs, "source": get_datasource(), "today": set(), "cooldown": set(),
    "start": (datetime.strptime(DAY, "%Y-%m-%d") - timedelta(days=ss._LOOKBACK_DAYS)).strftime("%Y-%m-%d"),
    "end": DAY,
}
items = [{"code": c, "name": ""} for c in SAMPLE]
print("now              =", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("trade_date       =", DAY, "| kline window =", ctx["start"], "→", ctx["end"])
print("defs             =", len(defs), "| sample =", len(items), "| batch budget =", BUDGET, "s")
print("PARALLEL_MAX     =", ss._PARALLEL_MAX, "| BATCH_SIZE =", ss.BATCH_SIZE,
      "| TOTAL_BUDGET =", ss._TOTAL_BUDGET_SECONDS, "s | MIN_BARS =", ss.MIN_BARS)

t = time.time()
rows, errors, dropped = ss._scan_batch(items, ctx, BUDGET)
el = time.time() - t
per = el * 1000 / max(1, len(items))
print("-" * 72)
print("elapsed=%.1fs | 单只=%.0fms | rows=%d errors=%d dropped=%d" % (el, per, len(rows), errors, dropped))
print("命中信号分布:", dict(Counter(r["signal_id"] for r in rows)))
hit_ids = {r["signal_id"] for r in rows}
print("未被命中的信号:", sorted({d.id for d in defs} - hit_ids))
print("命中明细(前 15):")
for r in rows[:15]:
    print("   ", r["stock_code"], r["signal_id"], r["direction"], "close=%s" % r["trigger_close"],
          "is_st=%s limit_up=%s dedup=%s" % (r["is_st"], r["limit_up"], r["dedup"]))

for n in (3000, 5500):
    est = el * n / max(1, len(items))
    print("外推 %d 只 ≈ %.0fs（预算 %ds）→ %s"
          % (n, est, ss._TOTAL_BUDGET_SECONDS, "OK" if est < ss._TOTAL_BUDGET_SECONDS else "⚠ 超预算"))
print("== 完成：未写 signal_trigger 任何一行 ==")
