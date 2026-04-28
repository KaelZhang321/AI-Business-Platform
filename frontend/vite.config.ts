// Vite 配置文件：负责插件注册、别名配置和本地代理设置。
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  console.log(env)
  const apiUrl = env.VITE_API_BASE_URL?.trim() || 'https://beta-ai-platform.ssss818.com/ai-platform/';

  return {
    base: env.NODE_ENV === 'development' ? '/' : '/ai-platform/',
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
        // AI网关其余接口 (chat, health, bi...)
        '/api/v1/api-query': {
          target: apiUrl,
          changeOrigin: true,
        },
        // 业务编排层接口 (auth, tasks, knowledge, audit...)
        '/api/v1': {
          target: apiUrl,
          changeOrigin: true,
        },
        '/bs': {
          target: apiUrl,
          changeOrigin: true,
        },
      },
    },
  };
});
