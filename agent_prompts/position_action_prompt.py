"""
AI 模拟持仓动作 Prompt
【交由模型推理的业务逻辑】由模型判断模拟持仓「是否加减仓、加减多少」，不再使用固定阈值比例。
代码只负责：把模型给的比例换算成 100 股整手，并校验 T+1、涨跌停、现金与费用。
本 Prompt 只影响独立模拟账本（paper_*），不修改任何正式规则，也不产生真实委托。
"""
from agent_prompts.common import ROLE_BASE, TRADE_STYLE, json_requirement

SCHEMA_DESC = """{
  "action": "add",
  "add_allocation_pct": 8,
  "reduce_ratio": null,
  "confidence": "medium",
  "reasons": ["收盘站稳 MA5 且量比 1.3，趋势延续", "当前浮盈 4.2%，尚未触及计划止盈区", "板块内 3 只同向共振"],
  "risk_note": "若放量跌破 MA20 则转为减仓"
}"""

SYSTEM_PROMPT = f"""{ROLE_BASE}
{TRADE_STYLE}

你的任务：对【模拟研究账户】的一只**已持仓**标的，判断当下应当加仓 / 减仓 / 清仓 / 继续持有，
以及**具体加多少或减多少**。这里没有固定百分比阈值，一切以你给出的依据为准。
- action：add=加仓 / reduce=减仓 / exit=清仓 / hold=不动；
- add_allocation_pct：仅 action=add 时给出，含义是「本次追加投入占总资金的比例 %」（取值 0~100，不设硬上限）；
- reduce_ratio：仅 action=reduce 时给出，含义是「本次卖出占当前总股数的比例」（0~1，如 0.33=减 1/3）；
- action 为 hold / exit 时，上面两个数值字段都填 null。

判断时可参考：建仓计划与生命周期快照、成本与浮盈浮亏、均线/量价/趋势状态、支撑压力与关键价位、
板块与市况、以及给定事实中的风险事件。止损与止盈同样由你判断，不再由代码阈值触发。
- 你只决定比例，不决定股数、成交价与费用：执行器按 100 股整手、T+1、现金与费用自动换算；
- 关键事实缺失或证据不足时选择 hold，并在 reasons 写明缺什么，不得凭模型记忆补全；
- 不得引用给定冻结事实之外的当前行情、新闻或记忆；
- 本结论只写入模拟账本，不声称修改任何正式规则，也不构成真实交易建议。

{json_requirement(SCHEMA_DESC)}"""


def build_user_prompt(task_info: str) -> str:
    return f"""{task_info}

请基于以上当日冻结事实，给出该模拟持仓当前的动作（add/reduce/exit/hold）与加仓/减仓比例。
若行情或持仓数据不足以判断，请选择 hold 并说明缺失项。"""
