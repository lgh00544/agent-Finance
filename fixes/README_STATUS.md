---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 4f33c877785187ed9e342c638762db33_953fefe7bb2a11f1a526525400cd780f
    ReservedCode1: WnA5gzVVJuIHir8LTFcnBT/ZvKIMeVJClnFiwobKaQr5aq+mRGZEO8NCaOWj9O43OYQx5HOZtPklQacAaxGOuGy4T3yMfKuHYqrUbJkVNoNu8HzxH+vVGSL8OOnHW4sF5V//VH9ymzWLvWsHJBoyZoAU6chMyRqmZXw58hmrQuz4d40k1jUYUdrgVBE=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 4f33c877785187ed9e342c638762db33_953fefe7bb2a11f1a526525400cd780f
    ReservedCode2: WnA5gzVVJuIHir8LTFcnBT/ZvKIMeVJClnFiwobKaQr5aq+mRGZEO8NCaOWj9O43OYQx5HOZtPklQacAaxGOuGy4T3yMfKuHYqrUbJkVNoNu8HzxH+vVGSL8OOnHW4sF5V//VH9ymzWLvWsHJBoyZoAU6chMyRqmZXw58hmrQuz4d40k1jUYUdrgVBE=
---

# 逐项修复状态（dsh 会话核验 → 补丁落地）

状态口径：
* **已产出补丁** —— `parts/` 里有精确 old→new 替换，`apply_fixes.py --apply` 后即生效；
* **判定不成立 / 不修复** —— 按会话核验结论无需改动；
* **部分/无法定位** —— 明确写出哪一部分没做及原因。

