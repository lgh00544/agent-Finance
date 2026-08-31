# 飞书手机接入 批2 teach 多轮补丁 v3 — A+C 组合

> 在批 2 teach 补丁 v2（97 行）基础上新增"多轮草稿模式"，配套软引导
> 路径：`D:\self\飞书手机接入_批2_teach补丁_Claude执行指令.md`（v2 同位合并，不要新建 v3 文件，in-place 在 v2 末尾追加 §七）
> 依赖：批 1/批 2/批 2 teach 补丁 v2 已落地且通过手机实测

## 〇 元信息

- **生成者**：Lark 主交付
- **执行者**：Claude Code（开新会话）
- **决策人**：sir（2026-08-29 拍板 A+C 组合）
- **原则**：A 草稿模式（用户主动控制节奏）+ C 软引导（拒时引导转 A），不引入 B 智能反问（不打断用户节奏）
- **Claude Code 端省 token 6 条 + ≤90 行改动预算**（A 80 + C 10）

## 一 目标

让 teach/remember 支持"分多轮说完再统一提交"。

- **不开多轮**：维持现状单回合判定
- **开多轮**：用户主动说"先存着/补一条/完成"控制节奏，每轮收集一条 piece，最终打包走原有 teach 审核链路
- **拒时引导**：单回合 reject 时回一行"如需多轮教，先发 `教·存草稿`"，引导用户转 A

## 二 架构约束

**不新建通路**，复用批 2 teach 补丁 v2 的：
- `_handle_teach`（chat_handlers.py:第 5 段）— 走 LLM 校验 + `add_pending_experience`
- `_handle_memory`（chat_handlers.py:第 5 段）— 走 `update_trade_profile`
- 草稿状态存在 bridge 内存表（与 pending_experience 同生命周期），不落 DB（草稿是用户私有临时数据，不入审计链）

**新增 1 个数据结构 + 1 个 handler + 4 条 chat_router 关键词**：
- `bridge._drafts: dict[open_id, DraftState]`（内存表，重启清空符合"草稿"语义）
- `chat_handlers._handle_draft`（新 handler：append / finish / cancel 三动作）
- chat_router.py 关键词表加 4 条：`先存着`/`存草稿`/`补一条`/`完成`/`放弃`/`继续` 之类（实施时取最自然的 2-3 个中文动词）
- 草稿 piece 列表中每条 piece 独立含 `{content, agent_tag, piece_type: 'fact'|'rule'}`

## 三 规则

### 3.1 草稿生命周期

- 起点：用户发"先存着"/"开始草稿"类指令 → 桥创建 DraftState，记录 `created_at`
- 续说：用户后续每发一条"补一条" + 内容 → append 到当前草稿的 pieces
- 提交：用户发"完成" → 调原 teach 链路（按 piece_type 分流：fact→remember，rule→teach），返回各 piece 处理结果
- 放弃：用户发"放弃" → 清空 DraftState，回执"已丢弃 N 条"
- 超时：24 小时无动作自动清空（bridge 启动时启动清道夫线程，每小时跑一次）

### 3.2 草稿内 piece 路由

- piece_type=fact（不命中阈值词）→ 走 `update_trade_profile`（立即生效）
- piece_type=rule（命中阈值词/教战法/新规则）→ 走 `_handle_teach`（LLM 校验 + pending）
- 同一草稿可混 fact+rule，"完成"时**逐 piece 处理**并汇总回执

### 3.3 草稿 vs 单回合兼容

- 用户没开草稿时，发"教/记住"按批 2 v2 现有逻辑处理（不变）
- 用户已开草稿时，发"教/记住 X"自动视为补一条 piece（**不**调单回合 teach 链路，避免双写）
- 用户已开草稿时，发"教 X 不存了"= 取消当前 piece 不入草稿（不影响其他 piece）

### 3.4 软引导（拒绝时一行 C）

- teach 单回合被 LLM 判 maintained（拒）→ 在原 reject 回执尾部追加：
  `如需多轮教，先发「教·存草稿」开草稿`
- 草稿模式下不触发 C 引导（草稿里 reject = 整稿拒，不会发生）
- remember 路径**不**加 C 引导（remember 阈值词已降级走 teach，无歧义）

