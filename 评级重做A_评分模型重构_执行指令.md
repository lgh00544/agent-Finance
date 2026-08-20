# 评级重做-A：评分模型重构（六因子透明评分体系）

> **批次**：评级重做 A（评分模型重构）
> **目标**：将 ScoreAgent 从"五维 0-100 不透明打分"重构为"六因子 0-10 透明评分 + 潜力标识 + 交叉验证"体系，使评级结果可追溯、可区分、可校准。
> **前置条件**：批次 1-4 + MarketIntel 深度化已完成（567 passed 0 failed）。
> **后续依赖**：评级重做-B（展示层可视化）依赖本批次的新 detail 格式；评级重做-C（因子回测校准闭环）依赖本批次的因子结构。

---

## 一、要什么

### 1.1 核心变更

将 ScoreAgent 的评分模型从当前的"五维 0-100 模糊打分"重构为"六因子 0-10 透明评分"：

| 维度 | 当前（v3） | 目标（v4） |
|------|-----------|-----------|
| 评分项 | 5 维（基本面/技术趋势/资金流向/舆情风险/行业景气），每维 0-100 | 6 因子（动量/催化/估值/主线契合/资金面/基本面质量），每因子 0-10 |
| 评分粒度 | 0-100 粗放，LLM 自由打分无依据 | 0-10 精细，每因子必须给出 reason（引用具体数据） |
| 信号方向 | verdict 三态（支持/中性/风险） | signal 三态（看多/中性/看空） |
| 潜力标识 | 无 | potential_flag（催化≥7 且 动量≤4 = 尚未被定价） |
| 交叉验证 | 无 | cross_validation_note（与 DiscoverAgent 选股逻辑交叉验证） |
| 综合分计算 | LLM 自由给 0-100 | LLM 按 prompt 六因子权重汇总输出 0-100（代码仅透传存储） |
| 评级阈值 | A≥80 / B 60-79 / C<60 | A≥75 / B 55-74 / C<55（初始值，后续回测校准） |

### 1.2 六因子定义与参考权重

| # | 因子名 | 权重 | 评判要点 | 数据来源 |
|---|--------|------|---------|---------|
| 1 | 动量 | 20% | 均线排列（MA5/10/20/60 多空头）、MACD/RSI 状态、量价配合、近期涨跌幅（5日/20日）、距 20/60 日高低点位置、威科夫阶段定位 | K线 + 技术指标（已有） |
| 2 | 催化 | 20% | 新闻/公告中的事件催化（政策利好、业绩预告、行业事件、重组、订单等），利好/利空强度与时效性 | 新闻公告（已有） |
| 3 | 估值 | 15% | PE/PB/PS 相对行业均值的位置、PEG、市值与成长性匹配度 | 财务指标（已有） |
| 4 | 主线契合 | 15% | 所属板块是否为当前市场主线、板块相对大盘强弱、板块资金关注度、MarketIntel 主线结构判断 | 行业板块行情 + MarketIntel（已有） |
| 5 | 资金面 | 15% | 主力资金净流入/占比、换手率活跃度、龙虎榜游资席位信号（一线游资净买=加分，对倒/出货=扣分） | 资金流向 + 游资聚合（已有） |
| 6 | 基本面质量 | 15% | ROE/毛利率/营收净利同比增速/负债率/现金流质量/财务健康度 | 财务指标（已有） |

> **权重说明**：初始参考权重，后续由"评级重做-C 因子回测校准闭环"根据 T+N 实际表现自动校准。当前写死在 prompt 中作为 LLM 参考权重（非死条件，LLM 可依据市场环境微调），代码层不做权重计算（LLM 自行汇总输出 score）。

### 1.3 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `potential_flag` | bool | 潜力标识：催化因子≥7 且 动量因子≤4 → true（催化尚未被定价，值得重点关注） |
| `cross_validation_note` | str | 与 DiscoverAgent 选股逻辑的交叉验证结论（一段话，引用 Discover 的选股理由与 Score 的因子结论对比） |

### 1.4 不改的部分

- **PositionAgent / SellAgent / ReviewAgent 的 dimensions 字段不动**——它们用的是 `DiscoverDimension`（通用维度归因），与 ScoreAgent 的因子化体系独立。
- **StockScore 表结构不改**——detail 列是 SafeJSON，新旧格式共存（通过 `detail.get("factors")` 检测新格式）。
- **数据采集逻辑基本不动**——`collect_data()` 已采集全部所需数据（K线/财务/资金流/新闻/行业/游资），仅需新增候选上下文 + 市况摘要注入。

---

## 二、谁做

Claude Code 执行。本指令为完整执行规格，含实现参考代码。

---

## 三、规则

### 3.1 硬性规则

1. **不删旧字段**：`ScoreOutput` 保留 `stock_code / stock_name / score / grade / risk_list / final_advice`，仅将 `dimensions` 替换为 `factors`，新增 `potential_flag` 和 `cross_validation_note`。
2. **缓存强制失效**：cache_key 从 `f"{code}:{today}:h{fingerprint}"` 改为 `f"{code}:{today}:v4:h{fingerprint}"`，确保新 schema 重新调用 LLM（旧缓存不会命中）。
3. **向后兼容**：`stock_score.detail` 新旧格式共存。前端展示层（评级重做-B）通过 `detail.get("factors")` 检测新格式；无 factors 走旧逻辑。本批次只改后端，不动前端。
4. **reasoning_trace 适配**：`trace_score` 必须同时处理新格式（`detail["factors"]` 列表）和旧格式（`detail["维度名"]` 字典），保证历史数据留痕不报错。
5. **数据缺失降级**：候选上下文（DiscoverAgent 理由）不存在时 `cross_validation_note` 输出空串，不阻塞评分；MarketIntel 不存在时主线契合因子按数据缺失处理。
6. **factor 固定六项**：LLM 必须输出恰好 6 个因子，因子名固定（动量/催化/估值/主线契合/资金面/基本面质量），不允许自创因子名。
7. **score 由 LLM 输出**：综合 score 仍由 LLM 根据六因子加权汇总后输出（0-100 整数），代码层不做权重计算（避免代码与 prompt 权重不一致的风险）。但 prompt 中必须明确权重参考值，LLM 汇总时须遵循。权重一致性校验（因子分×权重×10 vs score）属评级重做-C 回测环节，本批次不做。

### 3.2 评分阈值（初始值，后续回测校准）

- A ≥ 75（优质候选，多因子共振）
- B 55-74（一般关注，部分因子看多）
- C < 55（暂不关注，因子多数中性或看空）

