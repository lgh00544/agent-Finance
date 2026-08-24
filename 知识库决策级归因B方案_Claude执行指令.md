# 知识库决策级归因 B方案_执行指令（省token版）

## §0 元信息
- 生成者：Lark / 决策人：sir / 执行端：Claude Code
- 原则：仅加"可观测"，不改任何推理/交易逻辑。红线见 §五。

## §一 目标
给私有知识库（private_knowledge）补上"决策级归因"反馈，让 sir 能回答三问：①哪条知识被哪个 Agent 检索到了 ②命中多少次/多久没被用（死知识）③有哪次决策/对话真的引用了它。

**不做**：不改 LLM 推理、不改各 Agent 判级/回吐规则、不加新表不改 trade 判定。

## §二 架构约束
- 只动 4 处：`vector_store.py`（返回补 id）/ `db/repo.py`（命中计量两方法）/ `agents/common.py`（注入段带统一编号 + 命中时自增）/ `services/agent_chat.py`（ChatCompletion 加引用字段，提示词加一条）。
- 表中加字段走 `_ensure_*`（仿 `_ensure_quote_snapshot_table`）在启动时 ALTER，不手写迁移。
- 保持"失败不阻塞主链路"铁律：计量自增失败只 logger.warning，不抛异常。

## §三 规则
- `search_knowledge` 返回 `[{"id":int,"title","content"}]`（id 必带，勿破坏现有调用）。
- 新增计量：`private_knowledge` 加 `hit_count INT NOT NULL DEFAULT 0` + `last_used_at DATETIME NULL`。
- 命中自增时机：`knowledge_section(agent)` 成功拿到 docs（len>0）时，对每条的 id 执行 `repo.bump_knowledge_hit(id)`（hit_count+1、last_used_at=now）。批量一次 UPDATE，不逐条。
- 注入段格式改为**带统一编号**：
  `【你的私有交易经验/战法参考】（编号与本段一致，若在研判/回答中采用了某条，必须在下方"引用的知识"里回吐其编号）
  1. 【{title}】{content}
  2. ...（按 docs 顺序 1..N，最多 top_k=5 条）`
- `knowledge_section` 需把 docs（含 id+编号）一并返回给调用方（改函数签名或返回 tuple），供 agent_chat 注入编号映射。
- `ChatCompletion` 新增 `used_knowledge: list[dict]`（默认空，描述："本次回答/研判实际引用的私有知识，[{id:int,title:str}]，未引用则留空数组"）。
- 提示词 `_CHAT_SYSTEM_PROMPT` 第 3 条后追加一条：`若实际采用了注入的私有知识库某条，在 used_knowledge 回吐其编号与标题，代码层据此写回命中；未采用填空数组。`
- 展示：knowledge 页/knowledge 列表接口补 `hit_count` + `last_used_at` 字段（只读展示，不渲染逻辑）。

## §四 执行顺序
1. `db/models.py` PrivateKnowledge 加 `hit_count` + `last_used_at` 字段
2. `db/session.py` `_ensure_private_knowledge_table`（或对应的 ensure 钩子）启动时 ALTER 补两列
3. `db/repo.py` 加 `bump_knowledge_hit(id)` + `list_knowledge` 返回补两字段
4. `services/vector_store.py:193` `search_knowledge` 返回补 `id`（改返回 dict，勿动调用方对 title/content 的依赖）
5. `agents/common.py:143` `knowledge_section(agent)` 改为返回 `(注入文本, docs列表含id+编号)`；命中时 `bump_knowledge_hit`；文本升级为带编号格式
6. `services/agent_chat.py` ChatCompletion 加 `used_knowledge` 字段 + `_CHAT_SYSTEM_PROMPT` 加引用回吐指令 + 解析后把 used_knowledge 逐条 `bump_knowledge_hit` 写回
（若 B 只做"命中计量"止损、暂不强约束 LLM 回吐，则第 6 步的"写回"可保留但 used_knowledge 允许空——见 §六 说明）

## §五 红线（不能省）
- 不改任何 Agent 的判级/评分/买卖/回吐逻辑（Discover/Score/Position/Monitor/Sell/Review），纯观测。
- 不改 HARD_RULES / 6 因子权重 / 交易规则 / review_log 决策语义。
- 不改 Streamlit（前端默认 React `web/src/`）。
- `bump_knowledge_hit` 只加不自减：不因"未用"清零，便于看历史累计命中。
- 计量失败降级：任何 `bump_*` 异常只 warning，绝不让知识注入这段因此抛错阻塞主链路。
- 不新建表、不引新库（沿用现有 SQLite ALTER + 现有 vector_store 检索）。

## §六 验证清单
- [ ] `search_knowledge` 返回 3 项含 id（grep 断言 + 单测）
- [ ] `private_knowledge` 表两新列存在（dev.db `PRATTABLE` / `PRAGMA table_info` 核对）
- [ ] `bump_knowledge_hit` 单测：调 3 次 → hit_count=3、last_used_at 更新
- [ ] `knowledge_section` 注入文本带"1. 2. 3."编号头
- [ ] React 知识页/列表接口能读到 hit_count + last_used_at 并展示
- [ ] 全量回归：`pytest` 仅跑与 private_knowledge / agent_chat / vector_store 相关文件；改动 ≤150 行
- [ ] 汇报 ≤10 行（改了啥/测试/风险）

## 附：B 与 A 的关系说明（决策者已知，执行端不用管）
A（仅命中计量）是 B 的子集。本指令默认做 B（计量 + LLM 引用回吐），若执行中 used_knowledge 强制结构影响测试面过大，可先提交"命中计量 + 注入编号 + 展示"（即 A），LLM 回吐写回作为后续批次。
