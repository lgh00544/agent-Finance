import { useState } from 'react'
import { Layout } from 'antd'
import { Outlet } from 'react-router-dom'
import { SideMenu } from './SideMenu'
import { TopStatusBar } from './TopStatusBar'
import { TaskDrawer } from './TaskDrawer'

const { Sider, Content } = Layout

/** 应用外壳：左侧固定侧边栏（可折叠）+ 顶部状态栏 + 主内容区（Outlet）+ 全局任务面板 */
export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        width={220}
        collapsedWidth={64}
      >
        <div style={{ height: 48, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--text)', fontWeight: 700, fontSize: 15, letterSpacing: 0.05 }}>
          {collapsed ? '📊' : 'A股决策 Agent'}
        </div>
        <SideMenu collapsed={collapsed} />
      </Sider>
      <Layout>
        <TopStatusBar />
        <Content className="main-content">
          <Outlet />
        </Content>
      </Layout>
      {/* 全局后台任务面板：所有路由可见，z-index 高于内容 */}
      <TaskDrawer />
    </Layout>
  )
}