| 编号 | 修复状态 | 修改文件 | 一句话说明 |
| --- | --- | --- | --- |
| P0-1 | 已产出补丁 | `backend/app/services/signal_scan.py` | 新增 `_limit_pct()`：先按号段定基础涨跌幅（北交所 4xx/8xx/92x=30%、双创 300/301/688/689=20%、沪 B 900xxx/深 B 200xxx=10%），再**只对主板 ST** 叠加 5%，修掉「ST 一律 5%」与「900xxx 当北交所」两个误判；同时新增 `_code6()` 归一化代码 |
| P0-2 | 已产出补丁 | `backend/app/services/signal_scan.py` | `_persist()` 改「批量 flush + 单事务 commit」并用 `SAVEPOINT`（`begin_nested`）逐行幂等：**只捕获 `IntegrityError`**（唯一约束=重复写入），连接断开/字段约束/列超长等一律带堆栈上抛，不再被当成重复写入静默丢弃 |
| P0-3 | 已产出补丁 | `backend/app/services/signal_scan.py` | `_scan_batch()` 去掉 `with ThreadPoolExecutor`（其 `__exit__` 会二次 `shutdown(wait=True)` 架空 540s 预算），改显式 `shutdown(wait=False, cancel_futures=True)` 放在 `finally` |
| P0-4 | 已产出补丁（**判定需修正**） | `backend/app/datasource/http_client.py` | 改为「锁内预约起跑时刻 + 锁外 sleep」，消除「持锁 sleep」这一反模式；**实测吞吐与最小间隔完全不变**（8 线程 0.351s vs 原 0.356s），因此**未**采用会瞬时突破 `min_request_interval`（默认 0.5s）的突发令牌桶，理由见 §3 |
| P0-5 | 已产出补丁 | `backend/app/scheduler/jobs.py` | 新增 `_leader_demote()`（先关闸置 `_leader_acquired=False` 再停本实例 APScheduler）、`_leader_owned()/_ensure_leader()` 执行前 fencing 校验（经 `_add_job()` 统一包装全部 34 个任务入口，避免漏一个任务漏一个脑裂口）、`_leader_stop` 与续约终止事件拆分为两个 Event；**单用户 + memory 缓存下多 worker 重复调度属架构限制，已在代码注释中如实声明（未根治）** |
| P0-6① 百分号不换算 | 判定不成立 → 不修复 | — | `data_adapter.num()` 已 `replace("%", "")`，不存在该问题 |
| P0-6② 中文数量单位 | 判定不成立 → 不修复 | — | 同上（有条件成立已排除） |
| P0-6③ 复权口径未校验 | 已产出补丁 | `backend/app/services/factor_ic.py` | 新增 `KLINE_ADJUST` 口径门禁：`_local_kline()` 遇本地异口径返回 `None`（自动回退远端 qfq，**不丢样本**）、`_warm_local()` 拒绝异口径回写（避免把本地库搅成 `mixed_adjust`）、远端返回异口径才整票弃用；口径元数据读 `kline_store.series_adjust()`，读不到按「未知不拦截」处理，不编造口径 |
| P0-6④ 财报前视 | 已产出补丁 | `backend/app/factors/data_adapter.py`、`backend/app/services/factor_ic.py` | `latest()` 增加 `as_of` + 披露滞后约束，**按报告期分类**给缓冲（年报 12-31→120 天、一季报 03-31→30 天、中报 06-30→62 天、三季报 09-30→31 天，未识别报告期退回保守 120 天，可用 `disclosure_lag_days=<int>` 强制统一值）：只接受「报告期 + 缓冲 ≤ 快照日」的期次，全部不合格时返回 `{}`（绝不退回 `items[-1]`）；`as_of` 缺省时行为与原来逐字一致；`factor_ic` 采集时把快照日作为 `as_of` 传入。**注**：初版按核验文字「统一保守 120 天」实现，复核后改为分类缓冲 —— 统一 120 天会把「4 月底已披露的一季报」误判成 7 月底才可见，5/6/7 月快照退回上年年报，那不是保守而是口径错误（会让 f11/f18–f21 的 IC 建立在不存在的「数据陈旧」上） |
| P0-7 | 已产出补丁（**分位数一半无法定位**） | `backend/app/services/factor_ic.py` | 归因样本净化：新股前 5 个交易日、停牌占位行（量能为 0/空）、一字板（`high==low==close`，含目标日）逐样本剔除，ST/退市整理期经 `select_st_codes()` 整票剔除（`exclude_codes` 为可选参数，向后兼容）；**「ST 排除出全市场分位数」无法完全落地**：分位数由 `DataAdapter.extra["quantile_values"]` 传入，其生产侧不在本仓库（全仓库仅 `tests/test_score_factors.py` 用到该字段） |
| M1 | 已产出补丁 | `backend/app/services/signal_scan.py` | `_persist(rows)` 由 try 之外移入 try：DB 会话创建失败/连接断开不再中断整个全市场扫描 |
| M2 | 已产出补丁 | `backend/app/services/signal_scan.py` | 交易日历可用日不足 10 天时**显式告警**并把冷却窗口放宽到 30 个自然日（只放宽不回缩），不再静默缩短冷却 |
| M3 | 已产出补丁 | `backend/app/services/signal_scan.py` | 股票池代码经 `_code6()` 归一化，修掉 `numpy.float64` → `'600000.0'` 脏代码（它同时让所有 `startswith` 前缀判定失效） |
| M4 | 已产出补丁 | `backend/app/services/signal_scan.py` | 7 处 `except Exception` 日志补 `exc_info=True` |
| M5 | 已产出补丁 | `backend/app/services/signal_scan.py` | `eligible` 下夹紧到 0、`coverage_pct` 上夹紧到 100，消除负覆盖率 |
| M6 | 已产出补丁 | `backend/app/scheduler/jobs.py` | 新增 `_cn_now()/_today_cn()`（`ZoneInfo("Asia/Shanghai")`）并替换全部 `time.strftime(...)`/`datetime.now()` 用法；写 DB 的 `row.last_run` 用 `_cn_now().replace(tzinfo=None)` 保持 naive 列契约 |
| M7 | 已产出补丁（**定位修正**） | `backend/app/scheduler/jobs.py` | 复核发现 `services/kline_ingest.py` **内部没有任何锁代码**，真实调用点是 `jobs.py::kline_ingest_job`：TTL 3600→1800（崩溃残留死锁最长堵 30 分钟而非 1 小时），并改用 `acquire_lock_owner/release_lock_owner` 带 owner 校验（不再误删别人刚抢到的锁） |
| M8 | 已产出补丁 | `backend/app/scheduler/jobs.py` | 27 个任务的 `misfire_grace_time` 由统一的 3600 按任务性质收紧（密集窗口 600s / 重任务 900s / 低峰夜间 1800s），避免进程恢复后一小时内的错过任务集体补跑打爆数据源 |
| M9 | 已产出补丁 | `backend/app/scheduler/jobs.py` | 新增统一注册入口 `_add_job()`：单任务 `add_job` 失败只 `logger.error(..., exc_info=True)` 降级，不再让整个 `start_scheduler()` 起不来；并统一兜底 `coalesce=True/max_instances=1` |
| M10 | 已产出补丁 | `backend/app/datasource/http_client.py`、`backend/app/datasource/us_quote.py` | `get()` 默认 `raise_for_status=True`（4xx/5xx 不再被当数据解析），保留 `raise_for_status=False` 逃生口；`us_quote` 唯一按 `status_code` 分支的调用方显式关闭校验以保持原语义 |
| M11 | 已产出补丁 | `backend/app/datasource/http_client.py`、`backend/app/datasource/akshare_source.py`、`backend/app/services/kline_ingest.py` | 共享 Session 挂 `HTTPAdapter`（连接池 20 + 仅 GET/HEAD 的 connect/read/429·5xx 指数退避重试）；个股新闻裸 `requests.get(..., timeout=15)` 拆成连接/读取超时（保留直连，因为该模块测试用 `monkeypatch.setattr("requests.get", ...)` 打桩）；kline 快照自建会话挂连接池重试（调用方传入的会话不动） |
| M12 | 已产出补丁 | `backend/app/db/session.py`、`backend/app/core/config.py` | 连接池按「信号扫描 8 线程 + APScheduler 并发」扩容：`pool_size=20 / max_overflow=20 / pool_timeout=30 / pool_pre_ping=True`（非 SQLite 追加 `pool_recycle=1800`），4 个新配置字段可外部调节；SQLite 的 WAL/PRAGMA 分支未动 |
| M13 | 已产出补丁 | `backend/app/core/auth.py`、`backend/app/api/routes.py` | 新增线程安全 `LoginGuard`（连续失败 5 次锁 15 分钟，维度＝用户名 + TCP 对端 IP，成功登录清零，带滑动窗口清理防内存膨胀；刻意不信任 `X-Forwarded-For`）；登录接口被锁定返回 429 |
| M14 | 已产出补丁 | `backend/app/core/config.py`、`backend/app/api/routes.py`、`backend/app/db/repo.py` | 注册门槛双开关：`register_invite_code`（非空则校验，否则 403）与 `register_require_approval`（true 则 `is_active=False` 待审核、不签发 token）；**两项默认关闭 = 与旧行为逐行等价**，`repo.create_user` 增加关键字参数 `is_active=True` 保持既有调用方不变 |
| M15 | 已产出补丁 | `backend/app/scheduler/jobs.py` | `maintenance_job` 增加 `_purge_expired_sessions()`：清理过期/已撤销的 `UserSession`（保留 7 天审计窗口），单项失败只告警；清理条数进日志 |
| M16 | 已产出补丁（**需配套清扫，见下**） | `backend/app/db/models.py`、`backend/app/core/auth.py` | `_now()` 由 `datetime.now()`（服务器本地时区）改为 `datetime.now(UTC+8).replace(tzinfo=None)`，与调度/行情/展示口径统一，同时保持全库 naive `DateTime` 列契约；**配套**把 `auth.issue_token` 的 `expires_at` 从 `datetime.now()` 改为 `_now()` —— 否则 UTC 容器里 24h 会话会变成 16h（`expires_at` 是 UTC 口径、`repo.get_user_by_token` 用北京口径比较） |
| M17 | 已产出补丁 | `backend/app/api/routes.py`、`backend/app/services/chat_handlers.py`、`backend/app/scheduler/jobs.py` | 删除 3 处 `if False:` 不可达死代码（同花顺两个 410 接口 + `_fmt_pnl` + `jobs.py` 3 条 `ths_pnl` cron 停注册块），改为显式下线注释并写明恢复路径，不再留裸 `if False` 守卫 |
| M18 | 判定不成立 → 不修复 | — | — |
| M19 | 已产出补丁 | `backend/app/factors/data_adapter.py` | 新增 `_norm_sector()`（去全部空白 + NFKC 全半角归一 + 小写 + 去「行业/板块/概念/指数/产业」尾部后缀）与两级匹配：归一化精确 → 唯一子串兜底；仍不唯一/无匹配才返回 `{}`，并把原因写进 `extra["sector_match"]` |
| M20 | 已产出补丁 | `backend/app/factors/data_adapter.py` | `find()` 增加来源白名单 `_KEY_SOURCES`（只约束已知会产生量纲/同期性歧义的 key：行业名、`main_net_inflow`、`amount` 等），并新增 `find_in(source_name, *keys)` 供调用方显式指定来源；未列出的 key 行为完全不变 |