### 3.3 final_advice 格式

```
综合评估：N/6 因子看多，总分 XX 分（X 级），<结论>，止损-8%，主要风险…
```
- N = signal=看多 的因子数（0-6 如实统计）
- 结论为建仓/观望/排除的明确判断
- potential_flag=true 时追加「⚠️ 潜力标识：催化强但动量弱，可能尚未被定价」

---

## 四、约束

1. **禁止修改前端文件**（streamlit/ 目录）——展示层在评级重做-B 单独处理。
2. **禁止修改 PositionAgent / SellAgent / ReviewAgent 的 schema 和 prompt**——它们的 dimensions 体系不变。
3. **禁止修改 StockScore 表结构**（models.py 中的 StockScore 类）——detail 列已足够灵活。
4. **禁止修改 graph 结构**（graphs.py / router.py 中的 score 图定义和 run_score 调用）——节点名和流转不变。
5. **禁止在代码层做评分计算**——score、grade 由 LLM 输出，potential_flag 由代码层根据因子分值推导覆写（催化≥7 且 动量≤4 是纯数学换算，不信任 LLM 自报 bool），代码只做存储和透传。
6. **新增的 repo 函数只读不写**——`get_candidate_context` 只查询不修改候选表。

---

## 五、预期

### 5.1 功能预期

1. ScoreAgent 对每只候选股输出 6 因子评分（每因子 0-10 + reason + signal），综合 score 0-100 + grade A/B/C。
2. 催化≥7 且 动量≤4 的标的自动标记 `potential_flag=true`。
3. 评分时注入 DiscoverAgent 的选股理由，LLM 输出交叉验证结论。
4. 评分时注入 MarketIntel 摘要，LLM 据此判断主线契合度。
5. 新评分结果落库后，推理留痕（reasoning_trace）正确记录六因子归因。
6. 旧评分记录（五维格式）的留痕和展示不报错。

### 5.2 测试预期

- 新增 ≥10 条测试（六因子解析、potential_flag、交叉验证、旧数据兼容、reasoning_trace 新格式、cache_key 失效、potential_flag 代码层推导覆写、factors 六项强校验等）。
- 现有涉及 ScoreOutput/ScoreDimension 的测试全部适配通过。
- 全量测试 0 failed。

---

## 六、实现参考

### 6.1 文件清单与改动范围

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `backend/app/agents/schemas.py` | 改 | ScoreDimension → ScoreFactor，ScoreOutput 增加 factors/potential_flag/cross_validation_note |
| `agent_prompts/score_prompt.py` | 改（重写） | SCHEMA_DESC + SYSTEM_PROMPT + build_user_prompt 全部重写为六因子体系 |
| `backend/app/agents/score.py` | 改 | collect_data 新增候选上下文+市况注入；llm_score 适配新 schema 存储 |
| `backend/app/services/reasoning_trace.py` | 改 | trace_score 适配新 factors 列表格式（兼容旧 dimensions 格式） |
| `backend/app/db/repo.py` | 增 | 新增 `get_candidate_context(code, trade_date)` 函数 |
| `backend/tests/test_hot_money_inject.py` | 改 | ScoreDimension → ScoreFactor，dimensions → factors |
| `backend/tests/test_reasoning_trace.py` | 改 | score 测试数据适配新 factors 格式 + 新增 v4 格式测试 |
| `backend/tests/test_score_refactor.py` | 新建 | 六因子重构专项测试 |

### 6.2 schemas.py 改动

**位置**：`backend/app/agents/schemas.py` 第 112-128 行

**当前代码**：
```python
class ScoreDimension(BaseModel):
    """v3.0 白盒维度归因：单维度结论（资金流向维度内部体现游资信号）"""
    dim: str = Field(description="维度名（固定五维）：基本面/技术趋势/资金流向/舆情风险/行业景气")
    score: int = Field(ge=0, le=100, description="该维度得分 0-100")
    verdict: str = Field(default="中性", description="该维度结论三态：支持/中性/风险")
    advice: str = Field(default="", description="该维度针对性建议（1 句话，引用具体数据）")


class ScoreOutput(BaseModel):
    stock_code: str
    stock_name: str
    score: int = Field(ge=0, le=100, description="综合得分 0-100")
    grade: str = Field(pattern="^[ABC]$", description="综合评级 A/B/C")
    dimensions: list[ScoreDimension] = Field(description="五个维度评分明细（dim/score/verdict/advice）")
    risk_list: list[str] = Field(description="风险清单（减持/质押/立案/业绩暴雷/估值过高等）")
    final_advice: str = Field(default="",
        description="综合评估（v3.0）：「综合评估：N/5 维支持，总分 XX 分（X 级），结论，止损-8%，主要风险…」")
```

**替换为**：
```python
# 文件顶部 import 补充（如已有 BaseModel 则追加 model_validator）：
from pydantic import BaseModel, Field, model_validator

_FACTOR_NAMES = {"动量", "催化", "估值", "主线契合", "资金面", "基本面质量"}

class ScoreFactor(BaseModel):
    """v4.0 透明多因子评分项：每因子 0-10 + 打分依据 + 信号方向"""
    factor: str = Field(
        description="因子名（固定六因子）：动量/催化/估值/主线契合/资金面/基本面质量")
    score: int = Field(ge=0, le=10, description="该因子得分 0-10（整数）")
    reason: str = Field(
        description="打分依据（引用具体数据，如 'MA20上方多头排列，MACD金叉，5日涨幅3.2%'，中文 30-80 字）")
    signal: str = Field(
        pattern="^(看多|中性|看空)$",
        description="该因子信号方向：看多/中性/看空")


class ScoreOutput(BaseModel):
    """v4.0 六因子透明评分体系"""
    stock_code: str
    stock_name: str
    score: int = Field(ge=0, le=100,
        description="综合得分 0-100（六因子加权汇总，权重见 prompt）")
    grade: str = Field(pattern="^[ABC]$", description="综合评级 A/B/C")
    factors: list[ScoreFactor] = Field(
        description="六因子评分明细（factor/score/reason/signal），恰好 6 项")
    potential_flag: bool = Field(default=False,
        description="潜力标识：催化因子≥7 且 动量因子≤4 = 催化尚未被定价，值得重点关注")
    cross_validation_note: str = Field(default="",
        description="与 DiscoverAgent 选股逻辑的交叉验证结论（一段话，引用 Discover 理由与 Score 因子对比）")
    risk_list: list[str] = Field(description="风险清单（减持/质押/立案/业绩暴雷/估值过高等）")
    final_advice: str = Field(default="",
        description="综合评估：「综合评估：N/6 因子看多，总分 XX 分（X 级），结论，止损-8%，主要风险…」；"
                    "potential_flag=true 时追加「⚠️ 潜力标识：催化强但动量弱，可能尚未被定价」")

    @model_validator(mode="after")
    def _check_six_factors(self):
        """强校验：factors 必须恰好为六因子且名称固定。
        校验失败抛 ValidationError → 走 llm_call_json 既有重试机制（structured.py:84-131），
        不新增崩溃路径。"""
        names = [f.factor for f in self.factors]
        if len(names) != 6 or set(names) != _FACTOR_NAMES:
            raise ValueError(
                f"factors 必须恰好为六因子且名称固定，收到 {names}（期望 {sorted(_FACTOR_NAMES)}）")
        return self
```

