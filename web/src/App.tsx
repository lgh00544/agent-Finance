import { Routes, Route } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import {
  KnowledgePage,
  RuleChangesPage,
} from '@/pages'
import HoldingsPage from '@/pages/HoldingsPage'
import CandidatesPage from '@/pages/CandidatesPage'
import PlansPage from '@/pages/PlansPage'
import ScoresPage from '@/pages/ScoresPage'
import OverviewPage from '@/pages/OverviewPage'
import MarketIntelPage from '@/pages/MarketIntelPage'
import AlertsPage from '@/pages/AlertsPage'
import ExperiencePage from '@/pages/ExperiencePage'
import ReviewsPage from '@/pages/ReviewsPage'
import HotMoneyPage from '@/pages/HotMoneyPage'
import AgentChatPage from '@/pages/AgentChatPage'

/** 13 条路由（对齐 Streamlit 导航；7_个人交易偏好 未注册跳过） */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="market-intel" element={<MarketIntelPage />} />
        <Route path="candidates" element={<CandidatesPage />} />
        <Route path="scores" element={<ScoresPage />} />
        <Route path="plans" element={<PlansPage />} />
        <Route path="holdings" element={<HoldingsPage />} />
        <Route path="hot-money" element={<HotMoneyPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="reviews" element={<ReviewsPage />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="agent-chat" element={<AgentChatPage />} />
        <Route path="rule-changes" element={<RuleChangesPage />} />
        <Route path="experience" element={<ExperiencePage />} />
        <Route path="*" element={<OverviewPage />} />
      </Route>
    </Routes>
  )
}
