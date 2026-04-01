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

interface DashboardRouteContext {
  activeTab: 'work' | 'todo' | 'risk';
  setActiveTab: React.Dispatch<React.SetStateAction<'work' | 'todo' | 'risk'>>;
  selectedTaskId: number | null;
  setSelectedTaskId: React.Dispatch<React.SetStateAction<number | null>>;
  setIsCreateModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  messages: DashboardMessage[];
  chatInput: string;
  setChatInput: React.Dispatch<React.SetStateAction<string>>;
  handleSendMessage: (overrideText?: string) => void;
  isAIOpen: boolean;
  setIsAIOpen: React.Dispatch<React.SetStateAction<boolean>>;
  setIsReceptionModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

interface RouteRenderContext {
  navigateToPage: (page: AppPage) => void;
  dashboard: DashboardRouteContext;
}

type PageRenderer = (context: RouteRenderContext) => React.ReactNode;

const DashboardView = lazy(async () => {
  const module = await import('./components/DashboardView');
  return { default: module.DashboardView };
});

const FunctionSquareView = lazy(async () => {
  const module = await import('./components/FunctionSquareView');
  return { default: module.FunctionSquareView };
});

const UiBuilderPage = lazy(async () => {
  const module = await import('./pages/ui-builder/UiBuilderPage');
  return { default: module.UiBuilderPage };
});

const MeetingBiView = lazy(async () => {
  const module = await import('./components/MeetingBiView');
  return { default: module.MeetingBiView };
});

const HealthButlerView = lazy(async () => {
  const module = await import('./components/HealthButlerView');
  return { default: module.HealthButlerView };
});

const AIDiagnosisView = lazy(async () => {
  const module = await import('./components/AIDiagnosisView');
  return { default: module.AIDiagnosisView };
});

const MedicalAIWorkbench = lazy(async () => {
  const module = await import('./components/MedicalAIWorkbench');
  return { default: module.MedicalAIWorkbench };
});

const NurseAIWorkbench = lazy(async () => {
  const module = await import('./components/NurseAIWorkbench');
  return { default: module.NurseAIWorkbench };
});

const ConsultantAIWorkbench = lazy(async () => {
  const module = await import('./components/ConsultantAIWorkbench');
  return { default: module.ConsultantAIWorkbench };
});

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

const PAGE_RENDERERS: Partial<Record<AppPage, PageRenderer>> = {
  dashboard: ({ dashboard }) => <DashboardView {...dashboard} />,
  'function-square': ({ navigateToPage }) => (
    <FunctionSquareView setCurrentPage={navigateToPage} />
  ),
  'ui-builder': () => <UiBuilderPage />,
  'meeting-bi': () => <MeetingBiView />,
  'health-butler': () => <HealthButlerView />,
  'ai-diagnosis': () => <AIDiagnosisView />,
  'medical-ai': () => <MedicalAIWorkbench />,
  'nurse-ai': () => <NurseAIWorkbench />,
  'consultant-ai': () => <ConsultantAIWorkbench />,
};

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

export function renderAppPage(page: AppPage, context: RouteRenderContext): React.ReactNode {
  const renderer = PAGE_RENDERERS[page];
  if (!renderer) {
    return renderFallbackPage(page);
  }

  return <Suspense fallback={<PageLoadingFallback />}>{renderer(context)}</Suspense>;
}
