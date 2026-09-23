# 高频陷阱（执行／审核必查）

> 2026-09-15 从 MEMORY.md 拆出。写代码、出提示词、审核前先过一遍。

1. `structured.py:32` 注释"LIGHT=Discover 初筛"**是错的**，Discover 3 处全 DEEP
2. `fetch_industry_spot` 需传 `kind="snapshot"` 才走断路器
3. dashboard 聚合**禁止**调 `tradeable_view()`（`ensure_if_missing` 触发 900 次 DB 查询），用 `repo.list_candidate_tradeable(trade_date, limit=50)`
4. `repo.list_candidate_tradeable` 字段是 `tier/price_zone/label/block_reason`（**不是** `grade/reason/potential_flag`）
5. `TradeProfile` 在 `web/src/types/index.ts:294`（`types/trade.ts` **不存在**）
6. **win_rate 口径**：`track_verify._group_stats` 0-100 百分制；`_calc_stats` 0-1 小数 —— 展示层必须显式归一化（防 4400%）。`CandidatesPage.tsx:572` / `ReviewsPage.tsx:132` 曾误把百分制再乘 100，修复指令 `D:\self\React前端胜率展示修复_执行指令.md`
7. **React 候选池默认拉全表**（2026-08-20）：`CandidatesPage.tsx:480` 的 `date` state 始终 undefined，`<Select value={date ?? dates?.[0]}>` 是非受控显示 → queryFn 实际传 undefined → repo 拉全表 39 条。**修复模板**：`useEffect(() => { if (!date && dates?.length) setDate(dates[0]) }, [dates, date])` ＋ `enabled: !!date`。指令 `D:\self\React候选池页默认仅最近一次生成_执行指令.md`
8. 同 `trade_date` 下所有候选共用同批生成时间（毫秒级差），"最近一次生成结果"＝ `trade_date` 最大的那一天全部候选
9. `WebFetch` 失效时用 `request` 直调 akshare；`market_hours.snapshot_allowed()` 是交易日闸门
10. `useEffect` 替代写法是死循环 —— 不要在 render 阶段直接 `form.setFieldsValue`
11. tsc `EXIT=0` ≠ 落地（未使用的 import／函数 tsc 不报警）→ 必须 `grep 关键标识 | wc -l` 核对
12. AppTest 22 failed 是**环境性内存压力**，与代码无关
13. 复盘追踪列表缺徽章／排序：Streamlit `D:\self\选股效果验证_排序加徽章_执行指令.md` ＋ React `D:\self\React复盘页徽章排序_执行指令.md`（均未执行）

14. **`compute_indicators()` 无 `change_pct` 键**（只有 `change_pct_1d`）——涨停判定／量价信号若直接取 `snap["change_pct"]` 会恒为 `None` → `limit_up` 永远 0。修法：快照层从原始列取 `change_pct`，缺失时回退库内 `change_pct_1d`（`indicators/core.py` 已处理）
15. **指标算法唯一实现源 = `services/indicator.py`**（已有 `sma/ema/macd/rsi/atr/rolling_extreme/compute_indicators`）。`indicators/core.py` 只允许 `import` 聚合，函数名 `compute_signal_snapshot`；**重名 `compute_indicators` 即重复实现**。口径分歧实录：EMA/ATR 有无 `min_periods`、RSI 缺失时 `50.0` vs `NaN`

16. **启动即崩 = `init_db()` 迁移失败且无保护**（2026-09-16 实例）：`main.py:31` 调 `init_db()` 无 try/except，任一迁移异常 → lifespan 失败 → 进程死亡 → **调度器一起没了**（表现：8000 无监听、cron 一次都没跑、日志里找不到 job 记录）。排查顺序：先看 `backend-dev.stderr.log` 有无 `数据库初始化/迁移失败`，再查 `8000` 端口与进程
17. **`session.py:303` 冲突行清理有方言守卫 `if engine.dialect.name != "sqlite"`** —— 但本地 `data/dev.db` **就是 SQLite**，故清理被跳过。凡 `account_pnl_snapshot` 出现 `user_id IS NULL` 行且同 `(trade_date, ts)` 已有 `user_id` 行 → `_ensure_user_columns` 的 `UPDATE ... user_id=1` 必撞 `uq_account_pnl_user_date_ts`。**根因**：`_migrate_account_pnl_snapshot`（SQLite 分支）重建表时写 UNIQUE 并原样拷行，而 SQLite 中 `NULL` 互不相等 → NULL 行与已归属行可并存，建表无事、一回填就重复

18. **干跑跑在备份文件本身上会让备份失效**（2026-09-16 实例）：迁移前 `cp dev.db dev.db.bak-<日期>` 后，**干跑直接跑在备份文件上** → 备份被改写成迁移后状态（md5 与迁移后原库完全一致）→ 一旦迁移失败**无法回滚**。规则：干跑用**第三份副本**；备份文件只读、永不执行迁移；动原库前用 `md5sum` 记录备份指纹以便事后判断是否被改写
19. **`.env` 的 `DB_BACKEND`**：08-20 后**默认 `mysql`（云端 TiDB `stock_agent`）**，不再是本地 `data/dev.db`。`config.py:32` 默认值仍是 `sqlite`，故**未加载 .env 的裸启动会回落到本地 SQLite**（曾致启动即崩且现场难追溯）。查「数据写哪去了」先看 `.env` 的 `DB_BACKEND`，再看启动日志 `数据库初始化/迁移完成 backend=?`
20. **后端重启会覆盖 `backend-dev.stdout.log`** → 崩溃现场丢失。重启前先归档（改名带时间戳），否则事后无法定位

21. **`session.py:_database_identity(eng=engine)` 的默认参数在导入期绑定** → 启动日志的 `backend=?` **不可信**。`dev_run.py:78-84` 会临时把 `db_session.engine` 重绑到本地 SQLite 再还原，但默认参数仍指向导入时的云端 engine → **即使迁移跑在 SQLite 上，日志也打 `backend=mysql`**。曾因此误判「本次启动验证了 SQLite 路径」。判断真实库看 `.env` 的 `DB_BACKEND`，别信这行日志。修法（1 行）：`def _database_identity(eng=None): eng = eng or engine`
22. **`start_multi_user.ps1` 不能当"持久化启动"的替代**：`param` 默认 `$Port = 8100`，且设 `MULTI_USER_ENABLED='true'` / `CACHE_BACKEND='redis'` / `QDRANT_MODE='server'`；**第 30-31 行硬校验** `throw 'Redis is not listening on 6379'` / `throw 'Qdrant is not listening on 6333'`，且会拉起 5173 前端。Qdrant 常未启动 → 脚本直接 throw。单机 dev 用 `dev_run.py`，别用它

