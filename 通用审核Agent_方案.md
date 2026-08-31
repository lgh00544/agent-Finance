# 通用审核 Agent（AuditAgent）方案文档

> **写于**：2026-08-28
> **决策人**：sir
> **拍板路线**：全量 LLM 双闸门 + 全部覆盖 4 个待审点 + 辩证验证（投反对票 + 基础库检索） + 失败打回重思考
> **本文件性质**：方案，过审后再拆批次执行指令

---

## §0 一句话定位

> 在 sir 之前加一道 AI 闸门：所有"需要人工审核的结论"（策略建议 / 经验沉淀 / 规则变更 / 复盘建议）
> 先进 AuditAgent 做辩证验证（投反对票），只有 AI 通过后才呈给 sir。sir 第一眼看到的不是结论本身，
> 而是「AI 已审 + 反对意见 + 依据」三件套。AI 不通过 → 自动打回让原 Agent 重思考。

---

## §1 现状盘点（4 个待审点）

| # | 待审点 | 入口表 | 状态字段 | 现有审核 UI | 现有"打回重思考" |
|---|---|---|---|---|---|
| ① | **AgentSuggestion**（review 输出策略） | `agent_suggestion` | `pending/approved/rejected` | 概览页/侧栏无入口，散落在 `RuleChangesPage` | ✅ `llm_rethink_suggestion`（仅 review） |
| ② | **PendingExperience**（经验沉淀） | `pending_experience` + `experience` | `status=pending_review` | ✅ ExperiencePage M1/M3 + TopStatusBar 徽章 | ❌ 驳回直接丢，无重思考 |
| ③ | **RuleChange**（规则/标准变更） | `rule_change` | `active/rolled_back` | ✅ RuleChangesPage | ✅ `rollback` 可逆，无重思考 |
| ④ | **ReviewResult**（复盘建议） | `review_result` | `pending/adopted/rejected` | ✅ ReviewsPage | ✅ `reject → review_rethink` |

**问题**：4 个点的审核 UI 散落、流程各异、AI 不参与；sir 必须自己读完每条结论再判断。

---

## §2 目标

1. **统一闸门**：4 个点的待审结论都进 AuditAgent
2. **辩证验证**：AI 强制找反方/边界场景，写出「反对意见」字段
3. **基础库检索**：每个待审点必查 K 红线（K1-K227）+ private_knowledge + review.md，输出「依据」段
4. **失败打回重思考**：AI 不通过 → 自动触发原 Agent rethink（已实现 ④/① 的复用，未实现的 ②/③ 补上）
5. **首页标识**：所有"已 AI 审核"的项，UI 上加绿色「AI 已审」徽章 + 一键看 AI 审核意见
6. **sir 第一页**：首页/审核中心直接看到「AI 通过/不通过 + 反对意见 + 依据」，原结论折叠

---

## §3 架构

```
[原 Agent 产出结论]
        │
        ▼
[AuditAgent.collect_audit]   ← 读原结论 + 基础库检索（K 红线 / 知识库 / review.md）
        │
        ▼
[AuditAgent.llm_audit]       ← 辩证推理：force dissent 段 + 基础库引用 + 置信度
        │
        ├── pass ──────▶ [audit_log(verdict=pass)] ──▶ 呈 sir 审核（含 AI 意见）
        │
        └── fail ──────▶ [audit_log(verdict=fail)]  ──▶ 自动触发原 Agent rethink
                                              │
                                              └── rethink 完成后重新进 audit（最多 2 轮）
```

---

## §4 Schema 设计（4 个新表 + 1 个枚举）

### 4.1 `audit_log`（核心表，新）

```python
class AuditLog(Base):
    """AuditAgent 审核流水（所有待审点的 AI 审核记录，可追溯）
    状态机：pending → pass/fail → (rethink 后) pass/fail（最多 2 轮）
    """
    __tablename__ = "audit_log"
    id: int (PK)
    target_type: str (16)   # agent_suggestion / pending_experience / rule_change / review_result
    target_id: int          # 原表主键
    round: int = 1          # 审核轮次（1=首审 / 2=重审）
    verdict: str (8)        # pending / pass / fail
    confidence: int         # 0-100
    # ----- 辩证 4 段（强制非空，AI 拒答=FAIL）-----
    support_view: str       # 支持意见（为什么这条可以过）
    dissent_view: str       # 反对意见（为什么这条可能不过；至少 1 条具体场景）
    boundary_cases: str     # 边界场景/反例（至少 1 条；引用 counter_examples.md / K 红线）
    evidence_refs: str      # 依据引用（K 编号 / K 红线 / private_knowledge ID）
    # ----- 元信息 -----
    audit_model: str        # 用的哪个模型（DEEP/LIGHT）
    reasoning: str          # AI 完整推理（JSON，供调试/留痕）
    duration_ms: int
    created_at: datetime
```

### 4.2 索引

```sql
CREATE INDEX ix_audit_target ON audit_log(target_type, target_id);
CREATE INDEX ix_audit_verdict ON audit_log(verdict);
CREATE INDEX ix_audit_created ON audit_log(created_at);
```

