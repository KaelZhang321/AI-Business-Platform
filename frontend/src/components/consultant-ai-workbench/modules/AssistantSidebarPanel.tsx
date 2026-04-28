import React, { useEffect, useRef } from 'react';
import { ArrowUp, ChevronLeft, Sparkles, Bot, User, Loader2 } from 'lucide-react';
import type { ChatHistoryItem, CustomerRecord } from './types';

/** AI 助手侧边栏面板组件属性 */
interface AssistantSidebarPanelProps {
  /** 助手是否已收缩 */
  isAssistantShrunk: boolean;
  /** 当前选中客户 */
  selectedCustomer: CustomerRecord | null;
  /** 聊天历史记录 */
  chatHistory: ChatHistoryItem[];
  /** 当前聊天输入内容 */
  chatMessage: string;
  /** 更新聊天输入 */
  onChatMessageChange: (value: string) => void;
  /** 提交聊天消息 */
  onChatSubmit: () => void;
  /** 快捷问题点击回调 */
  onQuickPrompt: (prompt: string) => void;
  /** 收缩助手回调 */
  onShrink: () => void;
}

/* ────────────────────────────────────────────────
 * 子组件：单条消息气泡
 * 参照 assistant-ui 的 Thread message 结构：
 * - assistant 消息左对齐，带 avatar
 * - user 消息右对齐，背景高亮
 * ──────────────────────────────────────────────── */
const MessageBubble: React.FC<{ msg: ChatHistoryItem }> = ({ msg }) => {
  const isUser = msg.role === 'user';

  return (
    <div className={`group flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div
        className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full shadow-sm ${
          isUser
            ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white'
            : 'bg-gradient-to-br from-blue-500 to-indigo-600 text-white'
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Bubble */}
      <div
        className={`relative max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'rounded-tr-sm bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-md'
            : 'rounded-tl-sm border border-slate-100 bg-white text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
        }`}
      >
        {msg.content}
      </div>
    </div>
  );
};

/* ────────────────────────────────────────────────
 * 子组件：快捷建议 pills（参照 assistant-ui Suggestions）
 * ──────────────────────────────────────────────── */
const SuggestionPill: React.FC<{
  text: string;
  disabled?: boolean;
  onClick?: () => void;
}> = ({ text, disabled, onClick }) => (
  <button
    disabled={disabled}
    onClick={onClick}
    className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-xs font-medium transition-all duration-200 ${
      disabled
        ? 'cursor-not-allowed border-slate-100/50 bg-slate-50/50 text-slate-400 dark:border-slate-700/50 dark:bg-slate-800/30 dark:text-slate-500'
        : 'border-slate-200 bg-white text-slate-600 hover:-translate-y-0.5 hover:border-blue-300 hover:bg-blue-50/50 hover:text-blue-600 hover:shadow-sm active:translate-y-0 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-blue-500/40 dark:hover:bg-blue-900/20 dark:hover:text-blue-400'
    }`}
  >
    {text}
    {!disabled && <ArrowUp className="h-3 w-3 rotate-45 opacity-0 transition-opacity group-hover:opacity-100" />}
  </button>
);

/* ────────────────────────────────────────────────
 * 子组件：Thread 空状态欢迎视图
 * 参照 assistant-ui ThreadWelcome
 * ──────────────────────────────────────────────── */
