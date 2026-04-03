import { AnimatePresence, motion } from 'motion/react';
import { ChevronRight, RefreshCw, Send, Sparkles } from 'lucide-react';
import { buildJsonRenderParts } from './json-render/spec';
import { useJsonRenderMessage } from '@json-render/react';
import { useMemo } from 'react';
import { quickPromptActions } from './data';
import type { PlanningMessage } from './types';

/**
 * AiMessageText — AI 气泡内容组件（纯文本展示）
 *
 * 卡片（Spec）已移至中央主面板（MainReportsPanel）展示，
 * 气泡内只显示 AI 文本回复，并在有 Spec 时显示引导提示。
 */
function AiMessageText({ content }: { content: string }) {
  const parts = useMemo(() => buildJsonRenderParts(content), [content]);
  const { text, hasSpec } = useJsonRenderMessage(parts);

  return (
    <>
      {text.split('\n').map((line, index) => (
        <p key={`ai-line-${index}`} className={index > 0 ? 'mt-2' : ''}>
          {line}
        </p>
      ))}
      {/* 有 Spec 时提示用户在主面板查看交互卡片 */}
      {hasSpec && (
        <div className="mt-3 flex items-center space-x-1.5 px-2 py-1.5 bg-brand/10 rounded-xl border border-brand/15">
          <Sparkles className="w-3 h-3 text-brand flex-shrink-0" />
          <span className="text-[10px] font-bold text-brand">结构化卡片已展示在主面板</span>
        </div>
      )}
    </>
  );
}

interface AssistantSidebarProps {
  aiName: string;
  isNaming: boolean;
  planningChatMessage: string;
  planningMessages: PlanningMessage[];
  isGeneratingPlan: boolean;
  onAiNameChange: (value: string) => void;
  onNamingToggle: (value: boolean) => void;
  onPlanningMessageChange: (value: string) => void;
  onSendMessage: (text?: string) => void;
}


export function AssistantSidebar({
  aiName,
  isNaming,
  planningChatMessage,
  planningMessages,
  isGeneratingPlan,
  onAiNameChange,
  onNamingToggle,
  onPlanningMessageChange,
  onSendMessage,
}: AssistantSidebarProps) {
  return (
    <div className="col-span-3 flex flex-col bg-white/60 backdrop-blur-xl rounded-3xl border border-white/80 shadow-sm overflow-hidden">
      <div className="p-5 border-b border-slate-50 flex items-center justify-between bg-slate-50/50">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-5 h-5 text-brand" />
          {isNaming ? (
            <input
              autoFocus
              className="bg-transparent border-b border-brand outline-none font-bold text-slate-900 w-24"
              value={aiName}
              onChange={(e) => onAiNameChange(e.target.value)}
              onBlur={() => onNamingToggle(false)}
              onKeyDown={(e) => e.key === 'Enter' && onNamingToggle(false)}
            />
          ) : (
            <button
              type="button"
              className="font-bold text-slate-900 hover:text-brand transition-colors"
              onClick={() => onNamingToggle(true)}
              title="点击重命名助手"
            >
              {aiName}
            </button>
          )}
          <span className="text-[10px] bg-brand/10 text-brand px-1.5 py-0.5 rounded font-bold">AI 助手</span>
        </div>
        <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-6 custom-scrollbar">
        <div className="p-4 bg-gradient-to-br from-brand/5 to-purple-50 rounded-3xl border border-brand/10 mb-2">
          <p className="text-[10px] text-slate-500 leading-relaxed">
            我是您的数字健康管家 <span className="font-bold text-brand">{aiName}</span>。我已加载您负责的 128 位客户数据，随时待命。
          </p>
        </div>
        <AnimatePresence initial={false}>
          {planningMessages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              {msg.role === 'ai' && (
                <div className="flex items-center space-x-2 mb-2">
                  <div className="w-6 h-6 bg-brand rounded-lg flex items-center justify-center text-white text-[10px] font-bold">AI</div>
                  <span className="text-[10px] font-bold text-slate-400">{aiName} 助手</span>
                </div>
              )}
              <div
                className={`max-w-[95%] p-4 rounded-3xl text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-brand text-white rounded-tr-none'
                    : 'bg-slate-50 text-slate-700 rounded-tl-none border border-slate-100'
                }`}
              >
                {msg.role === 'ai' ? (
                  <AiMessageText content={msg.content} />
                ) : (
                  msg.content.split('\n').map((line, index) => (
                    <p key={`${msg.id}-${index}`} className={index > 0 ? 'mt-2' : ''}>
                      {line}
                    </p>
                  ))
                )}
              </div>
            </motion.div>
          ))}
          {isGeneratingPlan && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center space-x-3 p-4 bg-brand/5 rounded-2xl border border-brand/10"
            >
              <RefreshCw className="w-4 h-4 text-brand animate-spin" />
              <span className="text-xs font-bold text-brand">AI 正在分析全量数据并生成规划...</span>
            </motion.div>
          )}
        </AnimatePresence>

        {quickPromptActions.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onSendMessage(prompt)}
            className="w-full py-3 bg-slate-50 text-slate-600 text-xs font-bold rounded-3xl border border-slate-100 hover:bg-brand/5 hover:text-brand hover:border-brand/20 transition-all text-left px-4 flex items-center justify-between group"
            type="button"
          >
            <span>{prompt}</span>
            <ChevronRight className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-all" />
          </button>
        ))}
      </div>

      <div className="p-4 bg-white border-t border-slate-100">
        <div className="relative flex items-center">
          <input
            type="text"
            value={planningChatMessage}
            onChange={(e) => onPlanningMessageChange(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && onSendMessage()}
            placeholder={`给${aiName}下达指令...`}
            className="w-full pl-4 pr-12 py-3 bg-slate-50 border border-slate-100 rounded-2xl text-sm focus:outline-none focus:ring-2 focus:ring-brand/20 focus:border-brand transition-all"
          />
          <button
            type="button"
            onClick={() => onSendMessage()}
            aria-label="发送规划指令"
            className="absolute right-2 p-2 bg-brand text-white rounded-xl hover:bg-brand-dark transition-colors shadow-sm shadow-brand/20"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
