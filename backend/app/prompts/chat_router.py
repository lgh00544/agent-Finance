"""P1 智能路由：意图枚举 + 结构化输出 schema + 系统提示词（LIGHT 模型）。
方案 §5.3 意图表为唯一来源，不得自增意图。"""
from pydantic import BaseModel, Field

INTENTS = ("holdings", "pnl", "score", "sell", "discover", "market",
           "monitor", "review", "trigger", "help", "chat")


class RouteParams(BaseModel):
    code: str = Field(default="", description="6 位股票代码，无则空")
    name: str = Field(default="", description="股票名称，无则空")
    agent: str = Field(default="", description="chat 意图时目标 Agent：discover/score/position/monitor/sell/review")


class RouteIntent(BaseModel):
    intent: str = Field(description="11 类意图之一（仅枚举，不得自造）")
    params: RouteParams = RouteParams()
    reply_hint: str = Field(default="", description="用户意图一句话摘要")


SYSTEM_PROMPT = """你是股票决策系统的意图识别器。把用户消息映射到唯一意图并提取标的。
意图枚举（仅 11 类，不得自造）：
- holdings 查持仓   pnl 今日真实盈亏   score 分析/评分某股票（需标的）
- sell 卖出决策某持仓（需标的）   discover 今日选股/最新发现   market 大盘/板块/指数
- monitor 持仓监控/最新告警   review 最新复盘   trigger 触发任务（跑一次选股/挖掘）
- help 帮助/系统状态   chat 闲聊/知识问答/无把握
标的提取：用户提到股票时 params.code 填 6 位数字（如 600519），params.name 填名称（如 贵州茅台）。
chat 意图时 params.agent 填最相关 Agent（discover/score/position/monitor/sell/review）。
无法明确执行意图、信息不足或闲聊 → intent=chat，绝不瞎猜执行。只输出 JSON。"""


def user_prompt(text: str, prev: str) -> str:
    return (f"上轮对话（供「它/那个」指代消解，无关可忽略）：{prev or '（无）'}\n"
            f"用户消息：{text}\n"
            f"输出 JSON：{{\"intent\":\"...\",\"params\":{{\"code\":\"\",\"name\":\"\",\"agent\":\"\"}},\"reply_hint\":\"...\"}}")