> **注意**：`ScoreDimension` 类保留不删（PositionAgent/SellAgent 的 `DiscoverDimension` 是独立的，但 `test_whitebox_position_sell.py` 等测试不引用 `ScoreDimension`）。**全局搜索已完成（审核实测）**：`ScoreDimension` 引用仅 `schemas.py`（定义+引用）+ `test_hot_money_inject.py`（2 测试 4 处，41/44/65/68 行），无其他引用。

### 6.3 score_prompt.py 改动（全文重写）

**文件**：`agent_prompts/score_prompt.py`

```python
"""
ScoreAgent 六因子透明评分 Prompt（v4.0）
【交由模型推理的业务逻辑】六因子评判标准、权重参考、A/B/C 分级阈值、潜力标识、交叉验证。
代码只提供：行情/财务/资金流/新闻的原始数据与纯数学指标 + 候选上下文 + 市况摘要。

【个性化调教·层级2 深度风格调教】
- 本文件只允许修改 Prompt 文本（引号内的中文内容），禁止改动任何 Python 逻辑；
- 可调整六因子的权重侧重、各因子的评判口径、A/B/C 分级标准；
- 修改后重启后端服务即生效；建议自行备份本文件，防止版本升级覆盖。

【统一调教接口（自动注入，无需在本文件手写）】
- 人工硬性规则（common.HARD_RULES）：人工锁定的业务底线，LLM 无条件遵守、不得放宽；
- 个人交易偏好档案（sys_trade_profile）：「个人交易偏好」页可视化编辑，保存即时生效；
- 私有知识库（private_knowledge）：本 Agent 每次启动任务自动检索对应战法资料注入。
以上三段由 common.agent_call 统一拼接进 system prompt，本文件只承载本 Agent 专属研判标准。
"""
from agent_prompts.common import ROLE_BASE, TRADE_STYLE, json_requirement

SCHEMA_DESC = """{
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "score": 78,
  "grade": "B",
  "factors": [
    {"factor": "动量", "score": 7, "reason": "MA20上方多头排列，MACD金叉，5日涨幅3.2%，量价配合良好", "signal": "看多"},
    {"factor": "催化", "score": 8, "reason": "行业政策利好落地+业绩预告超预期，催化剂时效性强", "signal": "看多"},
    {"factor": "估值", "score": 5, "reason": "PE 35倍高于行业均值28倍，PEG 1.2偏高但成长性可部分消化", "signal": "中性"},
    {"factor": "主线契合", "score": 6, "reason": "所属白酒板块近5日跑赢大盘1.5%，属于当前活跃主线边缘", "signal": "中性"},
    {"factor": "资金面", "score": 7, "reason": "近5日主力净流入占比4.1%，龙虎榜一线游资净买2000万", "signal": "看多"},
    {"factor": "基本面质量", "score": 8, "reason": "ROE 25%，毛利率91%，净利同比+12%，负债率低，现金流充沛", "signal": "看多"}
  ],
  "potential_flag": false,
  "cross_validation_note": "Discover以技术突破+板块景气选中，Score因子验证：动量7+催化8共振，与选股逻辑一致，基本面质量8提供安全垫",
  "risk_list": ["PE高于行业均值", "短期涨幅偏大需警惕回撤"],
  "final_advice": "综合评估：4/6 因子看多，总分 78 分（B 级），可低吸建仓，止损-8%，主要风险：PE偏高、短期涨幅偏大"
}"""

SYSTEM_PROMPT = f"""{ROLE_BASE}
{TRADE_STYLE}

你的任务：对单只股票做六因子透明评分（每因子 0-10），并输出综合分与 A/B/C 评级。

【六因子定义与参考权重】（可依据市场环境灵活微调，但不得增减因子数量）
1. 动量（约 20%）：均线排列（MA5/10/20/60 多空头）、MACD/RSI 状态、量价配合、近期涨跌幅（5日/20日）、
   距 20/60 日高低点位置、威科夫阶段定位。
   - 吸筹末期-优选型 = 动量加分项；派发期-高风险型 = 动量强扣分项；
   - 5日涨幅 > 30% = 已拉升期（错过买点，动量因子须低分）。
2. 催化（约 20%）：新闻/公告中的事件催化（政策利好、业绩预告、行业事件、重组、订单、技术突破等）。
   - 判断催化强度（强/中/弱）与时效性（正在兑现/即将兑现/已兑现）；
   - 利好消息 + 股价不涨（量价背离）= 借利好出货嫌疑，催化因子须低分并标注风险；
   - 无明确催化时打 3-4 分（中性偏弱），不编造。
3. 估值（约 15%）：PE/PB/PS 相对行业均值的位置、PEG、市值与成长性匹配度。
   - PE 低于行业均值 = 估值因子加分；远高于行业均值 = 扣分；
   - 无法获取估值数据时打 5 分（中性），reason 标注「估值数据缺失」。
4. 主线契合（约 15%）：所属板块是否为当前市场主线、板块相对大盘强弱、板块资金关注度。
   - 参考注入的 MarketIntel 主线结构判断（进攻主线/接力方向/退潮方向）；
   - 板块属于进攻主线或接力方向 = 加分；属于退潮方向 = 强扣分；
   - 无 MarketIntel 数据时按板块相对大盘强弱判断，reason 标注「无 MarketIntel 数据，按板块相对强弱推断」。
5. 资金面（约 15%）：主力资金净流入/占比、换手率活跃度。
   - **如有龙虎榜/游资席位数据一并纳入**：游资净买方向与等级（一线游资净买=加分）、
     与机构/北向是否协同（同买=加分，矛盾=风险提示）、游资对倒/出货识别 = 资金面显著扣分；
   - 无游资数据时 signal 标注中性并如实说明，绝不臆测（K227 字段误读防御）。
6. 基本面质量（约 15%）：ROE/毛利率/营收净利同比增速/负债率/现金流质量/财务健康度。
   - ROE > 15% + 净利同比 > 10% + 负债率 < 50% = 基本面优秀（8-10 分）；
   - 业绩下滑/亏损/负债率过高 = 低分（0-3 分）。

【综合分汇总规则】
根据六因子得分与参考权重加权汇总为 0-100 综合分：
score ≈ (动量×0.20 + 催化×0.20 + 估值×0.15 + 主线契合×0.15 + 资金面×0.15 + 基本面质量×0.15) × 10
你可以在 ±5 分内微调以反映因子间的协同或冲突效应，但须与各因子 signal 方向一致。

【分级阈值】
- A ≥ 75：优质候选，多因子共振（≥4 因子看多且无看空）
- B 55-74：一般关注，部分因子看多
- C < 55：暂不关注，因子多数中性或看空

【潜力标识 potential_flag】
当催化因子 ≥ 7 且 动量因子 ≤ 4 时，potential_flag = true。
含义：存在强催化但股价尚未启动（动量弱），催化可能尚未被市场定价，值得重点关注。
注意：potential_flag 的最终值由代码层按此规则强制推导（不信任 LLM 自报），但你须在 final_advice 中按规则追加潜力标识文案。
此时 final_advice 须追加「⚠️ 潜力标识：催化强但动量弱，可能尚未被定价」。

【交叉验证 cross_validation_note】
你将收到 DiscoverAgent 对该标的的选股理由（如有）。请对比你的六因子结论与 Discover 的选股逻辑：
- 因子结论与选股逻辑一致 → 「Discover以XXX选中，Score因子验证：YYY共振，与选股逻辑一致」；
- 因子结论与选股逻辑有偏差 → 「Discover以XXX选中，但Score因子发现ZZZ偏弱，建议关注但谨慎」；
- 因子结论与选股逻辑矛盾 → 「交叉验证：不符——Discover以XXX选中，但Score因子显示AAA看空，建议剔除或降低优先级」；
- 无 Discover 上下文（非候选池标的，手动评分） → 输出空串。

【输出结构（v4.0 六因子透明框架）】
- factors 数组：恰好 6 项，每项输出 factor（固定六因子名）/score（0-10 整数）/reason（引用具体数据，30-80 字）/signal（看多/中性/看空）；
- potential_flag：bool，催化≥7 且 动量≤4 时为 true；
- cross_validation_note：一段话交叉验证结论；
- final_advice 综合评估：格式「综合评估：N/6 因子看多，总分 XX 分（X 级），<结论>，止损-8%，主要风险…」，
  N 为 signal=看多 的因子数（0-6 如实统计），结论为建仓/观望/排除的明确判断；
- 主结论以 factors + final_advice 为准，逐因子结论与总评分须互相印证，禁止自相矛盾。

【子 Agent 协作分工（思维团队模式）】
在最终输出前，按以下子 Agent 视角分步完成分析，主 Agent（你）统筹综合评分：
1. 量价动量子 Agent：均线结构、MACD/RSI、量价配合、威科夫阶段定位 → 动量因子；
2. 催化事件子 Agent：新闻/公告事件催化识别、强度与时效判断 → 催化因子；
3. 估值定价子 Agent：PE/PB/PS 行业对比、PEG、市值匹配度 → 估值因子；
4. 板块主线子 Agent：板块相对强弱、MarketIntel 主线结构匹配 → 主线契合因子；
5. 资金游资子 Agent：主力资金流向、龙虎榜游资席位、对倒/出货识别 → 资金面因子；
6. 基本面子 Agent：ROE/毛利率/增速/负债率/现金流 → 基本面质量因子；
7. 决策输出（主 Agent 收口）：综合各子 Agent 结论 → 六因子打分 → 潜力标识 → 交叉验证 → A/B/C 评级 → 风险清单 → final_advice。
子 Agent 结论冲突时按元规则裁决（实时走势 > 主力资金 > 政策消息 > 技术形态 > 历史对比），
并在各因子 reason 与 final_advice 中体现。

【研判参考框架（沉淀自《潜力股发掘方法论》，参考权重非死条件）】
分层到位的标的特征：处于吸筹末期（LPS 缩量不破低）、止损 ≤ -8%、盈亏比 ≥ 3:1、
5 日涨幅 < 15%、主力净流入 > 0。触发以下情形须在评分中显著体现：
- 5 日涨幅 > 30% = 已拉升期（错过买点，动量因子须低分）；
- 止损无法计算（如历史新高无参照系）= 动量因子低分；
- 利好消息 + 股价不涨（量价背离）= 借利好出货嫌疑（催化因子低分 + 风险清单标注）。

评分必须基于你收到的原始数据给出具体依据，禁止无数据支撑的评分。

{json_requirement(SCHEMA_DESC)}"""


def build_user_prompt(data_pack: str, preference: str,
                      discover_context: str = "",
                      market_intel_summary: str = "") -> str:
    """data_pack: 聚合后的原始数据 JSON；preference: 历史复盘反馈偏好（可为空）；
    discover_context: DiscoverAgent 选股理由（可为空，非候选池标的时无）；
    market_intel_summary: 当日市场研判摘要（可为空）"""
    pref_section = ("【历史复盘反馈】（来自过往交易的教训与偏好，供参考）\n" + preference
                    if preference else "")
    ctx_section = ""
    if discover_context:
        ctx_section = f"""
【DiscoverAgent 选股上下文】（供交叉验证用）
{discover_context}
"""
    intel_section = ""
    if market_intel_summary:
        intel_section = f"""
【当日市场研判摘要】（MarketIntel，供主线契合因子参考）
{market_intel_summary}
"""
    return f"""{pref_section}
{ctx_section}
{intel_section}

【标的原始数据包】（全部为原始数据与纯数学指标，供你研判）
{data_pack}

请对标的进行六因子透明评分并输出结构化结果。"""
```

