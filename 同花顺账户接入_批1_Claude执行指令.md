# 同花顺账户接入 · 批1（数据通道）· Claude Code 执行指令

> 复制本文件给 Claude Code 执行。**需求背景/目的/风险详见 `D:\self\同花顺账户接入_方案.md`（§1-§5、§6 数据契约）。** 本指令只给执行动作，背景不重抄。
> 先读方案 §1-§5 + §6，再执行。

## 一、目标
在 `D:\self` 后端新增**同花顺真实账户今日盈亏 + 上证指数**采集并入库，暴露 `GET /api/account/pnl`。默认关闭（`ths_pnl_enable=false`），不改变现有行为。

## 二、架构约束
- 数据链路：同花顺 `time_share`/`getQuotes` → 新服务 `backend/app/services/ths_pnl.py` → 新表 `account_pnl_snapshot` → `backend/app/scheduler/jobs.py` 定时采集 → `backend/app/api/routes.py` 暴露 `/account/pnl`。
- 只做数据拉取 + 归一化 + 落库，**不做任何研判、不修改交易规则、不超载既有 Agent**。
- 所有 SQL 走 `backend/app/db/repo.py` 网关（铁律），禁止在服务里写裸 SQL。
- Cookie/密钥**禁止打印日志或写入任何输出**（红线）。

## 三、规则
1. **配置**（`backend/app/core/config.py`，pydantic `Field` 风格）新增：
   ```
   ths_pnl_enable: bool = False          # 总开关，默认关
   ths_pnl_cookie: str = ""               # 直接给 Cookie（可选，绕过 DSH 文件）
   ths_pnl_cookie_file: str = r"D:\AI\Deepseek Harness\.dsh\.credentials.yaml"
   ths_pnl_poll_seconds: int = 20         # 采集间隔（交易时段）
   ths_pnl_user_id: str = ""              # 可选；空则从 Cookie 的 userid= 提取
   ths_pnl_fund_key: str = ""             # 可选；空则调 account_list 自动发现
   ```
2. **服务** `backend/app/services/ths_pnl.py`（新建）：
   - `_load_cookie()`：优先 `ths_pnl_cookie`（非空），否则读 `ths_pnl_cookie_file`（解析 `refs.STOCK_PNL_COOKIE` 块）——YAML 多行折叠需按方案 §6 归一化（`;` 拆分→去空白→`; ` 重连）。同样读 `STOCK_PNL_FUND_KEY`。
   - `fetch_pnl()`：POST `time_share`，payload 按方案 §6；返回 `{pnl_yk, pnl_pct, chart_data, updated_at, error, token_expired}`。
   - `fetch_index()`：POST `getQuotes`（`code=2%3A1A0001`），返回 `sh_pct`。
   - `get_snapshot()`：合并 → 归一化 dict；失败写 error 字段，**不抛异常、不伪造 0**（token 失效时 `token_expired=true`）。
   - 无 `requests`/`httpx` 依赖前提下用标准库 `urllib.request`；带 UA/Referer/Accept 头，`urlopen` 对非 2xx 抛 `HTTPError` 要捕获并解析。
3. **模型** `backend/app/db/models.py`：新增 `AccountPnlSnapshot`（`__tablename__="account_pnl_snapshot"`）：`id/trade_date/ts/pnl_yk/pnl_pct/sh_pct/chart_data(JSON)/source/error/token_expired/updated_at`（参照 `AccountBaseline` 写法，models.py:362 附近）。
4. **repo** `backend/app/db/repo.py`：`upsert_account_pnl_snapshot()`（按 `trade_date+ts` upsert）、`get_latest_account_pnl()`、`list_account_pnl_history(days)`。
5. **调度** `backend/app/scheduler/jobs.py`：新增 `ths_pnl_job` —— `ths_pnl_enable` 才跑 + 交易日 + 交易时段（9:30-11:30/13:00-15:00，参考现有 `monitor_interval_minutes` 判断风格）；间隔 `ths_pnl_poll_seconds`；失败只落 error 不崩。
6. **路由** `backend/app/api/routes.py`：`GET /account/pnl` 返回 `get_latest_account_pnl()`；未配置（`ths_pnl_enable=false` 或 cookie 空）返回 `{"configured": false}`，不报错。

## 四、执行顺序
1. config.py 加字段 → 2. models.py 加表 → 3. repo.py 加 3 个方法 → 4. 新建 ths_pnl.py → 5. jobs.py 加任务 → 6. routes.py 加端点。
7. **单测**：`backend/tests/test_ths_pnl.py`（新建）+ 跑相关回归。（现有测试基线：全量非 AppTest 约 577-634 passed；只跑 `test_holding_view/test_account_summary/test_account_baseline/test_scheduler` 相关，不全量。）
8. 运行 `python -m pytest backend/tests/test_ths_pnl.py -q`。

## 五、红线
1. **不打印 Cookie / 密钥明文**（任何 log/print/response 都不允许）。
2. 默认关闭（`ths_pnl_enable=false`），不改变现有行为；开启后才采集。
3. 不修改任何交易规则 / 研判标准；只新增采集与展示数据通道。
4. 所有 SQL 走 repo.py；不散落裸 SQL。
5. 采集失败只写 error，不伪造 0 值、不阻塞其他任务。
6. 修改文件最小化，预算 ≤ 全局若干文件（约 7 个），不夹带无关改动。

## 六、验收
- `ths_pnl_enable=true` 时，`GET /account/pnl` 返回真实今日盈亏，与同花顺卡片一致；
- `ths_pnl_enable=false` 时，`GET /account/pnl` 返回 `{"configured":false}`；
- `test_ths_pnl.py` 通过；相关回归通过；
- 所有输出不含 Cookie 明文。
