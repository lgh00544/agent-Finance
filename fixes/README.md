# dsh 修复包：Review 问题清单落地（P0 / M 项）

本目录是 **补丁包**，不是已落地的改动。原因见 §0。

---

## 0. 为什么是补丁包而不是直接改源码（会话环境事实）

本会话的 dsh 沙箱**只允许写会话工作区**（`...\Marvis\User\...\workspace\conv_.../temp`），
而目标仓库 `D:\space\self\self` 在工作区之外，因此：

| 尝试 | 结果 |
| --- | --- |
| `write` 工具写 `D:\space\self\self\.dsh_write_test.tmp` | `[sandbox: file access denied under workspace-write mode]` |
| 同上 + `sandbox_permissions=danger-full-access` | `escalation requires approval, but no approval channel is available`（headless 无审批通道 → fail closed） |
| pwsh 写 `D:\space\self\self\...` | `PermissionDenied`（pwsh 运行在只读沙箱、ConstrainedLanguage 模式） |
| pwsh 写 `%TEMP%` / 相对路径 | 同样 `PermissionDenied`；子进程甚至**看不到**工作区路径（`os.path.isdir` = False） |
| `python -m tempfile.gettempdir()` | `FileNotFoundError: No usable temporary directory found`（全部候选目录都不可写） |
| `python -m pytest ...` | 无法运行：pytest capture 需要临时文件 → `FileNotFoundError`；`-s -p no:cacheprovider` 亦无法稳定启动 |

结论：**本会话无法就地修改源码，也无法运行 backend/tests**。可用能力只有两类：
① 用 read/grep 精确读取仓库、②用 `python -c` 跑**纯内存**逻辑验证（不落任何文件）。
所以修复以 `parts/*.py` 的「精确 old→new 替换」形式交付，由 `apply_fixes.py` 落地。

## 1. 落地步骤

```powershell
# 0) 把本修复包拷到项目里（例如 D:\space\self\self\fixes\）
#    默认项目根目录已写死为 D:\space\self\self，可用 --project 覆盖

# 1) 只读演练：校验锚点唯一性 + 替换后 compile() 语法（不写任何文件）
D:\space\self\self\.venv\Scripts\python.exe fixes\apply_fixes.py --check

# 2) 落地：逐文件备份为 <file>.bak-<YYYYMMDD> 后写回
D:\space\self\self\.venv\Scripts\python.exe fixes\apply_fixes.py --apply

# 3) 语法复核
cd D:\space\self\self
.venv\Scripts\python.exe -m compileall -q backend\app

# 4) 回归
.venv\Scripts\python.exe -m pytest backend\tests -q

# 5) 修复点自检（专项断言，见 verify_fixes.py）
.venv\Scripts\python.exe fixes\verify_fixes.py
```

* `--check` / `--apply` 的安全性：
  * 锚点缺失、锚点出现多次、替换前后相同、替换后 `compile()` 语法错误 → **默认「全或无」**：
    一个文件都不写（本补丁包跨文件有依赖，例如 `session.py` 要用 `config.py` 新增的
    `db_pool_size`、`routes.py` 要用 `config.py` 的注册门槛开关与 `auth.py` 的 `LoginGuard`，
    半套补丁会让服务起不来）。确需只写通过的文件时显式加 `--force-partial`；
  * 已应用的项记为 `skipped`，脚本可重复执行；
  * 备份为**二进制逐字节**副本，且已存在则复用（同日重复执行不会覆盖首次备份）；
  * 写入按各文件**原有换行风格**（仓库里多为 CRLF、`http_client.py` 为 LF），
    diff 只包含真正改动的行，跨平台（Windows/Linux）执行结果一致；
  * 片段文件本身若有语法/结构错误，脚本会明确报错并退出，不会静默跳过。

## 2. 逐项修复状态

见 `README_STATUS.md`（逐项表）；`parts/` 目录即全部改动内容。

## 3. 本会话已完成的**实测**验证（证据）

这些验证全部用 `D:\space\self\self\.venv\Scripts\python.exe -c`（纯内存，不落文件）完成。