23. **`signal_trigger` 字段名 = `trade_date` / `stock_code` / `signal_id`**（`models.py:1535` 唯一约束 `uq_signal_trigger_identity`）。我曾在 09-17 核对提示词里误写成 `symbol/date/signal_code` → 会让执行端查错列。同表其余列：`direction / trigger_close / exec_price / limit_up / is_st / ret_5 / ret_10 / ret_20 / excess_10 / excess_20 / max_profit_20 / max_drawdown_20 / filled_at`
24. **signal_scan 首跑核对必须照抄代码里的日志文案**（近义词搜索会误判「没跑」）：
   - 成功：`买卖点信号扫描完成: {summary}`（`jobs.py:885`）＋ 方法内 `信号扫描结束 {date}: {summary}`（`signal_scan.py:194`）
   - 超预算：`信号扫描超出总预算 540s，已落 N 条记录`（`signal_scan.py:177`）
   - 批次超时：`信号扫描批次超时 {n}s，保留 x 条，丢弃 n 只`（`:125`）；批次失败 `信号扫描批次失败（跳过该批）`（`:185`）；股票池失败 `信号扫描股票池获取失败`（`:156`）
   - 锁占用：`signal_scan 锁被占用，跳过本次`（`jobs.py:881`）；非交易日：`今天 {date} 非交易日，跳过买卖点信号扫描`（`jobs.py:878`）
   - `summary = {trade_date, universe, records, errors, dropped, reason}`，**无耗时字段** → 时长只能由日志时间戳算（首批 `信号扫描批次` 行 → `信号扫描结束` 行），或「无超预算行」即视为在 540s 预算内
25. ~~**`/api/jobs/status` 只暴露 `id/name/next_run`，没有 `last_run`** → 末次执行必须靠「日志成功行 + DB 行数」双证据。~~
   **✅ 已过期（2026-09-23 复核）**：该端点现已返回 6 个字段 —— `id / name / next_run / last_run / last_status / last_reason`。
   实测样例：`{"id":"signal_scan","next_run":"2026-09-23 16:50:00+08:00","last_run":"2026-09-22 18:01:19","last_status":"ok","last_reason":null}`。
   ⇒ 末次执行现在**可直接读 `last_run`**；但 `last_reason=null` **不等于无异常**（业务 `reason` 在 summary 里，如 `total_budget_exceeded`）→ 仍须「`last_run` 定位 + 日志 summary 取业务结果」两段式。
   ⇒ 副作用提醒：`last_run=18:01:19` 而 cron 是 `16:50` → **末次执行时点偏离 cron 槽位 = 该次可能是重启后的补跑或手动触发**，核对观察日时必须追查，不能默认「16:50 已跑」。
   - ⚠️ **2026-09-21 17:07 实测已变**：该端点返回 `{id,name,next_run,last_run,last_status,last_reason}`，45 个 job；`signal_scan` 实测 `last_run=2026-09-21 17:03:01 / last_status=ok / last_reason=null`（= 完成时刻，非触发时刻 16:50:00）
   - ⚠️ 同日 **17:31 再次实测返回体结构又变**（顶层不再是 job 列表，`len()==1` 且元素非 dict）→ 该端点**当日被并发改动**，解析时要防御式取数，别写死 list
26. **`stderr` 体积增长 ≠ 异常**：`backend-dev.stderr.log` 从 883 B 涨到 13 KB，内容全是 tqdm 进度条（`Please wait for a moment: 100%|…| 70/70`）。判异常看 `Traceback`，别看文件大小
27. **signal_scan 调度参数**（`jobs.py:935-938`）：cron `mon-fri 16:50`、`max_instances=1`、**`misfire_grace_time=3600`**（16:50 进程不在、1 小时内补起仍会补跑）；`signal_scan.py:21` `_COOLDOWN_TRADING_DAYS=10` → 同股同信号 10 个交易日内不重触发，故重复组应恒为 0
28. **Grep 的 `head_limit` 会截断结果，不能用来下「某文案不存在」的结论**（2026-09-16 实例）：查 `signal_scan.py` 文案时 `head_limit=40` 截断了后续匹配，我据此误判「不存在『超出总预算』文案」，差点把已写对的判据改错 → 查「是否存在」用 `output_mode=count` 或调大 limit
29. **APScheduler 用内存 jobstore → 重启不补跑错过的 cron**（`jobs.py:908` `BackgroundScheduler(timezone="Asia/Shanghai")` **未配 jobstore** → 默认 MemoryJobStore）。`misfire_grace_time=3600` **只在进程存活期间**生效（job 被阻塞/延迟时）；**进程死后重启，jobstore 里没有历史 → 下一次触发＝下一个未来时点（次日 16:50）**，当天不补。故 signal_scan 这类「当日盘后只跑一次」的任务：**16:50 时进程必须在世**，否则当日无数据且无法靠重启补回。我曾在值守指令写「17:50 前补起会补跑」—— **错**，该说法只在有持久化 jobstore 时成立

30. **`backend-dev.stderr.log` 里没有任何时间戳行**（2026-09-17 实测：18,765 行 / 带 `YYYY-MM-DD` 前缀的行 = **0**）。故 stderr 无法按时间定位，traceback **只能靠关键字归属**（如 `signal_scan` / `pymysql`）；**一切时间判定一律以 stdout 为准**。归属判据：`grep 'signal_scan' stderr` 命中 0 → 该 traceback 与 signal_scan 无关
31. **`fetch_spot_universe` 的缓存兜底只在非交易日生效**（`akshare_source.py:509-513`：`cache.get(_cache_key("spot_em"))` 分支被 `if not market_hours.snapshot_allowed():` 包住）→ **交易日盘后（16:50 扫描窗口）若网络失败，无任何缓存兜底，直接抛异常**。链路：主源东财 `ak.stock_zh_a_spot_em` → 备源新浪 `ak.stock_zh_a_spot`（`akshare_source.py:507-524`），两路都失败即 `reason='error:universe'`
32. **本机 DNS 会整体降级**（2026-09-17 16:31~17:07 实测）：`vip.stock.finance.sina.com.cn` / `push2.eastmoney.com` / TiDB 主机同时 `gaierror`（每次解析耗时 11-13s），仅 `hq.sinajs.cn` 可通。**症状集合**（同时出现即判「网络降级」而非代码问题）：`NameResolutionError` ＋ `指数行情获取超时` ＋ `游资信号行情回溯失败` ＋ `数据源 kline 重试失败` ＋ stderr 大量 `pymysql 2003/2013/10060`。**此时连 TiDB 查询也会断连** → pymysql 必须加重连重试。快速自测：`socket.gethostbyname(<域名>)` 看是否 `gaierror`

30. **signal_scan 执行失败 ≠ 代码问题，先查外部数据源**（2026-09-17 首跑实例）：调度层日志是 `Job "买卖点信号扫描" executed successfully`（**APScheduler 只要函数没抛异常就报成功**），业务结果要看 `买卖点信号扫描完成: {…}` 里的 `reason`。当日 summary = `{universe:0, records:0, errors:0, dropped:0, reason:'error:universe'}`，原始异常 = `信号扫描股票池获取失败: HTTPConnectionPool(host='vip.stock.finance.sina.com.cn'): Max retries exceeded`。17:22 复测 `get_datasource().fetch_spot_universe()` 仍失败：`DataSourceError: 数据源 spot_em 重试失败: ('Unknown identifier','upstream')`（东财 spot 分页 138 页，耗时 98.9s）。旁证同期本机对外网络大面积异常：新浪 kline 多处 `Max retries exceeded`；**云端 TiDB 也超时**（16:35 `pymysql OperationalError 2003 timed out` → 「AI模拟复盘审核」job 抛异常崩）；`数据源 kline 已降级到备用接口` 168 次。09-16 同一函数正常（5563 行 / 28.1s）→ 判为**外部故障而非代码缺陷**
   **排查顺序**：① 看 summary 的 `reason` ② 看「信号扫描股票池获取失败」后的原始异常 ③ 同期其它 job 是否同样失败（判断网络级 vs 单点）④ 手动复测 `fetch_spot_universe()` 判是否恢复 ⑤ **别把 APScheduler 的 "executed successfully" 当成业务成功**

