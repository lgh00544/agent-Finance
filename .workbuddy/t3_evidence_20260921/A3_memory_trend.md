# A3 内存趋势结论（2026-09-21 17:11 → 2026-09-22 08:46）

单实例 PID 31632（后端），`mem_probe.py` 5min 粒度，179 样本 / ~15.6h。

## 实测
- RSS：**168.6 MB（17:11）→ 644.9 MB（08:46）**，总增 **+476.3 MB**
- 分时均值（MB）与环比：17:423（预热）→18:476(+52.9)→19:477.9(+2.0)→20:484.1(+6.2)→21:491.5(+7.4)→22:497.8(+6.3)→23:504.3(+6.5)→**00:523.0(+18.6)→01:552.7(+29.7)→02:589.4(+36.7)**→03:596.4(+7.0)→04:603.0(+6.7)→05:609.8(+6.7)→06:616.7(+7.0)→07:623.6(+6.9)→08:641.5(+17.9)
- 资源：threads 11→20（max 24）；handles 242→315（+73）
- 观测抖动：`/api/jobs/status` 在 **45/180** 采样返回 0 job（health 仍 200），需留意

## 判读（A3 三问）
1. **是泄漏还是稳态**：**持续增长（非纯稳态）**。18:00 预热结束（~476MB）后仍以 **~6.7 MB/h** 稳定上行；03:00–07:00 **无行情 job 时段仍在涨** ⇒ 非行情 job 独占。
2. **嫌疑时段/来源**：**夜间 00:00–02:00 突增 ~85 MB**（对齐 kline_backfill 00:40 / experience_worker 02:00 / db_maintenance / 因子月度等）+ **08:00 +17.9 MB**（sector_radar 等）；另有与 job 无关的稳态基线。
3. **修复建议（不在本批实现）**：优先按 job 分段采样定位（在 A3 探针里记录 job 最近执行时点与 RSS 差值）；dev 内存后端**无 cache 键数观测面**（记 `NA`），建议后续加只读 cache 统计端点或改用 Redis 模式采集键前缀。

## 对 Go/No-Go 的影响
- 判据「24h 增幅 < 200 MB」：观测 15.6h 已 +476 MB（含预热）；**预热后 14h 亦 +168 MB**，按 ~6.7 MB/h + 夜间突增外推，**24h ≈ +260–300 MB > 200 MB ⇒ #5 判 No-Go（增长趋势）**。
- 24h 完整窗口仍在采（新探针 `pwsh-68` 已续跑 10h，可覆盖至 17:11 满 24h 窗口）。

## 追加：PID 31632 全生命周期（233 样本 / ~20.1h，14:54 起探针）
- 09-21 17:11:53 **168.6 MB** → 09-22 13:20:10 **709.5 MB**，总增 **+540.9 MB**
- **预热结束（18:35）后：476.2 → 709.5 MB = +233.3 MB / ~18.75h** ⇒ **已超「24h < 200 MB」阈值（18.75h 就 +233 MB），判 No-Go 无需外推**
- 该实例于 **13:24 死亡**（uptime ~20.1h；`pwsh-63` exit 1；stderr 仅见进度条，无 traceback，死因未定）；随之新实例 **PID 17960** 已起（health ok），watchdog 正确未双开
- 分段速率：18:00–23:00 ~+6.5 MB/h；00:00–02:00 夜间 job 突增 ~+85 MB；03:00–07:00 ~+6.7 MB/h（无行情 job）；08:00 +17.9 MB
## 定位续（2026-09-22 14:3x）：新增只读诊断 + 首次采样

### 新增工具（只读，无业务行为变更）
- `app/cache.py`：`CacheBackend.debug_stats()`（MemoryCache 返回 `keys/expired_pending/value_bytes/top_prefixes`；RedisCache 用 SCAN）
- `app/api/routes.py`：`GET /api/diagnostics/memory`（`pid/rss_kb/threads/handles` + `cache` 统计）
- `mem_deep_probe.py`：60s 采样 `logs/mem_deep_probe.csv`（RSS/线程/handles/cache 键数+字节+前缀/job last_run）

