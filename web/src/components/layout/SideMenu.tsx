import { Menu } from 'antd'
import {
  AlertOutlined,
  BookOutlined,
  CompassOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  FireOutlined,
  FundOutlined,
  HomeOutlined,
  LineChartOutlined,
  MessageOutlined,
  SafetyOutlined,
  StarOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import { useLocation, useNavigate } from 'react-router-dom'
import type { MenuProps } from 'antd'

/** 导航项：route → {label, icon}（对齐 Streamlit st.navigation 4 组 13 页） */
const NAV_GROUPS: Array<{
  title: string
  items: Array<{ path: string; label: string; icon: React.ReactNode }>
}> = [
  {
    title: '系统概览',
    items: [
      { path: '/', label: '系统概览', icon: <HomeOutlined /> },
      { path: '/market-intel', label: '市场研判', icon: <FundOutlined /> },
    ],
  },
  {
    title: '选股决策',
    items: [
      { path: '/candidates', label: '每日候选池', icon: <LineChartOutlined /> },
      { path: '/scores', label: '评分报告', icon: <StarOutlined /> },
      { path: '/plans', label: '建仓计划', icon: <CompassOutlined /> },
    ],
  },
  {
    title: '持仓风控',
    items: [
      { path: '/holdings', label: '持仓监控', icon: <SafetyOutlined /> },
      { path: '/hot-money', label: '游资追踪', icon: <FireOutlined /> },
      { path: '/alerts', label: '告警日志', icon: <AlertOutlined /> },
    ],
  },
  {
    title: '策略沉淀',
    items: [
      { path: '/reviews', label: '交易复盘', icon: <SyncOutlined /> },
      { path: '/knowledge', label: '交易知识库', icon: <BookOutlined /> },
      { path: '/agent-chat', label: 'Agent对话', icon: <MessageOutlined /> },
      { path: '/rule-changes', label: '规则变更记录', icon: <FileTextOutlined /> },
      { path: '/experience', label: '经验沉淀', icon: <ExperimentOutlined /> },
    ],
  },
]

export function SideMenu({ collapsed }: { collapsed: boolean }) {
  const location = useLocation()
  const navigate = useNavigate()
  const current = location.pathname === '/' ? '/' : `/${location.pathname.split('/')[1]}`

  const items: MenuProps['items'] = NAV_GROUPS.map((g) => ({
    type: 'group',
    label: collapsed ? undefined : g.title,
    children: g.items.map((it) => ({
      key: it.path,
      icon: it.icon,
      label: collapsed ? it.icon : it.label,
    })),
  }))

  return (
    <Menu
      theme="dark"
      mode="inline"
      inlineCollapsed={collapsed}
      selectedKeys={[current]}
      items={items}
      onClick={({ key }) => navigate(key)}
      style={{ borderInlineEnd: 'none' }}
    />
  )
}
