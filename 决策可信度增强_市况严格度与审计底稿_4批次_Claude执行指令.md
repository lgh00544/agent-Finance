# 决策可信度增强：市况严格度 + 审计底稿 4批次合一 执行指令

> 生成者：WorkBuddy（助手）
> 执行者：Claude Code
> 决策人：sir
> 原则声明：把 claw 的可审计决策纪律落成代码层结构化产物。核心 = 从「只见结果」升级为「结果+为什么+依据」，在现有市况骨架上加两层，不推翻现有体系。关联上游方案文档：`D:\self\决策可信度增强_市况严格度与审计底稿_方案.md`（sir 已审核，5 处修正 in-place 写入，本指令以其为唯一标准）。

---

## 〇、元信息

- **批次数**：4（依赖串联 1→2→3→4，每批验收后停下问 sir）
- **工时预估**：批次1+2（后端）≈1.5 天；批次3（后端）≈0.5 天；批次4（前端）≈1 天
- **红线总表**：见 §七（执行期不得越界）
- **前置**：方案文档已含全部字段/函数/路径，本品仅含需求+规则+约束，不含实际代码，风格由执行端按项目统一。

---

## 一、目标

1. **市况严格度**：现有 `market_cap_bands` 4 档升级为「候选池上限 + 宏观定级(极差/坏/中/好) + 严格度(极严/严格/标准/宽松)」；严格度基准 = 五维评分分档 + MarketIntel(risk_appetite/phase) 修正。
2. **审计底稿 A 层**：每只候选 detail 加 `audit` 结构化字段（6 项判定 + passed/evidence 证据 + verdict + passed_ratio）。
3. **审计底稿 B 层**：`judge_tradeable` 的可建仓判定原因升级为 `block_details` 结构化数组（落 `detail["block_details"]`）。
4. **前端审计卡片**：候选池顶部市况徽章横幅 + 每行可展开审计卡片（Antd expandable）。

## 二、架构约束

- **只加字段/刻度/展示，不重建**：不改五维评分维度定义、不改候选生成与排序逻辑、不改 HARD_RULES/交易规则/研判标准表。
- **严格度只改 `judge_tradeable` 的 `is_tradeable` 结果**（可建仓/不可建仓），**绝不改 `rank` 排序分数**（见 §1.3 边界铁律）。
- **禁止动 `repo.upsert_candidate` / `repo.upsert_candidate_tradeable` 内部**（被多 Agent 共用）。审计/拒绝明细字段由 Discover/judge 层构造完整后作为 detail 子 dict 写入。
- **MarketIntel 缺失不瘫痪**：修正函数拿不到数据 → 退化基底严格度。
- **前端只读**后端已落库字段，不二次计算。

## 三、规则

### 批次 1（后端 · 市况严格度）
- `market_cap_bands` 每档结构扩展为 `[低分, 高分, 候选池上限, 档位名, 宏观定级, 严格度]`：
  | 分 | 上限 | 档位名 | 宏观定级 | 严格度 |
  |---|---|---|---|---|
  | 0-20 | 5 | 防御期 | 极差 | 极严 |
  | 21-35 | 10 | 过渡期 | 坏 | 严格 |
  | 36-45 | 15 | 温和期 | 中 | 标准 |
  | 46-50 | 20 | 强势期 | 好 | 宽松 |
- `market_band_info(score)` 返回 `(cap, band, grade, strictness)`。
- **⚠️ P0 兼容性铁律**：Python 双解构 `cap, band = market_band_info(x)` 遇 4 元组必抛 ValueError。**必须同步**改全部 4 处调用方为 `cap, band, *_ = market_band_info(...)`：
  - `backend/app/agents/discover.py:174`、`:187`
  - `backend/app/db/repo.py:193`、`:211`
  - `tests/test_discover_v2.py:24-32` 断言改 4 元组 `(5,"防御期","极差","极严")` 等 + 存 boundary 测试
  - 全仓 `grep market_band_info(` 确认无遗漏（.bak 备份不用管）
- 新增 `strictness_policy` 常量：`{strictness: {tier_allowed, extra_checks, prompt_phrase}}`。
- `_market_note` 注入升级：`今日市况评分 X 分（档位名，宏观定级），候选池上限 N 只。市况定级【好/中/坏/极差】→ 选股策略应【宽松门槛/常规门槛/从严门槛/只保留最强信号】`。
- `judge_tradeable` 接入 strictness 门槛：
  - 宽松：tier ∈ A/B 可建仓（C 观察）
  - 标准：A/B 可建仓（维持现状）
  - 严格：仅 A 可建仓 + 「历史 T+5 胜率 ≥ 40%」硬校验
  - 极严：仅 A + 「历史 T+5 胜率 ≥ 50% + 主力净流入 ≥ 1 亿」双重校验
