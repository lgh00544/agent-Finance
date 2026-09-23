"""日志编码诊断（只读）：判定 backend-dev.stdout.log 的真实编码，修正 signal_check 的硬编码 GBK。

用法: D:/self/.venv/Scripts/python.exe D:/self/log_encoding_check.py
"""
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

P = Path(r"D:/self/backend-dev.stdout.log")
raw = P.read_bytes()
print("bytes =", len(raw))
print("head hex =", raw[:16].hex())

PROBES = ["买卖点信号扫描完成: ", "信号扫描结束 2026-09-18:", "信号扫描批次超时", "信号扫描超出总预算"]
for enc in ("utf-8", "gbk", "utf-8-sig", "cp936", "latin-1"):
    try:
        text = raw.decode(enc)
        hits = {p: text.count(p) for p in PROBES}
        # 用「行数」做辅助判据：正解应能切出与文件规模相称的行数
        print("--- %-10s OK  lines=%-6d hits=%s" % (enc, len(text.splitlines()), hits))
    except Exception as exc:  # noqa: BLE001
        print("--- %-10s ERR %s: %s" % (enc, type(exc).__name__, exc))

# 逐行二分定位：找出含「批次」的行在两种解码下的样子
for enc in ("utf-8", "gbk"):
    try:
        lines = raw.decode(enc).splitlines()
        got = [l for l in lines if "1:00:25,912" in l or "17:00:25,912" in l]
        print("[%s] 命中 17:00:25,912 行数 = %d" % (enc, len(got)))
        for l in got[:2]:
            print("     >", l[:200])
    except Exception as exc:  # noqa: BLE001
        print("[%s] ERR %s" % (enc, exc))
