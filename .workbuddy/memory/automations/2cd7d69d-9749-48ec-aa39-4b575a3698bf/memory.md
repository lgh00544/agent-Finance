# 自动化执行记录 · 批1首跑核对（观察期 17:05）

> 职责：每个观察日 16:50 signal_scan 触发后，探活 → 复制归档 → 解码搜准确文案 → 查云端 TiDB 当日行数与重复组 → 报告 ≤8 行。
> 红线：不改码／不重启／不 commit·push·tag／不手动补跑。详细判据见 `PITFALLS.md` #23-#29、#39-#44。

## 2026-09-17（观察日 1/3）

- 结果：**不通过（外部网络降级，非代码问题）**。扫描 16:50:00 准时触发，16:52:16 因「信号扫描股票池获取失败」（DNS NameResolutionError，sina/eastmoney 域名解析全失败）→ `reason='error:universe'`，未进入批次扫描（「信号扫描批次」0 行）
- 五标准：①❌ ②❌ ③❌（失败文案 1 次）④✅ 重复组 0 ⑤✅ 时长 136.2s < 540s
- 探活：PID 1456 存活（09-16 19:29:44 起，未重启）；`next_run` 已推进 2026-09-18 16:50
- 处置：已向 sir 报告；观察期顺延（09-18 / 09-21 ＋ 追加 09-22）

## 2026-09-18（观察日 2/3）

- 结果：**不通过 —— `reason='total_budget_exceeded'`**
- 五标准：①✅ 成功两行齐 ②✅ `records=149` = TiDB 当日 149 行（全表亦 149）③❌ 异常文案有（「超出总预算 540s」×1 ＋「批次超时」×4）④✅ 重复组 0（`dedup=1` 亦 0）⑤❌ 时长 **625.9s > 540s**
- 探活：PID **25220**（今日 14:03:35 启动，非上次的 1456）；`next_run=2026-09-21 16:50` 已推进
- 覆盖度：4 批仅完成 ~284 只 → 落库 108 只 / universe 5564 = **2%**，仅 `600`/`603`/`920` 三段（样本有偏）
- 根因两层：①东财 kline 主源 8 并发全量限流（hour14/15 各 7 次降级 vs **hour16 = 556 次**）②**容量/参数不匹配**（`_PARALLEL_MAX=8` / 总预算 540s 要求单只 <0.78s；实测单只 ~7s）→ **主源正常也覆盖不了全市场**
- 🔴 P0 附带发现：`signal_check.py:57` / `log_scan.py:22` **硬编码 GBK**，今日日志实为 **UTF-8** → 实跑输出「未发现当日执行痕迹」＋「无异常文案」**两句全错**（静默假阴性）。已报 sir，观察期未改码
- 处置：已向 sir 报告；**建议先插「容量与主备切换」专项批次再重算观察期**，不按单纯顺延处理

## 复用要点（下次执行直接照做）

- **🔴 权威日志已换源：用 `D:\self\data\logs\app.log`（干净 UTF-8）**，不要用 `backend-dev.stdout.log`。09-21 实测后者是 **UTF-16LE 且中文已丢（2050 个 U+FFFD）**，中文文案检索全 0。`app.log` 同时含 `apscheduler.*`（Running job / executed successfully）与 `app.*`（summary）→ 单文件覆盖两类证据。判别坑档：`raw[:2]==b'\xff\xfe'` 且 `raw.count(b'\xfd\xff')>0`。详见 PITFALLS #52
- **编码不可硬编码**：先试 `utf-8`，用「是否含『数据库』/『信号扫描』marker」判定；09-16/17 为 GBK，09-18 起 UTF-8，09-21 的 stdout 为 UTF-16（不可用）
- **不要只信 `signal_check.py`**（GBK 硬编码，会误报「未执行＋无异常」）；以「`next_run` 已推进」＋「正确解码 grep」交叉验证。其 `[4] DB` 段不受影响
- **时长口径**：`Running job "买卖点信号扫描"` 行 → `信号扫描结束` 行（批超时场景下「首批次行」会少算，PITFALLS #44）
- **窗口**：工作日 17:05；`misfire_grace_time` 对内存 jobstore 无效（PITFALLS #29）
- **归档**：`Copy-Item backend-dev.stdout.log backend-dev.stdout.<YYYYMMDD-HHmm>.log`（**复制不可改名**，进程持句柄）
- **TiDB**：`D:/self/.venv/Scripts/python.exe` + `.env`(`D:/self/.env`) + pymysql 带 `ssl={"ssl":{}}`；沙箱 Bash 的 PATH 常损坏 → 也可直接用 `D:/self/.venv/Scripts/python.exe <脚本>` 落盘再 Read
- **判定口径**：`reason ∈ {error:universe, empty_universe, total_budget_exceeded}` 即不通过；`dropped` **不含**未进入批次的剩余股票 → 覆盖度须手算
- **必须同时报「当日行数」与「summary.records」两个数**（09-21 实测 912 vs 666 不一致，PITFALLS #53）

