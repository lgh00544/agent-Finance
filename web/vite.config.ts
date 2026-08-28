import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // 开发期：/api → FastAPI 8000（后端零改动；生产期由 FastAPI 静态挂载 web/dist）
      '/api': {
        target: process.env.VITE_API_PROXY || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Vendor 分包：React/Antd/ECharts/Query 各自独立 chunk（长期缓存 + 首屏瘦身；
        // ECharts 仅图表页按需加载，无图表页不加载）。
        // 注：Vite 8（rolldown）的 manualChunks 仅接受函数形式，不接受对象字面量。
        manualChunks(id: string) {
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom')
              || id.includes('node_modules/react-router')) {
            return 'vendor-react'
          }
          if (id.includes('node_modules/antd') || id.includes('node_modules/@ant-design')) {
            return 'vendor-antd'
          }
          if (id.includes('node_modules/echarts')) {
            return 'vendor-echarts'
          }
          if (id.includes('node_modules/@tanstack') || id.includes('node_modules/zustand')) {
            return 'vendor-query'
          }
          return undefined
        },
      },
    },
  },
})