## 改动文件清单（共 15 个）

| 文件 | 涉及编号 |
| --- | --- |
| `backend/app/services/signal_scan.py` | P0-1, P0-2, P0-3, M1, M2, M3, M4, M5 |
| `backend/app/factors/data_adapter.py` | P0-6④, M19, M20 |
| `backend/app/services/factor_ic.py` | P0-6③, P0-6④, P0-7 |
| `backend/app/datasource/http_client.py` | P0-4, M10, M11 |
| `backend/app/datasource/us_quote.py` | M10 |
| `backend/app/datasource/akshare_source.py` | M11 |
| `backend/app/services/kline_ingest.py` | M11 |
| `backend/app/db/session.py` | M12 |
| `backend/app/core/config.py` | M12, M14 |
| `backend/app/scheduler/jobs.py` | P0-5, M6, M7, M8, M9, M15, M17 |
| `backend/app/core/auth.py` | M13 |
| `backend/app/api/routes.py` | M13, M14, M17 |
| `backend/app/db/repo.py` | M14 |
| `backend/app/db/models.py` | M16 |
| `backend/app/services/chat_handlers.py` | M17 |

## 未修复 / 部分修复（如实列出）

| 项 | 范围 | 原因 |
| --- | --- | --- |
| P0-7 的「ST 排除出**全市场分位数**」 | 未修复 | 全市场分位数的生产侧（`extra["quantile_values"]`）不在本仓库，全仓库仅 `tests/test_score_factors.py` 引用该字段；不编造生产侧 API。已在 IC/归因样本口径上完成 ST/退市剔除 |
| P0-4 的「令牌桶/滑动窗口让 8 线程并发」 | 部分修复（有意） | 实测证明「持锁 sleep」不改变吞吐（0.351s vs 0.356s），等效速率＝1/min_interval 正是「最小间隔限流」的既定语义；若真给突发容量，会瞬时打出多个 0 间隔请求，与 `datasource_min_request_interval=0.5` 的反爬意图冲突。故只消除持锁 sleep，不放开速率。详见 `README.md` §3 |
| P0-5 的「单用户多 worker 重复执行」 | 部分修复（架构限制） | 单用户 + memory 缓存下根本没有跨进程协调手段（内存锁只在进程内有效），跨进程根治必须 `multi_user_enabled=True` + `CACHE_BACKEND=redis`；代码注释已如实声明，未谎称根治 |
| M18 | 不修复 | 会话核验判定不成立 |
| M12 的连接泄漏审计 | 未做 | 扩池只是把「取连接立即报错」变成「最多等 30s」；若线程内存在 Session 未关闭的泄漏，需另行专项审计（本次未做，已在报告中标出） |

