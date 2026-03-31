// 首页视图：承载工作概览、AI 助手和统计模块，供路由层统一挂载。
import React from 'react';
import { TaskSection } from './TaskSection';
import { RiskSection } from './RiskSection';
import { AIAssistant } from './AIAssistant';
import { CommonFunctions } from './CommonFunctions';
import { StatsSection } from './StatsSection';

type DashboardMessageRole = 'ai' | 'user';

export interface DashboardMessage {
  id: string;
  role: DashboardMessageRole;
  content: string;
}

interface DashboardViewProps {
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

export function DashboardView({
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
}: DashboardViewProps) {
  return (
    <>
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 mb-6">
        <TaskSection
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          selectedTaskId={selectedTaskId}
          setSelectedTaskId={setSelectedTaskId}
          setIsCreateModalOpen={setIsCreateModalOpen}
        />
        <RiskSection />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
        <AIAssistant
          messages={messages}
          chatInput={chatInput}
          setChatInput={setChatInput}
          handleSendMessage={handleSendMessage}
          isAIOpen={isAIOpen}
          setIsAIOpen={setIsAIOpen}
        />
        <CommonFunctions setIsReceptionModalOpen={setIsReceptionModalOpen} />
      </div>

      <StatsSection />
    </>
  );
}