### 4.3 4 个原表加字段（**轻量、向后兼容**）

```python
# agent_suggestion / review_result：加 audit_verdict + audit_round
audit_verdict: Mapped[str] = mapped_column(String(8), default="pending")  # pending/pass/fail
audit_round: Mapped[int] = mapped_column(Integer, default=0)
last_audit_id: Mapped[int] = mapped_column(Integer, nullable=True)  # 关联 audit_log.id

# pending_experience / rule_change：同上（同样的 3 个字段）
```

**注意**：加字段都用 `default=pending/0/None`，老数据全部视作"未 AI 审核"，UI 上不带徽章。

---

## §5 接口设计（FastAPI）

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/audit/pending` | sir 首页用：所有 target_type 下 verdict=pass 且原表 status=pending 的列表（带 AI 意见） |
| GET | `/audit/log?target_type=&target_id=` | 查某条结论的完整 AI 审核历史（多轮） |
| GET | `/audit/stats` | 首页角标：各 target 待审 / 已审 / fail 数 |
| POST | `/audit/{audit_id}/re-audit` | sir 主动要求重审（绕开自动 2 轮上限） |
| POST | `/audit/{audit_id}/confirm-fail` | 强制让 AI 一次就过的兜底（sir 急用时） |

**不动现有 approve/reject 端点**——AuditAgent 是"插队"在原 Agent 之后、sir 之前的中间层。

---

## §6 UI 设计

### 6.1 React 新版（默认实现，Streamlit 不动）

**新页：`/audit-center`（审核中心）**——总入口
- 顶部 4 个统计卡：策略建议 / 经验沉淀 / 规则变更 / 复盘建议 各 X 条待审
- 主体：表格，列 = 类型 | 标的 | 摘要 | AI 结论 | 置信度 | 操作
- 绿色「AI 已审」徽章 = AuditAgent verdict=pass
- 红色「AI 不通过」徽章 = verdict=fail（点击看反对意见）
- 灰色「未 AI 审」= 老数据 / 审核中

**首页（OverviewPage）** 加 1 个角标卡片：审计中心 N 条待审，点击跳转。

**ReviewsPage / RuleChangesPage / ExperiencePage** 各自的列表行加 1 列「AI 审核」
- 通过：绿色徽章 + hover 看「依据 K223, K226」
- 不通过：红色徽章 + 「AI 反对意见：...」展开
- 未审：灰色「—」

### 6.2 状态机

```
[原 Agent 产出]
    ↓ auto-trigger audit
[audit_log(round=1, verdict=pending)] + 原表 audit_verdict=pending
    ↓ LLM 推理
[audit_log.verdict = pass] → 原表 audit_verdict=pass → 呈 sir
[audit_log.verdict = fail] → 触发原 Agent rethink → 完成后 round=2 重审
                                  ↓
                            round=2 仍 fail → 标红待 sir 强制决策（不再自动重审）
                            round=2 pass → 正常呈 sir
