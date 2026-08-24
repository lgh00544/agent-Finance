# 经验沉淀急救 · Claude Code 执行指令

> **作者**：Lark
> **日期**：2026-08-21
> **改动范围**：3 个后端文件 + 1 个新增单元测试文件
> **依据**：`D:\self\经验沉淀与预测性选股_方案.md` §二 段 1（1 批次急救）
> **关联**：与段 2 五合一（`预测性选股重构_5批次_Claude执行指令.md`）可并行执行，互不依赖

---

## 〇 文档元信息

| 角色 | 说明 |
|---|---|
| **生成者** | Lark（assistant），按 sir 8/19 拍板的"默认输出 Claude Code 提示词"格式 |
| **执行者** | Claude Code（Anthropic Claude 4.x） |
| **决策人** | sir |
| **依赖** | 无（独立可执行） |
| **工时预估** | 0.5-1 天 |

---

## 一、目标

把 `experience` 表从「实测 0 行」恢复到「每周至少 30 行入审」，**不**：

- 不回放 168 条历史 done
- 不降 `auto_merge` 阈值（保持 0.85）
- 不改交易规则 / 研判标准 / SelectAgent / ScoreAgent
- 不动 `streamlit/pages/`（8/20 拍板铁律：前端默认改 React 新版，Streamlit 仅在阻塞时动）
- 不改 prompt 阈值

**只做**：让 168 条 done 的「实质信息」真的进 LLM，让 worth 判定不被宁缺毋滥卡死，让 monitor 反复写堆积被止住。

---

## 二、架构约束（5 铁律）

1. **Agent 解耦**：只动 `router.py` 钩子层和 `experience_worker.py` 处理层，不重写任何 Agent 节点
2. **失败兜底**：所有改动必须 try/except，绝不抛异常影响主任务
3. **不破坏既有 review_log 审计**：`experience` 表的 status 流转可回滚
4. **auto-merge 永远不动**：0.85 阈值不改；M3 硬闸门（impact=high → pending_review）不动
5. **8/20 前端铁律**：本批次不动前端；后端日志通过现有 `job_status()` 接口查看

---

## 三、规则（4 段）

### 3.1 加厚 `_exp_summary()` 输出（解决"摘要过薄触发 worth=False"）

**文件**：`backend/app/graph/router.py:29-67`

每个 kind 的 summary 必须包含：标的 / 关键数字 / 触发原因 / 至少 2 个上下文事实（板块 / 评级 / 时间窗 / 关键指标）。

**示例**（discover）：

| 维度 | 原（过薄） | 新（加厚） |
|---|---|---|
| 摘要 | "候选 4 只" | "候选 4 只｜沪市主板 3 / 创业板 1｜平均涨幅 +2.3%｜主线命中：AI 算力(2) 新能源(1)｜板块强度 ≥7 的 2 只" |
| artifacts | "codes" | "codes + 板块分布 dict + 评级分布 dict（见 summary，已可重建）" |

**示例**（monitor）：

| 维度 | 原 | 新 |
|---|---|---|
| 摘要 | "600547 监控信号 reduce" | "600547 监控信号 reduce｜浮盈 +8.5%｜板块 主线退潮信号｜量比 1.2 倍｜触发规则 K138-2｜距 C1 止损 -2.1%" |
| artifacts | "holding_id" | "holding_id + 当前价 + 成本价 + 浮盈率 + 触发的红线编号" |

**加厚原则**：
- 数字精度统一：百分比保留 2 位小数、价格保留 2 位小数
- 触发原因必须给「指标名 + 数值 + 阈值」三元组
- 板块 / 主线必须给名字而非代码
- **绝不编造**：缺失字段填 `missing`，不补 0 不补"—"

### 3.2 monitor 同日同码去重（解决 Worker 20 条批次被吃光）

**文件**：`backend/app/db/repo.py` + `backend/app/db/models.py`

**改动**：
- `PendingExperience` 表新增 `UniqueConstraint("task_id", "stage", name="uq_pending_task_stage")`（按 kind:trade_date + stage 维度去重；这覆盖了"同日同 stage 重复写"——包括 monitor 同日同码反复触发）
- `repo.add_pending_experience()` 用 `INSERT OR IGNORE`（SQLite）/ `INSERT ... ON CONFLICT DO NOTHING`（MySQL），重复插入返回 None 不报错
- **保留同日不同 stage 的多条**（discover 同日可写多次，monitor 同日可写多次，但 stage 不同即可共存）