31. **从受限环境启动后端会失败：`PermissionError: [WinError 5] 拒绝访问`**（2026-09-17 20:10 实例）：`backend-dev.stderr.reload-fail-2010.log` **54,714 行 / 2,736 个 Traceback**，全部指向 `multiprocessing/resource_sharer.py:138 _serve → connection.py:701 accept → _winapi.CreateNamedPipe` → **创建命名管道被拒**（Windows 受限会话／沙箱权限）。后果：后端起不来 + 日志被瞬间刷爆（2.9 MB）。
   **规则**：启动后端必须用**能创建命名管道的环境**（DSH 会话／普通用户交互终端）；**不要在 WorkBuddy 沙箱里的 Bash/PowerShell 启动 `dev_run.py`**。判别法：启动后 stderr 立刻出现 `CreateNamedPipe ... WinError 5` → 环境不对，换环境，**别原环境重试**。
   **且启动前先跑 `D:/self/net_check.py`** 确认出网与 TiDB 可达（出网断时启动会全量同步失败、当天扫描照样 `error:universe`）

33. **WorkBuddy 沙箱里的 Bash 工具 PATH 已损坏（2026-09-18 实测）**：`dirname` / `ls` / `date` / `head` 全 `command not found`，只有内建 `echo` 之类能用 → **核查类命令一律改走 PowerShell 工具**。
34. **PowerShell 工具的 stdout 不回显**（2026-09-18 实测）：直接 `Write-Output` / `Get-Date` 只返回「Command completed with exit code 0」，看不到内容。**规避**：把结果 `Out-File -Encoding utf8 <tmp>` 落盘 → 再用 Read 工具读取；`Invoke-WebRequest` 的返回同样需要落盘。
   附带：读 GBK 文本用 Python `open(..., encoding='utf-8', errors='replace')`，别用 PowerShell 默认重定向（会写成 UTF-16 被 Read 判为二进制）；沙箱下 `Remove-Item` **静默失效**，删临时文件用 `[System.IO.File]::Delete($p)`。

35. **WorkBuddy 沙箱出网对 A 股源不可用／极慢 → 沙箱数据不得用于判定「源可用性」或「耗时」**（2026-09-18 实测，曾因此产生一次假警报）：
   - 东财 push2 `ProxyError: Unable to connect to proxy, RemoteDisconnected`（沙箱注入代理）
   - 新浪 `Market_Center`（spot 备源）返回 **HTTP 456 + text/html**（反爬拦截页）→ 正是 `akshare` 报 `Can not decode value starting with character '<'` 的来源
   - 单只 `fetch_daily_kline` 需 **1.1–22s**（剥离代理后同）→ 由此外推全市场耗时会得出「超 540s 预算」的错误结论
   - 但 `net_check.py` 的 TCP 探测全 OK（raw socket 不走代理）→ **TCP 可通 ≠ HTTP 可用**
   **正确做法**：源可用性一律以**后端自身日志**为准。判别锚点：`func_name` 的唯一映射 —— `_fetch("spot_em", "spot_em", …)`（`akshare_source.py:544`）**全库仅 `fetch_spot_universe` 使用**，故日志出现 `数据源 spot_em 已降级到备用接口` = 该函数在后端环境**成功**（`_run_fallback:521` 仅当 fallback 返回非空表才打 INFO）。

36. **`signal_scan` 的"提前手动跑"会毁掉当日观测数据 —— 三重机制**（2026-09-18 查证）：
   - 落库唯一入口 = `_persist()`（`signal_scan.py:130`），只被 `scan_signal_triggers`(:189) 调用 → `_scan_one`(:56)/`_scan_batch`(:100) **本身不落库**，可安全干跑（做预演就调这两个）
   - `_scan_one:82` `if (code, definition.id) in ctx["today"]: continue` → 当日已入库的 (股票,信号) 组合**被整批跳过** → 提前跑完会让 16:50 正式跑 `records` 缩水甚至为 0
   - `uq_signal_trigger_identity` 幂等 → 16:50 **无法覆盖**提前写入的盘中价，`trigger_close` 永久错
   - 附带：`_load_keys`(:41) 取近 10 交易日做冷却判定 → 提前写入会让后续交易日的 `dedup` 非 0，污染「重复组应恒为 0」判据
   ⇒ 结论：**提前跑 = 当日报废且数据是错的**，比不跑更糟。正确替代 = 干跑 `_scan_batch` + `_persist` 不参与。

37. **`fetch_daily_kline` 尊重 `end` 参数 → 当日收盘后补跑同日期，数据口径正确**（`akshare_source.py:1004` 把 `end_date` 传入 akshare；`signal_scan._scan_one:68` 判据是「最后一根 bar 日期 == trade_date」）。故 `scan_signal_triggers('YYYY-MM-DD')` 只要在收盘后执行，取到的就是该日收盘 K 线 → **失败当天可当天补，不必等到下一交易日**。但补跑会削弱「验证自动化自身可靠」的观察意义，须 sir 授权。

38. **`Read` 带 `limit` 会被截断 —— 未见到的行不得推断为「不存在」**（2026-09-18 亲历，审核端自身出错）
   核验 `_call_with_timeout` 时用 `offset=1170, limit=45`（实际只到 `:1214`），没看到 `:1222` 的
   `pool.shutdown(wait=False)`，就断言「从不 shutdown」并据此提了修改要求 → 被执行端实查反驳。
   属**基于截断输出的臆断**，不是代码有问题。
   ⇒ 审核结论凡涉及「某行／某语句是否存在」，**必须完整读取或用精确 grep 定位**
   （`grep -n "pool.shutdown"` 一行即证），禁用「我读到的片段里没有」推出「代码里没有」。

39. **`backend-dev.*.log` 的编码会随启动方式变化，不可硬编码**（2026-09-18 实测）
   - 09-16 / 09-17 的 `backend-dev.stdout.log` = **GBK**
   - **09-18 的 = UTF-8**（逐字节判别：`decode("utf-8")` 成功且含「数据库／信号扫描」；`decode("gbk")` 在 position 485 抛 `illegal multibyte sequence`）
   ⇒ 解码前先判别：依次试 `utf-8` / `gbk`，用「是否含已知中文 marker（数据库／信号扫描）」判定胜者；**不要凭上一次的经验直接 `decode("gbk")`**。
   ⇒ 症状：解码错编码不会报错（`errors="replace"`），只会**静默产出乱码** → 所有中文文案检索返回 0，看起来像「没跑／无异常」。ASCII 标识（`signal_scan`、`Traceback`）仍能命中，极易造成「半对半错」的误判。
   ⇒ **stderr 同理**：09-18 的 stderr 也是 UTF-8，且同样无时间戳行（沿用 #30）。

