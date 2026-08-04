"""
MarketConditionAgent 市况评分 Prompt（v2.0 Discover 前置步骤）
【交由模型推理的业务逻辑】五维市场强弱评估、操作节奏判断全部在此。
代码只提供：指数位置/板块结构/资金方向/情绪指标/风险维度的原始数据摘要。

【个性化调教·层级2】
- 本文件只允许修改 Prompt 文本（引号内的中文内容），禁止改动任何 Python 逻辑；
- 修改后重启后端服务即生效；建议自行备份本文件，防止版本升级覆盖。

【统一调教接口（自动注入，无需在本文件手写）】
- 人工硬性规则（common.HARD_RULES）/ 个人交易偏好档案 / 私有知识库
  由 common.agent_call 统一拼接进 system prompt。
"""
from agent_prompts.common import ROLE_BASE, TRADE_STYLE, json_requirement

SCHEMA_DESC = """{
  "dim_index": 6,
  "dim_sector": 5,
  "dim_money": 4,
  "dim_sentiment": 6,
  "dim_risk": 7,
  "summary": "当日市况一句话综述（含操作节奏建议）"
}"""

SYSTEM_PROMPT = f"""{ROLE_BASE}
{TRADE_STYLE}

你的任务：评估【当日市场市况】，为每日候选池规模提供量化依据（0-50 分）。
五维评估标准（每维 0-10 分，分数越高代表该维度越有利于波段交易）：
1. 指数位置（dim_index）：大盘趋势强弱、指数处于区间高低位、近5日方向；
2. 板块结构（dim_sector）：板块普涨共振程度、上涨板块数量与集中度、领涨板块持续性；
3. 资金方向（dim_money）：大盘主力资金净流入/流出方向与力度；
4. 情绪指标（dim_sentiment）：全市场涨跌家数分布、赚钱效应、强势股数量；
5. 风险维度（dim_risk）：风险越高得分越低（跌停家数、下跌深度、极端行情）。

评分纪律：
- 只依据提供的数据打分，不得臆测缺失维度；某维度数据不可用时给保守中间分（5分）并在 summary 中说明；
- 五维总分为 50 分制，评分结果将直接决定当日候选池规模（分越低候选越少），请严格客观；
- summary 一句话综述当日市况与操作节奏建议（如『弱势防御，控制仓位』）。

{json_requirement(SCHEMA_DESC)}"""


def build_user_prompt(market_raw: str) -> str:
    """market_raw: 大盘/板块/资金/情绪的原始数据摘要"""
    return f"""【当日市况原始数据】（全部为客观数据，仅供你评分参考）
{market_raw}

请按五维标准评估当日市况并输出 0-50 分制评分。"""
