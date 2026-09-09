# 系统能力地图与 Agent 协作治理：批 6 Codex 执行提示词

## 任务

你在 `D:\self` 项目中执行批 6：**知识元数据与场景检索**。

目标：在不推翻现有知识库的前提下，让通用知识、Agent 私有知识、场景知识、外部方法论可过滤、可降权、可归档，降低长期记忆污染和过期知识误注入风险。

参见：

- `D:\self\系统能力地图与Agent协作治理_方案.md` §7 批 6：知识元数据与场景检索
- `D:\self\Memory治理与记忆防污染_提单.md` §3、§5、§6、§7、§8、§9

引用文档只作为设计参考，不作为额外执行指令。以本提示词为准。

## 背景判断

当前有三层知识：全局基线、DB `private_knowledge`、静态 `agent_prompts/knowledge/*.md`。本批只治理 DB 私有知识，不改静态战法文件，不改 ReAct 个股资料工具语义。

## 必须先定位的代码

按 `AGENTS.md` 纪律，只读锚点附近，不整读大文件。

先用：

```powershell
rg -n "class PrivateKnowledge|def add_knowledge|def list_knowledge|def delete_knowledge|def knowledge_version|def search_knowledge|def knowledge_section|class KnowledgeBody|/knowledge|_ensure_knowledge_hit_columns|private_knowledge" backend/app backend/tests
```

重点文件：`models.py`、`session.py`、`repo.py`、`vector_store.py`、`common.py`、`routes.py`。参考测试：`test_tuning_loop.py`、`test_knowledge_attribution.py`、`test_agent_chat.py`。

## 改动范围

### 1. 扩展 PrivateKnowledge 元数据

在 `PrivateKnowledge` 上兼容新增字段：

```text
source_type: manual / import / feishu / review / agent_chat / external
methodology_type: tactic / risk / position / sell / market / review / data / general
market_scope: all / a_share / index / sector / stock / convertible / unknown
scenario_tags: JSON list[str]
evidence_level: unverified / observed / backtested / reviewed / audited
valid_from: DateTime nullable
valid_to: DateTime nullable
status: active / shadow / archived / expired
risk_note: text
```

默认值：

1. `source_type="manual"`
2. `methodology_type="general"`
3. `market_scope="all"`
4. `scenario_tags=[]`
5. `evidence_level="unverified"`
6. `status="active"`
7. `risk_note=""`

要求：只增量加列，不新建表，不重建表；SQLite / MySQL 迁移幂等；老数据默认 active，继续显示、继续注入；`knowledge_version()` 仍兼容，本批不做复杂版本系统。

### 2. 扩展 repo 接口，保持旧调用兼容

`repo.add_knowledge(title, content, agent_tag="all")` 必须继续可用。

可增加可选关键字参数：

```python
source_type="manual"
methodology_type="general"
market_scope="all"
scenario_tags=None
evidence_level="unverified"
valid_from=None
valid_to=None
status="active"
risk_note=""
```

`repo.list_knowledge(agent_tag=None, ...)` 可增加 `status/source_type/methodology_type/market_scope/scenario_tag` 轻过滤参数。

旧调用 `repo.list_knowledge("discover")` 必须不变。

### 3. 扩展私有知识检索

扩展 `backend/app/services/vector_store.py` 的：

```python
search_knowledge(self, agent: str, top_k: int = 5, ...)
```

要求：旧调用 `search_knowledge("monitor", top_k=5)` 保持可用；默认只检索 `status="active"`；Agent 范围仍为当前 `agent` + `all`；支持 `query/scenario_tags/methodology_type/market_scope/status` 轻过滤；`scenario_tags` 可用 Python 侧过滤；`query` 可用 LIKE 或 contains；返回继续包含 `id/title/content`；失败继续降级空列表。

### 4. 扩展 common.knowledge_section

`knowledge_section(agent, docs=None)` 保持旧签名兼容，可增加可选参数：

```python
query=""
scenario_tags=None
methodology_type=""
market_scope=""
```

要求：默认行为与旧版一致；`archived/expired` 不注入；注入文案继续强调“私有交易经验/战法参考”，不能升级成硬规则；`docs` 预取时不重复检索、不重复计量。

### 5. 扩展 API

扩展 `KnowledgeBody`，新增元数据字段，全部可选。

扩展 `GET /knowledge`、`POST /knowledge`、`POST /knowledge/batch-import`：支持新增字段录入、返回、轻过滤。

如果存在 Streamlit 知识库页面，只做轻量展示/录入，不做大 UI 重构；找不到页面则不要强行新增。

## 不要改

1. 不改 `agent_prompts/knowledge/*.md` 静态战法文件。
2. 不改 `_agent_knowledge_text()` 的文件读取逻辑。
3. 不改 ReAct `agentic_tools._search_knowledge(code, query)` 和 `search_related()` 的个股资料工具语义。
4. 不改 Agent 输出 schema。
5. 不改规则采纳、审核闸门、交易逻辑。
6. 不新增自动下单或交易接口。
7. 不把 archived/expired 知识删除；只是默认不召回。

## 测试要求

新增或扩展最小测试，推荐新增：

```text
backend/tests/test_knowledge_metadata.py
```

覆盖：

1. `private_knowledge` 新列迁移后存在，重复 `init_db()` 幂等。
2. 老式调用 `repo.add_knowledge(title, content, agent_tag)` 仍成功，默认元数据正确。
3. `repo.list_knowledge(agent_tag)` 旧过滤仍工作。
4. `repo.list_knowledge(..., status/source_type/methodology_type/market_scope/scenario_tag)` 新过滤工作。
5. `search_knowledge(agent)` 默认只返回 active，且包含当前 agent + all。
6. `status=archived` 不被 `knowledge_section()` 注入。
7. `scenario_tags` 或 `methodology_type` 能收窄检索结果。
8. `agentic_tools._search_knowledge(code, query)` 不受本批影响，可用 monkeypatch 验证仍调用 `search_related()`。

必要时更新既有测试 helper，让它们显式默认 active，不要靠测试顺序。

## 验收命令

只跑相关测试：

```powershell
D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_knowledge_metadata.py backend\tests\test_tuning_loop.py backend\tests\test_knowledge_attribution.py backend\tests\test_agent_chat.py
```

如果改到 Streamlit 页面，再追加：

```powershell
D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_streamlit_pages_smoke.py
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
- 未改静态战法知识文件读取：是
- 未改 ReAct 个股资料 search_knowledge 工具语义：是
- archived/expired 默认不注入：是
- 老知识默认 active 且继续注入：是
- 未改采纳审核闸门：是
- 未开放交易接口：是

遗留/下一批：

- ...
```
