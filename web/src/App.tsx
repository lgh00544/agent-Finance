import { lazy, Suspense } from 'react'
import { Spin } from 'antd'
import { Routes, Route } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'

// 13 页懒加载（路由级代码分割；AppShell 布局保持静态首屏加载）
const OverviewPage = lazy(() => import('@/pages/OverviewPage'))
const MarketIntelPage = lazy(() => import('@/pages/MarketIntelPage'))
const CandidatesPage = lazy(() => import('@/pages/CandidatesPage'))
const ScoresPage = lazy(() => import('@/pages/ScoresPage'))
const PlansPage = lazy(() => import('@/pages/PlansPage'))
const HoldingsPage = lazy(() => import('@/pages/HoldingsPage'))
const HotMoneyPage = lazy(() => import('@/pages/HotMoneyPage'))
const AlertsPage = lazy(() => import('@/pages/AlertsPage'))
const ReviewsPage = lazy(() => import('@/pages/ReviewsPage'))
const KnowledgePage = lazy(() => import('@/pages/KnowledgePage'))
const AgentChatPage = lazy(() => import('@/pages/AgentChatPage'))
const RuleChangesPage = lazy(() => import('@/pages/RuleChangesPage'))
const ExperiencePage = lazy(() => import('@/pages/ExperiencePage'))
const ProfilePage = lazy(() => import('@/pages/ProfilePage'))

/** 页面加载过渡（路由切换时的懒加载 fallback） */
function PageLoading() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
      <Spin size="large" />
    </div>
  )
}

/** 13 条路由（全部懒加载；通配 * 兜底系统概览） */
export default function App() {
  return (
    <Suspense fallback={<PageLoading />}>
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
          <Route path="profile" element={<ProfilePage />} />
          <Route path="*" element={<OverviewPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
