"""出网与服务连通性自检（重启前后通用；只读、不改任何状态）

用法:
    D:/self/.venv/Scripts/python.exe D:/self/net_check.py
"""
import glob
import os
import socket
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TARGETS = [
    ("127.0.0.1", 8000, "本机后端"),
    ("www.baidu.com", 80, "公网基线"),
    ("vip.stock.finance.sina.com.cn", 80, "股票池源(sina)"),
    ("stock.finance.sina.com.cn", 443, "日线源(sina)"),
    ("gateway01.ap-southeast-1.prod.aws.tidbcloud.com", 4000, "云端 TiDB"),
]


def tcp(host: str, port: int, timeout: int = 6):
    start = time.time()
    try:
        sock = socket.create_connection((host, port), timeout)
        sock.close()
        return True, round(time.time() - start, 2)
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {str(exc)[:60]}"


def main() -> None:
    print("=== 连通性自检", time.strftime("%Y-%m-%d %H:%M:%S"), "===")
    for host, port, label in TARGETS:
        ok, info = tcp(host, port, 3 if port == 8000 else 6)
        mark = "OK  " if ok else "FAIL"
        print(f"[{mark}] {label:16s} {host}:{port}  {info}")

    print("=== 日志文件（按修改时间）===")
    for path in sorted(glob.glob("D:/self/backend-dev*"), key=os.path.getmtime):
        st = os.stat(path)
        print("  ", time.strftime("%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
              f"{st.st_size:>9d}", os.path.basename(path))


if __name__ == "__main__":
    main()
