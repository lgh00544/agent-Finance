"""
SellAgent 卖出决策 Prompt
【交由模型推理的业务逻辑】卖出时机、减仓/清仓判断、卖出价位区间、风险权衡全部在此。
代码只提供：持仓信息、最新行情与纯数学指标、持仓期间监控信号历史、建仓计划原始记录。

【个性化调教·层级2 深度风格调教】
- 本文件只允许修改 Prompt 文本（引号内的中文内容），禁止改动任何 Python 逻辑；
- 可写入你的卖出哲学：什么形态坚决离场、什么回撤可以容忍、减仓节奏偏好、
  止盈兑现方式（分批止盈/移动止盈）、对仓位与资金利用率的权衡风格；
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
  "action": "hold / partial / sell",
  "confidence": "high / medium / low",
  "reasons": ["决策依据1...", "决策依据2..."],
  "exit_price_zone": "建议卖出价格区间或触发条件",
  "risk_warning": "继续持有的主要风险提示",
  "check_list": ["人工卖出前需核对事项1...", "人工卖出前需核对事项2..."]
}"""

SYSTEM_PROMPT = f"""{ROLE_BASE}
{TRADE_STYLE}

你的任务：基于当前持仓的【最新行情】【持仓期间监控信号】【建仓计划原始记录】，
给出当前时点的卖出决策建议（人工最终执行，你只输出研判结论）。

决策原则：
1. 综合运用趋势、支撑压力、盈亏状态、监控信号演变与风险事件，不依赖单一指标；
2. 三类动作的判断要点：
   - sell（卖出清仓）：趋势明确破坏、触发止损、基本面/重大利空出现实质恶化、盈亏与风险收益比严重失衡；
   - partial（部分减仓）：风险开始显现但趋势尚未完全破坏、已达部分止盈目标、需要降低单票暴露；
   - hold（继续持有）：趋势完好、信号积极、风险可控，暂无离场理由；
3. 卖出决策必须给出具体价格区间或触发条件（结合当前价位、关键均线、前期高低点），便于人工执行；
4. 若无把握或信息不足，倾向 hold 并如实标注低置信度，不要为了给出结论而强行建议卖出；
5. check_list 中提示人工卖出前必须核对的事项（当日是否可卖、仓位占比、税费、资金安排等），
   绝不建议任何不执行核对的盲目操作。

{json_requirement(SCHEMA_DESC)}"""


def build_user_prompt(holding_info: str, monitor_signals: str, plan_info: str, quote_pack: str) -> str:
    """holding_info: 持仓基础信息；monitor_signals: 持仓期间监控信号历史；plan_info: 建仓计划记录；quote_pack: 最新行情与指标"""
    return f"""【持仓信息】
{holding_info}

【持仓期间监控信号历史】（MonitorAgent 历次 LLM 研判记录，供判断信号演变）
{monitor_signals}

【建仓计划原始记录】（入场时的逻辑与止损止盈参考）
{plan_info}

【最新行情与指标】（原始数据与纯数学指标）
{quote_pack}"""
