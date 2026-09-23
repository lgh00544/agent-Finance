"""买卖点信号体系 · 观察期核对脚本（只读 + 日志归档复制；不写库、不重启、不改码）

v2（2026-09-19 修）修复三处量具缺陷：
  1. 硬编码 decode("gbk") → 日志实为 UTF-8，中文探针全 0 命中，曾误判「未执行」（09-18 实录）
     改为编码自适应（utf-8 优先 / gbk 回退），并输出每个文件所用编码以便审计
  2. 只扫 live 日志 → 进程重启/截断会丢现场。改为 live + 全部 `backend-dev.stdout.*.log` 归档合并去重
  3. 只判「有无完成文案」→ 改为解析 summary 的 reason，reason != ok 一律判异常日

用法:
    D:/self/.venv/Scripts/python.exe D:/self/signal_check.py [YYYY-MM-DD]
    （省略日期 = 今日）

输出: 调度器 / 归档 / 日志（含编码与来源）/ summary 结构化字段 / DB 当日行数与重复组 / 结论
"""
import json
import re
import shutil
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

ROOT = Path(r"D:/self")
LOG_OUT = ROOT / "backend-dev.stdout.log"
LOG_ERR = ROOT / "backend-dev.stderr.log"
ENV = ROOT / ".env"

BAD = ["信号扫描超出总预算", "信号扫描批次超时", "信号扫描批次失败",
       "信号扫描股票池获取失败", "signal_scan 锁被占用，跳过本次", "Traceback"]
TS = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})")
REASON = re.compile(r"'reason':\s*'([^']*)'")
FIELD = {k: re.compile(r"'%s':\s*(-?\d+)" % k) for k in ("universe", "records", "errors", "dropped")}
SIG_LOGGER = "app.services.signal_scan"        # ASCII 锚点，编码无关
RUN_MARK = 'Running job "买卖点信号扫描'


def probe_api() -> dict:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/jobs/status", timeout=8) as r:
            data = json.loads(r.read().decode("utf-8"))
        for job in data.get("jobs", []):
            if job.get("id") == "signal_scan":
                return job
        return {"error": "signal_scan not found"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def archive_logs(stamp: str) -> list:
    made = []
    for src in (LOG_OUT, LOG_ERR):
        if src.exists():
            dst = src.with_name(f"{src.stem}.{stamp}.log")
            shutil.copy2(src, dst)
            made.append((dst.name, dst.stat().st_size))
    return made


def decode_auto(raw: bytes) -> tuple:
    """编码自适应：以 ASCII 锚点计数判定解码是否成功，避免再被 GBK/UTF-8 差异误判。"""
    best = None
    for enc in ("utf-8", "gbk"):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            text = raw.decode(enc, "replace")
        score = text.count(SIG_LOGGER) + text.count("apscheduler")
        if score > 0:
            return text, enc, score
        if best is None:
            best = (text, enc + "(replace)", score)
    return best or (raw.decode("utf-8", "replace"), "utf-8(replace)", 0)


def collect(day: str) -> tuple:
    """合并 live + 全部 stdout 归档，逐行去重（归档是同一流的快照，否则会重复计数）。"""
    srcs = [LOG_OUT] + sorted(p for p in ROOT.glob("backend-dev.stdout.*.log"))
    files, lines, seen = [], [], set()
    for p in srcs:
        if not p.exists():
            continue
        text, enc, score = decode_auto(p.read_bytes())
        all_lines = text.splitlines()
        hits = sum(1 for l in all_lines if SIG_LOGGER in l or "信号扫描" in l)
        files.append((p.name, p.stat().st_size, enc, score, hits))
        for line in all_lines:
            if line not in seen:
                seen.add(line)
                lines.append(line)
    return files, lines


def scan_log(day: str) -> dict:
    files, lines = collect(day)
    res = {"files": files, "total_lines": len(lines)}
    dlines = [l for l in lines if day in l]

    def cnt(phrase: str) -> int:
        return sum(1 for l in dlines if phrase in l)

    res["bad"] = {k: cnt(k) for k in BAD}
    res["batch_lines"] = [l for l in dlines if SIG_LOGGER in l and "信号扫描批次" in l]
    res["done_job"] = cnt("买卖点信号扫描完成: ")
    res["done_scan"] = cnt(f"信号扫描结束 {day}:")
    res["summary_line"] = next((l.strip() for l in dlines if f"信号扫描结束 {day}:" in l), None)
    res["run_line"] = next((l for l in dlines if RUN_MARK in l), None)

    summary = {}
    if res["summary_line"]:
        summary["reason"] = (REASON.search(res["summary_line"]) or [None, None])[1]
        for k, rx in FIELD.items():
            m = rx.search(res["summary_line"])
            summary[k] = int(m.group(1)) if m else None
    res["summary"] = summary

    stamps = sorted(m.group(1) for l in dlines for m in [TS.match(l.strip())] if m)
    res["log_span"] = (stamps[0], stamps[-1]) if stamps else (None, None)
    start = (TS.match((res["run_line"] or "").strip()) or [None, None])[1]
    end = (TS.match((res["summary_line"] or "").strip()) or [None, None])[1]
    res["first_ts"], res["end_ts"] = start or (stamps[0] if stamps else None), end
    if start and end:
        fmt = "%Y-%m-%d %H:%M:%S"
        res["duration_sec"] = (datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).total_seconds()
    else:
        res["duration_sec"] = None
    return res


def db_stats(day: str) -> dict:
    import pymysql
    env = {}
    for line in ENV.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if "=" in s and not s.startswith("#"):
            k, v = s.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    conn = pymysql.connect(host=env["MYSQL_HOST"], port=int(env["MYSQL_PORT"]), user=env["MYSQL_USER"],
                           password=env["MYSQL_ROOT_PASSWORD"], database=env["MYSQL_DATABASE"],
                           connect_timeout=15, ssl={"ssl": {}})
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM signal_trigger")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM signal_trigger WHERE trade_date=%s", (day,))
    today = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM signal_trigger WHERE dedup=1")
    dedup = cur.fetchone()[0]
    cur.execute("SELECT trade_date,stock_code,signal_id,COUNT(*) n FROM signal_trigger "
                "GROUP BY trade_date,stock_code,signal_id HAVING n>1")
    dup = cur.fetchall()
    cur.execute("SELECT signal_id, COUNT(*) n FROM signal_trigger WHERE trade_date=%s "
                "GROUP BY signal_id ORDER BY n DESC LIMIT 12", (day,))
    by_sig = cur.fetchall()
    cur.execute("SELECT stock_code,signal_id,direction,trigger_close,limit_up,is_st,dedup "
                "FROM signal_trigger WHERE trade_date=%s ORDER BY id DESC LIMIT 10", (day,))
    sample = cur.fetchall()
    cur.execute("SELECT DISTINCT stock_code FROM signal_trigger WHERE trade_date=%s", (day,))
    stocks = len(cur.fetchall())
    cur.execute("SELECT LEFT(stock_code,3) p, COUNT(DISTINCT stock_code) n FROM signal_trigger "
                "WHERE trade_date=%s GROUP BY p ORDER BY p", (day,))
    prefixes = cur.fetchall()
    conn.close()
    return {"total": total, "today": today, "dedup": dedup, "dup": dup, "by_signal": by_sig,
            "sample": sample, "stocks": stocks, "prefixes": prefixes}