**红线**：保留 `task_id` 现有结构 `kind:trade_date`，不引入新字段

### 3.3 worth 默认 true + extract 失败 fallback（让链路不静默）

**文件**：`backend/app/services/experience_worker.py`

**改动 3.3a**：`EXTRACT_SYSTEM` prompt 加 1 段
```
当以下任一情况存在时，worth 必须为 True（即使置信度低）：
- summary 中出现具体数字（百分比/价格/数量）
- summary 涉及 K 红线（K1-K227 任一编号）
- summary 含"触发/突破/跌破/退潮/放量"等动作词

worth=False 仅在 summary 完全是空话（如"已处理"/"无变化"）时使用。
```

**改动 3.3b**：`_llm_extract` 失败 fallback 进 pending_review
```python
# 原（line 184-186）：失败直接 release_pending(error="extract_failed")
# 改为：
try:
    draft = _llm_extract(...)
except Exception as exc:
    # 抽取失败 → 不丢，把摘要当 body 入 pending_review 待人工审核
    eid = repo.insert_experience(
        title=f"[待审·抽取失败] {item.get('summary', '')[:60]}",
        body=item.get("summary", "") + "\n\n[系统注：LLM 抽取失败，待人工整理]",
        stage=item.get("stage", "持仓"),
        tags=["extraction_failed", item["task_id"].split(":")[0]],
        impact="medium",
        confidence=0.0,
        source_pending_id=pending_id,
        status="pending_review",
    )
    repo.release_pending(pending_id, error=f"extract_failed_but_saved: {eid}")
    return
```

**改动 3.3c**：skip 必须留因
```python
# 原：if not draft.worth: repo.release_pending(pending_id, error=None)
# 改为：
if not draft.worth:
    repo.release_pending(pending_id, error="worth_false_空话")
    return
```

### 3.4 表 schema 同步（DDL 变更需幂等）

**文件**：`backend/app/db/models.py:577-579` + 初始化迁移

**改动**：
- `PendingExperience` `__table_args__` 加 `UniqueConstraint("task_id", "stage", name="uq_pending_task_stage")`
- **不写 ALTER TABLE 迁移脚本**（依赖 SQLAlchemy `create_all()` 幂等性 + 项目 `init_db.py` 重跑即可）
- 加 1 条防御：若用户数据库已建好表，DDL 差异由项目 `alembic upgrade head` 或手动 `init.sql` 处理（不引入 alembic，超出本批次范围）

---

## 四、实现参考（必读文件）

| 文件 | 必读理由 |
|---|---|
| `backend/app/graph/router.py:29-67` | `_exp_summary()` 真实定义（本批次主改点） |
| `backend/app/graph/router.py:70-85` | `_record_pending_experience()` 钩子（修改后必须 try/except 保留） |
| `backend/app/services/experience_worker.py:176-194` | `_process_item()` 链路（3.3 fallback 改造点） |
| `backend/app/services/experience_worker.py:114-145` | `route_draft()`（M3 硬闸门、auto_merge 路径，**不动**） |
| `backend/app/db/models.py:573-588` | `PendingExperience` 表（3.2 唯一约束改造点） |
| `backend/app/db/repo.py:1851` | `add_pending_experience()`（3.2 INSERT OR IGNORE 改造点） |
| `agent_prompts/experience_prompt.py` | `EXTRACT_SYSTEM`（3.3a 加段） |

**风格统一**：
- 中文 JSDoc 注释
- 中文日志 `logger.warning(...)` 不改英文
- 错误信息保留 `exc_info=True` 风格

---

## 五、执行顺序

1. **备份**：复制 3 个待改文件到 `.bak.exp_emergency`
   ```bash
   cp backend/app/graph/router.py backend/app/graph/router.py.bak.exp_emergency
   cp backend/app/services/experience_worker.py backend/app/services/experience_worker.py.bak.exp_emergency
   cp backend/app/db/models.py backend/app/db/models.py.bak.exp_emergency
   cp backend/app/db/repo.py backend/app/db/repo.py.bak.exp_emergency
   ```