40. **`signal_check.py` / `log_scan.py` 硬编码 GBK → 遇 UTF-8 日志会双重误判**（2026-09-18 实测）
   - `signal_check.py:57` `raw.decode("gbk", "replace")`、`log_scan.py:22` 同
   - 对 09-18 日志实跑结果：`完成行=0 结束行=0 批次行数=0 时长=None`、异常文案计数**全 0** → 输出「**未发现当日执行痕迹**」＋「**无异常文案**」
   - 而真相是：已执行（`next_run` 已推进、summary 完整）＋ **有 5 条异常文案**（超出总预算 1、批次超时 4）
   ⇒ **静默假阴性**：把「已执行＋超预算失败」误报成「未执行＋无异常」。
   ⇒ 修法 1 行（先试 utf-8 回落 gbk）；**未修前，观察期核对不得只信该脚本**，须用「探活 `next_run` 是否已推进」＋「原生日志 grep + 正确解码」交叉验证。DB 段（`[4]`）不依赖日志编码，结论仍可靠。

41. **`summary['dropped']` 不含「总预算耗尽后未进入批次的剩余股票」**（`signal_scan.py:173-185`）
   09-18 实例：`universe=5564`、只跑了 4 批（0~2000）、`dropped=1716`（=370+462+459+425，仅 4 批超时未完成数）。
   ⇒ 未进入批次的 **3564 只不计入 `dropped`** → 真实覆盖须手算：`records` 对应股票数 ÷ `universe`（09-18 = 108/5564 ≈ **2%**）。
   ⇒ 且批次按 universe 原序推进 → 覆盖是**前缀而非随机**，当日样本**有偏**（09-18 只落 `600`/`603`/`920` 三段），任何「因子/信号命中率」统计须先剔除该偏差。

42. **参数与全市场规模不匹配：540s / 8 并发覆盖不了 5564 只**（2026-09-18 结论，结构性）
   `signal_scan.py:18-25`：`BATCH_SIZE=500`、`_PARALLEL_MAX=8`、`_BATCH_BUDGET_SECONDS=120`、`_TOTAL_BUDGET_SECONDS=540`。
   全市场扫完要求 **单只 < 540×8/5564 ≈ 0.78s**；实测吞吐 0.92→0.32→0.34→0.74 只/s（单只 ~7s）。
   ⇒ **即使数据源完全正常，该预算也覆盖不了全市场** → 遇 `reason='total_budget_exceeded'` 别只归因数据源，须同时核算容量。
   ⇒ 附带：每次批超时的 `pool.shutdown(wait=False, cancel_futures=True)` 后，`with` 退出时**再次调用 `shutdown(wait=True)`** → 批实际墙钟 > 120s（09-18：150/157/142/121s），进一步压缩有效预算。

43. **东财 kline 主源在并发批量拉取下会整体限流**（`akshare_source.py:1001-1013`）
   链路：主源 `ak.stock_zh_a_hist`（东财）→ `_run_fallback` 备用 `ak.stock_zh_a_daily`（新浪，单只更慢）。
   **判据（按小时聚合「数据源 kline 已降级到备用接口」）**：09-18 hour14=7 / hour15=7 / **hour16=556（16:50:36 起，扫描窗口内 ~100%）** → 低并发时主源正常、8 并发批量时主源几乎全失败 ⇒ **限流**，非宕机。
   ⇒ 结论：`kline 已降级` 次数在扫描窗口内暴涨 = 主源限流，此时吞吐由更慢的备用源决定；不要据此判定「代码缺陷」。

44. **时长判据修正：批超时场景下「首批『信号扫描批次』行」会少算预算已耗时间**（2026-09-18）
   「信号扫描批次」文案会同时出现在**超时告警**（`信号扫描批次超时 120s，保留…`）与**批次完成**（`信号扫描批次 0~500 命中…`）两处；首批超时告警出现在批次**开始后 120s**。
   ⇒ 09-18 按该口径得 475.3s「<540s 通过」，而真实 job 墙钟 16:50:00.009→17:00:25.912 = **625.9s**（与「超出总预算 540s」告警自洽）。
   ⇒ **正确口径**：`Running job "买卖点信号扫描"` 行（或 `scheduled at` 时刻）→ `信号扫描结束` 行；无超时告警时才可退化为首批次行口径。

35. **`backend-dev.stdout.log` 是 UTF-8 编码（不是 GBK）—— 用 GBK 解码会让中文关键字检索全部失效**（2026-09-19 实测）：`raw.decode('gbk')` 得到「淇″彿鎵�鎻忔壒娆�」这类乱码（= UTF-8 字节被当 GBK 读），于是 `"买卖点信号扫描完成" in line` 恒为 **False** —— 我会据此误判「该文案不存在」。
   **规则**：查中文文案用 `raw.decode('utf-8', errors='replace')`（PITFALLS #34 已写对）；若必须兼容历史 GBK 档，用 UTF-8 优先、GBK 兜底双试。**ASCII 关键字（`KeyError` / `signal_scan` / `Traceback`）不受影响，检索结果可信。**

36. **`signal_scan` 每天都会「超预算截断」—— `reason='total_budget_exceeded'` 是第三种结果**（2026-09-18 观察日 1 实测）：
   ```
   {'trade_date':'2026-09-18','universe':5564,'records':149,'errors':0,
    'dropped':1716,'reason':'total_budget_exceeded'}
   ```
   - 16:50:00 → 17:00:25 = **625s > `_TOTAL_BUDGET_SECONDS=540`** → 观察期标准「时长<540s」**必挂**
   - 只进入 **4 批 = 2000 只**（日志「批次 1500~2000」为最后一批）；`dropped=1716` → **真正完成 284 只**
   - ⇒ **覆盖率 ≈ 284/5564 = 5.1%**；offset 2000~5564（3564 只）**从未进入** → `range(0,N,500)` 按池内序截断 = **选择偏差**，与方案 §5.2「必须全市场、防选择偏差」硬约束**直接冲突**
   - `signal_scan.py:173-178` 循环顶部查 `remaining<=0` 即 break 置该 reason；`:124` `dropped=sum(1 for f in futures if not f.done())`
   - **判定口径必须更新**：原来只看 `{error:universe, empty_universe}` 为不通过，**漏掉了 `total_budget_exceeded`**

37. **`_call_with_timeout` 已由其他会话改为硬超时（未提交）＋ 引入 `socket` 进程级副作用**（2026-09-19 实查 diff：48+/4-，文件 mtime 09-18 15:54）：
   - 新增 `_accepts_timeout()`（`inspect.signature` 预判，避开 `except TypeError` 吞异常）；
   - 兜底路径：`socket.setdefaulttimeout(settings.datasource_timeout)` + `ThreadPoolExecutor(1)` + `future.result(timeout=+1)`，超时抛 `DataSourceError`
   - ⚠️ **`datasource_timeout: int = 5`（`config.py:173`）**，而 `socket.setdefaulttimeout` 是**进程级**设置 → 兜底调用窗口内，其他线程**新建且未显式指定超时**的连接会继承 5s，docstring 自曝可能波及 **LLM(openai) 外呼**（缓解因素：openai SDK 通常自建 httpx 并显式设 timeout，故**须实测确认**，不可推断）
   - ⚠️ 该修复使主源被硬超时到 ~6s → **更频繁降级备用源** → 单只耗时**未必下降**（DSH 实测 45.5s ≈ 12s 主源两次 + 33.4s 备用，数目吻合到可疑）
   - ⇒ 容量核算的耗时基线若测于 15:54 之前，**已过期须重测**