def main() -> None:
    day = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    print(f"=== 买卖点信号 · 观察期核对 {day} ===")

    print("[1] 调度器:", probe_api())
    print("[2] 归档:", archive_logs(stamp))

    log = scan_log(day)
    print("[3] 日志来源（合并去重后 %d 行）:" % log["total_lines"])
    for name, size, enc, score, hits in log["files"]:
        print("      %-42s %9dB  enc=%-14s sig行=%d" % (name, size, enc, hits))
    print("    当日时间跨度:", log["log_span"])
    print("    完成行=%d 结束行=%d | 批次行=%d 起=%s 止=%s 时长=%ss"
          % (log["done_job"], log["done_scan"], len(log["batch_lines"]),
             log["first_ts"], log["end_ts"], log["duration_sec"]))
    print("    异常文案计数:", log["bad"])
    print("    summary 结构化:", log["summary"])
    if log["summary_line"]:
        print("    summary 原文:", log["summary_line"][:260])

    stats = db_stats(day)
    print(f"[4] DB: 总={stats['total']} 当日={stats['today']} 覆盖股票={stats['stocks']} "
          f"dedup=1={stats['dedup']} 重复组={stats['dup']}")
    print("    当日按信号:", stats["by_signal"])
    print("    当日代码前缀分布:", stats["prefixes"])
    for row in stats["sample"]:
        print("     样例:", row)

    s = log["summary"]
    bad_hit = [k for k, v in log["bad"].items() if v]
    ok = (log["done_scan"] > 0 and s.get("reason") == "ok" and not bad_hit
          and not stats["dup"] and s.get("records") == stats["today"])
    if log["done_scan"] == 0 and stats["today"] > 0:
        verdict = "⚠ 日志无执行文案但 DB 有数据 → 先查日志来源/编码（v2 已合并归档）"
    elif log["done_scan"] == 0:
        verdict = "未发现当日执行痕迹"
    elif ok:
        verdict = "✅ 通过（reason=ok / 无异常文案 / records==DB / 无重复组）"
    else:
        verdict = "❌ 异常日（见上：reason 非 ok 或命中异常文案或计数不符）"
    print("[5] 结论:", verdict)
    print("    reason =", s.get("reason"), "| records =", s.get("records"),
          "| DB当日 =", stats["today"], "| 命中异常文案 =", bad_hit or "无")


if __name__ == "__main__":
    main()