### 首采样（新实例 PID 35316，重启后 8 分钟内）
- 14:29:13 rss=614,896 KB, threads=22, handles=293, **cache_keys=21, cache_bytes=557,481**, job=45
- 14:30:29 rss=590,048 KB, cache_keys=28, cache_bytes=268,055
- 14:31:48 rss=593,236 KB, cache_keys=28, cache_bytes=1,273,128
- **结论（初步）：cache 仅 21–28 键、0.3–1.3 MB ⇒ 缓存不是内存增长来源**，可排除「缓存 key 无界累积」假说。
- 观测：新实例预热后 RSS 也在 ~590 MB 量级；增长需继续按 job 关联（deep probe 6h 采集中）。
- 下一步定位方向（若 job 关联无显著峰）：在诊断端点加入 tracemalloc / gc 类型计数，定位分配站点或对象类型（需再改一次只读端点）。
## 定位结论（2026-09-22，基于 PID 31632 全 20h 日志 + mem_probe）

### 已排除
- **缓存**：`cache.debug_stats()` 实测仅 **9–32 键 / 0.3–1.5 MB**，波动不累积 ⇒ 「缓存 key 无界累积」**证否**。
- **线程/句柄**：夜间两处跳变时 threads 19→20→21（基本平），handles 287→309（+22）⇒ **过程性跳变非线程泄漏**。

### 已定位（两类）
1. **离散台阶（夜间 job）**：
   - **00:40 `kline_backfill`**：RSS `00:36:46 513.0 → 00:42:01 548.9 MB`，**单次 +35.9 MB**（日志显示该次「已全量覆盖，无需回补」，但仍分配且未释放；同时段有 TiDB 连接超时重试）。
   - **02:00 `experience_worker`（日跑）**：`01:59:12 555.7 → 02:04:20 586.6 MB`，**单次 +30.9 MB**（日志显示大量 LLM 调用 + 反复 `MiniMax 摄取失败→deepseek` 降级）。
2. **连续基线**：无 job 时亦 **+0.5–1.0 MB / 5min ≈ 6–12 MB/h**（23:24–00:36 仅 30 分钟探针在跑，仍稳定上行）⇒ 存在**与具体 job 无关的慢速堆积**。

### 复核结论
- 24h 粗算：连续基线 ~24×7 ≈ **168 MB** + 夜间两台阶 ~**67 MB** ≈ **235 MB > 200 MB 阈值** ⇒ 与 #5 的 No-Go 判定一致，且**主因可拆为「夜间 job 台阶」+「连续基线」两块**。

### 下一步（进行中）
- 已加只读诊断：`GET /api/diagnostics/memory?trace=1&gc=1`（`tracemalloc` 前 15 分配点 + `gc` 对象类型计数）。
- `mem_deep_probe.py --trace-every 15`（20h，`pwsh-85`）每 15 分钟记一次 `trace_top/gc_top` 到 `logs/mem_trace.jsonl`，用于**差分定位连续基线的增长对象类型**。
- 首测 `gc_top`：tuple 22.9万 / function 18.8万 / dict 11.8万（待后续差分判断哪些在增长）。
## 定位结论 v2（2026-09-22 15:37–17:14，PID 3308，含首次 local-only 扫描窗口）

### 🔴 最大单次内存事件 = 盘后 job 窗口（16:25–17:15）
- RSS：15:37 **342 MB** → 16:42 **1077 MB** → 17:12 **1235 MB**（峰值 17:00 **1484 MB**）；threads 18 → **59**；handles 265 → 500。
- 日志显示该窗口由多个盘后 job 叠加，其中 **`hot_money_win_rate` 从 16:30 跑到 17:10（约 40 分钟）**，逐股拉 kline，且大量 `数据源 kline 获取失败: 'date'`（**即交接单已定位的缺陷 #1：`hot_money_review` 用个股接口拉沪深300 基准，`_BENCH_INDEX=000300` 被 `_market_of` 判成 sz**；该缺陷仍在发生）。
- **tracemalloc 只记到 ~160 MB**（`traced_current_kb`），而 RSS 1.2 GB ⇒ **主体是 pandas/numpy 原生缓冲**（逐股 DataFrame）而非 Python 对象 ⇒ 指向「盘后 job 逐股 DataFrame 未及时释放」。

### 其它来源（仍成立）
- 夜间台阶：00:40 `kline_backfill` +35.9 MB、02:00 `experience_worker` +30.9 MB。
- 连续基线：无 job 时 ~6–12 MB/h。
- **缓存已排除**（9–48 键 / 0.1–1.5 MB）。

