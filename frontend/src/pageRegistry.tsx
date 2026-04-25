// 页面注册表：集中管理页面到视图组件的映射，并通过懒加载控制首屏包体积。
import React, { Suspense, lazy } from 'react';
import type { AppPage } from './navigation';
import {
  isImplementedPage,
  PAGE_PATHS,
  PAGE_TITLES,
  PLACEHOLDER_PAGE_DESCRIPTIONS,
} from './navigation';
import type { DashboardMessage } from './components/DashboardView';
import { PlaceholderPage } from './components/PlaceholderPage';

/** 仪表盘路由上下文 —— Dashboard 页面所需的状态和回调 */
interface DashboardRouteContext {
  /** 当前活动页签：工作 / 待办 / 风险 */
  activeTab: 'work' | 'todo' | 'risk';
  /** 切换页签 */
  setActiveTab: React.Dispatch<React.SetStateAction<'work' | 'todo' | 'risk'>>;
  /** 当前选中的任务 ID */
  selectedTaskId: number | null;
  /** 设置选中任务 */
  setSelectedTaskId: React.Dispatch<React.SetStateAction<number | null>>;
  /** 打开创建任务弹窗 */
  setIsCreateModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  /** AI 助手对话消息列表 */
  messages: DashboardMessage[];
  /** 聊天输入框当前值 */
  chatInput: string;
  /** 设置聊天输入框内容 */
  setChatInput: React.Dispatch<React.SetStateAction<string>>;
  /** 发送消息回调 */
  handleSendMessage: (overrideText?: string) => void;
  /** AI 助手弹窗是否展开 */
  isAIOpen: boolean;
  /** 设置 AI 助手弹窗展开状态 */
  setIsAIOpen: React.Dispatch<React.SetStateAction<boolean>>;
  /** 打开到院接待弹窗 */
  setIsReceptionModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

/** 路由渲染上下文 —— 每个页面渲染时可获取的全局状态 */
interface RouteRenderContext {
  /** 导航到指定页面的回调 */
  navigateToPage: (page: AppPage) => void;
  /** 暗色模式开关 */
  isDarkMode: boolean;
  /** 切换暗色模式 */
  setIsDarkMode: React.Dispatch<React.SetStateAction<boolean>>;
  /** Dashboard 专属上下文 */
  dashboard: DashboardRouteContext;
}

/** 页面渲染器类型：接收路由上下文返回 React 元素 */
type PageRenderer = (context: RouteRenderContext) => React.ReactNode;

/* ---------- 懒加载页面组件（降低首屏包体积） ---------- */

/** 仪表盘首页 */
const DashboardView = lazy(async () => {
  const module = await import('./components/DashboardView');
  return { default: module.DashboardView };
});

/** 功能广场页 */
const FunctionSquareView = lazy(async () => {
  const module = await import('./components/FunctionSquareView');
  return { default: module.FunctionSquareView };
});

/** JSON Render 可视化构建器页 */
const UiBuilderPage = lazy(async () => {
  const module = await import('./pages/ui-builder/UiBuilderPage');
  return { default: module.UiBuilderPage };
});

/** 会议 BI 数据板页 */
const MeetingBiView = lazy(async () => {
  const module = await import('./components/MeetingBiView');
  return { default: module.MeetingBiView };
});

/** 健康管家 AI 页 */
const HealthButlerView = lazy(async () => {
  const module = await import('./components/HealthButlerView');
  return { default: module.HealthButlerView };
});

/** AI 辅助诊断页 */
const AIDiagnosisView = lazy(async () => {
  const module = await import('./components/AIDiagnosisView');
  return { default: module.AIDiagnosisView };
});

/** 医疗 AI 工作台页 */
const MedicalAIWorkbench = lazy(async () => {
  const module = await import('./components/MedicalAIWorkbench');
  return { default: module.MedicalAIWorkbench };
});

/** 护士 AI 工作台页 */
const NurseAIWorkbench = lazy(async () => {
  const module = await import('./components/NurseAIWorkbench');
  return { default: module.NurseAIWorkbench };
});

/** 顾问 AI 工作台页 */
const ConsultantAIWorkbench = lazy(async () => {
  const module = await import('./components/ConsultantAIWorkbench');
  return { default: module.ConsultantAIWorkbench };
});

/** AI 组件管理页 */
const AIComponentManagementView = lazy(async () => {
  const module = await import('./components/AIComponentManagementView');
  return { default: module.AIComponentManagementView };
});

/** AI 报告解读详情页 */
const AIReportComparisonDetailView = lazy(async () => {
  const module = await import('./components/ai-report/AIReportInterpretationDetailView');
  return { default: module.AIReportComparisonDetailView };
});

/** AI 四象限健康评估页 */
const AIFourQuadrantView = lazy(async () => {
  const module = await import('./components/ai-four-quadrant/AIFourQuadrantView');
  return { default: module.AIFourQuadrantView };
});

/** 体检报告页 */
const HealthReportView = lazy(async () => {
  const module = await import('./components/HealthReport/HealthReportView');
  return { default: module.HealthReportView };
});

/** 页面加载中的验证动画（Suspense fallback） */
function PageLoadingFallback() {
  return (
    <section className="rounded-[32px] border border-slate-200/70 bg-white/80 px-8 py-12 shadow-sm">
      <div className="space-y-6 animate-pulse">
        <div className="h-4 w-28 rounded-full bg-slate-200" />
        <div className="h-10 w-64 rounded-2xl bg-slate-200" />
        <div className="grid gap-4 md:grid-cols-3">
          <div className="h-40 rounded-3xl bg-slate-100" />
          <div className="h-40 rounded-3xl bg-slate-100" />
          <div className="h-40 rounded-3xl bg-slate-100" />
        </div>
      </div>
    </section>
  );
}

/** 页面标识 → 渲染器映射表：每个已实现页面的具体渲染逻辑 */
const PAGE_RENDERERS: Partial<Record<AppPage, PageRenderer>> = {
  dashboard: ({ dashboard }) => <DashboardView {...dashboard} />,
  'function-square': ({ navigateToPage }) => (
    <FunctionSquareView setCurrentPage={navigateToPage} />
  ),
  'ai-report-comparison': ({ navigateToPage, isDarkMode, setIsDarkMode }) => (
    <AIReportComparisonDetailView
      setCurrentPage={navigateToPage}
      isDarkMode={isDarkMode}
      setIsDarkMode={setIsDarkMode}
    />
  ),
  'health-report': ({ navigateToPage, isDarkMode, setIsDarkMode }) => (
    <HealthReportView
      setCurrentPage={navigateToPage}
      isDarkMode={isDarkMode}
      setIsDarkMode={setIsDarkMode}
    />
  ),
  'ai-four-quadrant': ({ navigateToPage, isDarkMode, setIsDarkMode }) => (
    <AIFourQuadrantView
      setCurrentPage={navigateToPage}
      isDarkMode={isDarkMode}
      setIsDarkMode={setIsDarkMode}
    />
  ),
  'ui-builder': () => <UiBuilderPage />,
  'meeting-bi': () => <MeetingBiView />,
  'health-butler': () => <HealthButlerView />,
  'ai-diagnosis': () => <AIDiagnosisView />,
  'medical-ai': () => <MedicalAIWorkbench />,
  'nurse-ai': () => <NurseAIWorkbench />,
  'consultant-ai': () => <ConsultantAIWorkbench />,
  'ai-component-management': ({ navigateToPage, isDarkMode, setIsDarkMode }) => (
    <AIComponentManagementView
      setCurrentPage={navigateToPage}
      isDarkMode={isDarkMode}
      setIsDarkMode={setIsDarkMode}
    />
  ),
};

/**
 * 渲染占位页：当页面未实现或未注册时显示提示文案。
 * @param page - 页面标识
 */
function renderFallbackPage(page: AppPage): React.ReactNode {
  if (!isImplementedPage(page)) {
    return (
      <PlaceholderPage
        title={PAGE_TITLES[page]}
        description={
          PLACEHOLDER_PAGE_DESCRIPTIONS[page] ??
          '该页面的视觉容器和路由已就绪，后续可以直接补充真实业务逻辑。'
        }
      />
    );
  }

  return (
    <PlaceholderPage
      title={PAGE_TITLES.dashboard}
      description={`当前页面尚未注册到页面映射中，请检查 ${PAGE_PATHS[page]} 的页面注册配置。`}
    />
  );
}

/**
 * 渲染指定页面：有注册渲染器则按配置渲染，否则显示占位页。
 * 外层包裹 Suspense 以支持懒加载加载态。
 * @param page - 页面标识
 * @param context - 路由渲染上下文
 */
export function renderAppPage(page: AppPage, context: RouteRenderContext): React.ReactNode {
  const renderer = PAGE_RENDERERS[page];
  if (!renderer) {
    return renderFallbackPage(page);
  }

  return <Suspense fallback={<PageLoadingFallback />}>{renderer(context)}</Suspense>;
}
