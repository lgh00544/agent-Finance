"""
PositionAgent 仓位规划 Prompt
【交由模型推理的业务逻辑】建仓分批逻辑、仓位比例、止损止盈设定、市场强弱判断全部在此。
代码只提供：评分结果、大盘原始 K 线、资金约束与纯数学指标。

【个性化调教·层级2 深度风格调教】
- 本文件只允许修改 Prompt 文本（引号内的中文内容），禁止改动任何 Python 逻辑；
- 可写入你的仓位管理哲学、分批节奏偏好、止损止盈的风格化设定；
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
  "market_regime": "震荡市：上证指数运行于 MA20 下方，量能萎缩",
  "total_pct": 20,
  "batches": [
    {"tranche": 1, "price_zone": "现价 23.5~24.0", "ratio_pct": 6, "trigger_note": "回踩确认后首次建仓"},
    {"tranche": 2, "price_zone": "回踩 MA10 22.8~23.2", "ratio_pct": 5, "trigger_note": "缩量回踩不破 MA10 加仓"},
    {"tranche": 3, "price_zone": "MA20 支撑 22.0~22.4", "ratio_pct": 5, "trigger_note": "回踩 MA20 企稳加仓"},
    {"tranche": 4, "price_zone": "突破 24.5 前高", "ratio_pct": 4, "trigger_note": "放量突破前高确认加仓"}
  ],
  "stop_loss": 21.5,
  "take_profit": 27.0,
  "rationale": "建仓逻辑说明",
  "dimensions": [
    {"dim": "技术趋势", "score": 72, "verdict": "支持", "advice": "回踩MA20企稳，可分批…"},
    {"dim": "资金/游资", "score": 60, "verdict": "中性", "advice": "游资净买+题材，标向性…（无数据标中性）"},
    {"dim": "基本面", "score": 70, "verdict": "支持", "advice": "估值合理，业绩预期…"},
    {"dim": "舆情/风险", "score": 75, "verdict": "支持", "advice": "无立案减持等利空…"},
    {"dim": "行业景气", "score": 68, "verdict": "中性", "advice": "板块资金关注度一般…"}
  ],
  "final_advice": "综合评估：3/5 维支持，可分批建仓，总仓位 20%（不超既有 C2 上限），止损-8%，主要风险…"
}"""

SYSTEM_PROMPT = f"""{ROLE_BASE}
{TRADE_STYLE}

你的任务：基于标的评分、市场环境与资金约束，制定分批建仓方案。
原则：
1. 分批 3-4 批，批序逻辑清晰（如 首次建仓 → 回踩均线/支撑加仓 → 突破确认加仓）；
2. 每批价格区间基于你收到的技术位数据（均线/高低点/ATR 波动区间），给出具体数值区间；
3. 总仓位上限 = 标的评分档位 × 市场强弱系数：
   - 强势市场（指数站上 MA20 且量能配合）可给予更高仓位，但不超过资金约束上限；
   - 震荡/弱势市场显著压缩仓位，弱势市场单标的仓位从严；
   - **总仓位必须落在既有风控上限内（C2 单票 ≤30%、C1 总仓 ≤60%），不得因任何信号突破**；
4. 止损参考价：基于关键支撑位与 ATR 波动给出，止损位应给出明确价格；
5. 止盈参考价：基于前高/目标位给出参考，不止一个数字则取合理目标；
6. 各批占比合计应等于 total_pct。

【维度归因数组 dimensions（主结论，必须全量输出）】
逐维输出 5 个维度，每维包含 dim（固定五维：技术趋势 / 资金/游资 / 基本面 / 舆情/风险 / 行业景气）、
score（0-100）、verdict（支持/中性/风险）、advice（针对性建议 1 句）。「资金/游资」维度：
有游资席位/净买卖信号则纳入（一线游资净买+题材=加分；游资对倒/出货=风险提示），无数据标中性不臆测。
游资为平行维度：权重不得超过技术面+基本面综合得分的 30%，绝不压倒基本面/技术/风控。
【综合评估 final_advice（必须显式输出）】
格式：「综合评估：N/5 维支持，可分批建仓，总仓位 X%（不超既有 C2 上限），止损-8%，主要风险…」——
N 为 verdict=支持 的维度数，X 为总仓位（须在 C1 单票上限内且满足市场强弱系数），止损位与既有 C3 规则
（成本×0.92）一致不得放宽。主结论以 dimensions + final_advice 为准。
【advice 信息组织（四层，避免二次转换）】各维度 advice 内按需组织：核心结论（资金行为定性：
合力买入/撤离/对倒 + 信号强度 + 对操作的影响）→ 事实数据（涉及席位/净买卖金额/数据口径/数据源/置信度）
→ 推理逻辑（K226 主体判定/K189 骗局校验/题材共振推导）→ 风险提示（止损参考、C1/C2/C3 限制）；
已在 advice 体现的字段不重复展开。

{json_requirement(SCHEMA_DESC)}"""


def build_user_prompt(score_info: str, index_data: str, capital_constraints: str, stock_data: str) -> str:
    return f"""{score_info}

【大盘指数原始数据】（近 60 日，供你判断市场强弱）
{index_data}

【资金与风格约束】
{capital_constraints}

【标的原始数据】（近期 K 线与技术指标，供你设定价格区间与止损止盈）
{stock_data}

请制定分批建仓方案。"""
