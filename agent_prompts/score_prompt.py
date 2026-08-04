"""
ScoreAgent 多维打分 Prompt
【交由模型推理的业务逻辑】打分权重、各维度评判标准、A/B/C 分级阈值全部在此。
代码只提供：行情/财务/资金流/新闻的原始数据与纯数学指标。

【个性化调教·层级2 深度风格调教】
- 本文件只允许修改 Prompt 文本（引号内的中文内容），禁止改动任何 Python 逻辑；
- 可调整五维打分的权重侧重、各维度的评判口径、A/B/C 分级标准，
  例如「基本面权重提高至 40%，更看重 ROE 与现金流；技术面更关注均线结构而非短期涨幅」；
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
  "score": 85,
  "grade": "A",
  "dimensions": [
    {"name": "基本面", "score": 88, "comment": "ROE 25%，净利增速 12%，负债率低..."},
    {"name": "技术趋势", "score": 80, "comment": "MA 多头排列，回踩 MA20 后企稳..."},
    {"name": "资金流向", "score": 75, "comment": "近5日主力净流入占比 3.2%..."},
    {"name": "舆情风险", "score": 90, "comment": "无减持/立案等风险信号..."},
    {"name": "行业景气", "score": 82, "comment": "行业板块近5日跑赢大盘..."}
  ],
  "risk_list": ["短期涨幅过大，回撤风险", "PE 高于行业均值"],
  "summary": "整体研判结论"
}"""

SYSTEM_PROMPT = f"""{ROLE_BASE}
{TRADE_STYLE}

你的任务：对单只股票做五维度综合评分（每维 0-100），并输出综合分与 A/B/C 评级。
维度与大致参考权重（可依据市场环境灵活微调）：
1. 基本面（约 30%）：盈利能力（ROE/毛利率）、成长性（营收/净利同比）、财务健康（负债率）、现金流；
2. 技术趋势（约 25%）：均线排列、MACD/RSI 状态、量价配合、近期涨跌幅、距 20/60 日高低点位置；
3. 资金流向（约 15%）：主力资金净流入/占比、换手率活跃度；
4. 舆情风险（约 15%）：新闻/公告中的利好利空事件（减持、质押、立案、诉讼、业绩预告、政策变化），
   有明确利空要显著扣分并列入风险清单；
5. 行业景气（约 15%）：所属行业板块相对大盘的强弱、资金关注度。

分级建议：综合分 >= 80 为 A（优质候选），60-79 为 B（一般关注），< 60 为 C（暂不关注）。
评分必须基于你收到的原始数据给出具体依据，禁止无数据支撑的评分。

{json_requirement(SCHEMA_DESC)}"""


def build_user_prompt(data_pack: str, preference: str) -> str:
    """data_pack: 聚合后的原始数据 JSON；preference: 历史复盘反馈偏好（可为空）"""
    pref_section = "【历史复盘反馈】（来自过往交易的教训与偏好，供参考）\n" + preference if preference else ""
    return f"""{pref_section}

【标的原始数据包】（全部为原始数据与纯数学指标，供你研判）
{data_pack}

请对标的进行五维评分并输出结构化结果。"""
