import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './index.css'

// React Query 全局配置：staleTime 30s、retry 1、失焦不刷新
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: theme.darkAlgorithm,
          token: {
            colorPrimary: '#3b82f6', // 延续现有系统主色科技蓝
            borderRadius: 6,
            fontSize: 14,
            colorBgBase: '#0f1115',
            colorBgContainer: '#171a21',
            colorBorder: 'rgba(60, 80, 120, 0.25)',
            colorText: '#e5e7eb',
            colorTextSecondary: '#9ca3af',
            colorTextTertiary: '#6b7280',
          },
        }}
      >
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ConfigProvider>
    </QueryClientProvider>
  </StrictMode>,
)
