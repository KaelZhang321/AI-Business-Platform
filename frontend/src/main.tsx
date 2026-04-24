// 渲染入口：将根组件挂载到页面中的 root 节点。
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { App } from './App.tsx';
import './index.css';

// React Query 客户端：为 legacy 会议 BI 与后续数据页提供统一的查询缓存能力。
const queryClient = new QueryClient();
// 路由基础前缀：与 Vite 的 public base URL 保持一致，避免刷新或直达子路由时报路径错误。
const routerBaseName = import.meta.env.BASE_URL === '/' ? undefined : import.meta.env.BASE_URL.replace(/\/$/, '');

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={routerBaseName}>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