38. **日志编码会随进程而变 → 一切日志探针必须编码自适应，禁止硬编码 `decode("gbk")`**（2026-09-19 实录）：
   - 09-17 之前：旧进程写出的日志中文已被 **U+FFFD 替换字符**污染（读起来是 `锟斤拷` / `淇″彿鎵弿`）
   - **09-18 14:03 起的新进程写干净 UTF-8**（`decode("utf-8")` 成功；`decode("gbk")` 在第 307 字节抛 `illegal multibyte sequence`）
   - 后果：`signal_check.py` / `log_scan.py` 硬编码 GBK → 中文探针 **0 命中** → 把「已执行且有 5 条异常文案」的失败 run 误报成「未执行痕迹」= **静默假阴性**（已修 v2）
   - **正确做法**：`for enc in ("utf-8","gbk")` 尝试，**以 ASCII 锚点计数**判定解码是否成功（`app.services.signal_scan` / `apscheduler` / `Traceback` / `[INFO]`），并打印所用编码以便审计

39. **`signal_scan` 全市场扫描的预算与真实数据源速度结构性不匹配 → 必然 `total_budget_exceeded`**（2026-09-18 实测，非网络抖动）：
   - 参数（`signal_scan.py:18-25`）：`BATCH_SIZE=500` / `_PARALLEL_MAX=8` / `_BATCH_BUDGET_SECONDS=120` / `_TOTAL_BUDGET_SECONDS=540` / `MIN_BARS=250` / `_LOOKBACK_DAYS=420`
   - 算术：`540s × 8 并发 / 5564 只` ⇒ 单只须 **< 0.78s**；实测单只 **~7s**（吞吐 0.32–0.92 只/s）→ 缺口约 **10 倍**
   - 09-18 结果：`universe=5564 / records=149 / dropped=1716 / reason=total_budget_exceeded / 耗时 625s`；4 批全部撞 120s 批次超时；**覆盖 108 只（2%）且仅 600/603/920 三个代码段 → 样本有偏，不可用于统计**
   - 加深原因：**本地无日线仓库**（`models.py` 无 per-stock 日线表，只有 `quote_snapshot`）→ 每天为每只票重拉 420 天历史，无法摊薄
   - 主源失败会放大问题：东财 kline 挂时每只要先付 connect/read 超时才降级新浪（单只更慢）；09-18 hour16 kline 降级 **556 次** vs hour14/15 各 7 次
   ⇒ 结论：**不是「等数据源恢复即可」**；要收口必须改扫描策略（提预算/提并发 / 建本地日线仓库做增量 / 缩小扫描范围到候选池+持仓 / 异步队列+Worker）

40. **观察期内核对待判定的「日志来源」必须跨归档**：进程重启会**覆盖** `backend-dev.stdout.log`（#20），当日证据可能只在归档里。判别锚点：live 日志首行时间戳 = 该进程启动时间（如 09-19 实测 live 首行 `2026-09-18 14:03` ⇒ PID 25220 于 14:03:35 启动，与 13:49 时的 PID 12412 非同一进程）。**核对必须 live + `backend-dev.stdout.*.log` 合并去重**，否则会漏掉被覆盖时段。

45. **异常文案检索必须用「调用方拼接后的原串」，不能用异常类名**（2026-09-20 亲历，审核端自身出错）：
   `akshare_source.py:509` 把异常拼成 `数据源 {kind} 重试失败: {exc}` —— **只取 `str(exc)`，类名被丢弃**。
   故「备用源返回英文列名 → 抛 `KeyError: 'date'`」这条缺陷，用 `-match 'KeyError'` 检索 **恒为 0 条**，
   而用 `-match 'kline 重试失败'` 得到 **21 条**（16:30:19,884–16:36:43）。
   ⇒ 我上一轮据此宣称「DSH 的 ③ 缺陷不成立」是**错的**：事实为真（21 条），只是根因被误判
     （调用方实为 `hot_money_review` 游资模块，`signal_scan` 当日 `errors:0`）。
   ⇒ 规则：**判「某异常是否存在」时，先读抛异常处的字符串拼接格式**，用拼接串（含中文前缀）检索；
     `str(exc)` 型拼接的日志里**搜不到异常类名**。同理，`result` 文案（如「已降级到备用接口」）比类名可靠。
   ⇒ 配套：核查结论凡「A 不存在」必须写明**检索串原文**与**编码**（见 #39/#44），否则结论不可复核。

46. **`_call_with_timeout` 硬超时修复已落地且实测优于担忧**（2026-09-20 实查，HEAD `96a6731`）：
   - `_accepts_timeout(ak.stock_zh_a_hist) == True`（签名含 `timeout`，无 `VAR_KEYWORD`）
     ⇒ 主源**直接透传 `timeout=5`**，不走 `socket.setdefaulttimeout` 兜底路径
     ⇒ 上一轮「6s 硬切 → 更频繁降级 → 耗时反升」的担忧 **未发生**（#37 该条作废）
   - 耗时（post-fix，n=8）：**均值 8.7s / P50 6.6s / P90 11.8s / 最坏 19.1s**
     （pre-fix：45.5s / 40.0s / 84.0s / 145.6s）→ 降幅约 5 倍
   - ⚠️ **并发无改善**：8 并发 **0.206 只/s**（pre-fix 0.080）、P50 47.6s
     ⇒ 距所需 ~10.3 只/s 仍差 **~50 倍** → 「单靠加并发覆盖不了全市场」结论不变，**瓶颈已转向备用源串行**
   - ⚠️ **live 进程起于 09-18 14:03:35（早于修复提交）→ post-fix 从未在真实调度路径跑过**
     ⇒ 任何参数调优（批 1.5 的 `_PARALLEL_MAX` / `_BATCH` / `_TOTAL` / cron 时刻）**必须等后端重启后实测再定**

47. **分位/均值口径混淆是「数字错误」的高发点 —— 报分位数必须给原始数据集**（2026-09-20 实例）：
   原始升序 `[4.382,4.947,5.284,6.281,6.614,11.021,11.791,19.112]`
   - 均值 = 8.679s、中位 = 6.448s → **P50 = 6.6s**（不是 8.7s —— 8.7s 是均值）
   - P90：线性插值法 = 13.99s；**最近下值法 = 11.79s** → 报「11.8s」时须注明取法
   ⇒ 规则：分位结论旁**必须附原始数据点**；n<10 时 `P90` 与「最大值/次大值」几乎等同，
     **分母口径（n vs n-1）差异可达 20%** → 不确定时同时给「线性法」与「最近下值法」两个数。
   ⇒ 描述统计的三件套（mean / median / P90）**禁止互相代填**；结论段引用均值时须与分位段数字自洽。

