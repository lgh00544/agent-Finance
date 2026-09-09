# 采纳前预览模块 · 5 批次 Claude 执行指令

> **执行者**：Claude Code
> **方案**：`D:\self\采纳前预览_方案.md` v1（**禁止再读全文，只 grep 关键标识**）
> **省 token 提示**：本文件 6 段已齐备，已固化阈值/红线/字段；执行时**只 grep 关键标识确认行号**

## §0 元信息

- **生成者**：Lark
- **执行者**：Claude Code（单批次独立会话，不要跨批次复用长会话）
- **决策人**：sir
- **任务**：采纳前预览 5 批次全套（后端 API + 弹窗 + 全链路 diff）
- **依赖**：无（独立模块）
- **总估时**：3-5 天（每批半天 ~ 1 天）

## §一 目标

让"复盘建议 → 人工采纳"不再是黑盒。点采纳前弹窗显示**采纳前 vs 采纳后**的 3 块 diff（候选池 / 排名 / 触发线），二级按钮二次确认。

5 批次：

| 批次 | 范围 | 验收 |
|---|---|---|
| **批 1** | 后端 `POST /agent-suggestions/{sid}/preview` + `services/suggestion_preview.py` + Discover diff | curl 返回 candidates 块 |
| **批 2** | React `SuggestionPreviewModal` + 候选池 diff + 二次确认 | 评审页点采纳弹窗显示新增/消失 |
| **批 3** | Score 排名 diff 集成 | 弹窗"排名"tab |
| **批 4** | Position+Monitor 触发线 + 风险敞口 | 弹窗"触发线"tab |
| **批 5** | preview_log 历史回放 + 软/硬规则视觉区分 | "最近预览"tab |

## §二 架构约束

### 新增（不删不改）
- **后端**：`backend/app/api/routes.py` 新增 `POST /agent-suggestions/{sid}/preview` 端点
- **后端**：`backend/app/services/suggestion_preview.py` 新建（dry-run 调度 + diff 计算）
- **后端**：`backend/app/db/models.py` + 迁移（如有 ORM）新增 `preview_log` 表（批 5）
- **前端**：`web/src/components/SuggestionPreviewModal.tsx` 新建
- **前端**：`web/src/api/suggestions.ts` 新增 `previewSuggestion(sid)`
- **前端**：`web/src/pages/ReviewsPage.tsx:119` 改 onClick 拦截

### 解耦红线
- **不动** `agent_call` 内部缓存逻辑——只新增 `dry_run: bool = False` 透传标志
- **不动** LangGraph 节点（`graphs.py:20-32`）——预览走独立 service
- **不动** Agent 业务逻辑（discover/score/position/monitor 主体）——profile/rule 走 in-memory 临时 patch
- **不动** 现有 UI 布局——只加弹窗
- **不引新库**——AntD Modal/Drawer 已有；diff 手写或用 `diff-match-patch`（如项目已有）

### 接口字段
- **请求**：`{ suggestion_id: int, confirm: bool = False, baseline: "latest"|"frozen" = "latest" }`
- **响应** PreviewDiff JSON（参见方案 §2.2）：
  - `snapshot_id / duration_ms / agents_called`
  - `candidates: { added[], removed[], total_before, total_after }`
  - `ranking: { up[], down[] }`（批 3 起）
  - `triggers: { position[], monitor[] }`（批 4 起）
  - `risk: { exposure_pct_before, exposure_pct_after, max_single_pct }`（批 4 起）
  - `warnings: string[]`（硬规则必填）

## §三 规则（不可省）

### 1. dry_run 透传（每批次都遵守）
- `discover.run(dry_run=True)` / `score.run(dry_run=True)` / 等
- dry_run=True 时所有 `INSERT/UPDATE/DELETE` 走短路（不真写 DB）
- dry_run=True 时 `cache_key = f"preview:{sid}:{session_id}"`（不入业务缓存）
- dry_run=True 时 `SimpleCache.get/set` 短路返回

### 2. 临时 patch 30s 自动回滚
- profile 临时 patch：`sys_trade_profile.content[field] = suggestion.value`
- rule 临时 patch：`rule_change` 表内存副本
- `finally` 强制还原原始 content
- `try/finally` 必须包住整个 preview 流程

### 3. 预览阈值
- **超时熔断 30s**（`asyncio.wait_for` 或 threading.Timer）
- 任一 Agent 超时 → 该模块 `partial=true` 继续返回
- 排名升降最大展示 10 条（多则按 score_delta 排序截断）
- 触发线变化最大展示 5 条

### 4. 硬规则视觉区分（批 5）
- `rule_type == "hard"` → 红色 `Tag color="red"` + ⚠️ 图标
- `rule_type == "soft"` → 橙色 `Tag color="orange"`
- 硬规则在弹窗顶部多一行 `Alert type="error"` 警告

## §四 执行顺序

**每批独立 Claude Code 会话**，按依赖排：

```
批 1（必先）
  ↓
批 2（依赖批 1）
  ↓
批 3 ∥ 批 4（并行，依赖批 2）——按工作量选先做哪个
  ↓
批 5（依赖批 1-4）
```

