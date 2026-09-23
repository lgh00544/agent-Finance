# 自动化执行记录 · 买卖点信号体系批 1 · 观察期值守（首跑抢起窗口探活）

## 任务定义
一次最小探活：`netstat -ano | findstr ":8000"`，判定 127.0.0.1:8000 是否 LISTENING。
不做：连 TiDB / 解码日志 / 写归档 / 擅自重启。
- 存活 → 一句话确认（含 PID），结束。
- 死亡且未过 16:50 → 醒目提示 sir 赶在 16:50 前重启 `D:\self\backend\scripts\dev_run.py`。
- 死亡且已过 16:50 → 当日观察作废顺延，等 sir 确认口径，不手动补跑。

## 背景铁律（复用时必读）
- 后端 BackgroundScheduler 未配 jobstore（内存态，`jobs.py:908`）→ 进程在当日 16:50 前死亡，重启后**不补跑**当天 cron。
- 重启含全量同步，实测约 6.8 分钟 → 必须在 16:50 前完成重启。
- 后端冷启动 bind :8000 前约 6.5 分钟**端口不监听 ≠ 挂了**，判定前须留足等待。

## 执行历史
| 时间 | 结果 | 凭据 |
|---|---|---|
| 2026-09-17 16:31 | 存活 | 127.0.0.1:8000 LISTENING，PID 1456 |
| 2026-09-18 16:31 | 存活 | 127.0.0.1:8000 LISTENING，PID 25220；net_check 全 5 项 OK（后端/百度/sina:80/sina:443/TiDB:4000）|
| 2026-09-21 16:42 | 存活（首探假 FAIL） | 127.0.0.1:8000 LISTENING，PID 34872；net_check 全 5 项 OK。16:35:22 首探 FAIL("该端口无监听" + netstat 无匹配)，复核后判定为**冷启动窗口误判**：该进程 16:30:14 起（`backend-dev.stdout.log` 首行 = DB init + SYNC_ON_START 全量同步），bind :8000 在 16:36 前后，16:40 已见 `/api/health` 200 与 APScheduler 正常调度 |

## 版本变更
- 2026-09-18：探活升级为 `net_check.py` 全量自检（端口 + 4 项出网 + backend-dev 日志清单），按 A/B/C 分流；B 类补充命名管道环境铁律与"已过 16:50 顺延"判据。
- 2026-09-21：新增**"端口 FAIL ≠ 后端死亡"复核动作**（教训来源见上行 16:35 假 FAIL）：
  1. 端口项 FAIL 时先查 `backend-dev.stdout.log` 首行时间戳 —— 若进程启动 <7 分钟，属冷启动未 bind，判 A 类（存活），不报 B。
  2. 再用 `curl -s -m8 -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/health` 二次确认（返回 200 即活）。
  3. 复核通过后重跑一次 `net_check.py`，以第二次结果作为最终判据写入本表。
  4. 注意 `backend-dev.stdout/stderr.log` 为 UTF-16，Read 工具会判为 binary，须用 python `decode('utf-16','replace')` 读。

## 备注
- 本次未写入当日 daily log / 无归档文件（遵守"不写归档"约束）。
- 每次执行只落一行结果到上表，不贴原始 netstat 输出。
- 2026-09-21 未做任何写操作（未重启、未改码、未 commit/push），仅只读探活 + 读日志复核。
