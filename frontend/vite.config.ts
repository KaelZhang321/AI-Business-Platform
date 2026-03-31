// Vite 配置文件：负责插件注册、别名配置和本地代理设置。
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const apiUrl = env.VITE_API_BASE_URL?.trim() || 'https://beta-ai-platform.kaibol.net/ai-platform';

  return {
    base: '/ai-platform/',
    plugins: [react(), tailwindcss()],
    define: {
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY),
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      hmr: process.env.DISABLE_HMR !== 'true',
      proxy: {
        '/api/v1/auth': {
          target: apiUrl,
          changeOrigin: true,
        },
        '/api/v1/tasks': {
          target: apiUrl,
          changeOrigin: true,
        },
        '/api/v1/knowledge/documents': {
          target: apiUrl,
          changeOrigin: true,
        },
        '/api/v1/audit': {
          target: apiUrl,
          changeOrigin: true,
        },
        '/api': {
          target: apiUrl,
          changeOrigin: true,
        },
        '/api/v1': {
          target: apiUrl,
          changeOrigin: true,
        },
      },
    },
  };
});