## 2026-09-21（观察日 · 首跑）

- 结果：**不通过** —— `reason='total_budget_exceeded'`，时长 **779.7s > 540s**，异常文案 ×2（超预算 1 + 批次超时 1）
- 五标准：①**records 666 ≠ 当日表 912 行** ✗ ②异常文案有 ✗ ③重复组 **0** ✓ ④时长 779.7s ✗ ⑤reason 超容集 ✗；`批次失败/股票池失败/锁占用/Traceback` 全 **0** ✓
- 探活：跑扫描的是 **PID 34872**（16:30:14 起）；**17:08–17:19 反复冷启动**（watchdog COLD_START ×4），17:31:38 health=200 恢复；`next_run` 已推进 **09-22 16:50**
- 覆盖：`universe=5564`、仅 4 批（offset 0~2000）、未进入的 **3564 只不计入 dropped**；`local_bars=1556 / remote_bars=82 / coverage_pct=84.5 / stale=700 / incomplete=164`
- 🔴 两处新发现（当日另一会话守护脚本未覆盖）：
  - **A**：`records=666` ≠ 当日 **912** 行（差 246）→ 写入点唯一、仅 1 次 Running、`created_at` 全在墙钟内、id 连续 30001–30947；同窗口仅只读脚本。**未定因**，首要嫌疑 `_persist` 的 `except: db.rollback()` 静默吞异常（in-doubt 提交）
  - **B**：`local_only: False` —— `config.py:249` 于 **17:08:15** 才改 True（且未提交），晚于进程启动 16:30:14 → **批1.5 本地优先开关当日未生效**，09-22 才是首次真实样本
- 数据源（当日全天）：`指数行情获取超时`×40（末 17:30:28）、`snapshot 连续 3 次失败`×7（末 17:30:30）、`kline 已降级`×154（扫描窗口内密集）、`信号扫描股票池获取失败`**×0** → 今日失败属**预算/容量**，非数据源获取失败
- 处置：已向 sir 报告；未改码、未重启、未 commit、未补跑。产出 `D:\self\买卖点信号体系_批1_观察核对_值守补充_20260921.md`

## 复用要点（下次执行直接照做）

- **编码不可硬编码**：先试 `utf-8`，用「是否含『数据库』/『信号扫描』marker」判定；今日（09-18）为 UTF-8，09-16/17 为 GBK。解码错只会静默乱码 → 中文文案全 0，ASCII（`signal_scan`/`Traceback`）仍命中 → 半边对半边错的陷阱
- **不要只信 `signal_check.py`**（GBK 硬编码，会误报「未执行＋无异常」）；以「`next_run` 已推进」＋「正确解码 grep」交叉验证。其 `[4] DB` 段不受影响
- **时长口径**：批超时场景下「首批『信号扫描批次』行」= 超时告警行（比分批开始晚 120s）→ 会少算；**应以 `Running job "买卖点信号扫描"` 行 → `信号扫描结束` 行**
- **窗口**：工作日 17:05；`misfire_grace_time` 对内存 jobstore 无效（PITFALLS #29）
- **归档**：`Copy-Item backend-dev.stdout.log backend-dev.stdout.<YYYYMMDD-HHmm>.log`（**复制不可改名**，进程持句柄）
- **TiDB**：`D:/self/.venv/Scripts/python.exe` + `.env`(`D:/self/.env`) + pymysql 带 `ssl={"ssl":{}}`
- **判定口径**：`reason ∈ {error:universe, empty_universe}` 即不通过；追加 `total_budget_exceeded` 亦不通过；`dropped` **不含**未进入批次的剩余股票 → 覆盖度须手算
- **沙箱**：Bash PATH 常损坏 → 核查走 PowerShell，且 PowerShell stdout 不回显 → `Out-File -Encoding utf8 <tmp>` 后 Read（PITFALLS #33/#34）