const ThreadWelcome: React.FC<{
  selectedCustomer: CustomerRecord | null;
  onQuickPrompt: (prompt: string) => void;
}> = ({ selectedCustomer, onQuickPrompt }) => {
  if (!selectedCustomer) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center px-4 py-8">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-blue-500/10 to-indigo-500/10">
          <Sparkles className="h-6 w-6 text-blue-500" />
        </div>
        <h4 className="mb-1 text-sm font-bold text-slate-800 dark:text-white">你好，我是小智</h4>
        <p className="mb-6 max-w-[85%] text-center text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          请先选择确定客户。我会基于该客户的档案、方案、消费与沟通信息，为你生成卡片化结果。
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          {['选中客户后可查看客户全景', '选中客户后可预测消费趋势', '选中客户后可生成跟进建议', '选中客户后可输出回访话术'].map(
            (text, i) => (
              <SuggestionPill key={i} text={text} disabled />
            ),
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col px-4 py-6">
      {/* 欢迎消息 */}
      <div className="space-y-4">
        <div className="flex gap-3">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-sm">
            <Bot className="h-4 w-4" />
          </div>
          <div className="space-y-3">
            <div className="rounded-2xl rounded-tl-sm border border-slate-100 bg-white px-4 py-3 text-sm leading-relaxed text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
              已同步<span className="font-bold text-blue-600 dark:text-blue-400">{selectedCustomer.name}</span>
              的客户档案、在管方案与消费记录。现在可以直接向我提问。
            </div>
            <div className="rounded-2xl rounded-tl-sm border border-slate-100 bg-white px-4 py-3 text-sm leading-relaxed text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
              你好，我已经准备好围绕
              <span className="font-bold text-blue-600 dark:text-blue-400">{selectedCustomer.name}</span>
              的客户经营进行分析。你可以让我整理客户全景、判断续费概率、预测消耗、提示风险，或输出升单方向。
            </div>
          </div>
        </div>
      </div>

      {/* Suggestions */}
      <div className="mt-6 flex flex-wrap gap-2">
        {[
          `生成${selectedCustomer.name}的客户全景摘要`,
          '查看风险处置建议',
          '预测消费节奏',
          '生成跟进动作与话术',
        ].map((text, i) => (
          <SuggestionPill key={i} text={text} onClick={() => onQuickPrompt(text)} />
        ))}
      </div>
    </div>
  );
};

/* ────────────────────────────────────────────────
 * 子组件：Composer（底部输入区域）
 * 参照 assistant-ui Composer
 * ──────────────────────────────────────────────── */
const ThreadComposer: React.FC<{
  value: string;
  placeholder: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
}> = ({ value, placeholder, onChange, onSubmit, disabled = false }) => {
  const isEmpty = !value.trim();
  const isSubmitDisabled = disabled || isEmpty;

  return (
    <div className="border-t border-slate-100 bg-white/60 p-3 backdrop-blur-sm transition-colors duration-300 dark:border-slate-700/50 dark:bg-slate-800/60">
      <div className="relative flex items-end gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-inner transition-all focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20 dark:border-slate-700 dark:bg-slate-900">
        <input
          type="text"
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              onSubmit();
            }
          }}
          placeholder={placeholder}
          className={`min-h-[20px] flex-1 resize-none border-none bg-transparent px-1 py-0.5 text-sm text-slate-900 placeholder-slate-400 focus:outline-none dark:text-white dark:placeholder-slate-500 ${
            disabled ? 'cursor-not-allowed text-slate-400 dark:text-slate-500' : ''
          }`}
        />
        <button
          onClick={() => onSubmit()}
          disabled={isSubmitDisabled}
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-all duration-200 ${
            isSubmitDisabled
              ? 'cursor-not-allowed bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-600'
              : 'bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-sm hover:scale-105 hover:shadow-md active:scale-95'
          }`}
        >
          <ArrowUp className="h-4 w-4" strokeWidth={3} />
        </button>
      </div>
    </div>
  );
};

/* ────────────────────────────────────────────────────────────────────────────
 * 主组件：AssistantSidebarPanel
 *
 * 整体布局参照 assistant-ui Thread 组件：
 *   ┌──────────────────────────┐
 *   │  Header（标题 + 操作）    │
 *   ├──────────────────────────┤
 *   │                          │
 *   │  Thread Messages         │  ← 滚动区域
 *   │  / Welcome               │
 *   │                          │
 *   ├──────────────────────────┤
 *   │  Follow-up Suggestions   │  ← 仅有消息时显示
 *   ├──────────────────────────┤
 *   │  Composer                │  ← 固定底部
 *   └──────────────────────────┘
 *
 * Props 接口与业务逻辑完全保持不变。
 * ──────────────────────────────────────────────────────────────────────────── */
export const AssistantSidebarPanel: React.FC<AssistantSidebarPanelProps> = ({
  isAssistantShrunk,
  selectedCustomer,
  chatHistory,
  chatMessage,
  onChatMessageChange,
  onChatSubmit,
  onQuickPrompt,
  onShrink,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  // 新消息时自动滚动到底部（参照 assistant-ui 的 useThreadScrollToBottom）
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatHistory]);

  if (isAssistantShrunk) {
    return null;
  }

  const hasMessages = chatHistory.length > 0;

  // 最后一条消息是否为用户（说明 AI 正在"思考"）
  const isThinking = hasMessages && chatHistory[chatHistory.length - 1].role === 'user';

  return (
    <div className="col-span-1 flex min-h-0 flex-col transition-colors duration-300 2xl:col-span-3">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-5 py-4 transition-colors duration-300">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 shadow-sm">
            <Sparkles className="h-3.5 w-3.5 text-white" />
          </div>
          <h3 className="text-sm font-bold text-slate-900 dark:text-white">小智</h3>
          <span className="rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-blue-500 dark:bg-blue-900/30 dark:text-blue-400">
            AI助手
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-green-500 shadow-[0_0_6px_rgba(34,197,94,.4)]" />
          <button
            onClick={onShrink}
            className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300"
            title="收起小助手"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* ── Thread Container ───────────────────────────────────── */}
      <div className="flex flex-1 min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-200/60 bg-white/80 shadow-sm backdrop-blur-md dark:border-slate-700/60 dark:bg-slate-800/80">
        {/* ── Messages / Welcome ────────────────────────────── */}
        <div ref={scrollRef} className="custom-scrollbar flex flex-1 min-h-0 flex-col overflow-y-auto">
          {hasMessages ? (
            <div className="flex flex-col gap-5 p-5">
              {chatHistory.map((msg, idx) => (
                <MessageBubble key={idx} msg={msg} />
              ))}

              {/* AI 思考状态指示器 */}
              {isThinking && (
                <div className="flex gap-3">
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-sm">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm border border-slate-100 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-800">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
                    <span className="text-xs font-medium text-slate-400">小智正在分析...</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <ThreadWelcome selectedCustomer={selectedCustomer} onQuickPrompt={onQuickPrompt} />
          )}
        </div>

        {/* ── Follow-up Suggestions（对话进行中时展示，参照 assistant-ui） ── */}
        {hasMessages && selectedCustomer && !isThinking && (
          <div className="flex flex-wrap gap-1.5 border-t border-slate-50 px-4 py-2.5 dark:border-slate-700/30">
            {[
              `${selectedCustomer.name}的客户全景`,
              '风险处置建议',
              '消费节奏预测',
              '跟进话术',
            ].map((text, i) => (
              <button
                key={i}
                onClick={() => onQuickPrompt(text)}
                className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 transition-colors hover:border-blue-300 hover:bg-blue-50/50 hover:text-blue-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400 dark:hover:border-blue-500/40 dark:hover:text-blue-400"
              >
                {text}
              </button>
            ))}
          </div>
        )}

        {/* ── Composer ──────────────────────────────────────── */}
        <ThreadComposer
          value={chatMessage}
          placeholder={!selectedCustomer ? '输入客户姓名/手机号/身份证号...' : '给小智下达指令...'}
          onChange={onChatMessageChange}
          onSubmit={onChatSubmit}
          disabled={!selectedCustomer}
        />
      </div>
    </div>
  );
};
