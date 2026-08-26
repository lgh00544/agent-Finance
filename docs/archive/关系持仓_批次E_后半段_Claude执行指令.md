# 关系持仓批次 E · 后半段（4 步收口）· Claude Code/DSH 执行指令

> 前半段已落地（capital_view.py / models / init.sql / session / repo / monitor.py collect 已改）· 本提示词只覆盖后半段 4 步
> 起点：步骤 1 · 终点：commit（不 push）· 详细背景：`关系持仓_批次E_Claude执行指令.md` §一/二/三 + DSH 报告 §三 5 处前端 diff

## 一、目标（4 步）

1. 覆盖正式测试文件 `test_capital_view.py`（DSH 因环境只读无法覆盖，需 Claude Code 在有写权限环境执行）
2. Apply 5 处前端/API 补丁（`types/index.ts` / `api/hotMoney.ts` / `pages/HotMoneyPage.tsx` / `streamlit/api_client.py` / `streamlit/pages/5_游资追踪.py`）
3. 跑 3 类验证：5/5 新测 + 定向回归 + `npm run build`
4. 清理临时（8 个 `_tmp_*` + `_tmp_db_inspect.py`）+ commit

## 二、规则（与前半段一致）

**5 红线**：①不动 agent_call/push_alert_node ②不碰 _TR 表 ③不写「无数据=无动作」（K227）④不硬绑席位映射 ⑤单源必标 source。

**已知 2 失败**（**与本批无关，保持原样**不修）：`test_agents_collect_inject_capital_view`（score.llm_score 读 state.get 而测试未给 state 注入，设计缺陷） + `test_force_cache_bypass`（routes.cache 非模块属性）。本批 commit **不阻塞**。

**已知 .bak 残留**：`git add -A` 后若带入，手动 `git reset HEAD *.bak*` 撤销（.bak 已在 .gitignore 范畴内）。

## 三、执行顺序（4 步）

### 步骤 1 · 覆盖正式测试文件

```bash
cd /d/self
cp backend/tests/_verify_capital_fix4.py backend/tests/test_capital_view.py
python -m pytest backend/tests/test_capital_view.py -v
```
**预期**：5/5 PASS（①K189 wash_suspect=True ②30 日无数据→coordination="数据不足" ③recent_actors 字段齐全 ④4 Agent collect 注入 ⑤force=true 跳缓存）。

### 步骤 2 · Apply 5 处前端/API 补丁

按 `关系持仓_批次E_Claude执行指令.md` §三 1-5（DSH 报告 §三同款）的 diff **1:1 复制粘贴**，不重写：

| # | 文件 | 位置 | 改动 |
|---|---|---|---|
| 2.1 | `web/src/types/index.ts` | L338 后 | 追加 `CapitalViewActor` / `CapitalViewRow` / `CapitalView` 3 interface |
| 2.2 | `web/src/api/hotMoney.ts` | import 改 + 文件末尾 | `import type { CapitalView, ... }` + 末尾追加 `capitalView(code, force)` |
| 2.3 | `web/src/pages/HotMoneyPage.tsx` | import + 新组件 + Tabs | import 改 + 末尾追加 `<CapitalViewPanel />` + Tabs items 末尾加 `{ key: 'capital', label: '个股资本视图', children: <CapitalViewPanel /> }` |
| 2.4 | `streamlit/api_client.py` | L414-416 后 | 追加 `capital_view(stock_code, force=False)` |
| 2.5 | `streamlit/pages/5_游资追踪.py` | L394 后 | 追加 6.个股资本视图模块（fold_module + 三维表 + 红/黄/灰徽章）|

### 步骤 3 · 跑 3 类验证

```bash
# (a) 新测试
python -m pytest backend/tests/test_capital_view.py -v
# 预期：5 passed

# (b) 定向回归（含 E/G/H 已落地模块 + E 既有 2 失败 known issue）
python -m pytest backend/tests/test_{capital_view,distribution_phase,red_line_check,track_verify_attribution,hot_money_inject,batch2_reduce_ratio,state,rule_change}.py -v
# 预期：除 E 既有 2 失败外全绿，known issue 不阻塞 commit

# (c) web build
cd web && npm run build && cd ..
# 预期：EXIT=0，零 TS 错
```

任一**不通过立即停手报告 sir，不 commit 半成品**。

### 步骤 4 · 清理 + commit

```bash
# (a) 清理临时
rm -f /d/self/backend/tests/_verify_capital_fix.py
rm -f /d/self/backend/tests/_verify_capital_fix2.py
rm -f /d/self/backend/tests/_verify_capital_fix3.py
rm -f /d/self/backend/tests/_dbg_force.py
rm -f /d/self/backend/tests/_dbg_force2.py
rm -f /d/self/_tmp_capital_view_verify.py
rm -f /d/self/_tmp_debug_cache.py
rm -f /d/self/_tmp_db_inspect.py

# (b) 验证工作区
cd /d/self && git status -s
# 预期：仅剩 8 个 M 后端 + 5 处前端 M + 新 test_capital_view.py（变 M），无 _tmp_* 残留，无 .bak 入 commit

# (c) commit（不 push）
cd /d/self && git add -A
# 若 .bak 被带入：git reset HEAD *.bak*
git commit -m "[批次E] 游资数据真接入：dragon_tiger_source + 4表 + capital_view + K189对倒 + 4 Agent 注入 + 前端徽章"
```

## 四、commit 后报告（≤ 10 行给 sir）

```
① commit hash（git log --oneline -1）
② 测试：test_capital_view.py N/N + 定向回归 N passed / N failed（列出 failed）
③ 前端：5 处 Apply Y/N + npm build EXIT=?
④ 清理：_tmp_* 0 个 + .bak 入 commit 否
⑤ 遗留：E 既有 2 失败标 known issue 下批处理
```

## 五、省 token 6 条

①禁止复读 DSH 报告全文，只 grep `capital_view` / `wash_suspect` / `_verify_capital_fix4`
②只动本批 5 处前端 + 1 测试覆盖 + 8 个清理文件，禁止顺手改其他
③复用 `routes.py:1082` 已落路由 + `capital_view.py` 已落 service
④不写新注释（docstring ≤ 3 行）
⑤不重写 DSH 已落文件（仅 Apply 增量）
⑥报告 ≤ 10 行

## 六、沟通节点

- 步骤 1 `cp` 失败（写保护）→ 报告 sir
- 步骤 2 任一文件冲突 → 报告 sir 选 (a) 手动解决 / (b) 跳过该补丁
- 步骤 3 任一不通过 → 立即停手报告 sir
- 步骤 4 commit 失败 → 报完整错误信息
- 全部完成 → 把 §四 5 项填好转给 sir，停等 5 批次收口报告