### 6.4 score.py 改动

**文件**：`backend/app/agents/score.py`

#### 6.4.1 collect_data 新增候选上下文 + 市况注入

在 `collect_data` 函数末尾（return state 之前）新增：

```python
    # ---- v4.0 新增：交叉验证上下文 + 市况摘要 ----
    # 候选上下文（DiscoverAgent 选股理由，供 ScoreAgent 交叉验证）
    discover_ctx = ""
    try:
        cand_ctx = repo.get_candidate_context(code, today)
        if cand_ctx:
            parts = []
            if cand_ctx.get("reasons"):
                parts.append(f"选股理由: {'；'.join(cand_ctx['reasons'])}")
            if cand_ctx.get("confidence_tier"):
                parts.append(f"信心度: {cand_ctx['confidence_tier']}")
            if cand_ctx.get("focus_type"):
                parts.append(f"关注类型: {cand_ctx['focus_type']}")
            if cand_ctx.get("final_advice"):
                parts.append(f"Discover综合评估: {cand_ctx['final_advice']}")
            discover_ctx = " | ".join(parts)
    except Exception as exc:  # noqa: BLE001
        logger.warning("候选上下文获取失败（降级跳过）: %s", exc)

    # 市况摘要（MarketIntel，供主线契合因子参考）
    intel_summary = ""
    try:
        intel = repo.get_latest_market_intel()
        if intel:
            intel_summary = intel.get("summary", "")
    except Exception as exc:  # noqa: BLE001
        logger.warning("MarketIntel 获取失败（降级跳过）: %s", exc)

    state["discover_context"] = discover_ctx
    state["market_intel_summary"] = intel_summary
```

