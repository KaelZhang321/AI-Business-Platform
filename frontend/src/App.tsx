// 应用主入口：负责登录态切换、会话恢复以及工作台主视图编排。
import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { AppPage } from './navigation';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { ReceptionModal, CreateTaskModal } from './components/Modals';
import { LoginPage } from './LoginPage';
import { NOTICES } from './data/mockData';
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
  const [isDarkMode, setIsDarkMode] = useState(true);
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

  /** 根据当前 URL 解析出页面标识，默认为 dashboard */
  const currentPage = getPageByPath(location.pathname) ?? 'dashboard';
  /** 当前 URL 是否为已注册路径 */
  const isKnownRoute = isKnownPath(location.pathname);
  /** 是否处于会议 BI 页面（会议 BI 采用独立全屏布局） */
  const isMeetingBiPage = currentPage === 'meeting-bi';

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
    // 会话恢复期间不做跳转，避免刷新时先被重定向导致丢失当前路由。
    if (isAuthBootstrapping) {
      return;
    }

    // 未登录时统一落到登录页；已登录访问登录页或未知路径时回到首页。
    if (!isAuthenticated && location.pathname !== PAGE_PATHS.login) {
      navigate(PAGE_PATHS.login, { replace: true });
      return;
    }

    if (isAuthenticated && (location.pathname === PAGE_PATHS.login || !isKnownRoute)) {
      navigate(PAGE_PATHS.dashboard, { replace: true });
    }
  }, [isAuthBootstrapping, isAuthenticated, isKnownRoute, location.pathname, navigate]);

  /**
   * 发送聊天消息：将用户输入加入对话流，并模拟 AI 回复。
   * 后续可替换为真实聊天接口。
   * @param overrideText - 可选，如果传入则替代输入框内容
   */
  const handleSendMessage = (overrideText?: string) => {
    const query = typeof overrideText === 'string' ? overrideText : chatInput;
    if (!query.trim()) return;

    setMessages((prev) => [...prev, createAppMessage('user', query)]);
    setChatInput('');

    // 这里仍然保留演示用的假数据回复，后续可以替换成真实聊天接口。
    setTimeout(() => {
      let response = '已为您汇总相关数据。';
      if (query.includes('王先生') && query.includes('库存')) {
        response = '📊 **数据简报**\n王先生（ID: VIP-8821）在客户云仓当前剩余：\n- 极品燕窝：2盒\n- 定制营养素：5瓶\n\n最近一次出库时间为 2026-03-10。';
      } else if (query.includes('空闲司机') || query.includes('派车') || query.includes('专车司机')) {
        response = '🚗 **运力简报**\n当前周边 3 公里内空闲司机：\n1. 张师傅 (京A·88***) - 距 1.2km\n2. 李师傅 (京A·66***) - 距 2.5km\n\n[点击一键派单至张师傅]';
      } else if (query.includes('效能报告')) {
        response = '📈 **效能简报**\n本周高端客户接待效能：\n- 客户满意度：99.2%\n- 平均等待时长：4.5分钟 (达标)\n- 异常派单率：0.1%\n\n报告已生成，[点击预览完整报告]';
      } else if (query.includes('红头文件')) {
        response = '🛡️ **政策速递**\n为您找到最新文件：《2026年度第一季度合规审查红头文件》\n核心内容：强调数据隐私保护，严禁跨权限导出老客户CRM数据。\n\n[点击查看文件详情]';
      }
      setMessages((prev) => [...prev, createAppMessage('ai', response)]);
    }, 1000);
  };

  if (isAuthBootstrapping) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#010107] text-white">
        <div className="rounded-2xl border border-white/10 bg-white/5 px-6 py-4 text-sm backdrop-blur-xl">
          正在恢复登录状态...
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      // onLogin={async ({ username, password }) => {
      //   await login(username, password);
      //   navigate(PAGE_PATHS.dashboard, { replace: true });
      // }}
      <LoginPage
        onIamLogin={async (code) => {
          await iamLogin(code);
          navigate(PAGE_PATHS.dashboard, { replace: true });
        }}
      />
    );
  }

  if (isMeetingBiPage) {
    return (
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
    );
  }

  return (
    <div id="root-app-container" className="flex h-screen bg-[#F4F6F8] font-sans text-slate-800 overflow-hidden">

      <Sidebar
        isDarkMode={isDarkMode}
        setIsDarkMode={setIsDarkMode}
        isCollapsed={isCollapsed}
        setIsCollapsed={setIsCollapsed}
        currentPage={currentPage}
        userName={user?.displayName}
        userRole={user?.role}
        onLogout={() => {
          logout();
          localStorage.removeItem('rememberedEmail');
          navigate(PAGE_PATHS.dashboard, { replace: true });
        }}
      />

      <div className="flex-1 flex flex-col h-screen overflow-hidden relative">
        {/* <Header
          currentNoticeIndex={currentNoticeIndex}
          currentPage={currentPage}
          currentUserName={user?.displayName}
        /> */}

        <main id="main-content-area" className={`flex-1 overflow-y-auto pb-8 relative px-8 ${currentPage === 'dashboard' ? 'pt-4' : 'pt-8'}`}>
          <div className="absolute top-0 left-0 w-full h-[500px] bg-gradient-to-br from-brand-light/40 via-brand-light/20 to-transparent pointer-events-none -z-10"></div>

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
  );
}
