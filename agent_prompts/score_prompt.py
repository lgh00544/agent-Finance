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
                      market_intel_summary: str = "",
                      factor_calibration: str = "") -> str:
    """data_pack: 聚合后的原始数据 JSON；preference: 历史复盘反馈偏好（可为空）；
    discover_context: DiscoverAgent 选股理由（可为空，非候选池标的时无）；
    market_intel_summary: 当日市场研判摘要（可为空）；
    factor_calibration: 因子校准相关性参考文本（可为空，无数据不注入）"""
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
    calib_section = ""
    if factor_calibration:
        calib_section = f"""
【因子校准相关性参考】
{factor_calibration}
"""
    return f"""{pref_section}
{ctx_section}
{intel_section}
{calib_section}
【标的原始数据包】（全部为原始数据与纯数学指标，供你研判）
{data_pack}

请对标的进行六因子透明评分并输出结构化结果。"""