#### 6.4.2 llm_score 适配新 schema

将 `llm_score` 函数中的 `agent_call` 和 `repo.upsert_score` 改为：

```python
def llm_score(state: StockAgentState) -> StockAgentState:
    """节点2：LLM 六因子透明评分 + 落库"""
    code = state["stock_code"]
    name = state.get("stock_name") or code
    today = state.get("trade_date") or time.strftime("%Y-%m-%d")

    preference = repo.get_latest_preference()
    preference_text = ""
    if preference:
        preference_text = f"偏好: {preference.get('偏好')}；调整方向: {preference.get('调整方向')}"

    data_pack = {
        "基本行情": {k: v for k, v in (state.get("tech_index") or {}).items() if k != "recent_klines"},
        "近期K线": (state.get("tech_index") or {}).get("recent_klines", [])[-20:],
        "财务指标": state.get("finance_data") or [],
        "资金流向": state.get("fund_flow_rows") or [],
        "新闻公告": state.get("news_report") or [],
        "行业板块行情": (state.get("basic_info") or {}).get("industry_spot", [])[:15],
        "游资聚合": state.get("hot_money"),
    }

    output = agent_call(
        agent="score",
        cache_key=f"{code}:{today}:v4:h{repo.hot_money_fingerprint()}",
        system_prompt=score_prompt.SYSTEM_PROMPT,
        user_prompt=score_prompt.build_user_prompt(
            _compact(data_pack), preference_text,
            discover_context=state.get("discover_context") or "",
            market_intel_summary=state.get("market_intel_summary") or "",
        ),
        schema=ScoreOutput,
        ttl_seconds=86400,
        model_level=ModelLevel.DEEP,
    )

    # ---- v4.0 代码层推导 potential_flag（不信任 LLM 自报；factor 分值为 LLM 判断，flag 为事实换算）----
    _催化 = next((f.score for f in output.factors if f.factor == "催化"), 0)
    _动量 = next((f.score for f in output.factors if f.factor == "动量"), 0)
    output.potential_flag = bool(_催化 >= 7 and _动量 <= 4)

    # v4.0 六因子透明评分：detail 存 factors 列表 + potential_flag + cross_validation_note + final_advice
    detail = {
        "factors": [f.model_dump() for f in output.factors],
        "potential_flag": output.potential_flag,
        "cross_validation_note": output.cross_validation_note,
        "final_advice": output.final_advice,
    }
    repo.upsert_score(
        code, name, today, float(output.score), output.grade,
        detail,
        output.risk_list,
    )
    state["score_result"] = output.model_dump()
    state["risk_notice"] = output.risk_list
    state["stage"] = "score"
    state["trace"] = [*state.get("trace", []),
                      f"打分完成: {output.score}分 {output.grade}级 "
                      f"潜力={output.potential_flag} 因子{len(output.factors)}项 风险{len(output.risk_list)}条"]
    logger.info("评分完成 %s: %s分 %s级 潜力=%s", code, output.score, output.grade,
                output.potential_flag)
    return state
```

> **注意**：函数文档字符串从"五维打分"改为"六因子透明评分"。trace 日志增加潜力标识和因子数。

### 6.5 repo.py 新增函数

**文件**：`backend/app/db/repo.py`

在 `get_candidate_snapshot` 函数之后（约第 113 行后）新增：

```python
def get_candidate_context(stock_code: str, trade_date: str) -> dict | None:
    """候选标的选股上下文（ScoreAgent 交叉验证用；只读 detail + reasons，不影响候选列表契约）
    返回 {reasons, confidence_tier, focus_type, final_advice}；无候选记录返回 None"""
    with SessionLocal() as db:
        row = db.execute(
            select(StockCandidate).where(
                StockCandidate.stock_code == stock_code,
                StockCandidate.trade_date == trade_date)
        ).scalar_one_or_none()
        if row is None:
            return None
        detail = row.detail or {}
        return {
            "reasons": row.reasons or [],
            "confidence_tier": detail.get("confidence_tier", ""),
            "focus_type": detail.get("focus_type", ""),
            "final_advice": detail.get("final_advice", ""),
        }
```

### 6.6 reasoning_trace.py 改动

**文件**：`backend/app/services/reasoning_trace.py`

**当前 `trace_score` 函数（第 186-206 行）**：
```python
def trace_score(stock_code: str, stock_name: str, trade_date: str,
                score: float, grade: str, detail: dict, risk_list: list) -> None:
    """ScoreAgent：五维分项研判 = dimensions[].verdict/advice（旧数据 comment 兜底），
    按维度归入技术/资金/基本面；v3.0 final_advice 进 final_conclusion"""
    detail = detail or {}
    by_name = {name: _dim_text(v) for name, v in detail.items() if isinstance(v, dict)}
    submit({
        ...
        "technical_reasoning": _line(by_name.get("技术趋势"), by_name.get("舆情风险")),
        "capital_reasoning": by_name.get("资金流向", ""),
        "fundamental_reasoning": _line(by_name.get("基本面"), by_name.get("行业景气")),
        ...
    })
```