### 3.5 草稿隔离

- 草稿严格按 open_id 隔离（一人一稿）
- 同一 open_id 已开草稿时，再发"开始草稿"= 询问"已有 N 条草稿，继续/放弃？"
- 草稿不写 DB（不入审计/不入 preference），重启清空可接受（草稿是会话级临时数据）

## 四 实现参考 + 0 步

**0 步（必做）**：先 grep 确认 `bridge._drafts` 不存在 / 关键词无冲突：
```
grep -n "_drafts\|存草稿\|补一条\|完成\|放弃" backend/app/services/feishu_bridge.py backend/app/services/chat_router.py backend/app/services/chat_handlers.py
```

**复用现有风格**：
- 关键词注册看 `chat_router.py:38` help intent 附近的 KEYWORD_TO_INTENT 映射（实施时按位置插入）
- pending_experience 提交看 `chat_handlers.py` 现有 `_handle_teach`（`add_pending_experience` 调用处）
- remember 走 `update_trade_profile`（与批 2 v2 同通路）

## 五 执行顺序

1. 在 `feishu_bridge.py` 加 `DraftState` dataclass + `bridge._drafts: dict[str, DraftState]` + 清道夫线程（24h 过期）
2. 在 `chat_handlers.py` 新增 `_handle_draft(open_id, text) -> str` 三动作（append/finish/cancel）
3. 在 `chat_router.py` 关键词表插入 3-4 个草稿动作关键词（先存着/补一条/完成/放弃）
4. 修改 `chat_handlers._handle_teach` 和 `_handle_memory` 入口：开草稿用户的消息自动走 `_handle_draft` 而不是原 handler
5. `_handle_teach` reject 尾部加 C 引导（1 行）
6. 自测：开草稿 → 补 3 条（混 fact/rule）→ 完成 → 验证 3 条按 piece_type 落库 + 草稿清空
7. pytest 加 4-5 用例（开草稿/补一条/完成/放弃/拒时引导）

## 六 验证清单

- [ ] 草稿不写 DB（grep `INSERT INTO.*draft` 0 命中）
- [ ] 开草稿后发"教 X"自动进草稿不进 pending（先验证落 pending_experience 0 命中）
- [ ] 完成时 fact 走 trade_profile、rule 走 pending（两条路各走一次成功）
- [ ] 24h 过期清空（mock 当前时间后查 `_drafts` 已空）
- [ ] 拒时引导文案一字不差（grep "如需多轮教" 命中 + 紧跟 reject 文案后）
- [ ] 草稿内 0 piece 时发"完成"→ 回"草稿为空，无可提交"
- [ ] pytest 全过；全量回归零新增失败

## 七 红线

1. **不绕过审核门**：草稿里 rule 类型 piece 仍走 `_handle_teach` → pending，与批 2 v2 一致
2. **草稿不落 DB**：仅内存表（`_drafts` 字典），重启清空可接受
3. **不动 v2 已测逻辑**：批 2 teach v2 的 _handle_memory / _handle_teach / _guard_hard 内部**不修改**，仅在入口加"开草稿用户走 _handle_draft"的分支判断
4. **不引新库**：用现有 dataclass + 字典 + 线程清道夫（threading.Timer 即可）
5. **预算 ≤90 行**（A 草稿 80 + C 引导 10），超出停下报告 sir
6. **改动行数预算简单 ≤50 / 中等 ≤80 / 复杂 ≤150 行**；超出 → 停下报告 sir
7. **Claude Code 端省 token 6 条**（不复读提示词 / 不写超出范围代码 / 不写大段注释 / 复用已有函数 / 测试 ≤5 个 / 报告 ≤10 行）

## 八 备注

- v2 路径在 `D:\self\飞书手机接入_批2_teach补丁_Claude执行指令.md`，本补丁不新建 v3 文件，in-place 在 v2 末尾追加 §七 段即可
- 改动行数预算：v2 现状 97 行 + 本补丁 ≤90 行 = 累计 ≤187 行，远低于批次上限
- 提交 commit message：`feat(feishu): teach 多轮草稿模式(A) + 拒时软引导(C)`，单独一笔 commit
- 完工后给 sir ≤10 行报告：①改了什么文件 ②测试结果 ③遗留风险