### 修复建议（按收益排序）
1. **修缺陷 #1**（`hot_money_review` 基准指数取数）——直接消除 40 分钟逐股失败重试与 DataFrame 堆积，是本次最大收益项。
2. 盘后重 job 结束显式释放（`del` 大 DataFrame + `gc.collect()`），并复核 `signal_scan` local-only 的并发 worker 持有量。
3. 连续基线（~7 MB/h）留待 tracemalloc 整夜差分定名（探针 `pwsh-93` 在跑）。

### 方法学备注
- 诊断端点已改轻量：`gc=1` 由 `gc.get_objects()`（107s、+200MB 污染）改为 `gc.get_count()/get_stats()`；新增廉价 `traced_current_kb`；全量快照仅 `trace=1` 按需。

## 🔴 定位结论 v3：根因 = 诊断端点自身常开 tracemalloc（2026-09-22 19:00，已修并生效）

### 决定性证据
- **活进程自报**：PID 3308 调 `GET /api/diagnostics/memory`（**本次未带 `trace=1`**）返回 `traced_current_kb=212655`（207 MB）、`traced_peak_kb=251949` ⇒ **tracemalloc 一直开着**。
- **代码事实**：`routes.py` 原实现 `if trace: if not tracemalloc.is_tracing(): tracemalloc.start(15)` —— **只 start，全文无 stop**。tracemalloc 为每条*存活分配*保留 15 帧调用栈，其元数据**不计入 `get_traced_memory()`**，故表现为「RSS 涨但 traced 只占小头」。
- **修正 v2 的推论**：v2 由「traced ~160MB vs RSS 1.2GB」推出「主体是 pandas/numpy 原生缓冲」——该推论**不成立**（差值主要是 tracemalloc 自身元数据）。真正主体是本次自伤，pandas 缓冲尚需在干净窗口重判。

### 逐 PID 还原（`logs/mem_probe.pre-fix-20260922.csv`，313 样本 / 2026-09-21 14:54 → 09-22 18:41）
| pid | 样本 | 首→末 MB | 峰值 MB | 存活 min | MB/h |
|---|---|---|---|---|---|
| 31632 | 233 | 169→709 | 709 | 1208 | 27（tracemalloc 后段开启）|
| 3308 | 36 | 167→1414 | **1770** | 191 | **392**（tracemalloc 开启，threads 峰值 79）|
| 27604 | 6 | 156→654 | 693 | 29 | 1044 |
| 35316 | 6 | 416→611 | 611 | 27 | 432（**traced=0，同窗口基本持平 600→612**）|
| 7848 | 10 | 157→619 | 627 | 48 | 575 |
| 27220 | 4 | 190→514 | 516 | 22 | 868 |
| 21156 / 34872 | 5 / 6 | 316→595 / 193→541 | 595 / 541 | 29 / 34 | 578 / 622 |

- **12 次进程更替、5739 处 Traceback 全来自历史 `reload-fail` 文件**；本轮各实例 stderr **0 条 Python 异常**（1.2 MB 内容全是 akshare `Please wait for a moment` 进度条）⇒ 进程是**被静默杀掉**（沙箱回收/OOM），不是自己抛错退出。
- 开关对照：**开启 tracemalloc 的实例 3.2h 334→1414 MB；未开启的 35316 同窗口 600→612 MB**。

### 修复（一次性收口，非打补丁）
| 文件 | 改动 |
|---|---|
| `backend/app/core/mem_diag.py`（新） | `enabled()/start()/stop()/state()/trace_guard()`；默认禁开 + **硬 TTL** 自动 stop |
| `backend/app/core/config.py` | `mem_diag_trace_enable=False`、`mem_diag_trace_ttl_s=600` |
| `backend/app/api/routes.py` | 端点入口先 `trace_guard()`；`trace=1` 仅在启用时 start，`trace=-1` 立即 stop，回报 `trace_disabled/tracing/on_s/ttl_s` |
| `backend/app/scheduler/jobs.py` | `_reclaim_memory()` 内调 `trace_guard()`（每 30min `experience_worker` 起兜底，防「开了就没人再请求」）|
| `backend/tests/test_mem_diag_trace.py`（新） | 4 例：默认禁开 / 启用后可采样且 TTL 到期自动关 / 显式 stop / 外部开启也被兜住 |