**替换为**（兼容新旧格式）：
```python
def trace_score(stock_code: str, stock_name: str, trade_date: str,
                score: float, grade: str, detail: dict, risk_list: list) -> None:
    """ScoreAgent：因子/维度分项研判留痕。
    v4.0 新格式：detail["factors"] 列表（factor/score/reason/signal）→ 按因子归入技术/资金/基本面；
    v3.0 旧格式：detail["维度名"] 字典（score/verdict/advice/comment）→ 按维度名归入（兼容历史数据）；
    final_advice + potential_flag + cross_validation_note 进 final_conclusion"""
    detail = detail or {}

    # ---- v4.0 新格式：factors 列表 ----
    factors_list = detail.get("factors")
    if factors_list and isinstance(factors_list, list):
        by_factor = {}
        for f in factors_list:
            if isinstance(f, dict):
                fname = f.get("factor", "")
                reason = f.get("reason", "") or f.get("advice", "")
                by_factor[fname] = f"{reason}（{f.get('signal', '')}，{f.get('score', '')}分）"
        technical = _line(by_factor.get("动量"), by_factor.get("催化"))
        capital = by_factor.get("资金面", "")
        fundamental = _line(by_factor.get("基本面质量"), by_factor.get("估值"),
                           by_factor.get("主线契合"))
        extra_conclusion = {}
        if detail.get("potential_flag"):
            extra_conclusion["potential_flag"] = True
        if detail.get("cross_validation_note"):
            extra_conclusion["cross_validation"] = detail["cross_validation_note"]
    else:
        # ---- v3.0 旧格式：维度名字典（兼容历史数据）----
        by_name = {name: _dim_text(v) for name, v in detail.items() if isinstance(v, dict)}
        technical = _line(by_name.get("技术趋势"), by_name.get("舆情风险"))
        capital = by_name.get("资金流向", "")
        fundamental = _line(by_name.get("基本面"), by_name.get("行业景气"))
        extra_conclusion = {}

    final_conclusion = {"score": score, "grade": grade,
                        "final_advice": detail.get("final_advice", "")}
    final_conclusion.update(extra_conclusion)

    submit({
        "stock_code": stock_code, "stock_name": stock_name,
        "source_module": "score", "generate_date": trade_date,
        "fact_basis": _j(detail),
        "technical_reasoning": technical,
        "capital_reasoning": capital,
        "fundamental_reasoning": fundamental,
        "risk_reasoning": _line(*(risk_list or [])),
        "rule_refs": "",
        "final_conclusion": _j(final_conclusion),
        "confidence": 0.0,
        "data_source": "行情/财务/资金流/新闻原始数据 + LLM 六因子透明评分",
        "ext_info": "",
    })
```

### 6.7 测试改动

#### 6.7.1 test_hot_money_inject.py 适配

**文件**：`backend/tests/test_hot_money_inject.py`

将所有 `ScoreDimension` → `ScoreFactor`，`dimensions` → `factors`，适配新字段：

```python
# 第 41-46 行改为：
from app.agents.schemas import ScoreFactor, ScoreOutput

out = ScoreOutput(stock_code="601138", stock_name="工业富联", score=70, grade="B",
                  factors=[ScoreFactor(factor="资金面", score=6, reason="主力净流入占比3.2%",
                                       signal="中性")],
                  potential_flag=False, cross_validation_note="",
                  risk_list=[], final_advice="综合评估：1/6 因子看多")

# 第 65-70 行同理改为 ScoreFactor + factors
```

> **注意**：`_capture` 函数验证 data_pack 内容的逻辑不变（data_pack 结构没变，仍是基本行情/财务/资金流等）。只改 ScoreOutput 构造方式。

#### 6.7.2 test_reasoning_trace.py 适配

**文件**：`backend/tests/test_reasoning_trace.py`

`test_score_mapping_dimension_split`（第 69-84 行）保留旧格式测试（验证向后兼容），新增 v4 格式测试：

```python
def test_score_mapping_v4_factors():
    """v4.0 六因子格式留痕：factors 列表 → 技术/资金/基本面归因 + potential_flag/cross_validation"""
    detail = {
        "factors": [
            {"factor": "动量", "score": 7, "reason": "MA20多头排列", "signal": "看多"},
            {"factor": "催化", "score": 8, "reason": "政策利好", "signal": "看多"},
            {"factor": "估值", "score": 5, "reason": "PE偏高", "signal": "中性"},
            {"factor": "主线契合", "score": 6, "reason": "板块跑赢大盘", "signal": "中性"},
            {"factor": "资金面", "score": 7, "reason": "主力净流入", "signal": "看多"},
            {"factor": "基本面质量", "score": 8, "reason": "ROE 25%", "signal": "看多"},
        ],
        "potential_flag": True,
        "cross_validation_note": "与Discover选股逻辑一致",
        "final_advice": "综合评估：4/6 因子看多，总分 78 分（B 级）",
    }
    reasoning_trace.trace_score("600109", "测试股109", "2026-08-05",
                                78.0, "B", detail, ["PE偏高"])
    reasoning_trace.flush()
    t = _trace("600109", "score")
    assert t is not None
    assert "MA20多头排列" in t.technical_reasoning
    assert "政策利好" in t.technical_reasoning
    assert "主力净流入" in t.capital_reasoning
    assert "ROE 25%" in t.fundamental_reasoning
    concl = json.loads(t.final_conclusion)
    assert concl["potential_flag"] is True
    assert concl["cross_validation"] == "与Discover选股逻辑一致"
```

#### 6.7.3 新建 test_score_refactor.py

**文件**：`backend/tests/test_score_refactor.py`