| 编号 | 验证内容 | 结果 |
| --- | --- | --- |
| P0-1 | 新涨跌幅判定 18 个用例（创业板 ST 20%、688/689 ST 20%、900xxx/200xxx 沪B深B 10%、920/430/830/871 北交所 30%、主板 ST 5%、float64 代码、带后缀代码） | 18/18 通过（其中 2 条初始期望值是我写错，非代码问题） |
| P0-2 | SAVEPOINT 幂等落库模式（SQLAlchemy 2.0.44 + SQLite 真库）：只捕获 `IntegrityError`、其余异常上抛、重复执行幂等 | 通过：`done=2`（1 行已存在 + 1 行批内重复被跳过）、提交 3 行、重跑 `done=0`、`TypeError` 正常上抛 |
| P0-3 | `with ThreadPoolExecutor` vs 显式 `shutdown(wait=False)` 在批超时后的返回耗时 | 旧 2.00s / 新 0.22s → 判定成立且修复有效 |
| P0-4 | 旧 `RateLimiter.wait()` 实测：8 线程 × `min_interval=0.05` | 0.356s（完全串行化）→ 判定成立；但新实现（预约式）实测 **0.351s**，速率不变 —— 说明「等效 QPS=1/min_interval」是限流器既定语义而非缺陷，故只消除持锁 sleep，见 §3 的修正说明 |
| M2 | 日历充足 → 取 10 个交易日；日历为空 → 显式放宽到 30 个自然日（只放宽不回缩） | 通过 |
| M3 | `_code6` 归一化：`600000.0`→`600000`、`600000.SH`→`600000`、`000001`→`000001`、`''`→`''` | 通过 |
| P0-6④ | 旧 `latest()` 真实模块复现：`as_of=2026-04-01` 时取到尚未披露的 `2026-03-31` 一季报 | 复现成功（前视成立） |
| P0-6④ | **新**披露滞后逻辑 16 条断言（年报 120 / 一季报 30 / 中报 62 / 三季报 31 天分类缓冲、截止日当天含/前一天不含、5·6·7 月仍能用一季报、未知报告期退回 120 天、显式覆盖、非法 `as_of` 不过滤、无日期退回 `items[-1]`、空输入） | 16/16 通过 |
| P0-3 归因样本 | 子代理用 `tests/test_factor_ic.py` 的 `_frame()`（`high==low` 但 close 递增、volume=100）验证脏样本过滤器**不误触发** | 既有 collect 测试期望样本数不变 |
| M19 | 旧 `DataAdapter.sector()` 真实模块复现：`industry="半导体"` vs `board_name="半导体行业"` | 返回 `{}`（静默空值复现成功） |
| M16 | `models._now()` 与本机 UTC+8 墙钟对比 | 差 0.0s；本机时区即 UTC+8，故该缺陷在本机**潜伏**，只在 TZ=UTC 的容器里爆发（M6 同理） |

### 关于 P0-4 的判定修正（重要）

会话核验结论里 P0-4 写的是「持锁 sleep 使多线程串行化，等效 QPS=1/min_interval，应改令牌桶让 8 线程并发」。
实测后需要修正为：

* 「等效 QPS = 1/min_interval」**正是最小间隔限流器的既定语义**，不是缺陷（老实现 0.356s vs 新实现 0.351s，吞吐一致）；
* 请求本身并不在锁内发出（`wait()` 返回后才发请求），所以并发并没有被锁吃掉；
* 唯一真实缺陷是「在持锁状态下 sleep」这一反模式（对端 sleep 期间锁持有 0.279s → 修复后 0.000s），
  只影响锁的卫生，不影响吞吐；
* 若真改成带突发容量的令牌桶，会瞬时打出多个 **0 间隔**请求，与
  `datasource_min_request_interval = 0.5s` 的反爬意图直接冲突（更可能触发源站封禁）。

因此 P0-4 的落地是「锁内预约起跑时刻 + 锁外 sleep」：**严格保持平均速率与最小间隔不变**，
只消除持锁 sleep。如需真正放开突发，请单独评估源站限流策略后再调 `RateLimiter` 容量参数。

### 关于换行风格（CRLF）

仓库里绝大多数目标文件是 **CRLF**（只有 `datasource/http_client.py` 是 LF）。
`apply_fixes.py` 会逐文件探测原有换行风格，写入时用 `newline=<原风格>`，
锚点比较前也把两侧 CRLF 归一为 LF —— 因此在 Windows/Linux 上 `--apply` 都**不会**把整文件行尾改写，
diff 只包含真正改动的行。

## 4. 本会话**无法**验证的部分（如实说明）

* **backend/tests 全量回归未运行**：沙箱无可用临时目录，pytest 起不来（原因见 §0）。
  已在 §3 用等价的纯内存断言替代了纯逻辑部分；涉及 DB/HTTP/调度的集成行为
  必须在你的机器上跑步骤 3~5 才能确认。
* **锚点校验做了两级**：① 用 `read` 逐行比对 + `grep` 确认每个锚点首行在目标文件中唯一
  （`signal_scan.py` 的全部 11 个锚点块 + 其他文件的抽样）；② 对 p03 片段覆盖的 6 个文件，
  用项目 venv **内联复现 applier 算法**（`read_text` → `count(old)==1` → replace → `compile()`）：
  12/12 全部 applied、6 个文件 `RESULT OK`。其余片段的完整锚点匹配由 `--check` 在落地前把关。
* 未在真实 TiDB/Redis 上验证 SAVEPOINT 与 leader fencing：`SAVEPOINT` 在 TiDB 上支持，
  但若生产库拒绝 `SAVEPOINT`，P0-2 的 `db.flush()` 会抛出**非** `IntegrityError` 的
  数据库异常并向上冒泡（这是**有意**的：宁可见错，也不再静默丢数据）。
* 未验证 `pool_maxsize` 调整对真实并发的影响（需压测）。

## 5. 未修复项

见 `README_STATUS.md` 中状态为「未修复」的行，均附原因。