2. **改 3.1**：扩 `_exp_summary()` 6 个 kind 的 summary 加厚（discover/score/position/monitor/sell/review）
3. **改 3.2**：加 `PendingExperience` 唯一约束 + `add_pending_experience()` INSERT OR IGNORE
4. **改 3.3**：3 个子改动（prompt 段 / extract 失败 fallback / skip 留因）
5. **新增单测**：`backend/tests/test_experience_emergency.py`，覆盖：
   - `_exp_summary()` 6 个 kind 的输出非空断言
   - `add_pending_experience()` 同 (task_id, stage) 第二次返回 None 不报错
   - `_process_item` extract 失败时入 pending_review
   - skip 时 error 字段非 None

6. **运行单测**：
   ```bash
   D:\self\.venv\Scripts\python.exe -m pytest backend/tests/test_experience_emergency.py -v
   ```
   预期：≥ 4 passed

7. **运行全量回归**（避免改动波及其他）：
   ```bash
   D:\self\.venv\Scripts\python.exe -m pytest backend/tests --ignore=backend/tests/test_streamlit_pages_smoke.py --ignore=backend/tests/test_system_status.py -q
   ```
   预期：≥ 当前 599 passed，新增 emergency 测试通过

8. **重启后端 + worker 探针**（如部署）：
   ```bash
   curl -X POST http://127.0.0.1:8000/api/experience/worker/run
   ```

---

## 六、验证清单（sir 独立验收用）

### 6.1 静态验收
- [ ] `python -m py_compile backend/app/graph/router.py backend/app/services/experience_worker.py backend/app/db/models.py backend/app/db/repo.py` 0 error
- [ ] `grep -nE "_exp_summary|_record_pending_experience" backend/app/graph/router.py | wc -l` ≥ 3
- [ ] `grep -nE "uq_pending_task_stage" backend/app/db/models.py | wc -l` ≥ 1
- [ ] `grep -nE "INSERT OR IGNORE|ON CONFLICT DO NOTHING" backend/app/db/repo.py | wc -l` ≥ 1
- [ ] `grep -nE "extract_failed_but_saved|worth_false_空话" backend/app/services/experience_worker.py | wc -l` ≥ 2

### 6.2 运行时验收
- [ ] `pytest backend/tests/test_experience_emergency.py` 全通过
- [ ] 全量回归 ≥ 599 passed + 新增 emergency 全通过
- [ ] **重启后端后**：手动触发 1 次 `run_discover()` + 1 次 `run_monitor()`，5 分钟内查 `data/dev.db`：
  ```sql
  SELECT id, task_id, stage, summary, status FROM pending_experience ORDER BY id DESC LIMIT 5;
  ```
  预期：summary 包含具体数字、板块、评级名（不再是"候选 4 只"这种空摘要）
- [ ] **24h 后查 experience 表增量**：
  ```sql
  SELECT COUNT(*) FROM experience;
  ```
  预期：从 0 → ≥ 5（首批由 fallback 入 pending_review + 摘要加厚后 worth=True 入库）

### 6.3 红线验收
- [ ] `git diff --stat` 只出现本批次 4 个文件（router.py / experience_worker.py / models.py / repo.py）+ 新增单测
- [ ] `streamlit/pages/`、`web/src/`、`agent_prompts/*_prompt.py`（除 experience_prompt.py 外）、`backend/app/agents/*`、`backend/app/services/candidate_tradeable.py` 等均**零改动**
- [ ] `auto_merge` 阈值 0.85 未变（在 `experience_worker.py:route_draft` 路径里检查）

---

## 七、红线（5 条必守）

1. **不动交易规则 / 研判标准**：score 阈值、stop_loss、take_profit、tradeable 判定、SelectAgent 红线 全部不动
2. **不动 8/20 拍板的前端铁律**：本批次零前端改动
3. **不降 auto_merge 0.85**：人工 fail-closed 阈值不动
4. **失败兜底必须保留**：所有改动 try/except，绝不抛异常影响主任务
5. **不引入新依赖 / 不引入 alembic**：纯 SQLAlchemy create_all 幂等迁移

---

## 八、Claude Code 执行前必读清单

1. 先备份 4 个文件（§五 第 1 步）
2. 严格按 3.1 → 3.2 → 3.3 顺序改，不要并行
3. 新增单测覆盖 4 个核心场景（§五 第 5 步）
4. 改完先跑单测，再跑全量回归，最后手动验证 DB
5. 24h 后查 `experience` 表增量，把数字反馈给 sir（这是段 1 唯一的关键指标）
6. 遇方案决策点 → 先停下问 sir，不自行决定
7. 遇红线触碰 → 立即停下报告