```python
"""评级重做-A：六因子透明评分体系测试
覆盖：ScoreFactor/ScoreOutput schema 解析、potential_flag 逻辑、
交叉验证字段、cache_key v4 失效、collect_data 候选上下文注入、
旧数据向后兼容、reasoning_trace v4 格式留痕。
"""
import json
import pytest

from app.agents.schemas import ScoreFactor, ScoreOutput


# ---- Schema 解析 ----

def test_score_factor_valid():
    """ScoreFactor 正常解析"""
    f = ScoreFactor(factor="动量", score=7, reason="MA20多头排列", signal="看多")
    assert f.score == 7 and f.signal == "看多"

def test_score_factor_score_range():
    """score 超出 0-10 被 pydantic 拦截"""
    with pytest.raises(Exception):
        ScoreFactor(factor="动量", score=11, reason="x", signal="看多")
    with pytest.raises(Exception):
        ScoreFactor(factor="动量", score=-1, reason="x", signal="看多")

def test_score_factor_invalid_signal():
    """signal 不是 看多/中性/看空 被拦截"""
    with pytest.raises(Exception):
        ScoreFactor(factor="动量", score=5, reason="x", signal="强买")

def test_score_output_six_factors():
    """ScoreOutput 正常解析 6 因子"""
    factors = [
        ScoreFactor(factor=name, score=i, reason=f"测试{name}", signal="看多")
        for i, name in enumerate(["动量", "催化", "估值", "主线契合", "资金面", "基本面质量"], 1)
    ]
    out = ScoreOutput(stock_code="600519", stock_name="贵州茅台",
                      score=78, grade="B", factors=factors,
                      potential_flag=False, cross_validation_note="测试",
                      risk_list=[], final_advice="综合评估：6/6 因子看多")
    assert len(out.factors) == 6
    assert out.potential_flag is False
    assert out.cross_validation_note == "测试"


def test_score_output_defaults():
    """potential_flag 默认 False，cross_validation_note 默认空串"""
    factors = [ScoreFactor(factor="动量", score=5, reason="x", signal="中性")]
    out = ScoreOutput(stock_code="001", stock_name="t", score=50, grade="C",
                      factors=factors, risk_list=[])
    assert out.potential_flag is False
    assert out.cross_validation_note == ""


# ---- cache_key v4 失效 ----

def test_score_cache_key_v4(monkeypatch):
    """cache_key 包含 v4 前缀，确保旧缓存不命中"""
    from app.agents import score as score_mod

    captured = {}

    def _fake_agent_call(**kwargs):
        captured["cache_key"] = kwargs.get("cache_key", "")
        return ScoreOutput(stock_code="600000", stock_name="测试", score=60, grade="C",
                           factors=[ScoreFactor(factor="动量", score=5, reason="x", signal="中性")],
                           risk_list=[])

    monkeypatch.setattr(score_mod, "agent_call", _fake_agent_call)
    monkeypatch.setattr(score_mod.repo, "hot_money_fingerprint", lambda: "fp123")
    monkeypatch.setattr(score_mod.repo, "get_latest_preference", lambda: None)
    monkeypatch.setattr(score_mod.repo, "get_candidate_context", lambda *a: None)
    monkeypatch.setattr(score_mod.repo, "get_latest_market_intel", lambda: None)
    monkeypatch.setattr(score_mod.repo, "upsert_score", lambda *a, **k: None)

    state = {"stock_code": "600000", "stock_name": "测试",
             "trade_date": "2026-08-18", "trace": [],
             "tech_index": {}, "finance_data": [], "fund_flow_rows": [],
             "news_report": [], "basic_info": {}, "hot_money": None}
    score_mod.llm_score(state)
    assert "v4" in captured["cache_key"], f"cache_key 缺 v4: {captured['cache_key']}"


# ---- collect_data 候选上下文注入 ----

def test_collect_data_injects_discover_context(monkeypatch):
    """collect_data 注入 discover_context 和 market_intel_summary"""
    from app.agents import score as score_mod

    monkeypatch.setattr(score_mod.repo, "get_candidate_context",
                        lambda code, date: {"reasons": ["技术突破+量能放大"],
                                            "confidence_tier": "建议关注",
                                            "focus_type": "突破",
                                            "final_advice": "综合评估：3/5维支持"})
    monkeypatch.setattr(score_mod.repo, "get_latest_market_intel",
                        lambda: {"summary": "结构性分化，主线AI+消费"})

    # 最小化 mock 数据源
    class _FakeSource:
        def fetch_daily_kline(self, *a): return []
        def fetch_financial(self, *a): return type("DF", (), {"empty": True, "head": lambda s: s})()
        def fetch_fund_flow(self, *a): return None
        def fetch_news(self, *a): return type("DF", (), {"empty": True, "iterrows": lambda s: []})()
        def fetch_industry_spot(self, *a): return type("DF", (), {"empty": True})()

    monkeypatch.setattr(score_mod, "get_datasource", lambda: _FakeSource())
    monkeypatch.setattr(score_mod, "compute_indicators", lambda k: {})
    monkeypatch.setattr(score_mod, "get_vector_store",
                        lambda: type("VS", (), {"index_news": lambda *a: None})())

    state = {"stock_code": "600000", "stock_name": "测试",
             "trade_date": "2026-08-18", "trace": []}
    result = score_mod.collect_data(state)
    assert "技术突破+量能放大" in result.get("discover_context", "")
    assert "结构性分化" in result.get("market_intel_summary", "")


# ---- 向后兼容 ----

def test_trace_score_old_format_compat():
    """v3 旧格式 detail（维度名字典）留痕不报错"""
    from app.services import reasoning_trace
    detail = {
        "技术趋势": {"score": 85, "verdict": "支持", "advice": "均线多头排列"},
        "基本面": {"score": 70, "verdict": "支持", "advice": "业绩稳定"},
        "final_advice": "综合评估：3/5 维支持",
    }
    # 不抛异常即通过
    reasoning_trace.trace_score("600110", "兼容测试", "2026-08-05",
                                78.0, "B", detail, ["无"])
    reasoning_trace.flush()


# ---- potential_flag 代码层推导（P1-1 审核增强）----

def test_potential_flag_derived_from_factors(monkeypatch):
    """代码层按催化>=7 且 动量<=4 覆写 potential_flag（不信任 LLM 自报）"""
    from app.agents import score as score_mod
    from app.agents.schemas import ScoreFactor, ScoreOutput

    # LLM 自报 True 但因子不满足 → 强制 False
    out = ScoreOutput(stock_code="600000", stock_name="测试", score=60, grade="C",
                      factors=[
                          ScoreFactor(factor="催化", score=5, reason="x", signal="中性"),
                          ScoreFactor(factor="动量", score=3, reason="x", signal="看空"),
                          ScoreFactor(factor="估值", score=5, reason="x", signal="中性"),
                          ScoreFactor(factor="主线契合", score=5, reason="x", signal="中性"),
                          ScoreFactor(factor="资金面", score=5, reason="x", signal="中性"),
                          ScoreFactor(factor="基本面质量", score=5, reason="x", signal="中性"),
                      ],
                      potential_flag=True, risk_list=[])

    def _fake_agent_call(**kwargs):
        return out
    monkeypatch.setattr(score_mod, "agent_call", _fake_agent_call)
    monkeypatch.setattr(score_mod.repo, "get_latest_preference", lambda: None)
    monkeypatch.setattr(score_mod.repo, "get_candidate_context", lambda *a: None)
    monkeypatch.setattr(score_mod.repo, "get_latest_market_intel", lambda: None)
    monkeypatch.setattr(score_mod.repo, "hot_money_fingerprint", lambda: "fp")
    monkeypatch.setattr(score_mod.repo, "upsert_score", lambda *a, **k: None)

    state = {"stock_code": "600000", "stock_name": "测试", "trade_date": "2026-08-18",
             "trace": [], "tech_index": {}, "finance_data": [], "fund_flow_rows": [],
             "news_report": [], "basic_info": {}, "hot_money": None}
    score_mod.llm_score(state)
    assert out.potential_flag is False          # 自报 True 被覆写为 False

    # 因子满足 → 强制 True
    out2 = ScoreOutput(stock_code="600000", stock_name="测试", score=60, grade="C",
                       factors=[
                           ScoreFactor(factor="动量", score=4, reason="x", signal="中性"),
                           ScoreFactor(factor="催化", score=8, reason="x", signal="看多"),
                           ScoreFactor(factor="估值", score=5, reason="x", signal="中性"),
                           ScoreFactor(factor="主线契合", score=5, reason="x", signal="中性"),
                           ScoreFactor(factor="资金面", score=5, reason="x", signal="中性"),
                           ScoreFactor(factor="基本面质量", score=5, reason="x", signal="中性"),
                       ],
                       potential_flag=False, risk_list=[])
    monkeypatch.setattr(score_mod, "agent_call", lambda **kw: out2)
    score_mod.llm_score(state)
    assert out2.potential_flag is True          # 因子满足 → 强制 True


# ---- factors 六项强校验（P1-2 审核增强）----

def test_score_output_rejects_partial_factors():
    """少于 6 因子或因子名不合法 → pydantic 拦截（走 LLM 重试修正）"""
    from app.agents.schemas import ScoreFactor, ScoreOutput

    # 少于 6 因子
    with pytest.raises(Exception):
        ScoreOutput(stock_code="600519", stock_name="贵州茅台", score=78, grade="B",
                    factors=[ScoreFactor(factor="动量", score=5, reason="x", signal="中性")],
                    risk_list=[])

    # 因子名不合法（自创因子）
    with pytest.raises(Exception):
        ScoreOutput(stock_code="600519", stock_name="贵州茅台", score=78, grade="B",
                    factors=[
                        ScoreFactor(factor=n, score=5, reason="x", signal="中性")
                        for n in ["动量", "催化", "估值", "主线契合", "资金面", "自创因子"]],
                    risk_list=[])
```