## 落地前请先决定这 3 件事（不是补丁错误，是需要你拍板的取舍）

### 1. M16 改 `_now()` 会与残留的裸 `datetime.now()` 形成混用（**建议同批清扫**）

M16 把 `models._now()` 改成北京口径后，**同批必须**把「与库内时间列做比较、却仍用裸 `datetime.now()`」的位置一起改口径
（`issue_token` 的 `expires_at` 已作为配套修好，否则 UTC 容器里 24h 会话会变成 16h）。
未清扫的位置（子代理逐行排查所得，供你决定是否同批处理）：

* `backend/app/db/repo.py`：990, 1195, 1721, 1789, 1942, 2498, 2507, 3687, 4446–4475, 4533, 4605, 4615, 4710
  （重点 4615/4710：`Experience.created_at/expires_at` 的比较）
* `backend/app/scheduler/jobs.py`：116, 350, 391, 737, 752 —— **M6 补丁已覆盖 116/350/391/737/752**
* `backend/app/system_map/health.py`:138（租约过期判断）
* `backend/app/services/sector_snapshot.py`:99、`track_verify.py`:119、`memory_curator.py`:108、
  `paper_execution.py`:166、`sector_forecast_stats.py`:24、`vector_store.py`:217

风险判断：本机（Windows）时区就是 UTC+8，**这些混用是潜伏的**，只有在 `TZ=UTC` 的容器里才爆发。
若你的部署时区不是 UTC+8，请务必同批清扫；否则 M16 会让「以 `_now()` 落库、以 `datetime.now()` 比较」
的那几处从「一致」变成「差 8 小时」（其余以 `market_hours.CN_TZ` 为准的地方则从「差 8 小时」变成「一致」）。

### 2. M12 只是扩容，不是修泄漏

`pool_size=20 / max_overflow=20 / pool_timeout=30` 把「取连接立即报错」变成「最多等 30s」。
若信号扫描 8 线程路径上存在 **Session 未关闭导致连接未归还** 的泄漏，扩池只会把
`QueuePool limit reached` 推迟出现。建议另开一项「线程内 DB 会话生命周期」审计。

### 3. M11/M11c 引入了 `urllib3` 的直接 import

补丁里用了 `from urllib3.util.retry import Retry`（`urllib3` 是 `requests` 的硬依赖，本机 2.7.0 已装），
但 `requirements.txt` 未显式声明。若你的依赖清单要求显式，请补一行 `urllib3>=1.26`。
*（内容由AI生成，仅供参考）*
