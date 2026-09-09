# 系统能力地图与 Agent 协作治理 · 批 4 Codex 执行提示词

你在 `D:\self` 项目中执行本批任务。

## 前置状态

批 1/2/3 已完成并验证：

- 批 1：系统能力地图最小闭环。
- 批 2：协作矩阵最小闭环。
- 批 3：入口路由读取系统地图与协作矩阵。
- 验证命令：`D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_system_map.py backend\tests\test_system_map_collaboration.py backend\tests\test_chat_router_system_map.py backend\tests\test_feishu_teach.py`：30 passed。

## 任务目标

实现“规则注入隔离”：`rule_change` 中已采纳 active 规则按当前 Agent / all / 兼容空值注入，减少跨 Agent 规则污染。

本批只改规则注入读取与相关测试，不改规则采纳入口治理；采纳入口治理留到批 5。

详细设计参见 `系统能力地图与Agent协作治理_方案.md`：

- §5 知识与规则隔离
- §7 批 4：规则注入隔离
- §8 Codex 执行兼容要求

## 执行纪律

1. 先用 `rg -n` 定位目标符号，只读附近代码。
2. 本批只处理 `rule_change` 注入范围。
3. 不改 `HARD_RULES` 内容。
4. 不改知识库检索逻辑。
5. 不改 Agent 输出 schema。
6. 不改采纳入口 `approve/adopt` 审核逻辑。
7. 不新增写库路径。
8. 不引入网络依赖。
9. 只跑本批相关测试。

## 先定位

```powershell
rg -n "def dynamic_rules_section|dynamic_rules_section\\(|def get_active_rules|def rule_version|class RuleChange|target_agent|rule_change" backend/app/agents/common.py backend/app/db/repo.py backend/app/db/models.py backend/tests/test_rule_change.py
```

重点确认：

1. `common.dynamic_rules_section()` 当前是否仍为无参函数。
2. `build_agent_context()` 中是否仍无参调用 `dynamic_rules_section()`。
3. `repo.get_active_rules()` 当前是否返回全部 active 规则。
4. `RuleChange.target_agent` 默认值是否仍为空串。
5. `test_rule_change.py` 是否仍有无参 `dynamic_rules_section()` 测试。

## 必做：存量规则盘点

执行代码改动前，先用最小脚本或现有 repo 函数盘点 active `rule_change.target_agent` 分布。

要求：

1. 只读查询，不改库。
2. 报告 all / 空值 / 各 Agent 数量。
3. 若空值数量 > 0，本批实现中必须保留空值兼容为 all，并在最终汇报注明“兼容阶段，污染未完全消除”。

可用方式：

```powershell
D:\self\.venv\Scripts\python.exe -c "from app.db import repo; from collections import Counter; print(Counter((r.get('target_agent') or '') for r in repo.get_active_rules()))"
```

如 import 路径需要 `backend` 工作目录或 `PYTHONPATH`，按项目现有测试写法处理；不要写临时文件。

## 建议改动

### 1. 修改 dynamic_rules_section 签名并保持兼容

在 `backend/app/agents/common.py`：

```text
dynamic_rules_section() -> dynamic_rules_section(agent: str = "")
```

兼容要求：

1. `agent=""` 时保持旧行为：返回全部 active 规则，用于旧测试和兼容调用。
2. `agent` 非空时只注入：
   - `target_agent == agent`
   - `target_agent == "all"`
   - `target_agent == ""` 或 None 的存量兼容规则
3. 过滤逻辑必须在 hard/soft 分组前完成。
4. 异常降级行为保持不变：读取失败返回空字符串，不阻塞主链路。

### 2. 修改 build_agent_context 调用

在 `build_agent_context()` 中：

```text
adopted = dynamic_rules_section(agent)
```

不要改变其它注入段顺序。

### 3. 可选 repo 轻量 helper

如实现更清晰，可在 `backend/app/db/repo.py` 增加只读 helper：

```text
get_active_rules_for_agent(agent: str) -> list[dict]
```

但不是必须。若新增 helper：

1. 不改变 `get_active_rules()` 旧语义。
2. 不改变 `rule_version()`。
3. 不写库。

### 4. 测试

更新或新增 `backend/tests/test_rule_change.py` 用例：

1. 保留原无参 `dynamic_rules_section()` 测试通过。
2. 新增 agent 过滤测试：
   - discover 规则只进 discover。
   - score 规则只进 score。
   - all 规则两个 Agent 都能看到。
   - 空 target_agent 兼容为 all，两个 Agent 都能看到。
3. 验证 `build_agent_context()` 会调用带 agent 的动态规则注入。可通过轻量 monkeypatch 或检查生成 prompt 实现。

## 验收命令

只跑相关测试：

```powershell
D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_rule_change.py backend\tests\test_system_map.py backend\tests\test_system_map_collaboration.py backend\tests\test_chat_router_system_map.py
```

不要跑全量测试。

## 红线核对

完成后逐条核对并在汇报中给结论：

1. 未改任何交易/评分/卖出/监控业务判断。
2. 未改任何 Agent 输出 schema。
3. 未改 `HARD_RULES` 内容。
4. 未改知识库检索逻辑。
5. 未改采纳入口审核逻辑。
6. 未新增写库路径。
7. 未开放任何下单/撤单/券商接口。
8. 已报告 active `rule_change.target_agent` 分布。

## 停手条件

遇到以下情况停止并报告：

1. 需要改 `RuleChange` 表结构。
2. 需要批量修改存量规则数据。
3. 需要改采纳入口治理。
4. 需要改业务 Agent 输出 schema。
5. 需要改知识库检索。
6. 存量空 target_agent 规则很多，导致无法判断是否应归属 all 或具体 Agent。

## 最终汇报格式

只汇报：

```text
存量规则盘点：
- all：X
- 空值：X
- discover：X
- score：X
- position：X
- monitor：X
- sell：X
- review：X
- 其它：X
- 若空值 > 0：兼容阶段，污染未完全消除/否

改动文件+行号：
- ...

测试：
- D:\self\.venv\Scripts\python.exe -m pytest backend\tests\test_rule_change.py backend\tests\test_system_map.py backend\tests\test_system_map_collaboration.py backend\tests\test_chat_router_system_map.py：passed X / failed Y

红线核对：
- 未改业务判断：是/否
- 未改 Agent 输出 schema：是/否
- 未改 HARD_RULES：是/否
- 未改知识库检索：是/否
- 未改采纳入口：是/否
- 未新增写库路径：是/否
- 未开放交易接口：是/否

遗留/下一批：
- ...
```