### 批 1 执行步骤
1. `backend/app/services/suggestion_preview.py` 新建：`class SuggestionPreview` 含 `preview(sid, confirm, baseline)` 方法
2. 临时 patch：`save_profile_snapshot()` / `restore_profile_snapshot()` / `save_rule_snapshot()` / `restore_rule_snapshot()`
3. dry-run 调度：按 `target_agent` 字段决定调哪个 Agent（discover / score / position / monitor）
4. diff 计算：候选池 = `set(after) - set(before)` 算 added/removed
5. `backend/app/api/routes.py` 新增端点（参考 `routes.py:1487 adopt_agent_suggestion` 模式）
6. 跑通 `curl -X POST /agent-suggestions/{sid}/preview` 返回 candidates 块
7. 测试 3 例：dry_run=True / 软规则 / 硬规则（无 confirm）

### 批 2 执行步骤
1. `web/src/components/SuggestionPreviewModal.tsx` 新建：AntD `Modal` + `Tabs`
2. 复用 `web/src/pages/MarketIntelPage.tsx:76` 之后的样式（已有 conf-bar 组件）
3. "候选池" tab：上"新增 N" + 下"消失 M"，每条一行（代码 + 名称 + 原因）
4. `web/src/api/suggestions.ts` 新增 `previewSuggestion(sid, { confirm, baseline })`
5. `web/src/pages/ReviewsPage.tsx:119` 改 onClick：先 `await previewSuggestion(sid)` → 弹窗 → 二次按钮
6. "确认采纳"按钮调原 `adoptSuggestion(sid, confirm=true)`
7. 测试 1 例：弹窗显示新增/消失/确认采纳/取消 4 路径

### 批 3 执行步骤
1. 后端扩展 `SuggestionPreview.preview()` 增加 ranking 块：调 `score.run(dry_run=True)` 拿前 50 排名
2. 排名 diff：按 score 排序取前 20，比对 before/after
3. `up[] / down[]` 数组（按 score_delta 排序）
4. 前端 "排名" tab：列表 + 排名变化徽章（↑+12 绿 / ↓-7 红）
5. 测试 1 例：采纳"风险偏好"类建议，排名重排

### 批 4 执行步骤
1. 后端扩展：调 `position.run(dry_run=True)` 拿所有 holding 的触发线快照 + `monitor.run(dry_run=True)` 拿告警快照
2. `triggers.position[]` / `triggers.monitor[]` 按持仓分组
3. `risk.exposure_pct_before/after` 从 `holding.cost` 聚合
4. 前端 "触发线" tab：表格 + 状态 Tag（未触发灰 / 已触发红）
5. 风险敞口变化用 AntD `Statistic` 展示
6. 测试 1 例：硬规则 C1 阈值改后，触发线变化正确

### 批 5 执行步骤
1. 后端新增 `preview_log` 表（id / sid / snapshot_id / user / previewed_at / diff_summary / duration_ms / partial）
2. 每次 preview 成功后写入（dry_run 不影响——这是写审计表）
3. `backend/app/api/routes.py` 新增 `GET /preview-history?sid=xx`
4. 前端 "最近预览" tab：时间倒序列表，每条点击可回看 diff
5. 软/硬规则视觉区分：硬规则红 tag + ⚠️ + 顶部 Alert
6. 测试 1 例：硬规则预览，警告条显示

## §五 验证清单（每批次）

- [ ] 批 1：`curl -X POST /agent-suggestions/{sid}/preview` 返回 candidates 块合法 JSON
- [ ] 批 2：评审页点采纳弹窗显示新增/消失/确认/取消 4 路径全过
- [ ] 批 3：弹窗"排名" tab 显示 up/down 最多 10 条
- [ ] 批 4：弹窗"触发线" tab 显示 position+monitor 最多 5 条 + 风险敞口
- [ ] 批 5："最近预览" tab 倒序展示 + 软/硬规则视觉区分正确
- [ ] 全程 sys_trade_profile / rule_change 表无写入（K222）
- [ ] LLM 缓存键无 `preview:` 污染
- [ ] 预览超时 30s 熔断，部分 Agent 返回 `partial=true`
- [ ] 临时 patch `try/finally` 自动回滚验证（强杀进程不污染）

## §六 红线（绝对不可破）

1. **预览绝不落库**（K222）——所有 INSERT/UPDATE/DELETE 在 dry_run=True 时短路
2. **预览不入 LLM 缓存**——cache_key 强制 `preview:` 前缀
3. **临时 patch 30s 自动回滚**——`finally` 强制还原
4. **仅人工触发**——后端无 cron / scheduler 调度
5. **不引新库**——AntD + 已有 diff 库
6. **不动 Agent 业务逻辑**——只新增 `dry_run` 透传标志
7. **不动 LangGraph**（`graphs.py:20-32`）——预览走独立 service
8. **不动现有 UI 布局**——只加弹窗

## §七 Claude Code 端省 token 6 铁律

1. **不复读提示词已固化信息**——6 段 + Schema + 阈值已齐备，**禁止再 read 方案全文**（只 grep 关键标识确认行号）
2. **不写超出提示词范围的代码**——列了改哪几个文件就只动那几个，禁止顺手改其他文件
3. **不写大段注释**——函数 docstring ≤ 3 行，函数体内不写 `# 注释`（除关键 trade-off）
4. **复用已有函数**——`agent_call` / `SimpleCache` / `repo.update_trade_profile` 已有实现直接调，禁止重写
5. **测试用例不超规定数量**——批 1 = 3 例，批 2-5 各 1 例，共 7 例
6. **报告精简**——每批执行完毕报告 ≤ 10 行：①改了什么（文件清单）②测试结果 ③遗留风险

**代码侧最小改动铁律**：每批 ≤ 200 行（含测试），超出 → 停下报告 sir，不要自行加功能。
