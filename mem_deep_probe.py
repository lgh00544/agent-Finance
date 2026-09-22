"""A3 内存定位探针（只读）：60s 采样 RSS/线程 + cache 键数与前缀分布 + 关键 job last_run。

用法:
    python mem_deep_probe.py --hours 6 --interval 60
输出: logs/mem_deep_probe.csv
需后端已加载 GET /api/diagnostics/memory。
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "logs" / "mem_deep_probe.csv"
DIAG = "http://127.0.0.1:8000/api/diagnostics/memory"
JOBS = "http://127.0.0.1:8000/api/jobs/status"
KEY_JOBS = ("kline_backfill", "kline_ingest", "daily_discover", "market_intel",
            "monitor", "paper_monitor", "experience_worker", "experience_worker_probe",
            "sector_radar", "sector_refresh", "quote_snapshot_refresh", "signal_scan")
FIELDS = ["ts", "pid", "rss_kb", "traced_kb", "threads", "handles", "cache_keys", "cache_bytes",
          "cache_expired", "top_prefixes", "job_count", "key_jobs"]


def _get(url: str, timeout: float = 20):
    try:
        resp = httpx.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception:  # noqa: BLE001
        return None


def _sample() -> dict:
    row = {k: "" for k in FIELDS}
    row["ts"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    diag = _get(DIAG) or {}
    row["pid"] = diag.get("pid", "")
    row["rss_kb"] = diag.get("rss_kb", "")
    row["traced_kb"] = diag.get("traced_current_kb", "")
    row["threads"] = diag.get("threads", "")
    row["handles"] = diag.get("handles", "")
    cache = diag.get("cache") or {}
    row["cache_keys"] = cache.get("keys", "")
    row["cache_bytes"] = cache.get("value_bytes", "")
    row["cache_expired"] = cache.get("expired_pending", "")
    row["top_prefixes"] = json.dumps(cache.get("top_prefixes") or [], ensure_ascii=False)
    jobs = _get(JOBS)
    if jobs:
        rows = jobs.get("jobs") or []
        row["job_count"] = len(rows)
        row["key_jobs"] = json.dumps(
            {r.get("id"): r.get("last_run") for r in rows if r.get("id") in KEY_JOBS},
            ensure_ascii=False)
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=6.0)
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--trace-every", type=int, default=0, help="每 N 次采样记录一次 tracemalloc/gc 明细（0=关）")
    args = ap.parse_args()
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    new = not CSV_PATH.exists()
    deadline = time.time() + args.hours * 3600
    first = None
    cycle = 0
    with CSV_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        while time.time() < deadline:
            row = _sample()
            writer.writerow(row)
            fh.flush()
            rss = row["rss_kb"]
            if isinstance(rss, int) and first is None:
                first = rss
            print(f"[{row['ts']}] pid={row['pid']} rss_kb={rss} cache_keys={row['cache_keys']} "
                  f"cache_bytes={row['cache_bytes']} top={str(row['top_prefixes'])[:120]}", flush=True)
            cycle += 1
            if args.trace_every and cycle % args.trace_every == 0:
                deep = _get(DIAG + "?trace=1", timeout=300) or {}
                with (ROOT / "logs" / "mem_trace.jsonl").open("a", encoding="utf-8") as tf:
                    tf.write(json.dumps({"ts": row["ts"], "pid": deep.get("pid"),
                                         "rss_kb": deep.get("rss_kb"),
                                         "trace_top": deep.get("trace_top"),
                                         "gc_top": deep.get("gc_top")}, ensure_ascii=False) + chr(10))
                print(f"  [trace] {row['ts']} top_sites="
                      f"{[s.get('file','').split(chr(92))[-1]+':'+str(s.get('line')) for s in (deep.get('trace_top') or [])[:5]]}",
                      flush=True)
            time.sleep(max(20, args.interval))
    if first is not None:
        print(f"SUMMARY first_rss_kb={first}", flush=True)


if __name__ == "__main__":
    main()
