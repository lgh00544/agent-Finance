# 批 18：System Map 事实源导入路径一致性修复

请在 `D:\self` 项目中执行本批任务。

## 一、当前基线

系统治理批次 1～17 已完成到当前工作树，尚未统一提交。

批 17 已补齐：

- `market_intel` 出现在 `registry.list_agents()`
- `portfolio_sentinel` 出现在 `registry.list_agents()`
- 两者未加入 `AGENT_CHAT_META`，仍不是用户直接聊天 Agent
- 未新增协作 allow 关系

但批 17 验收时发现一个新的运行环境问题：

从 `D:\self\backend` 目录直接运行：

```powershell
D:\self\.venv\Scripts\python.exe -c "from app.system_map import integrity; print(integrity.check_system_map_integrity())"
```

会得到：

```text
source_read_error: No module named 'agent_prompts'
```

而相关 pytest 在 `D:\self` 根目录下可以通过。

这说明完整性检查依赖的事实源导入路径，在不同启动目录 / PYTHONPATH 下不一致。

## 二、本批目的

修复 System Map 完整性事实源读取的导入路径一致性，使健康页和完整性检查在真实后端启动方式下稳定工作。

本批解决的问题：

1. 完整性检查不能只在 pytest 环境下通过。
2. `/system-map` 健康页不能因启动目录不同而显示 `source_read_error`。
3. `agent_prompts` 作为项目级提示词目录，被部分 Agent 以顶层模块导入，必须明确运行时路径契约。
4. 后续 Codex / opencode 执行批次时，应知道从哪个目录启动、怎样验证。

本批不是扩大 System Map 功能，不是新增 Agent，也不是把错误吞掉。

## 三、先定位真实启动路径

不要先改代码。先使用 `rg` 精准定位并读取：

- `backend/app/main.py`
- `backend/app/agents/market_intel.py`
- `backend/app/agents/portfolio_sentinel.py`
- `backend/app/graph/graphs.py`
- `backend/app/system_map/integrity.py`
- `backend/app/system_map/health.py`
- `backend/app/core/config.py`
- `pyproject.toml` / `pytest.ini` / `setup.cfg` / `backend/pyproject.toml` 如存在
- 启动脚本、bat、docker、README 中的 uvicorn 启动命令
- 所有 `from agent_prompts` / `import agent_prompts` 调用
- 所有 `from app.` 调用

必须先回答：

1. 后端标准启动目录到底是 `D:\self` 还是 `D:\self\backend`。
2. `agent_prompts` 是否设计为项目根目录顶层包。
3. pytest 为什么能通过，直接从 `backend` 目录为什么失败。
4. 当前 dev server / uvicorn 实际如何启动。
5. 修复应该落在启动路径、导入方式，还是完整性事实源的导入边界。

## 四、修复原则

优先选择最小、明确、可验证的修复。

可选方向包括但不限于：

### 方向 A：明确运行时路径并在启动入口补齐

如果项目约定 `agent_prompts` 是根目录模块，可以在后端启动入口或包初始化中以最小方式确保项目根目录进入 `sys.path`。

要求：

- 只添加项目根目录，不添加任意外部路径。
- 不泄露敏感路径到接口。
- 不影响 pytest。
- 不制造循环导入。
- 不在完整性检查中伪造成功。

### 方向 B：修正 Agent 提示词导入方式

如果代码风格允许，也可以统一将 Agent 中的 `from agent_prompts import ...` 调整为稳定导入方式。

要求：

- 改动面必须可控。
- 不改变 prompt 内容。
- 不改变 Agent 输出 schema。
- 不改变调用链。
- 覆盖所有相关导入。

### 方向 C：完整性检查延迟或降级读取事实源

仅当 A/B 都不合适时，允许让 `integrity._source_snapshot()` 避免导入会触发 `agent_prompts` 的重模块。

要求：

- 不能把真实导入错误吞掉后显示 healthy。
- 不能凭猜测构造 graph_agents。
- 如果无法读取事实源，应保留 error/unknown，并给出可定位原因。

不要选择“捕获 ImportError 然后忽略”这种假修复。

## 五、验证矩阵

修复后必须验证以下命令都能得到一致结果：

### 1. 项目根目录验证

```powershell
cd D:\self
D:\self\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend'); from app.system_map import integrity; r=integrity.check_system_map_integrity(); print(r['status'], r['summary'])"
```

### 2. backend 目录验证

```powershell
cd D:\self\backend
D:\self\.venv\Scripts\python.exe -c "from app.system_map import integrity; r=integrity.check_system_map_integrity(); print(r['status'], r['summary'])"
```

### 3. FastAPI health 入口验证

如果已有 dev server，可探活：

```text
GET /api/system-map/health
```

重点确认：

- 不再出现 `No module named 'agent_prompts'`
- `registration_integrity` 不因导入路径失败而 error
- 如果仍有真实 issue，要显示真实 issue，而不是 source_read_error

## 六、测试要求

只新增或修改本批直接相关测试，至少覆盖：

1. 从项目根目录导入完整性检查成功。
2. 从 `backend` 目录导入完整性检查成功。
3. `agent_prompts` 能被 `market_intel` 和 `portfolio_sentinel` 相关导入链找到。
4. 完整性检查不会因为导入路径问题返回 `source_read_error`。
5. `registration_integrity` 健康模块能显示真实状态。
6. 如果真实 registry/handler/tool 漂移存在，仍然返回真实 issue。
7. 不把 ImportError 静默吞成 healthy。
8. 修复不改变 Agent prompt 内容。
9. 修复不改变 Agent 输出 schema。
10. 不新增写库、任务执行、自动审核或交易路径。

运行最小相关测试：

- 本批新增测试
- `test_batch16_system_map_integrity.py`
- `test_system_map_health.py`
- `test_system_map.py`
- 必要时运行 `test_market_intel.py` / `test_portfolio_sentinel.py` 相关最小测试

不要默认跑全量测试。

## 七、治理红线

必须保持：

- System Map 只读。
- 完整性检查只观察，不自动修复。
- 不隐藏真实错误。
- 不把 unknown/error 伪装成 healthy。
- 不修改 prompt 内容。
- 不改变 Agent 输出 schema。
- 不改变 Knowledge、Shadow、Memory、RuleChange、Audit、Collaboration 语义。
- 不改变 `chat_handlers.dispatch()` 拒绝语义。
- 不新增业务写库路径。
- 不开放自动交易、下单或撤单接口。

## 八、实施前说明

开始修改前先说明：

- 标准启动目录和当前失败目录
- `agent_prompts` 的真实定位
- pytest 通过但直接导入失败的原因
- 选择 A/B/C 哪个修复方向及理由
- 风险、缓解方式和预期效果

## 九、完成后汇报

完成后只汇报：

- 改动文件 + 行号
- 测试 passed / failed
- 根目录与 backend 目录两种导入验证结果
- `/system-map` 健康页是否还存在 `source_read_error`
- 是否仍有真实完整性 issue
- 红线逐条核对
- 是否存在未提交改动

不要自动提交 Git。
