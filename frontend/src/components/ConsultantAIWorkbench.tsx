import { useMemo, useState } from 'react';
import { useJsonRenderMessage } from '@json-render/react';
import type { Spec } from '@json-render/react';
import { AssistantSidebar } from './consultant-ai-workbench/AssistantSidebar';
import { CustomerInfoBar } from './consultant-ai-workbench/CustomerInfoBar';
import { MainReportsPanel } from './consultant-ai-workbench/MainReportsPanel';
import { InsightsSidebar } from './consultant-ai-workbench/InsightsSidebar';
import { WorkbenchHeader } from './consultant-ai-workbench/WorkbenchHeader';
import { getAiResponse, createPlanningMessage } from './consultant-ai-workbench/chat';
import { historyItems, suggestionItems } from './consultant-ai-workbench/data';
import { buildJsonRenderParts } from './consultant-ai-workbench/json-render/spec';
import type { PlanningMessage, WorkbenchViewMode } from './consultant-ai-workbench/types';

/**
 * AiSpecExtractor — 内部工具组件，用于从 AI 回复内容中提取 Spec 对象。
 *
 * 为什么需要这个组件：
 *   useJsonRenderMessage 是 React Hook，只能在组件内调用。
 *   父组件需要把最新 AI 消息的 Spec 提升到父级 state，
 *   所以用一个专用子组件来解析，并通过 onSpec 回调上报。
 */
function AiSpecExtractor({ content, onSpec }: { content: string; onSpec: (spec: Spec | null) => void }) {
  const parts = useMemo(() => buildJsonRenderParts(content), [content]);
  const { spec } = useJsonRenderMessage(parts);

  // 每次 spec 变化时上报（只在变化时执行，通过 useMemo 缓存比较）
  useMemo(() => {
    onSpec(spec ?? null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spec]);

  return null; // 纯逻辑组件，不渲染任何 DOM
}

export function ConsultantAIWorkbench() {
  const [planningChatMessage, setPlanningChatMessage] = useState('');
  const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);
  const [showNewPlan, setShowNewPlan] = useState(false);
  const [aiName, setAiName] = useState('小智');
  const [isNaming, setIsNaming] = useState(false);
  const [viewMode, setViewMode] = useState<WorkbenchViewMode>('PLAN');
  const [planningMessages, setPlanningMessages] = useState<PlanningMessage[]>([
    createPlanningMessage(
      'ai',
      `您好！我是您的 AI 助手 ${aiName}。作为您的健康管家助手，我可以帮您整理客户的全量信息、查询治疗记录、对比治疗结果并生成追踪建议。您可以试着对我说："整理张三的所有信息"或"对比张三近半年的治疗结果"。`,
    ),
  ]);

  /**
   * latestAiSpec — 最新 AI 回复中解析出的 Spec 对象。
   *
   * 设计思路：
   *   - 每次收到新 AI 消息且存在 Spec 时，父组件更新此 state
   *   - 同时切换 viewMode 到 'AI_PANEL'，让 MainReportsPanel 展示卡片
   *   - Sidebar 气泡中只保留纯文本，卡片渲染移至中央主面板
   */
  const [latestAiSpec, setLatestAiSpec] = useState<Spec | null>(null);

  // 取最新一条 AI 消息，用于 AiSpecExtractor 解析
  const latestAiMessage = useMemo(
    () => [...planningMessages].reverse().find((m) => m.role === 'ai'),
    [planningMessages],
  );

  const handleSendPlanningMessage = (text?: string) => {
    const input = text || planningChatMessage;
    if (!input.trim()) return;

    setPlanningMessages((prev) => [...prev, createPlanningMessage('user', input)]);
    setPlanningChatMessage('');
    setIsGeneratingPlan(true);

    setTimeout(() => {
      const result = getAiResponse(input);

      if (result.viewMode) {
        setViewMode(result.viewMode);
      }
      if (typeof result.showNewPlan === 'boolean') {
        setShowNewPlan(result.showNewPlan);
      }

      setPlanningMessages((prev) => [...prev, createPlanningMessage('ai', result.response)]);
      setIsGeneratingPlan(false);
    }, 1500);
  };

  /**
   * handleSpecExtracted — AiSpecExtractor 解析完成后的回调。
   *
   * spec 不为 null 时：自动切换主面板到 AI_PANEL 模式展示交互卡片。
   * spec 为 null 时：说明最新 AI 消息是纯文本，主面板保留当前 viewMode。
   */
  const handleSpecExtracted = (spec: Spec | null) => {
    if (spec) {
      setLatestAiSpec(spec);
      setViewMode('AI_PANEL');
    }
  };

  return (
    <div className="h-full flex flex-col space-y-6">
      {/* 纯逻辑组件：监听最新 AI 消息，提取 Spec 并上报给父组件 */}
      {latestAiMessage && (
        <AiSpecExtractor
          content={latestAiMessage.content}
          onSpec={handleSpecExtracted}
        />
      )}

      <WorkbenchHeader />
      <CustomerInfoBar />

      <div className="flex-1 grid grid-cols-12 gap-6 overflow-hidden">
        {/* 左侧：AI 对话栏 — 气泡内只显示纯文本，卡片已移至主面板 */}
        <AssistantSidebar
          aiName={aiName}
          isNaming={isNaming}
          planningChatMessage={planningChatMessage}
          planningMessages={planningMessages}
          isGeneratingPlan={isGeneratingPlan}
          onAiNameChange={setAiName}
          onNamingToggle={setIsNaming}
          onPlanningMessageChange={setPlanningChatMessage}
          onSendMessage={handleSendPlanningMessage}
        />

        {/* 中央：主报告面板 — AI_PANEL 模式时渲染 JSON-Render 交互卡片 */}
        <MainReportsPanel
          viewMode={viewMode}
          showNewPlan={showNewPlan}
          historyItems={historyItems}
          suggestionItems={suggestionItems}
          aiSpec={latestAiSpec}
        />

        <InsightsSidebar />
      </div>
    </div>
  );
}
