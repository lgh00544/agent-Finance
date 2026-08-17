import { PagePlaceholder } from './PagePlaceholder'

/**
 * 13 个页面组件（Phase 1 全为占位；Phase 2+ 逐个替换为真实页面，届时拆分为独立文件）。
 * 与 Streamlit st.navigation 4 组 13 页一一对应（7_个人交易偏好未注册，跳过）。
 */

export const OverviewPage = () => (
  <PagePlaceholder name="系统概览" desc="系统服务 / 今日概览 / 性能统计 数据看板。" />
)
export const MarketIntelPage = () => (
  <PagePlaceholder name="市场研判" desc="阶段定性 / 核心矛盾 / 板块量能 / 操作含义 / 次日盯盘点。" />
)
export const CandidatesPage = () => (
  <PagePlaceholder name="每日候选池" desc="DiscoverAgent 候选列表 + 详情分区。" />
)
export const ScoresPage = () => (
  <PagePlaceholder name="评分报告" desc="ScoreAgent 五维评分列表与详情。" />
)
export const PlansPage = () => (
  <PagePlaceholder name="建仓计划" desc="PositionAgent 分批建仓方案。" />
)
export const HoldingsPage = () => (
  <PagePlaceholder name="持仓监控" desc="MonitorAgent 持仓行情 / 操作面板 / 告警 / 历史。" />
)
export const HotMoneyPage = () => (
  <PagePlaceholder name="游资追踪" desc="游资档案 / 龙虎榜 / 席位监控 / 研判留痕。" />
)
export const AlertsPage = () => (
  <PagePlaceholder name="告警日志" desc="MonitorAgent 全部信号记录。" />
)
export const ReviewsPage = () => (
  <PagePlaceholder name="交易复盘" desc="ReviewAgent 黑盒总览 + 详情与历史（黑盒规范保留）。" />
)
export const KnowledgePage = () => (
  <PagePlaceholder name="交易知识库" desc="私有交易经验 / 战法管理。" />
)
export const AgentChatPage = () => (
  <PagePlaceholder name="Agent对话" desc="六 Agent 对话 / 规则调教 / 多模态学习。" />
)
export const RuleChangesPage = () => (
  <PagePlaceholder name="规则变更记录" desc="复盘建议一键采纳的全量留痕，可回滚。" />
)
export const ExperiencePage = () => (
  <PagePlaceholder name="经验沉淀" desc="M1 沉淀队列 / M2 Digest / M3 高影响审核 / M4 经验库 / M5 设置。" />
)
