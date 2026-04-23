// 首页视图：承载工作概览、AI 助手和统计模块，供路由层统一挂载。
import React from 'react';
import { TaskSection } from './TaskSection';
import { RiskSection } from './RiskSection';
import { AIAssistant } from './AIAssistant';
import { CommonFunctions } from './CommonFunctions';
import { StatsSection } from './StatsSection';

/** 消息角色类型 */
type DashboardMessageRole = 'ai' | 'user';

/** AI 助手对话消息结构 */
export interface DashboardMessage {
  /** 消息唯一 ID */
  id: string;
  /** 消息角色：ai / user */
  role: DashboardMessageRole;
  /** 消息文本内容 */
  content: string;
}

/** 首页视图组件属性 */
interface DashboardViewProps {
  /** 当前活动页签 */
  activeTab: 'work' | 'todo' | 'risk';
  setActiveTab: React.Dispatch<React.SetStateAction<'work' | 'todo' | 'risk'>>;
  /** 当前选中任务 ID */
  selectedTaskId: number | null;
  setSelectedTaskId: React.Dispatch<React.SetStateAction<number | null>>;
  setIsCreateModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  /** AI 助手对话消息 */
  messages: DashboardMessage[];
  /** 聊天输入框内容 */
  chatInput: string;
  setChatInput: React.Dispatch<React.SetStateAction<string>>;
  /** 发送消息回调 */
  handleSendMessage: (overrideText?: string) => void;
  /** AI 助手显示状态 */
  isAIOpen: boolean;
  setIsAIOpen: React.Dispatch<React.SetStateAction<boolean>>;
  setIsReceptionModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

/** 首页视图组件：承载工作概览、AI 助手和统计模块 */
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