### 验证
- 门禁：staged 树 `git write-tree`=9b3ea257 → 干净副本 `import app.main` **APP_MAIN_IMPORT_OK**；`test_mem_diag_trace.py` 干净 4 = 工作区 4 collected；用例 4 passed。
- 运行时：重启后 PID 32024（19:02）`?trace=1` 返回 `trace_disabled="MEM_DIAG_TRACE_ENABLE=false…"`、`tracing=false`、`ttl_s=600` ⇒ 不再有任何路径留下常开态。

### 仍未定（需干净窗口）
- 静默被杀的确切机制（沙箱回收 vs OOM）：改由 A1 看门狗 + 日志对齐；本轮 12 次更替中 WATCHDOG_RESTART 仅 2 次，其余为人工/脚本重复拉起。
- 连续基线残余（`35316` 持平、`31632` 27 MB/h）与夜间台阶（00:40 +35.9、02:00 +30.9 MB）需在无 tracemalloc 的 24h 重测。

### 重测安排
- 旧证据已转存 `logs/mem_probe.pre-fix-20260922.csv`；干净基线自 **2026-09-22 19:02** 起写入 `logs/mem_probe.csv`（`mem_probe.py --hours 24 --interval 300`，作业 `pwsh-100`）。

## 定位结论 v4：修复后满 24h 实测（2026-09-23 19:03）——#5 仍 No-Go，主因转为盘中

### 满窗数据（277 样本，跨 2 个实例）
- 全窗：`425.9 → 678.6 MB（+252.7 MB）`（19:02 PID 32024 → 18:58 PID 15984）。
- 长活实例 **PID 15984**（00:47:30→18:58:30，18.2h）：`168.9 → 678.6 MB`，**含冷启动预热 +257.7 MB（0.26h，973 MB/h）**。
- **剔除预热**：01:03→18:58 `+252.0 MB / 17.92h = 14.06 MB/h` ⇒ **24h 外推 +337 MB > 200 MB 阈值 ⇒ No-Go**。

### 分段（首次把增长钉到盘中）
| 段 | 窗口 | ΔMB | MB/h | 24h 外推 |
|---|---|---|---|---|
| 预热 | 00:47→01:03 | +257.7 | 974 | （一次性冷启动成本，不计入趋势）|
| 夜间/盘前 | 01:03→09:03 | +64.2 | **8.02** | +192.5 |
| **盘中** | 09:03→15:05 | **+173.8** | **28.78** | +690.7 ← **主因** |
| 收盘 | 15:05→16:03 | −4.2 | −4.31 | — |
| 盘后窗口 | 16:03→17:34 | +16.8 | 11.11 | +266.7 |
| 盘后之后 | 17:34→18:58 | +1.4 | 0.98 | +23.6 |

- **盘中 09:03→09:44 单次台阶 +120.6 MB（490.8→611.4）** 是当前最值得钉的单点；盘中 threads 20→24、handles 295→327 同步抬升。
- **盘后段从修复前 +300 MB/h 降到 +16.8 MB/1.5h ⇒ tracemalloc 那次修复在盘后段确实见效**；但盘中的累积与它无关。

### 修正与收益
- ⚠️ **修正**：早前基于 19:02→00:41（仅 5.1h 夜间平段）给出的「24h 外推 +2.1 MB」**不成立**，已由满窗实测证伪；`#5` 自始至终为 **No-Go**。
- ✅ **真实收益（与 #5 判据无关但重要）**：修复后单实例**连续存活 18.3h、全程零挂起、零看门狗重启**（修复前 20–50 分钟即被静默杀、28h 内 12 次进程更替）⇒ 自伤型崩溃环已消除。
- `tracing=false` 全程保持，无回退。

### 下一步（盘中累积）
1. 钉 09:03→09:44 的 +120 MB：该窗口对应盘中高频 job（`quote_snapshot_refresh` 每分钟、`sector_refresh`、`monitor`/`paper_monitor`）与首轮快照；用 `mem_deep_probe --interval 60`（cache 键数/字节 + job last_run）在明日 09:00–10:00 做 1 分钟粒度关联。
2. 复核 `hot_money_win_rate`/`signal_scan` 之外的高频 job 是否持有 DataFrame/连接不释放（成交明细、快照缓存）。
3. 连续基线（夜间 8 MB/h）单独定名，与盘中项分开修。




