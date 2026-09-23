# 因子细分化 · 批 1 Claude/Codex 执行指令 v2（自包含版）

> **执行者**：Codex CLI（gpt5.5 MAX）或 Claude Code
> **方案**：`D:\self\因子细分化_批1_方案.md` v2（**已自包含项目背景**，禁止再 read 全文）
> **省 token**：6 段齐备 + 方案 §2 25 因子清单全——执行时**只 grep 关键标识确认行号**

## §0 元信息 + 自包含项目背景

### 0.1 执行者须知
- **平台**：Codex CLI（gpt5.5 MAX 模型）开新对话
- **工作目录**：`D:\self`（codex 启动建议 `codex --approval-mode auto-edit --no-auto-commits --cd D:\self`）
- **任务**：阶段 1「基建期」批 1——Score 6 大类拆 25 个 Python 因子函数 + 注册表 + 单测 + Score 接入
- **依赖**：无（独立模块）
- **工时**：1-2 天

### 0.2 项目一句话
- A 股全生命周期决策 Agent 系统（FastAPI + SQLite/TiDB + 8 个 LangGraph Agent + DeepSeek LLM）
- sir 是项目所有者 + 拍板人，自称"父"
- 本次只动 `backend/app/agents/score.py`（+collect 段）+ 新建 `backend/app/factors/` 模块

### 0.3 sir 协作铁律（**执行必须死守**）
- 提示词只含需求+规则+约束，不含代码
- **Agent 之间解耦**——不超载既有 Agent，不动 LangGraph 节点（`graphs.py:20-32`）
- **数据缺失不编造**（K227）——返 `None + reason`，禁凑数
- **人工终审红线**——任何规则/阈值启用必须人工拍板
- **改动行数 ≤ 501**（含 30 例测试）——超出停下报告 sir

### 0.4 本任务的"为什么"（执行时请理解再动手）
- **现状痛点**：Score 6 大类因子 LLM 一句话给 7-8 分，无法独立验证预测力、无法动态调权
- **本次目标**：拆 25 细分因子 = 为批 2（IC 回测）/ 批 3（自迭代）打基础
- **不破坏现有 LLM Schema**——Python 只算细分值，权重仍 LLM 决定

### 0.5 决策点（sir 已拍板，无需再问）
| # | 决策 | 取值 |
|---|---|---|
| 1 | 3 阶段路线 | 接受（基建→自动化→自迭代）|
| 2 | 25 细分颗粒度 | 接受 |
| 3 | 同时启用上限 | 30 |
| 4 | 新因子样本外验证期 | 2 年 |
| 5 | 因子启停终审权 | 人工 |

---

## §一 目标

6 大类拆 25 个 Python 因子函数（动量 5 + 催化 3 + 估值 4 + 资金 5 + 质量 4 + 主线 4）——每函数 1 例单测。Score collect 段注入明细，LLM 仍按 6 大类出 Schema，**不破坏现有结构**。

**5 个交付物**：
1. `backend/app/services/factor_registry.py`（注册表 + 装饰器）
2. `backend/app/factors/` 7 个文件（6 类 + 适配器 + `__init__`）
3. `backend/tests/test_score_factors.py`（30 例单测）
4. `backend/app/agents/score.py` collect 段改 +20 行
5. `backend/app/core/config.py` +1 行版本号

---

## §二 架构约束

### 新增（不删不改）
- `backend/app/services/factor_registry.py` 新建：FactorDef Pydantic + 装饰器 `@factor_registry.register`
- `backend/app/factors/__init__.py`：注册 25 因子
- `backend/app/factors/momentum.py`：f01-f05
- `backend/app/factors/catalyst.py`：f06-f08
- `backend/app/factors/valuation.py`：f09-f12
- `backend/app/factors/fund.py`：f13-f17
- `backend/app/factors/quality.py`：f18-f21
- `backend/app/factors/sector.py`：f22-f25
- `backend/app/factors/data_adapter.py`：行情/财务/资金统一接口 + 缺失兜底
- `backend/tests/test_score_factors.py`：30 例（25 因子正常 + 5 边界）
- `backend/app/agents/score.py` 改：collect 段拼接 25 因子值
- `backend/app/core/config.py` 增 1 项：`FACTOR_REGISTRY_VERSION = "v1"`

