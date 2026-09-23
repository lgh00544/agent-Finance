import sys, inspect
sys.path.insert(0, r"D:\self\backend")
from app.services import signal_scan as ss
from app.services.signal_registry import list_all
out = []
out.append("=== signal_scan public/private fns present ===")
for n in ("_scan_batch", "_scan_one", "_load_keys", "_persist", "scan_signal_triggers"):
    f = getattr(ss, n, None)
    out.append("  %-22s %s" % (n, "OK " + str(inspect.signature(f)) if f else "MISSING"))
out.append("  BATCH_SIZE=%s PARALLEL_MAX=%s BATCH_BUDGET=%s TOTAL_BUDGET=%s MIN_BARS=%s" % (ss.BATCH_SIZE, ss._PARALLEL_MAX, ss._BATCH_BUDGET_SECONDS, ss._TOTAL_BUDGET_SECONDS, ss.MIN_BARS))
out.append("")
defs = list_all()
out.append("=== signal definitions ===")
out.append("  count=%d" % len(defs))
out.append("  ids=%s" % [getattr(d, "id", None) for d in defs])
out.append("")
out.append("=== _load_keys read-only? ===")
src = inspect.getsource(ss._load_keys)
out.append("  writes? INSERT/UPDATE/DELETE present: %s" % any(k in src for k in ("INSERT", "UPDATE", "DELETE", "db.add", "commit")))
out.append("  query only: %s" % ("db.query(SignalTrigger" in src))
open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\_recon_scope.txt", "w", encoding="utf-8").write("\n".join(out))
print("OK")