39. **提交清单遗漏已连发 5 次 —— 必须用机制而非人工列清单**（2026-09-20）
   历史：依赖遗漏 3 次（`app/factors/`、`factor_registry.py`、`config.py` 致 HEAD `import app.main` 崩）
   + 测试遗漏 2 次（`test_financial_normalization.py`、`test_datasource_stability.py` 致 HEAD 零回归守卫）。
   **其中第 4、5 次是审核端（我）漏的**：第 4 次是 grep 关键词不含 `factor`，第 5 次是**手写清单时没把配套测试列进去**。
   ⇒ 已有机制（见 `AGENTS.md`「提交门禁」）：
   ① 列清单按**依赖闭包**（模块 + 其 import + **配套测试**），禁用关键词 grep；
   ② 干净副本 `import app.main` 必须 OK（挡依赖遗漏）；
   ③ 干净副本跑同一批 pytest，**用例数必须与工作区一致**（挡测试遗漏，②验证不了这个）。
   判据示例：工作区 `test_datasource_stability` 20 例、HEAD 版 16 例 → 必有 4 个测试没提交。

41. 🔴 **`fetch_daily_kline` 未传 `kind` → 断路器/限流器/统计对该链路完全失效 → 主源不可达时每只票付满超时代价**（2026-09-19 定位、09-20 补出后果链）：
   - `akshare_source.py:1014` `self._fetch("kline…", "kline", primary, ttl_seconds=3600, fallback=…, normalize=…)` —— **无 `kind=`**
   - ⇒ `_call_with_retry(kind=None)` → `:476/:488/:493` 三处 `if kind is not None` **全不生效** ⇒ 断路器打开时**不会跳过主源**，每次都硬打
   - **代价公式**：单只耗时 ≈ 主源硬超时（`datasource_timeout=5` +1 = 6s）× `range(1, retry_times+2)` 次（`retry_times=1` → **2 次**）＋ 备源 ≈ **12–15s**
   - 09-20 实测对齐：单只中位 **15.0s** = 2×6s(主源) + 备源；而**备源 URL 本身仅 ~60ms**（`finance.sina.com.cn/realstock/company/shXXXXXX/hisdata_klc2/klc_kl.js`：59/66/1927ms 经代理，57/58/2463ms 直连）
   - ⇒ **"源慢"是误判**：真实顺序是「主源全天不可达（东财 push2his 两路均失败）＋ 断路器失效」
   - **修法（1 行）**：补 `kind="kline"` → 断路器 1 次失败后 30s 内跳过主源直达备源 ⇒ 单只 6s → 亚秒级（量级 60×）
   - 判别口诀：**单只耗时 ≈ 主源超时 × 尝试次数 ⇒ 一定是主源在被反复硬打；若真是源慢，备源裸测也会慢**。备源裸测快 = 病灶在主备切换，不在源。

42. **本机数据源请求走系统代理（2026-09-20 实测）**：WinINET `ProxyEnable=1`、`ProxyServer=127.0.0.1:7897`（Clash 类客户端，PID 21188 监听），`ProxyOverride` = `localhost;127.*;192.168.*;10.*;…` —— **不含 `eastmoney.com` / `sina.com.cn`** ⇒ 行情请求被绕道代理。直接证据：异常原文里出现 `HTTPSConnection(host='127.0.0.1', port=7897)`。
   ⚠️ 注意：WorkBuddy **沙箱另有自己的代理**（如 `HTTP_PROXY=http://127.0.0.1:60265`），与系统代理**不同源** ⇒ 在沙箱测得的"代理"行为**不能代表后端进程**。要判定后端的代理路径，看后端日志的异常原文里出现的是哪个端口。

43. **改了代码但不重启 = 修复未生效**（Python 进程在启动时 load 模块）：2026-09-18 `akshare_source.py` 于 **15:54:33** 被改（硬超时修复），而承载当日 16:50 观察跑的进程 **14:03:35 就启动了** ⇒ 16:50 那次跑的是**改前版本**，硬超时**未生效**（这也解释了为何当日单只 ≈17.6s，比后来实测的 15s 更差）。
   **判别法**：判定"某修复是否生效"永远先比对 **进程启动时间 vs 文件 mtime**（`Get-Process -Id <pid> | Select StartTime` / live 日志首行时间戳 vs 文件 mtime）。**改码后必须重启，否则观测到的仍是旧行为。**

44. **`_call_with_retry` 的 fallback 在 attempt 内部即时尝试**（`akshare_source.py:502-506`）：即每一轮 attempt 里「主源失败 → 立刻试 fallback → 成功即 return」。
   ⇒ 单只耗时 = 主源超时 × **实际 attempt 数** ＋ 备源耗时。故"备源也经常首次失败"时，耗时会翻倍到 2×超时 —— 15s 这个数正好落在"主源 2 次超时"的格子上，可用来反推主源是否真的被打了 2 次。

48. **`hot_money_review` 的基准指数 `000300` 走个股日K接口 → 主源限流时必抛 `KeyError('date')`**（2026-09-20 定位 + 复现，附记 `D:\self\买卖点信号体系_批1_核验附记_游资基准指数date异常根因定位_20260920.md`）：
   - **链路**：`hot_money_review.py:106` `fetch_daily_kline(_BENCH_INDEX='000300', start, end)` —— `_BENCH_INDEX` 是**沪深300**，但 `fetch_daily_kline` 是**个股**接口
   - `_market_of('000300') == 'sz'`（把指数判成深市个股）→ 备用源调 `ak.stock_zh_a_daily(symbol='sz000300')`
   - 新浪 `sz000300` 无对应个股 → 上游 `akshare/stock/stock_zh_a_sina.py:184` `data_df["date"]` 抛 `KeyError('date')`（**空表无列 + 无列存在性校验**）
   - ⇒ 与 `_normalize`（`akshare_source.py:165-172`）**无关**，不是「备用源英文列名丢 date」
   - **复现**（只读）：`fetch_daily_kline('000300','2026-01-01','2026-09-18')` → `DataSourceError("数据源 kline 重试失败: 'date'")`；`fetch_index_daily('sh000300',…)` **OK rows=174**（正确接口）
   - **为何只有 21 条**：主源正常时东财 `secid=0.000300` 返回**空表不抛异常** → 静默走 `None`（无日志）；仅**主源被限流**时才降级新浪 → 抛 KeyError → WARNING。⇒ **21 条是下界，不是失败总数**（静默 None 无日志）
   - **⚠️ 通用诊断盲区（D3）**：`_call_with_retry:505-506` `except Exception as f_exc: last_err = f_exc` → **备用源异常覆盖主源异常**，`:509` 只打 `str(last_err)` → **主源真实失败原因永久丢失**（影响所有 `_fetch` 调用方）
   - **⚠️ 日志归因错误（D2）**：`hot_money_review.py:108-109` 把 stock 与 bench 两次取数包在同一 `try`，日志只打 `stock_code` → **基准失败被记成「某股票回溯失败」**（DSH 由此误判为「备用源列名」，浪费一轮）
   - ⇒ 排查规则：见 `重试失败: {非典型类型}` 时，先看 **`_market_of`/symbol 归属**与**调用方是否把指数传进个股接口**，不要先怀疑列名映射

