# T5 批C 基线锁 · 前置门禁（2026-09-21，未提交）

## 状态
- **未 commit / 未 tag**（AGENTS「不自动 commit/push/tag」）→ `pre-live-2026-10-08` 待 sir 授权后打。
- 工作区改动：18 个后端/前端文件 + 5 个测试文件（本批契约/收口）+ 新增 `scripts/backend_watchdog.ps1`、`scripts/register_backend_watchdog_task.ps1`、`mem_probe.py`。

## 门禁 1：工作区导入
`PYTHONPATH=D:\self\backend python -c "import app.main"` → **APP_MAIN_IMPORT_OK**

## 门禁 2：回归
| 套件 | 结果 | 备注 |
|---|---|---|
| group1：paper_monitor / paper_analysis / paper_execution / holding_view / ths_pnl / feishu_b4 | **56 passed + 24 skipped** | ths_pnl 全 skip（已下线） |
| batch14 / batch15 / db / dashboard_status | **23 passed** | |
| datasource_stability / end_to_end | **25 passed** | |
| batch4_pre_market / portfolio_sentinel / model_optimizations / batch2_reduce_ratio | **63 passed** | 契约变更后 |
| test_kline_store（harness4，清空复用目录后） | **21 passed** | 干净 temp 下全绿 |
| test_signal_registry | **29 passed + 1 error** | error=沙箱 tmp_path setup（环境） |
| test_feishu_media | **7 passed + 1 failed** | `PermissionError`，`feishu_bridge` 未改（环境） |

## 本批需同步的测试改动（契约依赖闭包）
- T1-A4 将 `push_alert` 改为 dict 三态 → 更新 stub：`test_batch4_pre_market.py`(5)、`test_portfolio_sentinel.py`(2)、`test_model_optimizations.py`(4)、`test_batch2_reduce_ratio.py`(1)。
- `test_feishu_b4.py`：pre-existing 陈旧 monkeypatch（多用户签名 `build_holding_view(user_id,is_admin=)` / `list_alerts(user_id=)`）。
- T4 开 local-only → `test_signal_registry.py` 显式 `local_only=False` + 隔离 `KLINE_DB_PATH`；`test_kline_store.py` 隔离真实股票池；+2 例覆盖 `short_history` 标记/pending 跳过/`unsupported` 分类。
  （后两项由并行会话落盘，已复核逻辑：`kline_ingest` 函数内 `from ...fallback import get_datasource`，故 monkeypatch `fb.get_datasource` 有效。）

## 判读
- 除 1 个沙箱 `PermissionError` 与 1 个沙箱 `tmp_path` setup error 外，改动模块闭包测试全绿；两项均为环境限制，非代码回归。
- `harness4.py` 复用 `D:\self\.wb_harness_tmp\r3\tNN` 会遗留 `k.db` → 复跑前须清空该目录，否则出现假失败。

## 门禁 3：干净副本预演（无 commit 的等价验证）
- `git archive HEAD` → `.wb_gate/tree`，再叠加本批 **31 个**改动/新增文件；
- 干净副本导入：`PYTHONPATH=.wb_gate/tree/backend python -c "import app.main"` → **CLEAN_TREE_IMPORT_OK**（证明本批文件集自洽，无「漏提交依赖」）；
- 用例数一致：同一批 18 个测试文件 `--collect-only` → 工作区 **242 collected**，干净副本 **242 collected**（一致；含本批新增 2 例短史/unsupported）；
- 局限：这是「工作区叠加」预演而非真 commit 后的 HEAD 归档；正式门禁须在 commit 后重跑。
## 待办（sir 授权后）
1. 按依赖闭包整理 commit（建议 T1/T2/T3/T4 与配套测试同批）；
2. 跑「干净副本 git archive HEAD → import + 同批 pytest 用例数一致」双门禁；
3. 打 `pre-live-2026-10-08` tag；届时重跑 `实盘GoNoGo清单_核对_20260930.md`。
