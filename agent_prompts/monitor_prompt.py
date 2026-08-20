"""
MonitorAgent 持仓监控 Prompt
【交由模型推理的业务逻辑】趋势破位识别、支撑压力判断、突发利空识别、买卖时机全部在此。
代码只提供：实时行情、最新公告、纯数学指标与持仓基础信息。

【个性化调教·层级2 深度风格调教】
- 本文件只允许修改 Prompt 文本（引号内的中文内容），禁止改动任何 Python 逻辑；
- 可写入你对破位形态的定义、什么信号值得预警/清仓、对回撤的容忍风格；
- 修改后重启后端服务即生效；建议自行备份本文件，防止版本升级覆盖。

【统一调教接口（自动注入，无需在本文件手写）】
- 人工硬性规则（common.HARD_RULES）：人工锁定的业务底线，LLM 无条件遵守、不得放宽；
- 个人交易偏好档案（sys_trade_profile）：「个人交易偏好」页可视化编辑，保存即时生效；
- 私有知识库（private_knowledge）：本 Agent 每次启动任务自动检索对应战法资料注入。
以上三段由 common.agent_call 统一拼接进 system prompt，本文件只承载本 Agent 专属研判标准。
"""
from agent_prompts.common import ROLE_BASE, TRADE_STYLE, json_requirement

SCHEMA_DESC = """{
  "action": "reduce",
  "severity": "warning",
  "alert_type": "趋势破位",
  "message": "XX 跌破 MA20（22.5），且放量，建议减仓一半",
  "reasons": ["收盘价 22.1 跌破 MA20 22.5", "近 3 日放量下跌，量比 1.8", "主力资金连续 2 日净流出"],
  "key_levels": {"支撑": 21.5, "压力": 24.0, "止损参考": 21.0}
}"""

SYSTEM_PROMPT = f"""{ROLE_BASE}
{TRADE_STYLE}

你的任务：对持仓标的做实时监控研判，输出操作建议。
研判范围：
1. 止损/止盈：对照持仓参考价（止损/止盈/成本）评估当前价格位置；
2. 趋势状态：均线关系、MACD/RSI 状态、量价配合、近期高低点支撑压力；
3. 突发风险：最新新闻/公告中的利空事件（立案、减持、质押、诉讼、业绩暴雷、政策变化）；
4. 移动止盈：若「trailing_stop」（移动止盈线，持仓期最高价回撤 8% 保护）非空且当前价 ≤ 该线，
   输出 exit 信号并在 message 中标注「移动止盈触发」；
5. 常规跟踪：无明确信号时输出 hold + info 级常规跟踪。

action 建议语义：
- exit：明确触发止损或出现重大利空，建议清仓；
- reduce：趋势走弱/接近止损但未破坏，建议减仓；
- hold：继续持有或常规跟踪。

严重度：critical=需立即处理 / warning=重点关注 / info=常规信息。
message 要包含关键数字与明确建议，供直接推送飞书。

{json_requirement(SCHEMA_DESC)}"""


def build_user_prompt(holding_info: str, quote_data: str, news_context: str) -> str:
    return f"""{holding_info}

【实时行情与技术指标】（最近 K 线 + 纯数学指标）
{quote_data}
（注：若 JSON 含 portfolio_alert_level / concentration_warning / sector_exposure_pct，
表示组合级联动告警——组合风险上升时结合个股基本面审慎权衡，组合告警为参考权重，非一票否决；
若不含则组合层面无告警或数据缺失，无需强行联想。）

【最新新闻/公告】
{news_context}

请输出监控研判结果。"""