### 解耦铁律
- **不删** 现有 6 大类（LLM Schema 兼容）
- **不增** 第 7 大类（K227 不变）
- **不改** score_prompt.py 主体（只在 collect 段加 1 段）
- **不引新库**（只用 numpy/pandas/pydactic 已有依赖）
- **不动** LangGraph（`graphs.py:20-32`）
- **不改** LLM 权重计算方式（Python 只算细分值）

---

## §三 规则（不可省）

### 1. 25 因子函数规格
- 签名：`def f<NN>_<name>(data: DataAdapter, code: str) -> FactorResult`
- FactorResult = `Pydantic{value: float|int|str|None, quantile: float|None, reason: str}`
- 缺失数据 → `value=None, reason="data_missing:xxx"`（**禁编造**）
- 同 input → 同 output（无随机性）
- 单只股票 25 因子全跑 < 500ms

### 2. 行业分位（13 个因子）
- 需行业分位：f01/f03/f04/f09/f10/f11/f12/f13/f18/f19/f20/f21/f22/f23
- 取申万一级行业近 1 年滚动分位（0-100%）
- 复用 `backend/app/services/sector_snapshot.py`，**不新加表**

### 3. 注册表版本
- `FACTOR_REGISTRY_VERSION = "v1"` 入 `config.py`
- LLM 缓存键拼接版本号（`_rule_version()` 同款）
- 旧版本保留 90 天可回滚（本次不实现，预留接口）

### 4. 数据缺失兜底（4 类边界）
- 数据源返回 None/异常 → 因子上报缺失，不抛
- 极值处理：f01 偏离度 < -50% 或 > 50% 截断
- 单只票全 25 因子全 None → 仍能跑
- 测试必须覆盖：缺失/极值/异常/空数据 4 类

### 5. collect 段拼接（Score 接入点）
- 注入位置：`backend/app/agents/score.py:344-350` 现有 `build_user_prompt` 之前
- 格式：每行 `f<NN>_<name>: value=X (行业前Y%) | reason`
- 25 行明细，超 50 行截断
- 缺失行：标 `data_missing:xxx` 不留空

---

## §四 执行顺序（5 步）

### 步 1：建 registry（30 分钟）
- `factor_registry.py`：FactorDef Pydantic + `register(factor)` / `list_active()` / `get(fid)` 3 函数
- 内存 dict 存（不落 DB，IC 历史在批 2）
- 装饰器接口：`@factor_registry.register`

### 步 2：建 data_adapter（1 小时）
- 统一接口：行情/财务/资金/板块 4 大类
- 每个接口含：原始数据获取 + 异常兜底（try/except 返 None）
- 复用已有 SQLite 查询，**不新加表**
- 行业归属查询（用于分位）：复用 `sector_snapshot.py`

### 步 3：建 25 因子函数（3 小时）
- 每类 1 个文件，按方案 §2 表实现
- 公式参考：
  - f01: `(close - MA20) / MA20`
  - f03: `(close_t - close_t-20) / close_t-20`
  - f04: `vol_today / MA5(vol_20d)`
  - f09: `percentile_rank(PE, 行业 PE 历史)`
  - f11: `PE / growth_rate_pct`
  - f13: `主力净流入 / 当日成交额`
  - f18: `净利润 / 净资产`
  - f22: `板块 5 日涨幅 / 大盘 5 日涨幅`

### 步 4：写 30 例单测（2 小时）
- 25 因子各 1 例正常 + 1 例缺失 = 25 例
- 5 例边界：极值/异常/空数据/全缺失/单缺失
- 断言：`value/quantile/reason` 三字段
- 测试数据用 mock（**不**用真实行情）

