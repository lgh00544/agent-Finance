"""
LangGraph 全局状态结构体（用户给定结构 + 运行期扩展字段）
所有字段可选，节点只更新自己负责的部分，其余状态自动透传。
"""
from typing import Dict, List, Optional, TypedDict


class StockAgentState(TypedDict, total=False):
    # ---------- 用户给定核心字段 ----------
    stock_code: str
    stage: str  # discover / score / plan_position / holding_monitor / exit_review
    basic_info: Optional[Dict]
    tech_index: Optional[Dict]
    finance_data: Optional[Dict]
    fund_flow_rows: Optional[List[Dict]]
    news_report: Optional[List[Dict]]
    score_result: Optional[Dict]
    position_plan: Optional[Dict]
    holding_signal: Optional[Dict]
    exit_suggest: Optional[Dict]
    sell_input: Optional[Dict]
    sell_decision: Optional[Dict]
    risk_notice: Optional[List[str]]

    # ---------- 运行期内部字段 ----------
    trade_date: str  # YYYY-MM-DD 分析日期
    universe: Optional[List[Dict]]        # 刚性过滤后的全市场表（Discover）
    shortlist: Optional[List[Dict]]       # LLM 初选候选（Discover）
    enrichment: Optional[Dict]            # code -> 新闻检索结果（Discover）
    data_enrichment: Optional[Dict]       # code -> 增量数据（资金/股东/52周，v2.0）
    market_condition: Optional[Dict]      # 市况评分结果（v2.0 前置步骤）
    market_cap: Optional[int]             # 当日候选池上限（市况档位映射）
    candidates: Optional[List[Dict]]      # 最终候选（Discover）
    holding_id: Optional[int]             # 持仓 ID（Monitor/Review）
    batch_quotes: Optional[Dict[str, Dict]]  # code -> 批量预取实时行情（批量监控一次获取）
    error: Optional[str]                  # 节点错误信息（容错流转）
    trace: List[str]                      # 执行轨迹（调试/面板展示）