- **边界铁律**：严格度只改 is_tradeable 与 block_details，**不改 rank 分数与候选顺序**。某票从可建仓变不可建仓 = is_tradeable=0 + 「严格度门槛」一项 passed=false，rank 不动。

### 批次 1 附加 · MarketIntel 修正
- 新增 `apply_market_intel_correction(base_strictness, market_intel) -> final_strictness` 纯函数（放 config.py 或新增 `services/market_intel_correction.py`）：
  | 基底 | 避险 | 中性 | 进取 |
  |---|---|---|---|
  | 宽松 | 上调→标准 | 不变 | 不变 |
  | 标准 | 上调→严格 | 不变 | 不变（进取不再下调）|
  | 严格 | 不变 | 不变 | 不降（保持严格）|
  | 极严 | 不变 | 不变 | 不降（保持极严）|
- **要点**：只允许上调或保持，禁止"进取/乐观放宽坏市况"；采用 `repo.get_market_intel(trade_date)`，None/非三态→不修正退化基底。
- **phase 黑名单**：`退潮/出货/弱势/存量博弈` 命中时，即使 risk_appetite=进取也不下调（保持基底），最多因避险上调。
- 配置：新增 `market_intel_correction_map` + `phase_blacklist` 常量，冻结写 review_log。

### 批次 2（后端 · A 层候选 audit）
- `discover.py` 候选 detail 增加 `audit` 字段（作为 `new_detail` 里的子 dict，一次 merge 写入）：
  ```json
  "audit": {
    "trade_date": "...",
    "market": {"score":, "band":, "grade":, "strictness":, "cap":},
    "decisions": [
      {"key":"market_gate","label":"市况门槛","passed":,"evidence":},
      {"key":"tier_gate","label":"评级档位","passed":,"evidence":},
      {"key":"stop_loss","label":"止损约束","passed":,"evidence":},
      {"key":"profit_risk_ratio","label":"盈亏比≥2:1","passed":,"evidence":},
      {"key":"major_negative","label":"重大利空排查","passed":,"evidence":},
      {"key":"pool_position","label":"位置(距52高)","passed":,"evidence":}
    ],
    "verdict":, "passed_ratio": "n/6", "note":
  }
  ```
- verdict 默认 = confidence_tier；`strictness=极严 且 passed_ratio < 5/6` → verdict 降一档 + note 说明「降档原因：严市况未全项通过」。
- ⚠️ **audit 子 dict 内部必须完整**（6 项齐全，缺项=audit 内丢键）；`existing` 来自 `repo.get_candidate_detail`，`detail = {**existing, **new_detail}`（沿用 discover.py:673 现有 merge，**不动 repo 层**）。
- 测试：audit 构造、严格度降档逻辑。

### 批次 3（后端 · B 层可建仓拒绝明细）
- `judge_tradeable` 增加 `block_details` 数组返回（每项 `{rule, passed, evidence}`），并写入 `detail["block_details"]`。
- **落库路径（P0 明确）**：`block_details` 放 `detail["block_details"]` JSON 内随 detail 落库（`upsert_candidate_tradeable` 的 detail 形参承载）。**不改 upserC 签名、不新增平铺列**。
- `is_tradeable` = 各 passed AND；`block_reason` 平铺列保留（拼接失败 rule+evidence），兼容旧读取方（CandidatesPage.tsx:642 / batch_chat / 测试）。
- 测试：block_details 生成、block_reason 兼容。

### 批次 4（前端 · 审计卡片）
- `web/src/pages/CandidatesPage.tsx`：
  - 顶部横幅：市况徽章 + 严格度说明（`市况 30分 [坏] 严格 → 仅保留最强信号 · 候选上限10`）；徽章色 好=绿/中=蓝/坏=amber/极差=红。
  - Table 每行 `expandable` 展开审计卡片：audit.decisions 逐行规则名+✅/❌+evidence；顶部 passed_ratio + verdict；可建仓高亮 / 降档灰色标「降档：严市况未全项通过」。
