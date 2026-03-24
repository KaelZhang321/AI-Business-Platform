import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 业务编排层接口 → :8080
      '/api/v1/auth': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/api/v1/tasks': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/api/v1/knowledge/documents': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/api/v1/audit': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      // AI网关接口 → :8000（chat, knowledge/search, query, health）
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