```

---

## §7 AuditAgent 实现要点

### 7.1 `collect_audit`（collect 段，**只注入事实**）

按 target_type 收集：

| target_type | 注入什么 |
|---|---|
| `agent_suggestion` | 原建议全文 + 关联 review_result 摘要 + 关联 rule_change 历史 + target_agent 当前 prompt 片段 |
| `pending_experience` | 经验草案 + route_draft 分流原因 + impact / confidence / conflict 信息 + 关联私有知识条目 |
| `rule_change` | 变更全文 + before/after 对比 + 来源 suggestion + 历史同 rule_name 变更 |
| `review_result` | 复盘全文 + 关联 holding/plan/score 摘要 + 已驳回历史 |

**统一注入 3 段**（所有 target_type 都加）：
1. **K 红线索引**：从 `agent_prompts/knowledge/*.md` + `red_line_check.py:21-26` 摘要相关条款
2. **private_knowledge 检索**：FTS5 精确检索（precise / precise-query），返回 top-5
3. **counter_examples**：从 `knowledge/counter_examples.md` 检索相关反例

**不变**：
- 不引新库（SimpleCache + 已有 SQLite）
- 不破坏 collect 段既有事实（K223 事实为先）
- 不动 agent_call / push_alert_node

### 7.2 `llm_audit`（DEEP 级别，辩证 schema）

```python
class AuditOutput(BaseModel):
    verdict: str = Field(pattern="^(pass|fail)$")
    confidence: int = Field(ge=0, le=100)
    support_view: str       # 支持意见（≥30 字）
    dissent_view: str       # 反对意见（≥50 字，必须含 1 个具体反例/场景）
    boundary_cases: str     # 边界场景（≥30 字）
    evidence_refs: list[str]  # 至少 1 条，格式 "K223" 或 "knowledge_id=42" 或 "rule_change#15"
    one_line_summary: str   # 一句话给 sir 看（≤40 字）
```

**Prompt 强制项**（system_prompt 写死）：

```
你是一个辩证型 AI 审核员，必须采用「正反辩论」思维：
1. 列出至少 1 条支持原结论的具体依据
2. 强制列出至少 1 条反对意见（无论你是否认同都要找反方）
   - 反方必须含具体场景/反例（如"亨通惨案根因 1"）
   - 不得用"可能存在风险"这种空话
3. 至少 1 条边界场景（什么情况下结论会失效）
4. 至少 1 条基础库引用（K 编号 / 私有知识 / 反例库）

你必须独立判断；不能因为原 Agent 是"系统"就倾向 pass。
如果找不到反对意见 → 强制返回 fail + 写"我没找到具体反方，但请 sir 复核"
```

**失败重审**（round=2）：system_prompt 追加 `历史 fail 原因：<dissent_view>，请重新评估并明确回应每条反对`。

### 7.3 触发点（4 处原 Agent 完成后）

| 原 Agent | 触发位置 | 备注 |
|---|---|---|
| `llm_review` | `backend/app/agents/review.py:249` 后 | review.py 已有 rethink，直接用 audit 替代手输 |
| `insert_agent_suggestion` 后 | review.py 循环内（`review.py:225-235`） | 一条 suggestion → 一次 audit |
| `route_draft` (experience_worker) | `experience_worker.py:191` 后 | pending_review 时触发 |
| `RuleChange` 新增 | `routes.py:1053` adopt_suggestion 路径后 | 写入 rule_change 后触发 |

**4 处都改成"异步 task"**——不阻塞原 Agent 落库，audit 在 task_queue 里跑（参考 `task_queue.py` 既有模式）。

---

## §8 红线（sir 决策底线）

1. **审计逻辑可旁路**：sir 急用时可点 `/audit/{aid}/confirm-fail` 强制 pass，绝不卡死流程
2. **不破坏老数据**：4 个原表加字段全部 default，老数据 UI 标"未审"（不删不迁移）
3. **audit 失败不丢结论**：audit fail 不删原表记录，只标 audit_verdict=fail，sir 仍可在原页面看到
4. **重审最多 2 轮**：第 2 轮仍 fail → 不再自动 rethink，标红待 sir 强制决策（防止无限循环）
5. **不污染 LLM 缓存**：audit cache_key 必须包含 round + audit_verdict，老 cache 自动失效
6. **基础库不引新依赖**：只用 FTS5 + 已有知识库文件 + SimpleCache
7. **不写代码改规则**：AuditAgent 只审核，不修改任何 agent_prompts / K 红线 / 阈值
8. **React 优先，Streamlit 不动**：UI 全部在 `web/src/` 出，Streamlit 仅补顶部通知（不开发新页面）
9. **失败有据可查**：audit_log.reasoning 完整留痕 JSON，sir 可一键看 AI 推理全文

---

## §9 批次拆分（4 批次，按依赖）

| 批次 | 主题 | 关键改动 | 依赖 |
|---|---|---|---|
| **批 1**（最小闭环） | AuditAgent 后端 + audit_log + 4 原表加字段 + 触发点 + 1 个 target（agent_suggestion） | 新表 + Agent + 触发 + UI 角标 | 无 |
| **批 2** | 扩 3 个 target（pending_experience / rule_change / review_result）+ 审计中心页 + 各原页徽章 | UI 全开 | 批 1 |
| **批 3** | 首页统计卡 + 顶栏角标 + Streamlit 顶部通知 + audit_stats API | 概览集成 | 批 2 |
| **批 4** | 失败重审 2 轮 + /re-audit 端点 + audit_log 详情页 | 重审闭环 | 批 3 |

**每批独立可交付，sir 验收通过再进下批。**

---

## §10 验证清单（批 1 必过）

- [ ] `audit_log` 表建好，老数据全部 audit_verdict=pending 不报错
- [ ] `agent_suggestion` 走一遍 review → 出现 audit_log(round=1)
- [ ] 模拟 dissent 强信号 → audit_log.verdict=fail → review 触发 rethink → round=2
- [ ] round=2 仍 fail → 不再自动 rethink，原表 audit_verdict=fail
- [ ] React 概览页能拉到 audit_stats
- [ ] agent_suggestion 列表行 AI 审核列显示「AI 已审/未通过/—」三态
- [ ] pytest 全过（不破老测试）

---

## §11 风险与缓解

| 风险 | 缓解 |
|---|---|
| LLM 审核耗时翻倍 | 异步 task + SimpleCache，audit 跑在后台，前端轮询 |
| AI 倾向 pass 放过 | 强制 dissent 段 + 缺反方强制 fail + round=2 仍可投 fail |
| 老数据 audit_verdict 永远 pending | UI 灰显"未审"，sir 主动 `/re-audit` 触发 |
| audit 和原 Agent 锁表竞争 | audit 只读 + 落 audit_log，不动原表，row-level 无竞争 |
| FTS5 检索太慢 | 5 条 top，硬截断 ≤200ms |

---

**审阅要点（sir 关注）**：
1. Schema §4 是否合理（特别是 dissent_view 强制 ≥50 字 + 必含具体反例）
2. 4 批次顺序 §9 是否合理
3. 触发点 §7.3 是否覆盖到位
4. 旁路开关 §8.1 必要否（担心急用时卡死）

过审后出 **批 1 执行指令**（≈ 250 行）。
