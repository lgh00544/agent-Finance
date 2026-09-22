"""批A A3 内存趋势探针（只读，不改后端）。

用法:
    D:/self/.venv/Scripts/python.exe D:/self/mem_probe.py --hours 5 --interval 300
输出: D:/self/logs/mem_probe.csv（列见 FIELDS）

判据: 连续 24h RSS 增幅 < 200 MB。cache 键数仅在 CACHE_BACKEND=redis（多人模式）可观测；
dev 内存缓存无对外观测面，记 NA（K227 不编造）。不改后端、不引新依赖。
"""
from __future__ import annotations

import argparse
import csv
import os
import time
from datetime import datetime
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "logs" / "mem_probe.csv"
HEALTH = "http://127.0.0.1:8000/api/health"
JOBS = "http://127.0.0.1:8000/api/jobs/status"
FIELDS = ["ts", "pid", "rss_kb", "cpu_pct", "threads", "handles", "health_ok", "job_count", "cache_keys"]


def _find_backend_pid() -> int | None:
    best = None
    for p in psutil.process_iter(["pid", "name", "cmdline", "create_time"]):
        try:
            name = (p.info.get("name") or "").lower()
            cmd = " ".join(p.info.get("cmdline") or [])
            if "python" not in name:
                continue
            if "dev_run.py" in cmd or "uvicorn" in cmd:
                if best is None or p.info["create_time"] > best[1]:
                    best = (p.info["pid"], p.info["create_time"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return best[0] if best else None


def _http_json(url: str):
    try:
        import httpx

        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _redis_cache_keys() -> str:
    try:
        value = os.environ.get("CACHE_BACKEND")
        env_file = ROOT / ".env"
        if not value and env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("CACHE_BACKEND="):
                    value = line.split("=", 1)[1].strip()
                    break
        if (value or "").lower() != "redis":
            return "NA"
        import redis  # type: ignore

        client = redis.Redis(db=int(os.environ.get("REDIS_DB", "0")))
        return str(sum(1 for _ in client.scan_iter(count=500)))
    except Exception:
        return "NA"


def _sample() -> dict:
    row = {k: "" for k in FIELDS}
    row["ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pid = _find_backend_pid()
    if pid:
        try:
            proc = psutil.Process(pid)
            with proc.oneshot():
                row["pid"] = pid
                row["rss_kb"] = int(proc.memory_info().rss / 1024)
                row["cpu_pct"] = round(proc.cpu_percent(interval=None), 1)
                row["threads"] = proc.num_threads()
                row["handles"] = proc.num_handles() if hasattr(proc, "num_handles") else ""
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            row["pid"] = pid
    row["health_ok"] = 1 if (_http_json(HEALTH) or {}).get("status") == "ok" else 0
    row["job_count"] = len((_http_json(JOBS) or {}).get("jobs") or [])
    row["cache_keys"] = _redis_cache_keys()
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=5.0)
    ap.add_argument("--interval", type=int, default=300)
    args = ap.parse_args()
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    new = not CSV_PATH.exists()
    deadline = time.time() + args.hours * 3600
    first_rss = last_rss = None
    with CSV_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        while time.time() < deadline:
            row = _sample()
            writer.writerow(row)
            fh.flush()
            rss = row["rss_kb"]
            if isinstance(rss, int):
                first_rss = rss if first_rss is None else first_rss
                last_rss = rss
            print(f"[{row['ts']}] pid={row['pid']} rss_kb={rss} jobs={row['job_count']} "
                  f"health={row['health_ok']} cache_keys={row['cache_keys']}", flush=True)
            time.sleep(max(30, args.interval))
    if first_rss and last_rss:
        print(f"SUMMARY rss_delta_mb={(last_rss - first_rss) / 1024:.1f} "
              f"first={first_rss} last={last_rss}", flush=True)


if __name__ == "__main__":
    main()
