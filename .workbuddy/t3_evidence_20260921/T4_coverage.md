# T4 本地日线仓库覆盖（2026-09-21 复核 · 修正）

- 库文件：`D:\self\data\kline.db`
- 股票池 `universe_codes.json` = **5564** 只；库 `rows=1,690,309`、`codes=5535`
- **存在率 99.48%（5535/5564）**；**可扫描率（≥MIN_BARS 250 根）97.03%（5399/5564）**
- 结构性短史 **165 只**（`<250` 根），其中 136 只有部分数据（thin）、29 只 0 行（全 920 段）；165 只中 **71 只为北交所**
- 已按交接单「显式标 unsupported」落地：`short_history` 表记录 165 只 → `pending_codes` 跳过（不再夜夜重试）、`signal_scan` local-only 记 `unsupported`（不计入 `data_missing`/`incomplete`，`eligible` 精确扣除）
- `kline_scan_local_only=True`（≥95% 阈值达成：存在率 99.48% / 可扫描率 97.03%）
- 未验证：首次 local-only 扫描须等 09-22 16:50 调度（红线 #2 禁止手动跑 scan_signal_triggers）