### 步 5：接入 Score（1 小时）
- `score.py:344` 之前：调 `factor_registry.list_active()` 拿 25 因子
- 拼成 50 行明细字符串注入 collect
- 改 `config.py` 加 `FACTOR_REGISTRY_VERSION = "v1"`
- 加 1 例集成测试：跑 1 只票 → 验证 25 因子明细全有 OR 缺失明确

---

## §五 验证清单（执行完毕自检）

- [ ] 25 因子函数全部 `@register`，`list_active()` 返 25 条
- [ ] 30 例单测全过（25 正常 + 5 边界）
- [ ] `score.run()` collect 段打印 25 因子明细日志（DEBUG 级别）
- [ ] 集成测试：1 只票，25 因子值全有或缺失项 reason 明确
- [ ] 25 因子运行时长 < 500ms
- [ ] LLM Schema 不变（factors 仍是 6 大类结构）
- [ ] 数据缺失不抛异常，返 None + reason
- [ ] 行业分位 13 个因子都跑通
- [ ] 测试覆盖：缺失/极值/异常/空数据 4 类

---

## §六 红线（**绝对不可破**，执行需逐条核对）

1. **不增第 7 大类**（K227 锁 6 类）
2. **不删 6 大类**（LLM Schema 兼容）
3. **不编造数据**（缺失返 None + reason，禁编造）
4. **不改 LLM 权重计算**（Python 只算细分值）
5. **不引新库**（只用 numpy/pandas/pydantic）
6. **不写大段注释**（docstring ≤ 3 行）
7. **不动 LangGraph**（`graphs.py:20-32`）
8. **不落因子数据**（本次只算不存）
9. **因子值不归一化**（保留原始解释力）
10. **代码侧最小改动**：≤ 501 行（含 30 例测试），超出停下报告 sir

---

## §七 Claude/Codex 端省 token 6 铁律

1. **不复读提示词已固化信息**——6 段 + Schema + 25 因子清单已齐备，**禁止再 read 方案全文**（只 grep `FactorDef|list_active|f01_ma20_deviate|sector_snapshot|main_inflow` 关键标识）
2. **不写超出提示词范围的代码**——列了改哪几个文件就只动那几个，禁止顺手改其他文件
3. **不写大段注释**——函数 docstring ≤ 3 行，函数体内不写 `#`（除关键 trade-off）
4. **复用已有函数**——`agent_call` / `SimpleCache` / `sector_snapshot` 已有实现直接调，禁止重写
5. **测试用例不超规定数量**——25 因子各 1 例 + 5 边界 = 30 例，禁止多写
6. **报告精简**——执行完毕报告 ≤ 10 行：①改了什么（文件清单）②测试结果 ③遗留风险

---

## §八 失败兜底（**执行遇到问题怎么办**）

| 情况 | 怎么做 |
|---|---|
| 行情/财务数据查不到 | 该因子上报缺失，**不抛异常**，reason="data_missing:xxx" |
| 25 因子全 None | 仍继续到 LLM（不让单股卡死） |
| 数据源 akshare 超时 | data_adapter 内部 try/except，返 None |
| 13 个行业分位跑不出 | 复用 `sector_snapshot.py` 已有表，**不新加表** |
| 测试数据 mock 写不出来 | 允许最小真实数据（1 只票 1 天），但必标 `@pytest.mark.integration` |
| 集成测试跑 1 只票失败 | 把 fail 数据记入报告，不掩盖问题 |
| 行数超 501 | **立即停下报告 sir**，不要自行加功能或砍功能 |

---

## §九 验收交付（**执行完毕必报**）

完成后回复格式（**≤ 10 行**）：
```
① 改了什么（文件清单 path:line）
② 测试结果（30 例 passed/failed）
③ 25 因子运行时长（ms）
④ 遗留风险（如果有）
```

**举例**：
```
① factors/ 7 文件新建（factor.py 60L / momentum.py 35L / ...）+ score.py:344 collect 段 +18 行
② pytest test_score_factors.py → 30 passed
③ 25 因子全跑 380ms
④ 无遗留
```