49. **「人工维护的长文档」不在版本控制 + 脚本原地改写 = 单点毁灭**（2026-09-20 实际事故，`买卖点信号体系_批1_观察期台账.md`）：
   - **事故**：patch 脚本有控制流缺陷（**循环内提前清空输出缓冲**）→ 台账被写坏至 **5 行**；该文件 `git status` = `??`（**未入 git、无任何前像**）→ 只能凭会话上下文重建 79 行
   - **重建虽通过交叉验证**（见下），但**过程不可复现**：属侥幸，不是流程
   - **四条规则**：
     1. **改前必快照**：`Copy-Item <文档> D:\self\.workbuddy\ledger_snapshots\<名>_<YYYYMMDD>.md` 并记 `sha256`（约定位置 `D:\self\.workbuddy\ledger_snapshots\`）
     2. **写盘脚本一律「先收集、后写盘」**：绝不在循环内建/清输出缓冲；写盘只发生一次，且写前校验行长/行数
     3. **台账类文件不入 git 也要有快照基线** —— 「不入版本控制」不等于「不需前像」
     4. **说「可一键回退」前先验前像**：本例 `ledger_patch.json` 的 op2 `old: null` ⇒ **该行无前像**，"可回退"对 op2 **不成立**（op1 有 `old`，可回退）
   - **重建的核验方法**（无前像时的唯一路径）：跨**事故前**多份独立记录交叉比对 —— 本例 09-17 / 09-18 / 09-19 三份 memory 各命中不同数字，且 `570 = hour14(7) + hour15(7) + hour16(556)` **算术自洽**，另与 09-19 回执引用的 `:45` / `探活` 行逐字吻合
   - ⇒ 通用判据：**「文档被写坏后重建」不得以作者自述为准**，必须①找前像（快照/git/临时文件）②无前像则跨源交叉验证 + 校验算术自洽 ③明确标注哪些行无法验证

50. **出指令方必须自证前提时点：把上一轮探活结果当本轮前提 = 指令自带过期前提**（2026-09-20 亲历，**出指令方自身出错**）：
   - **实例**：我 17:07 给 DSH 的指令写「09-18 进程 PID 25220 仍在世，观察为 pre-fix 行为」—— 依据是 DSH **09-19 回执**里的探活结论。实测 09-20 17:35：`PID 25220 GONE`，8000 owner = **PID 15748（2026-09-20 14:39:13 启动，RSS 463.6MB）**
   - 该重启由**另一会话**于 14:32 发起（`D:\self\.workbuddy\memory\2026-09-20.md:81-111`：远程 `8a9e95c` 动运行时代码 → kill 25088 → 14:39 重启）
   - **后果**：若不纠偏，09-21 会被记成「**pre-fix 行为**」，而实际是**post-fix 首次真实调度观察** → 观察结论整段错位（且这恰是批 1.5 参数定值的关键样本）
   - **规则**：
     1. 指令的「前提」段**必须标注采集时点**（如「前提采集：09-19 00:34」），并要求执行端**先重验、再执行**；执行端有权并应当做「前提过期」判定（本例 DSH 做对了）
     2. 依赖 **进程 / 端口 / HEAD / DB 行数 / 日志首行** 的前提**时效极短**（多会话并行下分钟级失效）→ 出指令前**当轮重验**，**禁止复用上一轮结论**
     3. 判别式：前提中凡出现「**仍在世 / 仍为 X / 未变**」字样 → 一律标记为**须重验项**
   - **配套（另一会话已记）**：`2026-09-20.md:113-119`「update 核实是**时点快照**，多会话下会失效」⇒ **代码是最新 ≠ 运行中的实例是最新**；判断是否需重启 = 后端启动时间 vs `backend/**` 最新提交时间（只改测试/文档/`.gitignore` 不需重启）

51. **同一指标存在「记录口径 / 去重口径」两种数，必须显式标注**（2026-09-20 实测）：
   - **实例**：`signal_trigger` 2026-09-18 的「代码前缀分布」
     - `signal_check.py` 输出 = `(('600',33),('603',41),('920',34))` → 合计 **108** = **去重标的口径**（与台账 `:63` 一致）
     - DSH 09-20 新基线写 = `600:44 / 603:63 / 920:42` → 合计 **149** = **记录行口径**
     - 两者**都对**，但新基线未标口径，且与同表 `distinct stock_code = 108` 并列 → **09-21 对比时极易误判为「分布变化」**
   - ⇒ 规则：凡「分布 / 分桶 / 分组计数」，**必须写明口径**（`按记录行` 或 `按去重标的`）并给出**合计值**；合计 = `records` ⇒ 记录口径，合计 = `distinct` ⇒ 去重口径
   - ⇒ 这是继 #47（分位/均值混淆）之后**同族问题的第二次**：**同一指标多口径并存**是数字误导的第一来源

45. 🔴 **akshare 单只取数 74% 耗时在「本地开销」，不是网络**（2026-09-20 v4 实测定案，**全项目共用**）：
   - 实测（`ak.stock_zh_a_daily("sh600519", adjust="qfq")`）：整只 **23,814ms**，而内部**仅 3 个 HTTP 请求、合计 6,124ms（26%）、无重试无重复**
   - cProfile 定位剩余 74%（17,690ms）：**`chardet.pipeline.orchestrator.run_pipeline` 8.96s（59%，2 次）** ＋ **`_SSLContext.load_verify_locations` 4.85s（32%，3 次）** ≈ 91%
   - ⇒ **每次取数都重新做全量字符集探测 + 重建 SSL 上下文**；这两项正常量级约 0.2s / 0.01s，实测慢 **15–150×**
   - **影响面**：所有走 akshare 的链路（Discover / Score / Monitor / signal_scan …）都在付这笔开销
   - **规避**：① 复用 `requests.Session` 与 SSLContext ② **固定已知编码**（新浪 GBK/东财 UTF-8）以跳过 chardet ③ 批量场景改用 `hq.sinajs.cn`（见 #46）
   - **判别口诀**：单只耗时远大于"裸 URL 实测"，且**请求数少而无重试**时，**几乎必是本地开销**，别再往网络/代理/断路器方向查（本项目已连续误判 4 轮）

46. **批量行情接口 `hq.sinajs.cn/list=`（当日 bar 的最优通道）**：`?list=sh600519,sz000001,...` 逗号拼多只，
   实测 **50 只 / 1.41s**（≈36 只/s）、**34 字段**（0 名称、1 今开、2 昨收、3 现价、4 最高、5 最低、8 成交量、9 成交额、29 日期、30 时间），返回 GBK，
   **必须带 `Referer: https://finance.sina.com.cn`**（否则 403）。
   ⚠️ 是**当日实时快照 ⇒ 不复权**；成交量单位与 akshare 日线**需逐字段核对**（手 vs 股）后方可入库。

47. **前复权（qfq）的基准是「最新交易日」** ⇒ **最新一根 bar 的 qfq 价 = 不复权价**（待实测确认）。
   ⇒ 当日 bar 可用不复权快照追加到 qfq 历史段而**当日口径一致**；
   **但除权除息日历史会被整体重算** ⇒ 自建本地日线仓库时**必须识别除权日并重建受影响股票的历史段**，否则 MA/EMA/ATR 等指标**静默失真**。
   **禁止**：不复权当日 bar 直接追加到 qfq 历史却不处理除权。

48. **容量算术模板**（观察期/批 1 用）：`全市场只数 ÷ 预算秒数 = 所需吞吐`。当前 **5564 / 540 = 10.304 只/s**
   ⇒ 任何方案的达标判据都拿这个数比。注意口径要写清：**有效吞吐 = 成功只数 / wall 秒**（用样本数当分子会虚高）。

52. 🔴 **`backend-dev.stdout.log` 的编码随「启动方式」而变，最坏情况中文**不可恢复** —— 中文文案检索应改用 `data/logs/app.log`**（2026-09-21 实测）
   - 当日 `backend-dev.stdout.log` 与其归档 = **UTF-16LE**（BOM `FF FE`，ASCII 间夹 `00`），且**中文已全变成 U+FFFD（实测 2050 个 / 30,008 字符）** → 系 PowerShell 重定向把子进程 GBK 输出按 UTF-8 解码后再写 UTF-16，**信息已销毁，任何解码都救不回**
   - 症状：`decode('utf-16')` 成功且 ASCII 行完好（`[INFO]`、`Started server process` 都能看），但 `'信号扫描' in line` **恒 False** → 会被误判为「当日没跑 / 无异常文案」（沿 #39/#40 的静默假阴性）
   - 判别法：`raw[:2] == b'\xff\xfe'` 且 `raw.count(b'\xfd\xff') > 0` → 中文已丢，**换源，不要在这份日志上做中文结论**
   - ✅ **正解**：`D:\self\data\logs\app.log` = **干净 UTF-8**，同时收录 `apscheduler.*`（`Running job` / `Job ... executed successfully` / `Added job`）与 `app.*` 全部行 → **单文件即可覆盖「调度层成功」与「业务层 summary」两类证据**
   - 仅 stderr 的 tqdm 进度条、`multiprocessing` 栈这类纯 ASCII 场景才需要 stdout/stderr（沿 #26/#30）

53. 🔴 **判据「当日表行数 = `summary.records`」可能**不成立** —— 2026-09-21 实测 912 vs 666**（差 246）
   - `records` 来自 `records += _persist(rows)`，`_persist` 返回**实际 commit 成功条数**；理论上应等于当日行数
   - 实测：summary `records=666`，`signal_trigger` 当日 **912 行**；已排除「写入点不唯一」（全库仅 `signal_scan._persist:191`）、「重复运行」（当日仅 1 次 `Running job`、`锁被占用`=0）、「历史残留」（`created_at` 全落在本次墙钟 16:52:50–17:02:59）
   - 🔎 **首要嫌疑**：`_persist:195` 的 `except Exception: db.rollback()` **静默吞异常、不写日志** → 跨洋 TiDB（`ap-southeast-1`）提交响应丢失造成的 **in-doubt 提交** 会让「服务端已落行、客户端记失败」→ **行数 > 计数** 且**完全无痕**
   - ⇒ 核对时**必须同时报「当日行数」与「summary.records」两个数**，不得只报其一就说「一致 ✓」
   - ⇒ 查因前先给 `_persist` 的 except 分支补日志（当前无任何失败痕迹，无法归因）

54. **配置类改动同样受「改码未重启」约束，必须比对「进程启动时刻 vs 文件 mtime」**（2026-09-21 实例，沿 #43）
   - `config.py:249 kline_scan_local_only` 于 **17:08:15** 由 False 改 True（批1.5 本地优先开关，**且未提交**），而跑当日 16:50 扫描的进程 **16:30:14 就启动了** → 当日 summary 实为 `local_only: False`，**开关未生效**
   - ⇒ 判读 summary/配置开关时，不能说「配置已开」就认为生效；`settings` 在 import 期取值，**只认进程启动时刻的文件状态**
   - ⇒ 配套：**未提交的改动也会被运行中的进程使用** —— 判断「某行为是否生效」既不能只看 git，也不能只看文件，必须看**进程启动时间轴**

52. **「启动项目」前必须先看 watchdog —— 后端由看门狗托管，盲目拉起会被自锁拒绝**（2026-09-23 实例）：
   - **现象**：8000 无 `LISTENING`（只剩 TIME_WAIT），看似「后端挂了、需要启动」
   - **真相**：`D:\self\logs\watchdog.log` **每分钟一行**健康探测，链路为
     `00:45:59 / 00:46:26 / 00:46:51 HEALTH_PROBE_FAIL n/3 : 操作超时` → `00:46:57 HEALTH_BAD pid=32024 -> 拉起`
     → `00:47:03 WATCHDOG_RESTART newpid=35064 archived=20260923-004703` → `00:49:34–00:53:39 COLD_START marker age=150s…395s -> 宽限期内不重复拉起`
     → `00:54:39 OK pid=15984 health=ok`
     ⇒ **后端是看门狗自动重启的**；`00:47–00:54` 这段 8000 不通属**正常的重启空窗**，不是故障
   - **`dev_run.py` 自带互斥**：`127.0.0.1:8000 已被占用：已有后端实例在跑，拒绝重复启动（防双实例双 APScheduler 抢任务锁）` ⇒ 重复拉起会失败，但**若互斥失效则会出现双 APScheduler 抢任务锁**（双跑扫描）
   - **正确启动顺序**：
     1. 读 `D:\self\logs\watchdog.log` 末 20 行 → 是否处于 `COLD_START` 宽限期 / 刚 `WATCHDOG_RESTART`
     2. 查 `8000` LISTENING + `/api/health` + `/api/jobs/status`（`last_run`/`next_run` 是否在推进）
     3. **watchdog 正在拉起 → 等，不要手动起**；只有「watchdog 未运行 且 无宽限标记 且 8000 长期无监听」才手动启动
   - **组件现状（2026-09-23 实测）**：后端 8000 ✓（`dev_run.py`，launcher 与 worker 双进程：`newpid` 是 launcher，实际服务 PID 另算）｜React dev 5173 ✓（`cd web && npm run dev`）｜Redis 6379 ✓｜**Streamlit 8501 已退役，不需启动**（`run_dev.bat` 注释「Streamlit 已退役，不再启动」）｜Qdrant 6333 未起（仅多用户模式需要）
   - **⚠️ `run_dev.bat` 已停用**：内容为 `echo ... 已停用 ... & exit /b 2`，正式入口指向 `start_multi_user.ps1`；但后者硬校验 Redis 6379 **与 Qdrant 6333**（`throw`），本机单机 dev **不要用它**（沿用 #22），直接用 `dev_run.py`

## 调试快速路径

- 数据不显示 → `curl /api/<endpoint>` 直验后端；浏览器 vs 后端分离判定
- LLM 异常 → 先 `light_stats` / `deep_stats` 看命中率，3 次失败自动降级
- 任务调度 → `job_status()` 接口看 `last_*` 时间戳
- 行情缺失 → `sector_snapshot.updated_at` ＋ `sector_refresh_job` cron 日志
- 经验沉淀全链路空 → 查 `pending_experience.status` ＋ `experience COUNT(*)` ＋ `worker_run.last_*`；168 done 但 experience 0 行 = LLM `worth=False` 全被丢（EXTRACT_SYSTEM 宁缺毋滥 ＋ 摘要过薄）
