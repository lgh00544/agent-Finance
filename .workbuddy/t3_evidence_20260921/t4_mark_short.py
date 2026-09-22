import json, sqlite3, sys, os
sys.path.insert(0, r"D:\self\backend")
os.environ.setdefault("APP_ENV", "dev")
from app.services import kline_store
uni = json.load(open(r"D:\self\.workbuddy\batch1_date_rootcause_20260920\universe_codes.json", encoding="utf-8"))
cs = {str(c) for c in (uni.get("codes") if isinstance(uni, dict) else uni)}
con = sqlite3.connect(kline_store.db_path())
counts = {r[0]: r[1] for r in con.execute("SELECT stock_code, COUNT(*) FROM daily_kline GROUP BY stock_code")}
con.close()
n = 0
for c, cnt in counts.items():
    if c in cs and cnt < 250:
        kline_store.mark_short(c, cnt); n += 1
probe = {"920003":214,"920009":218,"920015":239,"920020":222,"920022":243,"920036":136,"920045":176,"920050":163,"920055":120,"920069":122,"920076":162,"920078":129,"920080":234,"920081":52,"920086":166,"920096":90,"920119":156,"920121":180,"920124":200,"920158":230,"920159":158,"920168":143,"920176":41,"920180":149,"920183":139,"920187":138,"920188":121,"920206":75,"920211":76}
for c, bars in probe.items():
    if c not in counts:
        kline_store.mark_short(c, bars); n += 1
sc = kline_store.short_codes()
print(json.dumps({"newly_marked": n, "short_total": len(sc), "short_bj": sum(1 for c in sc if c[:2] in ("43","83","92"))}, ensure_ascii=False))
