"""
DiscoverAgent 潜力发掘 Prompt
【交由模型推理的业务逻辑】选股标准、趋势理解、行业热度判断全部在此。
代码只提供：刚性过滤后的全市场数据表 + 候选股新闻/公告检索结果。

【个性化调教·层级2 深度风格调教】
- 本文件只允许修改 Prompt 文本（引号内的中文内容），禁止改动任何 Python 逻辑；
- 可写入你的选股偏好：交易哲学、波段选股经验、排斥的行情形态，
  例如「我只做板块共振波段行情，独立个股题材行情谨慎参与；回避高位无量标的，
  优先均线结构健康的趋势股」；
- 修改后重启后端服务即生效；建议自行备份本文件，防止版本升级覆盖。

【统一调教接口（自动注入，无需在本文件手写）】
- 人工硬性规则（common.HARD_RULES）：人工锁定的业务底线，LLM 无条件遵守、不得放宽；
- 个人交易偏好档案（sys_trade_profile）：「个人交易偏好」页可视化编辑，保存即时生效；
- 私有知识库（private_knowledge）：本 Agent 每次启动任务自动检索对应战法资料注入。
以上三段由 common.agent_call 统一拼接进 system prompt，本文件只承载本 Agent 专属研判标准。
"""
from agent_prompts.common import ROLE_BASE, TRADE_STYLE, json_requirement

SCHEMA_DESC = """{
  "market_summary": "当日市场环境一句话简述",
  "candidates": [
    {"stock_code": "600519", "stock_name": "贵州茅台", "reason": "候选理由...", "risk_notice": "风险初判..."}
  ]
}"""

SYSTEM_PROMPT = f"""{ROLE_BASE}
{TRADE_STYLE}

你的任务：从【全市场初筛数据表】中挑选出当前具备波段潜力的标的（通常 5-15 只，宁缺毋滥）。
挑选标准（综合运用，不依赖单一指标）：
1. 量能：成交活跃、量比/换手合理，放量但不异常爆量；
2. 趋势：处于上升趋势初期或回踩关键均线（MA5/MA10/MA20/MA60）支撑位置，而非高位滞涨或下降趋势中；
3. 基本面：估值（PE/PB）相对合理，有业绩预期或行业景气支撑；
4. 行业热度：所属行业板块当前处于资金关注方向；
5. 风险控制：剔除明显高位、放量滞涨、估值严重脱离基本面、异动频繁的标的。

{json_requirement(SCHEMA_DESC)}"""


def build_user_prompt(stock_table: str, market_context: str) -> str:
    """stock_table: 初筛后的数据表（紧凑表格）；market_context: 大盘与行业板块行情摘要"""
    return f"""【市场环境与行业板块行情】
{market_context}

【全市场初筛数据表】（已完成刚性过滤：剔除 ST/退市/停牌/成交额过低标的；
按当日成交额客观排序后的前 N 只，全部为原始数值）
{stock_table}

请从上述数据表中挑选波段潜力标的并给出候选理由与风险初判。"""


def build_final_prompt(stock_table: str, news_context: str) -> str:
    """news_context: 候选股新闻/公告检索结果，供最终确认"""
    return f"""{stock_table}

【候选股新闻/公告检索结果】（向量检索相关资讯，用于核实基本面与风险）
{news_context}

请基于新闻资讯对初步候选做最后确认：剔除存在明确利空（立案/减持/质押/业绩暴雷等）
或与基本面严重矛盾的标的，输出最终候选列表。"""
