// AI 助手面板：负责展示消息、推荐问题和悬浮聊天入口。
import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Sparkles, Send, MessageSquare, X } from 'lucide-react';

/** AI 助手聊天消息结构 */
interface Message {
  /** 消息唯一 ID */
  id: string;
  /** 消息角色*/
  role: 'ai' | 'user';
  /** 消息文本 */
  content: string;
}

/** AI 助手面板组件属性 */
interface AIAssistantProps {
  /** 对话消息列表 */
  messages: Message[];
  /** 聊天输入框内容 */
  chatInput: string;
  /** 设置聊天输入 */
  setChatInput: (val: string) => void;
  /** 发送消息回调 */
  handleSendMessage: (overrideText?: string) => void;
  /** 悬浮助手是否展开 */
  isAIOpen: boolean;
  /** 设置助手展开状态 */
  setIsAIOpen: (val: boolean) => void;
}

/** AI 助手面板组件：展示对话消息、推荐问题和悬浮聊天入口 */
export function AIAssistant({
  messages,
  chatInput,
  setChatInput,
  handleSendMessage,
  isAIOpen,
  setIsAIOpen
}: AIAssistantProps) {
  /** 推荐问题快捷入口列表 */
  const suggestedPrompts = [
    { id: 'inventory', text: '帮我查询王先生在云仓的剩余库存', tag: '客户云仓' },
    { id: 'drivers', text: '今天下午3点到5点，有哪些空闲的专车司机？', tag: '约车调度' },
    { id: 'report', text: '生成一份本周高端客户接待效能报告', tag: '数据分析' },
    { id: 'policy', text: '查看最新的合规审查红头文件', tag: '政策中心' },
  ] as const;

  /** 渲染消息内容：支持标题行、普通文本和按钮行的分行解析 */
  const renderMessageContent = (content: string) => {
    return content.split('\n').map((line) => (
      <React.Fragment key={`${content}-${line}`}>
        {line.startsWith('📊') || line.startsWith('🚗') ? (
          <strong className="block mb-2 text-slate-900 text-base font-bold">{line}</strong>
        ) : line.includes('[点击一键派单') ? (
          <button
            type="button"
            className="mt-3 w-full py-2.5 bg-brand-light text-brand font-bold rounded-xl hover:bg-brand-border transition-colors border border-brand-border shadow-sm"
          >
            {line}
          </button>
        ) : (
          <span className="block">{line}</span>
        )}
      </React.Fragment>
    ));
  };

  /** 推荐问题列表子组件（支持紧凑和展开两种模式） */
  const SuggestedQuestions = ({ isSmall = false }: { isSmall?: boolean }) => (
    <div className={`${isSmall ? 'shrink-0 pt-3 border-t border-slate-200/60' : 'flex-1 overflow-y-auto pr-2 custom-scrollbar'}`}>
      <p className={`font-medium text-slate-500 mb-4 ${isSmall ? 'text-xs mb-2' : 'text-sm'}`}>
        {isSmall ? '猜您想问' : '您可以尝试问我以下问题'}
      </p>
      <div className={`${isSmall ? 'flex flex-wrap gap-2' : 'flex flex-col space-y-3'}`}>
        {suggestedPrompts.map((prompt) => (
          <button
            key={prompt.id}
            type="button"
            onClick={() => handleSendMessage(prompt.text)}
            className={`${isSmall
                ? 'bg-white border border-slate-200 hover:border-brand-border text-slate-600 hover:text-brand text-xs px-3 py-1.5 rounded-full transition-colors truncate max-w-[200px]'
                : 'bg-white hover:bg-brand-light/50 cursor-pointer p-5 rounded-2xl transition-all shadow-sm flex flex-col space-y-3 border border-transparent hover:border-brand-border text-left'
              }`}
            title={prompt.text}
          >
            <span className={`${isSmall ? '' : 'text-sm font-bold text-slate-700'}`}>
              {isSmall ? prompt.text : `"${prompt.text}"`}
            </span>
            {!isSmall && <span className="text-xs text-slate-400">{prompt.tag}</span>}
          </button>
        ))}
      </div>
    </div>
  );

  /** 聊天输入框子组件（带渐变发光边框动画） */
  const ChatInput = ({ isFloating = false }: { isFloating?: boolean }) => (
    <div className={`relative group w-full shrink-0 ${isFloating ? '' : 'mb-6'}`}>
      <motion.div
        className="absolute -inset-0.5 rounded-full opacity-30 blur-md group-focus-within:opacity-60 transition-opacity duration-500"
        style={{
          backgroundImage: 'linear-gradient(to right, #3b82f6, #60a5fa, #93c5fd, #2563eb, #3b82f6)',
          backgroundSize: '200% 200%'
        }}
        animate={{ backgroundPosition: ['0% 50%', '100% 50%'] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
      />

      <motion.div
        className="absolute inset-0 rounded-full opacity-50 group-focus-within:opacity-100 transition-opacity duration-500"
        style={{
          backgroundImage: 'linear-gradient(to right, #3b82f6, #60a5fa, #93c5fd, #2563eb, #3b82f6)',
          backgroundSize: '200% 200%'
        }}
        animate={{ backgroundPosition: ['0% 50%', '100% 50%'] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
      />

      <div className="relative bg-white rounded-full m-[1.5px] flex items-center shadow-sm border border-slate-100">
        <input
          type="text"
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
          placeholder="请告诉我需要协助的事情..."
          className={`w-full bg-transparent rounded-full pl-6 pr-28 py-4 text-sm focus:outline-none text-slate-800 placeholder:text-slate-400 relative z-10 ${isFloating ? 'py-3.5' : ''}`}
        />
        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center space-x-3 z-10">
          <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{chatInput.length}/100</span>
          <button
            type="button"
            onClick={() => chatInput.trim() && handleSendMessage()}
            disabled={!chatInput.trim()}
            aria-label="发送消息"
            className="w-10 h-10 flex items-center justify-center bg-brand hover:bg-brand-hover rounded-full text-white shadow-lg shadow-brand/30 transition-all hover:scale-105 active:scale-95"
          >
            <Send className="w-4 h-4 ml-0.5" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div>
      <section className="xl:col-span-1 flex flex-col bg-slate-50/80 backdrop-blur-xl border border-white/60 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] h-[600px]">
        {messages.length <= 1 && <ChatInput />}

        <div className="w-full flex-1 flex flex-col min-h-0">
          {messages.length > 1 ? (
            <>
              <div className="flex-1 overflow-y-auto pr-2 space-y-4 mb-4 custom-scrollbar">
                {messages.slice(1).map((msg) => (
                  <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {msg.role === 'ai' && (
                      <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center shrink-0 mr-2">
                        <Sparkles className="w-4 h-4 text-brand" />
                      </div>
                    )}
                    <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${msg.role === 'user'
                        ? 'bg-blue-500 text-white rounded-tr-sm'
                        : 'bg-white border border-slate-100 text-slate-700 rounded-tl-sm'
                      }`}>
                      {renderMessageContent(msg.content)}
                    </div>
                  </div>
                ))}
              </div>
              <ChatInput />
              <SuggestedQuestions isSmall />
            </>
          ) : (
            <SuggestedQuestions />
          )}
        </div>
      </section>

      {/* Floating AI Assistant */}
      <div className="fixed bottom-8 right-8 z-50 flex flex-col items-end">
        <AnimatePresence>
          {isAIOpen && (
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="bg-white w-[400px] h-[550px] rounded-3xl shadow-2xl border border-slate-200/60 mb-4 flex flex-col overflow-hidden"
            >
              <div className="h-16 bg-gradient-to-r from-brand to-brand-hover px-5 flex items-center justify-between shrink-0 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
                <div className="flex items-center text-white relative z-10">
                  <div className="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center mr-3 backdrop-blur-sm">
                    <Sparkles className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="font-bold block text-sm">AI 智能助手</span>
                    <span className="text-[10px] text-cyan-100">Lizi Kar Workspace</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setIsAIOpen(false)}
                  className="w-8 h-8 flex items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20 transition-colors relative z-10"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-5 space-y-5 bg-slate-50/50">
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {msg.role === 'ai' && (
                      <div className="w-8 h-8 rounded-full bg-brand flex items-center justify-center shrink-0 mr-2 shadow-sm">
                        <Sparkles className="w-4 h-4 text-white" />
                      </div>
                    )}
                    <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${msg.role === 'user'
                        ? 'bg-gradient-to-br from-cyan-500 to-blue-600 text-white rounded-tr-sm'
                        : 'bg-white border border-slate-100 text-slate-700 rounded-tl-sm'
                      }`}>
                      {renderMessageContent(msg.content)}
                    </div>
                  </div>
                ))}
              </div>

              <div className="p-4 bg-white border-t border-slate-100 shrink-0">
                <div className="relative flex items-center">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                    placeholder="询问跨系统数据或SOP..."
                    className="w-full bg-slate-100/80 border-transparent rounded-2xl pl-4 pr-12 py-3.5 text-sm focus:bg-white focus:border-brand focus:ring-4 focus:ring-brand/10 transition-all outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => handleSendMessage()}
                    disabled={!chatInput.trim()}
                    aria-label="发送消息"
                    className="absolute right-2 w-9 h-9 flex items-center justify-center bg-gradient-to-r from-brand to-brand-hover text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-md hover:shadow-brand/20 transition-all"
                  >
                    <Send className="w-4 h-4 ml-0.5" />
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <button
          type="button"
          onClick={() => setIsAIOpen(!isAIOpen)}
          aria-label={isAIOpen ? '关闭 AI 助手' : '打开 AI 助手'}
          className="w-14 h-14 bg-gradient-to-r from-brand to-brand-hover text-white rounded-full shadow-lg shadow-brand/30 flex items-center justify-center transition-transform hover:scale-105 active:scale-95 relative group"
        >
          <MessageSquare className="w-6 h-6 group-hover:scale-110 transition-transform" />
          {!isAIOpen && (
            <span className="absolute top-0 right-0 w-3.5 h-3.5 bg-[#D54941] border-2 border-white rounded-full shadow-sm"></span>
          )}
        </button>
      </div>
    </div>
  );
}