- `web/src/types/index.ts` 增 `AuditDecision` / `CandidateAudit` 类型。
- **读取路径**：audit 从 `detail.audit` 读；block_details 从 `r.detail.block_details` 读（detail 内 JSON，非平铺列）。字段缺失显示「-」不报错。

## 四、实现参考

- 市况档位映射：`backend/app/core/config.py:90 market_cap_bands` + `:223 market_band_info`
- 市况注入：`discover.py:104` `_market_condition_raw` / `:158` `market_condition` / `:201` `_market_note`
- 候选 detail merge：`discover.py:673` `{**existing, **new_detail}`（沿用现模式，禁动 repo）
- 可建仓判定：`services/candidate_tradeable.py` `judge_tradeable`（return 主体）+ `repo.upsert_candidate_tradeable`（detail 形参承载）
- MarketIntel 读取：`repo.get_market_intel(trade_date)`（phase/risk_appetite）
- 前端审计卡参照现有 expandable：`web/src/pages/CandidatesPage.tsx` 现有 Table + `types/index.ts:294 TradeProfile` 附近
- 胜率口径：`track_verify` 0-100 百分制（展示须一致，防 4400% 那类 bug）

## 五、执行顺序

1. **批次 1**：config.py（档位扩列 + strictness_policy + correction 函数 + phase_blacklist）→ discover.py（market_band_info 解构改 + _market_note 注入）→ repo.py（解构改 ×2）→ candidate_tradeable.py（strictness 门槛）→ test_discover_v2.py 断言改 → 全仓 grep 核对 → 测试跑绿 → 验收
2. **批次 2**：discover.py 候选 detail 加 audit → 测试（构造 + 降档）→ 验收
3. **批次 3**：candidate_tradeable.py judge_tradeable 加 block_details → detail["block_details"] 落库 → 测试（生成 + 兼容）→ 验收
4. **批次 4**：CandidatesPage.tsx（横幅 + expandable 卡片）+ types/index.ts → tsc + grep 核对 → 验收

每批次完成即停下问 sir，未验收不进下一批。

## 六、验证清单

- [ ] P0-1：`cap, band, *_ = market_band_info(x)` 4 处调用方（discover×2 + repo×2）同步改，`grep market_band_info(` 活跃代码无 `cap, band = ` 遗漏
- [ ] test_discover_v2.py 断言已改 4 元组并含 boundary
- [ ] `market_band_info(30)` == (10,"过渡期","坏","严格")
- [ ] `_market_note` 输出含「市况定级 + 严格度措辞」
- [ ] 4 档 strictness 下 judge_tradeable 门槛正确（宽松 A/B、标准 A/B、严格 A+胜率40%、极严 A+双重）
- [ ] 严格度改变 is_tradeable 时 rank 排序分数不变
- [ ] `apply_market_intel_correction`：标准+避险→严格、标准+进取→标准（不降）、严格+进取→严格（不降）、None→退化基底
- [ ] phase 黑名单命中不降档
- [ ] 候选 detail 含 audit 6 项 decisions + passed/evidence 正确（merge 写入，不动 repo 层）
- [ ] 极严市况 + passed_ratio<5/6 → verdict 降档有 note
- [ ] judge_tradeable 返回 block_details 落 `detail["block_details"]`，block_reason 平铺列兼容旧读取
- [ ] 前端顶部徽章横幅 + 每行 expandable 审计卡片，缺字段显「-」
- [ ] 全量回归测试通过
- [ ] review_log 记录严格度 mapping 冻结（含修正规则 + phase 黑名单）

## 七、红线（执行期绝不动）

- **不改五维评分维度定义**（dim_index/dim_sector/dim_money/dim_sentiment/dim_risk 的 prompt 与得分口径）
- **不改候选真实排序**：严格度只影响 is_tradeable/展示，绝不改 rank 分数与候选生成
- **不改 HARD_RULES / 交易规则 / 研判标准表**；strictness 阈值落 review_log 可回滚
- **禁止动 `repo.upsert_candidate` / `repo.upsert_candidate_tradeable` 内部**（P0-4 经验）
- **前端只读落库字段，不做二次计算**（防 4400% 口径 bug）
- **不改 Streamlit 旧前端**（默认开发 React 新版）
- **MarketIntel 缺失必须退化基底**，不得因修正常用导致阻塞主链路
- audit/block_details 用 JSON 字段承载，**不新增平铺数据库列**