---

## 七、执行顺序

```
1. schemas.py     — ScoreDimension → ScoreFactor + ScoreOutput 重构
2. score_prompt.py — 全文重写（SCHEMA_DESC + SYSTEM_PROMPT + build_user_prompt）
3. repo.py        — 新增 get_candidate_context 函数
4. score.py       — collect_data 新增上下文注入 + llm_score 适配新 schema
5. reasoning_trace.py — trace_score 兼容新旧格式
6. 测试适配        — test_hot_money_inject.py + test_reasoning_trace.py
7. 新建测试        — test_score_refactor.py
8. 全量测试        — pytest backend/tests/ -x 确认 0 failed
```

> **重要**：步骤 1-2 必须先完成，因为步骤 3-5 依赖新 schema。步骤 6-7 在步骤 1-5 完成后执行。

---

## 八、验证清单

### 8.1 代码验证

- [ ] `ScoreFactor` 字段：factor(str) / score(int 0-10) / reason(str) / signal(看多|中性|看空)
- [ ] `ScoreOutput` 字段：stock_code / stock_name / score(int 0-100) / grade(A|B|C) / factors(list[ScoreFactor]) / potential_flag(bool) / cross_validation_note(str) / risk_list(list[str]) / final_advice(str)
- [ ] `score_prompt.py` SCHEMA_DESC 示例含 6 个 factor + potential_flag + cross_validation_note
- [ ] `score_prompt.py` SYSTEM_PROMPT 含六因子定义、权重、分级阈值、潜力标识规则、交叉验证规则
- [ ] `build_user_prompt` 签名含 discover_context + market_intel_summary 参数
- [ ] `score.py` cache_key 含 `v4` 前缀
- [ ] `score.py` detail 存储格式为 `{factors: [...], potential_flag, cross_validation_note, final_advice}`
- [ ] `score.py` collect_data 注入 discover_context + market_intel_summary 到 state
- [ ] `repo.py` 新增 `get_candidate_context(code, trade_date)` 返回 {reasons, confidence_tier, focus_type, final_advice}
- [ ] `reasoning_trace.py` trace_score 兼容 factors 列表（新）和维度名字典（旧）
- [ ] 全局搜索 `ScoreDimension` 确认无遗漏引用（除测试文件外）

### 8.2 测试验证

- [ ] `test_score_refactor.py` 全部通过（≥10 条新测试，含 potential_flag 代码层推导覆写 + factors 六项强校验）
- [ ] `test_hot_money_inject.py` 适配后通过
- [ ] `test_reasoning_trace.py` 适配后通过（含旧格式兼容 + 新 v4 格式）
- [ ] `test_whitebox_position_sell.py` 不受影响（Position/Sell 的 DiscoverDimension 不变）
- [ ] `pytest backend/tests/ -x` 全量 0 failed

### 8.3 运行时验证（部署后）

- [ ] 手动触发一次评分，确认 LLM 输出 6 因子 + potential_flag + cross_validation_note
- [ ] 确认评分报告页（2_评分报告.py）旧数据不报错（新格式展示待评级重做-B）
- [ ] 确认推理留痕页正确显示六因子归因

---

## 九、风险与回滚

### 9.1 风险

1. **LLM 输出不稳定**：六因子比五维复杂，LLM 可能偶尔漏因子或格式错误。mitigation：pydantic 严格校验拦截，agent_call 重试机制已有。
2. **旧数据展示**：评级重做-B 完成前，新格式评分在旧前端展示为「（该轮未输出分项明细）」。mitigation：不影响功能，仅展示降级。
3. **权重未校准**：初始权重是经验值，未经回测验证。mitigation：评级重做-C 因子回测校准闭环解决。

### 9.2 回滚

1. cache_key 改回不含 `v4`（旧缓存命中，恢复五维评分）。
2. schemas.py 恢复 ScoreDimension + 旧 ScoreOutput。
3. score.py 恢复旧 llm_score 逻辑。
4. reasoning_trace.py 恢复旧 trace_score。
5. 旧评分数据不受影响（detail 列新旧格式共存）。
