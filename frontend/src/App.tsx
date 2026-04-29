// 应用主入口：负责登录态切换、会话恢复以及工作台主视图编排。
import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ConfigProvider, theme as antdTheme } from 'antd';
import type { AppPage } from './navigation';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { ReceptionModal, CreateTaskModal } from './components/Modals';
import { LoginPage } from './LoginPage';
import { NOTICES } from './data/mockData';
import { aiQueryApi } from './services/api/aiQueryApi';
import { useAppStore } from './stores/useAppStore';
import { getPageByPath, isKnownPath, PAGE_PATHS } from './navigation';
import { renderAppPage } from './pageRegistry';
import type { DashboardMessage } from './components/DashboardView';

/** 消息角色类型：AI 回复或用户输入 */
type AppMessageRole = 'ai' | 'user';

/** 消息 ID 自增计数器，保证每条消息的 key 唯一 */
let messageIdCounter = 0;

/**
 * 创建一条 Dashboard 消息对象。
 * @param role - 消息角色（ai / user）
 * @param content - 消息文本
 * @returns 带唯一 id 的消息对象
 */
function createAppMessage(role: AppMessageRole, content: string): DashboardMessage {
  messageIdCounter += 1;
  return {
    id: `msg-${messageIdCounter}`,
    role,
    content,
  };
}

