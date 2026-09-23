"""日志快速扫描（编码自适应：utf-8 优先，gbk 回落）：Top 消息 / 异常类型 / 尾部若干行

v2（2026-09-19 修）：原硬编码 decode("gbk","replace")，而 09-18 14:03 起的日志实为 UTF-8 →
中文全被打成替换字符、探针 0 命中（同 signal_check 旧版缺陷，见 PITFALLS #38）。改为自适应。

用法:
    D:/self/.venv/Scripts/python.exe D:/self/log_scan.py <日志路径> [尾部行数]
"""
import collections
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def decode_auto(raw: bytes) -> tuple:
    """以 ASCII 锚点判断解码是否成功（日志行必含 apscheduler/Traceback/INFO 等 ASCII）。"""
    best = None
    for enc in ("utf-8", "gbk"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            text = raw.decode(enc, "replace")
        score = text.count("apscheduler") + text.count("Traceback") + text.count("[INFO]")
        if score > 0:
            return text, enc
        if best is None:
            best = (text, enc + "(replace)")
    return best or (raw.decode("utf-8", "replace"), "utf-8(replace)")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: log_scan.py <log path> [tail_n]")
        return
    path = sys.argv[1]
    tail_n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    text, enc = decode_auto(open(path, "rb").read())
    lines = text.splitlines()
    print(f"=== {path}")
    print(f"enc={enc} lines={len(lines)} tracebacks={text.count('Traceback')}")

    kinds = collections.Counter()
    for i, line in enumerate(lines):
        if "Traceback" in line:
            nxt = [x.strip() for x in lines[i + 1:i + 8] if x.strip().startswith("File ")]
            kinds[nxt[-1][:120] if nxt else "(no file frame)"] += 1
    print("--- 异常位置 Top ---")
    for key, cnt in kinds.most_common(6):
        print(f"  x{cnt} {key}")

    errs = collections.Counter()
    for line in lines:
        if "Error" in line or "Exception" in line or "[ERROR]" in line:
            errs[re.sub(r"\d+", "#", line.strip())[:150]] += 1
    print("--- ERROR/异常行 Top ---")
    for key, cnt in errs.most_common(10):
        print(f"  x{cnt} {key}")

    print(f"--- 尾部 {tail_n} 行 ---")
    for line in lines[-tail_n:]:
        print("  ", line.strip()[:220])


if __name__ == "__main__":
    main()
