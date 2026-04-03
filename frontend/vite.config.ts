// Vite 配置文件：负责插件注册、别名配置和本地代理设置。
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const apiUrl = env.VITE_API_BASE_URL?.trim() || 'http://39.96.197.81:8080';

  return {
    base: mode === 'development' ? '/' : '/ai-platform/',
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
        // 业务编排层接口 (auth, tasks, knowledge, audit...)
        '/api/v1': {
          target: apiUrl,
          changeOrigin: true,
        },
        // AI网关其余接口 (chat, health, bi...)
        '/api': {
          target: apiUrl,
          changeOrigin: true,
        },
      },
    },
  };
});
