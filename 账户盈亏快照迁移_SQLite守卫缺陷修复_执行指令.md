# 账户盈亏快照迁移 · SQLite 守卫缺陷修复 执行指令

> **生成**：Lark（WorkBuddy）｜**执行**：DSH / Claude Code｜**决策人**：sir
> **性质**：修复**前序批次**遗留缺陷（`app/db/session.py`，工作区 `M` 未提交）
> **触发**：2026-09-16 16:12 后端启动即崩 → 无调度器 → 买卖点信号体系批 1 首跑观察被阻断
> **工作目录**：`D:\self`

---

## 一、根因（已验证，非猜测）

**症状**：后端 16:12:16 启动失败，8000 端口无监听，无进程 → 16:50 的 `signal_scan` cron 从未触发。

**崩溃链**：
```
init_db() → _ensure_user_columns()
  → UPDATE account_pnl_snapshot SET user_id=1 WHERE user_id IS NULL
  → IntegrityError: UNIQUE constraint failed (user_id, trade_date, ts)
  → session.py:187 raise
  → main.py:31 lifespan 失败 → 进程死亡
```

**真根因**（`session.py:303`）——冲突行清理被**方言守卫写漏**：

```python
if engine.dialect.name != "sqlite":          # ← 清理只对 MySQL / TiDB 生效
    conn.execute(text("DELETE FROM account_pnl_snapshot WHERE user_id IS NULL "
                      "AND (trade_date, ts) IN (SELECT trade_date, ts FROM account_pnl_snapshot "
                      "WHERE user_id = :uid)"), {"uid": default_id})
```

本地 `data/dev.db` **正是 SQLite** → 清理被跳过 → 后续通用 `UPDATE` 直接撞唯一约束。

**为什么 SQLite 也会冲突**：`_migrate_account_pnl_snapshot`（SQLite 分支，`session.py:248-283`）重建表时写入 `CONSTRAINT uq_account_pnl_user_date_ts UNIQUE (user_id, trade_date, ts)` 并**原样拷贝全部行**。SQLite 中 `NULL` 互不相等，故 `(NULL, 日期, ts)` 与 `(1, 日期, ts)` 可以并存——建表时没事，一旦把 NULL 回填成 1 就变成真重复。

**实测冲突数据**（只读查证）：

| 项 | 值 |
|---|---|
| 总行数 | 14,756 |
| `user_id IS NULL` | 1,995 |
| 唯一索引 | `uq_account_pnl_user_date_ts`（SQLite 下为 `sqlite_autoindex_..._1`, unique=1） |
| **冲突组** | **4 组**，均为 `2026-09-16` 的 `13:55:00` / `14:00:20` / `14:06:20` / `14:11:00`，每组 NULL 1 行 + user_id=1 1 行 |

---

## 二、修复（方言无关，改动 ≤ 5 行）

`backend/app/db/session.py` `_ensure_user_columns()`：

**去掉 `if engine.dialect.name != "sqlite":` 守卫**，让冲突清理在 SQLite 上同样执行。

- 该 DELETE 是标准 SQL，SQLite / MySQL 均支持，**无需改写**
- 对 MySQL / TiDB 行为**完全不变**（原本就跑）
- 仅新增 SQLite 覆盖，**不新增分支、不改 MySQL 语义**

**已用合成表验证修复正确性**（复刻 4 组冲突 + 2 组无冲突 NULL）：

| 步骤 | 结果 |
|---|---|
| 不清理直接 UPDATE | `IntegrityError: UNIQUE constraint failed` ← 与线上崩溃一致 |
| 先清理冲突 NULL 行 | 删除 **4** 行 |
| 再 UPDATE | 成功，无异常 |
| NULL 残留 | **0** |
| 唯一键重复组 | **0** |
| 无冲突的 NULL 行 | 正确回填为 `user_id=1`（未被误删） |

---

## 三、执行顺序（分段落盘，每步落盘 + 自检）

1. **改 `session.py`**：移除方言守卫（≤5 行）→ 落盘
2. **停机备份**：先确认后端已停（`8000` 无监听），把 `data/dev.db` 复制为 `data/dev.db.bak-20260916`，确认副本存在且大小一致
3. **干跑验证**（**在副本上**，不碰原库）：
   ```
   cd /d/self/backend
   ../.venv/Scripts/python.exe -c "
   import shutil, os; os.environ['DB_PATH']='../data/dev.db.bak-20260916'
   from app.db.session import init_db; init_db(); print('init_db OK')"
   ```
   若环境变量不生效，改用临时配置指向副本；**严禁直接对 `data/dev.db` 试跑**
4. **复核副本结果**（只读 SQL）：
   - `account_pnl_snapshot` 行数 = 14,756 − 4 = **14,752**
   - `user_id IS NULL` = **0**
   - 唯一键重复组 = **0**
5. **应用到原库**：确认 ①②③④ 全部通过后，再对 `data/dev.db` 执行 `init_db()`
6. **启动后端**，确认 `8000` 已监听 + 日志出现「数据库初始化/迁移完成」
7. **确认调度器**：日志中确认 `signal_scan` job 已注册（工作日 16:50）
8. **提交**（路径限定，不 `git add -A`）：
   ```
   git add backend/app/db/session.py
   git commit -m "[账户盈亏快照 迁移修复] SQLite 分支补冲突行清理，修启动即崩"
   ```
   不 push、不建 tag

---

## 四、红线

1. **只改 `session.py` 的方言守卫，不重构该函数**；`_migrate_account_pnl_snapshot` 重建逻辑**不动**
2. **不碰 MySQL / TiDB 分支语义** —— 改动只新增 SQLite 覆盖
3. 不改因子体系 / K 红线 / 交易规则文件 / 买卖点信号体系批 1 已提交代码
4. **删行必须报告**：删除的是「NULL 归属、且同 `(trade_date, ts)` 已有 user_id 行」的冗余采集残留，须在报告中给出实际删除行数与 `id` 列表
5. **先备份再动原库**；备份失败 → 停下报告
6. 不 `git add -A`（工作区另有约 72 项前序批次改动）
7. **不 push、不建 tag**
8. 观察期（09-17 / 09-18 / 09-21）发现问题只报告，不自作主张改码

---

## 五、完成判据

- `init_db()` 对 `dev.db` 无异常；`account_pnl_snapshot` = 14,752 行 / NULL 0 / 重复 0
- 后端启动成功，`8000` 监听，`signal_scan` job 已注册
- 报告 ≤ 10 行：①改了什么（`path:line`）②删除行数与 `id` ③`init_db` 结果 ④后端/调度器状态 ⑤遗留风险

**随后**：按 `D:\self\买卖点信号体系_批1_提交与首跑观察_执行指令.md` §三 进入 3 交易日观察（09-17 / 09-18 / 09-21，16:50 触发）。

---

## 附：不在本批范围但需 sir 知悉

`main.py:31` 的 `init_db()` **无异常保护** —— 任何一次迁移失败都会让整个后端（含调度器）启动即崩，而非降级运行。本次即因该结构缺陷导致「无调度器」。是否加固属独立议题，**本批不做**，供 sir 决策。
