import subprocess, os
GIT = r"C:\Users\57388\.workbuddy\binaries\PortableGit\versions\1.2.0\cmd\git.exe"
os.chdir(r"D:\self")
FILES = ["backend/app/services/kline_store.py", "backend/app/services/kline_ingest.py",
         "backend/app/services/kline_backfill.py", "backend/app/services/signal_scan.py",
         "backend/app/scheduler/jobs.py", "backend/app/core/config.py",
         "backend/scripts/kline_backfill_once.py", "backend/tests/test_kline_store.py"]
MSG = "[买卖点信号体系 批1.5续] 本地日线仓库落地：复权门禁 + local-only + 夜间回补\n\n- kline_store: stock_name 列(老库 ALTER 迁移)/name_map/series_adjust/codes_below/pending_codes;\n  MixedAdjustError 复权口径门禁(混用即拒绝计算, 宁缺不算)\n- kline_ingest: 当日 bar 继承该票既有复权口径; 写 stock_name; 除权票当天不落 bar 待重建\n- kline_backfill: pending_codes 修「首次填充库空误判全部已足」; workers 受控并发\n- signal_scan: local_only 模式(禁止静默回退远端) + eligible/incomplete/data_missing/stale/coverage_pct 审计\n- scheduler: kline_backfill_job 每夜 00:40 分批(不占 16:50 扫描窗口)\n- config: kline_scan_local_only(默认 False)/batch_limit/sleep/workers\n- tests: +6 (test_kline_store 15 到 21)\n\n门禁: 改动仅限已入库目录下已有文件; IMPORT_OK 已验证; 测试数工作区 21 vs HEAD 15\n验证: 20/20 测试(隔离运行); 冒烟 600519 回补 281 根/18.8s; 夜间路径实跑 300 只 ok=229 failed=71(全部920段)"
p = subprocess.run([GIT, "commit", "-m", MSG] + FILES, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("commit_rc=%d" % p.returncode)
print((p.stdout or "").strip()[:500])
if p.returncode: print("STDERR: " + (p.stderr or "").strip()[:400])
q = subprocess.run([GIT, "log", "-1", "--format=%h %ad %s", "--date=format:%Y-%m-%d %H:%M"], capture_output=True, text=True, encoding="utf-8", errors="replace")
print("HEAD: " + q.stdout.strip())
q2 = subprocess.run([GIT, "show", "--stat", "--format=", "HEAD"], capture_output=True, text=True, encoding="utf-8", errors="replace")
print(q2.stdout.strip())
q3 = subprocess.run([GIT, "status", "--porcelain", "--", "backend/"], capture_output=True, text=True, encoding="utf-8", errors="replace")
print("backend dirty: " + (q3.stdout.strip() or "(clean)"))