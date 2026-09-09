# 系统能力地图与 Agent 协作治理：批 9 Codex 执行提示词

## 任务

你在 `D:\self` 项目中执行扩展批 9：**Memory Curator / 记忆策展与过期机制**。

目标：让自动沉淀的经验记忆可命中计量、可过期、可归档、可策展压缩，防止长期旧记忆污染 Agent 判断。第一版只做经验记忆 `experience`，不处理 RuleChange，不处理 KnowledgeShadow。

参见：

- `D:\self\Memory治理与记忆防污染_提单.md` §8、§9、§10、§12、§13
- `D:\self\系统能力地图与Agent协作治理_批8_Codex执行提示词.md` 的 shadow 隔离红线

引用文档只作参考，以本提示词为准。

## 当前代码事实

1. Memory 主要在 `pending_experience` / `experience`。
2. `experience_section()` 调 `repo.search_experience(..., status="active")` 注入软上下文。
3. `Experience` 已有 `status/confidence/auto_merged/last_reviewed_at`，但没有命中计量和过期字段。
4. `ReviewLog` 可复用做 curator 留痕。
5. `experience_worker.DEFAULTS` + `/experience/config` 已有配置中心。

## 必须先定位

只读锚点附近，不整读大文件：

```powershell
rg -n "class Experience|class ReviewLog|def search_experience|def insert_experience|def list_experience|def update_experience_status|def experience_section|DEFAULTS|/experience/config|/experience/list|review_log" backend/app backend/tests
```

重点文件：

1. `backend/app/db/models.py`
2. `backend/app/db/session.py`
3. `backend/app/db/repo.py`
4. `backend/app/agents/common.py`
5. `backend/app/services/experience_worker.py`
6. `backend/app/api/routes.py`
7. `backend/tests/test_pending_dedup.py`

## 数据模型

扩展 `Experience`，兼容新增字段：

```text
hit_count INTEGER DEFAULT 0
last_used_at DATETIME NULL
expires_at DATETIME NULL
curator_note TEXT DEFAULT ''
```

要求：

1. 幂等增量加列，SQLite/MySQL 兼容。
2. 老数据默认 `hit_count=0`，`expires_at=NULL`，继续 active 注入。
3. 不物理删除任何 memory。

## Repo 能力

在 `repo.py` 增加最小函数：

1. `bump_experience_hits(ids: list[int]) -> int`
   - 类似 `bump_knowledge_hits`。
   - 更新 `hit_count + 1` 和 `last_used_at=now`。
2. `list_curator_candidates(...)`
   - 只读列出可策展候选。
   - 支持 `status/stage/older_than_days/max_hit_count/max_confidence/limit`。
3. `mark_experience_curated(eid, status, note, reviewer="auto")`
   - 仅允许 `archived/expired/pending_review` 等非交易状态。
   - 更新 `curator_note`，写 `ReviewLog(action="curator_archive/curator_expire/curator_propose")`。
4. 可选：`set_experience_expires_at(eid, expires_at, note="")`，用于人工设置单条过期时间。

不要改 `CandidateTrackVerify`、`RuleChange`、`PrivateKnowledge`。

## 命中计量

在 `common.experience_section(agent)` 中：

1. 检索仍只取 `status="active"`。
2. 注入后调用 `repo.bump_experience_hits([ids])`。
3. 计量失败只 warning，不阻断主链路。
4. 文案仍是“历史经验参考（自动沉淀，仅供参考）”，不能升级成硬规则。

## Curator 服务

新增：

```text
backend/app/services/memory_curator.py
```

核心函数建议：

```python
def run_curator(dry_run: bool = True, limit: int = 100) -> dict:
    ...
```

第一版规则：

1. `expires_at <= now` 且 `status="active"` -> 建议/执行 `expired`。
2. `active` 且 `confidence < low_confidence_threshold` 且 `created_at` 早于 retention_days 且 `hit_count <= stale_hit_threshold` -> 建议/执行 `archived`。
3. 同 `stage` 且 tags 有交集、标题或正文高度相似的多条 active -> 只生成“策展摘要候选”。
4. 策展摘要候选只能 `status="pending_review"`，不能自动 active。
5. `dry_run=True` 不写库，只返回 actions。
6. `dry_run=False` 执行状态变更并写 ReviewLog；不删除原文。

配置放入 `experience_worker.DEFAULTS`，让 `/experience/config` 可管理：

```text
memory_curator_enabled=1
memory_retention_days=90
memory_low_confidence_threshold=0.55
memory_stale_hit_threshold=0
memory_duplicate_similarity=0.86
```

## API

在 `routes.py` 增加：

1. `GET /experience/curator/candidates`
   - 只读候选列表。
2. `POST /experience/curator/run`
   - body: `dry_run=True, limit=100, confirm=False`
   - `dry_run=False` 时必须 `confirm=True`。
3. `POST /experience/{eid}/expire`
   - body: `expires_at` 或 `status=expired/archived` + `note`
   - 人工设置过期/归档，必须留痕。

所有接口不触发 LLM，不触发交易，不触发 RuleChange。

## 不要改

1. 不改 Agent 输出 schema。
2. 不改正式 prompt 段序。
3. 不改知识库 `PrivateKnowledge` / `KnowledgeShadowHit`。
4. 不改 RuleChange / 采纳审核闸门。
5. 不改 T+N 验证口径。
6. 不自动删除 memory。
7. 不自动把策展摘要 active。
8. 不新增交易接口，不自动下单。

## 测试要求

新增最小测试，推荐：

```text
backend/tests/test_memory_curator.py
```

覆盖：

1. `experience` 新列存在，重复 `init_db()` 幂等。
2. `experience_section()` 只注入 active，并 bump `hit_count/last_used_at`。
3. bump 失败不阻断 `experience_section()`。
4. `run_curator(dry_run=True)` 不改任何状态。
5. 过期 active 经验执行后变 `expired`，写 `review_log`。
6. 低置信老旧低命中 active 经验执行后变 `archived`。
7. 相似经验只生成 `pending_review` 策展候选，不自动 active。
8. `/experience/curator/run` 非 dry-run 必须 `confirm=True`。
9. `/experience/{eid}/expire` 可人工归档/过期并留痕。
10. active 且高命中/高置信/未过期经验不被 curator 处理。

必要时补充 `test_pending_dedup.py` 或经验相关测试，保持旧 pending/worker 流程兼容。

## 验收命令

只跑相关测试：

```powershell
D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_memory_curator.py backend\tests\test_pending_dedup.py backend\tests\test_knowledge_shadow.py backend\tests\test_knowledge_metadata.py
```

不要跑全量测试，除非相关测试暴露跨模块问题。

## 汇报格式

```text
改动文件+行号：

- [文件](绝对路径)：说明

测试：

- 命令：passed X / failed Y

红线核对：

- 未改 Agent 输出 schema：是
- 未改正式 prompt 段序：是
- 未改 Knowledge/Shadow/RuleChange：是
- curator 只归档/过期/提议，不物理删除：是
- 策展摘要不会自动 active：是
- 非 dry-run 执行必须 confirm：是
- 未开放交易接口：是

遗留/下一批：

- ...
```