/** 应用根组件：管理登录态、主视图编排、全局状态和路由导航 */
export function App() {
  const THEME_STORAGE_KEY = 'ai_platform_theme';
  const location = useLocation();          // 当前路由位置
  const navigate = useNavigate();          // 路由跳转函数
  /* ---------- 从全局 Store 读取认证状态与操作 ---------- */
  const isAuthenticated = useAppStore((state) => state.isAuthenticated);
  const token = useAppStore((state) => state.token);
  const user = useAppStore((state) => state.user);
  const login = useAppStore((state) => state.login);
  const iamLogin = useAppStore((state) => state.iamLogin);
  const logout = useAppStore((state) => state.logout);
  const restoreSession = useAppStore((state) => state.restoreSession);

  /* ---------- 局部 UI 状态 ---------- */
  /** 标记是否正在恢复登录状态（防止回话恢复期间被重定向） */
  const [isAuthBootstrapping, setIsAuthBootstrapping] = useState(Boolean(token));
  /** 暗色模式开关 */
  const [isDarkMode, setIsDarkMode] = useState(() => {
    if (typeof window === 'undefined') {
      return true;
    }
    const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (savedTheme === 'light') {
      return false;
    }
    if (savedTheme === 'dark') {
      return true;
    }
    return true;
  });
  /** 侧边栏是否折叠 */
  const [isCollapsed, setIsCollapsed] = useState(false);
  /** AI 助手面板是否展开 */
  const [isAIOpen, setIsAIOpen] = useState(false);
  /** 工作台当前页签：工作 / 待办 / 风险 */
  const [activeTab, setActiveTab] = useState<'work' | 'todo' | 'risk'>('work');
  /** AI 聊天输入框内容 */
  const [chatInput, setChatInput] = useState('');
  /** 当前滚动公告索引 */
  const [currentNoticeIndex, setCurrentNoticeIndex] = useState(2);
  /** 到院接待弹窗开关 */
  const [isReceptionModalOpen, setIsReceptionModalOpen] = useState(false);
  /** 创建任务弹窗开关 */
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  /** 当前选中的任务 ID */
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  /** 到院接待表单默认值 */
  const [receptionForm, setReceptionForm] = useState({
    name: '张三',
    serial: 'REQ-20240125-001',
    details: '客户到院，体温正常，准备进行深度体检方案签署。'
  });

  /** AI 助手对话消息列表（首条为系统欢迎语） */
  const [messages, setMessages] = useState<DashboardMessage[]>([
    createAppMessage(
      'ai',
      '您好，我是丽滋卡尔AI助手。您可以向我查询跨系统数据，例如：“王先生在云仓还剩多少库存？”或“今日下午约车排班”。',
    ),
  ]);

  /** 根据当前 URL 解析出页面标识，默认为 function-square */
  const currentPage = getPageByPath(location.pathname) ?? 'function-square';
  /** 当前 URL 是否为已注册路径 */
  const isKnownRoute = isKnownPath(location.pathname);
  /** 是否处于会议 BI 页面（会议 BI 采用独立全屏布局） */
  const isMeetingBiPage = currentPage === 'meeting-bi';
  const antdAlgorithm = isDarkMode ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm;
  const defaultAuthenticatedPath = PAGE_PATHS['function-square'];

  /* ---------- 副作用：滚动公告自动切换（每 4 秒轮播下一条） ---------- */
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentNoticeIndex((prev) => (prev + 1) % NOTICES.length);
    }, 4000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;

    // 如果本地已经有 token，但内存态还没恢复，就主动拉取一次当前用户信息。
    if (!token || isAuthenticated) {
      setIsAuthBootstrapping(false);
      return;
    }

    setIsAuthBootstrapping(true);
    restoreSession().finally(() => {
      if (!cancelled) {
        setIsAuthBootstrapping(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, restoreSession, token]);

  useEffect(() => {
    // 统一监听接口层抛出的鉴权失效事件，避免在多个组件里重复处理登出。
    const handleAuthLogout = () => {
      logout();
    };

    window.addEventListener('auth:logout', handleAuthLogout);
    return () => {
      window.removeEventListener('auth:logout', handleAuthLogout);
    };
  }, [logout]);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('dark', isDarkMode);
    window.localStorage.setItem(THEME_STORAGE_KEY, isDarkMode ? 'dark' : 'light');
  }, [isDarkMode]);

  useEffect(() => {
    // 会话恢复期间不做跳转，避免刷新时先被重定向导致丢失当前路由。
    if (isAuthBootstrapping) {
      return;
    }

    // 未登录时统一落到登录页；已登录访问登录页或未知路径时回到默认首页。
    if (!isAuthenticated && location.pathname !== PAGE_PATHS.login) {
      navigate(PAGE_PATHS.login, { replace: true });
      return;
    }

    if (isAuthenticated && (location.pathname === PAGE_PATHS.login || !isKnownRoute)) {
      navigate(defaultAuthenticatedPath, { replace: true });
    }
  }, [defaultAuthenticatedPath, isAuthBootstrapping, isAuthenticated, isKnownRoute, location.pathname, navigate]);

  /**
   * 发送聊天消息：将用户输入加入对话流，并模拟 AI 回复。
   * 后续可替换为真实聊天接口。
   * @param overrideText - 可选，如果传入则替代输入框内容
   */
  const handleSendMessage = async (overrideText?: string) => {
    const query = typeof overrideText === 'string' ? overrideText : chatInput;
    if (!query.trim()) return;

    setMessages((prev) => [...prev, createAppMessage('user', query)]);
    setChatInput('');

    try {
      const response = await aiQueryApi.query({
        query,
        conversationId: 'dashboard-assistant',
        context: aiQueryApi.buildContext('dashboard', {
          module: activeTab,
          availableActions: ['query_inventory', 'query_dispatch', 'query_report', 'query_policy'],
          extra: { currentPage },
        }),
      });

      const responseText = response.message || response.error || '已为您汇总相关数据。';
      setMessages((prev) => [...prev, createAppMessage('ai', responseText)]);
    } catch (error) {
      console.error('[App] AI query error:', error);
      setMessages((prev) => [...prev, createAppMessage('ai', '抱歉，当前无法完成智能查询，请稍后重试。')]);
    }
  };

  if (isAuthBootstrapping) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 text-slate-900 transition-colors duration-300 dark:bg-[#010107] dark:text-white">
        <div className="rounded-2xl border border-slate-200 bg-white/80 px-6 py-4 text-sm backdrop-blur-xl dark:border-white/10 dark:bg-white/5">
          正在恢复登录状态...
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      // onLogin={async ({ username, password }) => {
      //   await login(username, password);
      //   navigate(defaultAuthenticatedPath, { replace: true });
      // }}
      <LoginPage
        onIamLogin={async (code) => {
          await iamLogin(code);
          navigate(defaultAuthenticatedPath, { replace: true });
        }}
      />
    );
  }

  if (isMeetingBiPage) {
    return (
      <ConfigProvider theme={{ algorithm: antdAlgorithm }}>
        <div id="root-app-container" className="h-screen bg-[#050f24] text-slate-100">
          {renderAppPage(currentPage, {
            navigateToPage: (page: AppPage) => navigate(PAGE_PATHS[page]),
            isDarkMode,
            setIsDarkMode,
            dashboard: {
              activeTab,
              setActiveTab,
              selectedTaskId,
              setSelectedTaskId,
              setIsCreateModalOpen,
              messages,
              chatInput,
              setChatInput,
              handleSendMessage,
              isAIOpen,
              setIsAIOpen,
              setIsReceptionModalOpen,
            },
          })}
        </div>
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider theme={{ algorithm: antdAlgorithm }}>
      <div
        id="root-app-container"
        className="flex h-screen overflow-hidden bg-[#F4F6F8] font-sans text-slate-800 transition-colors duration-300 dark:bg-slate-950 dark:text-slate-100"
      >

        <Sidebar
          isDarkMode={isDarkMode}
          setIsDarkMode={setIsDarkMode}
          isCollapsed={isCollapsed}
          setIsCollapsed={setIsCollapsed}
          currentPage={currentPage}
          userName={user?.username}
          userRole={user?.role}
          onLogout={() => {
            logout();
            localStorage.removeItem('rememberedEmail');
            navigate(defaultAuthenticatedPath, { replace: true });
          }}
        />

        <div className="relative flex h-screen flex-1 flex-col overflow-hidden">
          {/* <Header
          currentNoticeIndex={currentNoticeIndex}
          currentPage={currentPage}
          currentUserName={user?.displayName}
        /> */}

          <main
            id="main-content-area"
            className={`relative flex-1 overflow-y-auto px-8 pb-8 ${currentPage === 'dashboard' ? 'pt-4' : 'pt-8'}`}
          >
            <div className="pointer-events-none absolute left-0 top-0 -z-10 h-[500px] w-full bg-gradient-to-br from-brand-light/40 via-brand-light/20 to-transparent dark:from-brand/12 dark:via-brand/5 dark:to-transparent"></div>

            <div className="max-w-[1720px] mx-auto space-y-6 h-full">
              {renderAppPage(currentPage, {
                navigateToPage: (page: AppPage) => navigate(PAGE_PATHS[page]),
                isDarkMode,
                setIsDarkMode,
                dashboard: {
                  activeTab,
                  setActiveTab,
                  selectedTaskId,
                  setSelectedTaskId,
                  setIsCreateModalOpen,
                  messages,
                  chatInput,
                  setChatInput,
                  handleSendMessage,
                  isAIOpen,
                  setIsAIOpen,
                  setIsReceptionModalOpen,
                },
              })}
            </div>
          </main>
        </div>

        <ReceptionModal
          isOpen={isReceptionModalOpen}
          onClose={() => setIsReceptionModalOpen(false)}
          form={receptionForm}
          setForm={setReceptionForm}
        />

        <CreateTaskModal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
        />

      </div>
    </ConfigProvider>
  );
}
