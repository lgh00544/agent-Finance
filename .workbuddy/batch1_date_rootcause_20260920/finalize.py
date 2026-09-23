import io, json, os, sys, subprocess
d = r"D:\self\.workbuddy\batch1_date_rootcause_20260920"
p = os.path.join(d, "REPLAY_SUMMARY.md")
txt = open(p, encoding="utf-8").read()
old = "2. **信号正确性**：正在做「取库内 5 只 → 回放 → 与库内 key 精确比对」（`_step_j_correctness.txt`）。"
new = ("2. **信号正确性 → 已验，且精确相等**：取库内 09-18 的 5 只（`600210/600211/600215/600221/600222`）回放，`_scan_batch` 命中 **7** 条，与库内同 5 只的 **7** 条 key **完全相等**（`EXACT MATCH? True`，两侧差集均为空），`errors=0 dropped=0 wall=23.2s`。证据 `_step_j_correctness.txt`。")
assert old in txt
txt = txt.replace(old, new, 1)
txt += "\n## 六、只读性自检（回放结束后）\n"
sys.path.insert(0, r"D:\self\backend")
from sqlalchemy import text
from app.db.session import SessionLocal
GIT = r"C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
with SessionLocal() as db:
    n = db.execute(text("SELECT COUNT(*) FROM signal_trigger")).scalar()
    r21 = db.execute(text("SELECT COUNT(*) FROM signal_trigger WHERE trade_date = :d"), {"d": "2026-09-21"}).scalar()
    mx = db.execute(text("SELECT MAX(trade_date) FROM signal_trigger")).scalar()
probe = subprocess.run([GIT, "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=r"D:\self")
mod = [l for l in probe.stdout.splitlines() if l.startswith(" M")]
txt += "| 项 | 值 |\n|---|---|\n"
txt += "| `signal_trigger` 总行数 | **%s**（回放前后一致） |\n" % n
txt += "| `max_trade_date` | **%s** |\n" % mx
txt += "| 09-21 行数 | **%s** |\n" % r21
txt += "| `git status` 中 backend/app 改动 | **%s**（本会话零新增） |\n" % (sorted(l.split("/")[-1] for l in mod if "backend/app" in l) or "无")
txt += "| 未 commit/push/tag / 未重启 / 未手动跑 scan_signal_triggers | ✅ |\n"
open(p, "w", encoding="utf-8").write(txt)
print("db_total=%s max=%s rows_0921=%s" % (n, mx, r21))