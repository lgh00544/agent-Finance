p = r"D:\self\买卖点信号体系_批1.5续_代码实现_交接_20260920.md"
txt = open(p, encoding="utf-8").read()
add = "\n\n---\n\n## 六、A′ 路线收尾（2026-09-20 深夜补）\n\n### 6.1 修掉一个会让首填失效的 bug\n`kline_backfill_job` 原本用 `kline_store.codes_below()` 取待办 —— **首次全量填充时库里 0 只，该函数返回空 → 任务误判「全部已足」直接 return**。\n新增 `kline_backfill.pending_codes(path, codes)`：把**本地完全没有记录的票**也算进待办；任务改用它。\n实测：库空时 `pending_codes=5564`（= universe）✅，回补后 pending 相应减少 ✅。\n\n### 6.2 夜间路径实跑（12 只真实样本，只写本地 SQLite）\n```\nuniverse=5564（41.2s）\npending_codes=5564\n切片=12 只 → backfill: ok=8 failed=4 bars=2236 wall=57.1s\nstats_after={rows:2236, codes:8, min_date:2025-07-28, max_date:2026-09-18}\n等效单只=7.1s（**不是预估的 19s**）\n```\n⇒ 全量 5564 只约 **11 小时**（串行）/ 每夜 300 只 = **19 夜**。\n\n### 6.3 受控并发（本批新增参数）\n`backfill(workers=N)`：>1 时用 ThreadPoolExecutor 并跳过 sleep；默认 **1（保持既有测试/调用不变）**，夜间任务取 `settings.kline_backfill_workers=8`（依据：独立实测腾讯批量源 8 并发 ≈2.9 只/s 且 16 并发不再提升）。\n⇒ 若 8 并发同样适用于逐票源，19 夜可压到 **≈3 夜**；**并发收益待首夜实跑确认**（本次 bench 因源侧限流未跑成）。\n\n### 6.4 失败码集中在 920 段（北交所）\n12 只样本中失败的 4 只**全部是 920xxx**（新浪链路对北交所老段/部分新段支持有限）。\n⇒ `failed_codes` 已进 summary；首夜后需按段统计失败率，920 段可能需单独换源或显式标 `unsupported`。\n\n### 6.5 仍需动作（不由本批执行）\n1. **重启后端**：夜间任务与 local-only 开关需重启才生效（PID 15748 仍是旧代码）。\n2. **local-only 开关保持 False**：覆盖率达标（≥95%）前不要开。\n3. 首夜建议先跑 `--limit 300` 观察失败率与并发收益，再放开。\n"
if "A′ 路线收尾" not in txt:
    txt = txt.replace("## 五、门禁自检（提交前须补）", add.strip() + "\n\n## 五、门禁自检（提交前须补）", 1)
    open(p, "w", encoding="utf-8").write(txt)
    print("updated")
else:
    print("already")