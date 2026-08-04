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
  "rationale": "建仓逻辑说明"
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
4. 止损参考价：基于关键支撑位与 ATR 波动给出，止损位应给出明确价格；
5. 止盈参考价：基于前高/目标位给出参考，不止一个数字则取合理目标；
6. 各批占比合计应等于 total_pct。

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
