# 系统能力地图与 Agent 协作治理：批 8 Codex 执行提示词

## 任务

你在 `D:\self` 项目中执行批 8：**方法论 shadow 试运行**。

目标：外部方法论/新知识先进入 shadow 观察，不影响正式 Agent 结论；记录命中、模拟倾向和 T+N 后验表现，再由人工决定升级 active 或归档 archived。

参见：

- `D:\self\系统能力地图与Agent协作治理_方案.md` §7 批 8：方法论 shadow 试运行
- `D:\self\Memory治理与记忆防污染_提单.md` §3、§5、§7、§8、§9

引用文档只作参考，以本提示词为准。

## 当前代码事实

1. 批 6 已给 `PrivateKnowledge` 增加 `status=active/shadow/archived/expired`。
2. `knowledge_section()` 默认只注入 active，archived/expired 不注入。
3. `vector_store.search_knowledge(..., status="active")` 已支持 status 和场景过滤。
4. T+N 后验在 `CandidateTrackVerify` / `track_verify.run_verify_chain()`。
5. 本批只做知识类 shadow，不做 RuleChange shadow。

## 必须先定位

只读锚点附近，不整读大文件：

```powershell
rg -n "class PrivateKnowledge|class CandidateTrackVerify|def search_knowledge|def knowledge_section|def add_knowledge|def list_knowledge|def update_track_verify|def list_track_verify|def run_verify_chain|def llm_final|def llm_score|/knowledge" backend/app backend/tests
```

重点文件：

1. `backend/app/db/models.py`
2. `backend/app/db/session.py`
3. `backend/app/db/repo.py`
4. `backend/app/services/vector_store.py`
5. `backend/app/agents/common.py`
6. `backend/app/agents/discover.py`
7. `backend/app/agents/score.py`
8. `backend/app/services/track_verify.py`
9. `backend/app/api/routes.py`

## 数据模型

新增一张最小 shadow 命中表，建议模型名：

```python
class KnowledgeShadowHit(Base):
    __tablename__ = "knowledge_shadow_hit"
```

建议字段：

```text
id
knowledge_id
agent
stock_code
stock_name
trade_date
query
scenario_tags JSON
shadow_bias: boost / reduce / risk / neutral / unknown
shadow_summary
t3_pct
t5_pct
t10_pct
max_drawdown
verify_status: pending / partial / finished
created_at
updated_at
```

约束：

1. 唯一键建议：`knowledge_id + agent + stock_code + trade_date`。
2. 只新增表，不改 `CandidateTrackVerify` 口径。
3. shadow 表只记录观察，不参与正式评分、候选、交易、规则生效。

## Repo 能力

在 `repo.py` 增加最小函数：

1. `update_knowledge_status(knowledge_id, status, reason="")`
   - 仅允许 `active/shadow/archived/expired`。
   - 必须保留旧知识内容，不删除。
   - reason 可追加到 `risk_note` 或返回给调用方；不要新增复杂审核流。
2. `record_knowledge_shadow_hit(...)`
   - 幂等 upsert。
   - 同一知识、Agent、标的、日期重复命中不新增重复行，可更新 `query/scenario_tags/shadow_summary`。
3. `list_knowledge_shadow_hits(...)`
   - 支持 `knowledge_id/agent/stock_code/trade_date/verify_status` 过滤。
4. `refresh_knowledge_shadow_outcomes()`
   - 读取 `candidate_track_verify`，按 `stock_code + select_date/trade_date` 回填 `t3_pct/t5_pct/t10_pct/max_drawdown`。
   - 有 T+10 或 `is_finished=1` 标 finished；只有部分结果标 partial；没有后验标 pending。

## Shadow 检索与记录

新增一个轻服务模块也可以，推荐：

```text
backend/app/services/knowledge_shadow.py
```

职责：

1. 只检索 `status="shadow"` 的 DB 私有知识。
2. 只在 Discover / Score 记录命中。
3. 不返回给正式 prompt，不改变 Agent 输入。
4. `shadow_bias` 第一版可用保守启发式：
   - `methodology_type in ("risk", "sell")` -> `risk`
   - title/content 含 “加分/强化/主线/突破” -> `boost`
   - title/content 含 “降权/回避/风险/派发” -> `reduce`
   - 否则 `unknown`
5. `shadow_summary` 只保存短摘要，如标题 + 前 120 字，不调用额外 LLM。

## 接入位置

### Discover

在 `discover.py` 最终候选落库附近接入 shadow 记录：

1. 对最终候选逐个记录。
2. `agent="discover"`。
3. `trade_date` 用候选交易日。
4. query 可由候选理由/风险/关注类型拼一个短字符串。
5. 不把 shadow 结果写入 candidate detail，不进入正式输出。

### Score

在 `score.py` 评分完成或落库附近接入 shadow 记录：

1. `agent="score"`。
2. `stock_code/stock_name/trade_date` 用当前评分标的。
3. query 可由评分因子、风险列表、候选上下文拼短字符串。
4. 不改 `ScoreOutput`，不改 score 数值，不改 risk_list。

接入必须 try/except 降级，失败只 warning，不阻断主链路。

## API

在 `routes.py` 增加只读/手动接口：

1. `GET /knowledge/shadow-hits`
   - 支持过滤：`knowledge_id/agent/stock_code/trade_date/verify_status`。
2. `POST /knowledge/shadow/refresh-outcomes`
   - 手动触发回填 shadow 后验。
3. `POST /knowledge/{kid}/status`
   - body: `status` + `reason`。
   - 允许人工把 shadow 升级 active 或归档 archived。
   - 不允许自动升级。

## 不要改

1. 不改 Agent 输出 schema。
2. 不改正式 prompt 注入段序。
3. 不让 shadow 知识进入 `knowledge_section()` 正式注入。
4. 不改 RuleChange / 采纳审核闸门。
5. 不改 T+N 计算口径。
6. 不自动把 shadow 升级 active。
7. 不新增交易接口，不自动下单。

## 测试要求

新增最小测试，推荐：

```text
backend/tests/test_knowledge_shadow.py
```

覆盖：

1. `knowledge_shadow_hit` 表创建/迁移幂等。
2. `status=shadow` 不被 `knowledge_section()` 注入。
3. shadow 检索能命中当前 Agent + all 的 shadow 知识。
4. `record_knowledge_shadow_hit()` 幂等，不重复插入。
5. Discover/Score 接入 shadow 记录时不改变正式返回/落库字段，可用 monkeypatch 验证。
6. `refresh_knowledge_shadow_outcomes()` 能从 `candidate_track_verify` 回填 T+N。
7. `/knowledge/shadow-hits` 可过滤查看。
8. `/knowledge/{kid}/status` 可把 shadow 改 active/archived，reason 留痕。
9. 自动流程不会把 shadow 改 active。

必要时扩展 `test_knowledge_metadata.py`，锁定 shadow 默认不注入。

## 验收命令

只跑相关测试：

```powershell
D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_knowledge_shadow.py backend\tests\test_knowledge_metadata.py backend\tests\test_track_verify.py backend\tests\test_score_refactor.py
```

如果改到 discover 接入，再追加：

```powershell
D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_discover_v2.py
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
- shadow 未进入正式 prompt：是
- shadow 不改变正式候选/评分/交易结果：是
- T+N 口径未改：是
- 不自动升级 active：是
- 未改 RuleChange/采纳审核闸门：是
- 未开放交易接口：是

遗留/下一批：

- ...
```

