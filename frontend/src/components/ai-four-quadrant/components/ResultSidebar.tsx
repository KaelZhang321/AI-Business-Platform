import { Send, Sparkles } from 'lucide-react'
import type { AnalysisResultSnapshot, ChatMessage } from '../types'

interface ResultSidebarProps {
  analysis: AnalysisResultSnapshot
  chatMessages: ChatMessage[]
  chatInput: string
  onChatInputChange: (value: string) => void
  onSendMessage: () => void
}

export const ResultSidebar = ({
  analysis,
  chatMessages,
  chatInput,
  onChatInputChange,
  onSendMessage,
}: ResultSidebarProps) => {
  return (
    <div className="flex flex-col h-full">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-2">报告与统计</h2>
      </div>

      <div className="space-y-4 overflow-y-auto pr-2 custom-scrollbar shrink-0">
        <div className="p-4 bg-white dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-700">
          <p className="text-xs font-bold text-brand mb-2">客户</p>
          <p className="text-sm font-bold text-slate-900 dark:text-white">{analysis.clientInfo}</p>
        </div>
        <div className="p-4 bg-white dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-700">
          <p className="text-xs font-bold text-brand mb-2">体检报告</p>
          <p className="text-sm font-bold text-slate-900 dark:text-white">{analysis.reportInfo}</p>
        </div>
        <div className="p-4 bg-white dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-700">
          <p className="text-xs font-bold text-brand mb-2">AI结论</p>
          <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{analysis.conclusion}</p>
        </div>
      </div>

      <div className="mt-6 bg-white dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden flex flex-col flex-1">
        <div className="flex border-b border-slate-200 dark:border-slate-700">
          <div className="flex-1 py-2 text-xs font-bold text-brand bg-brand/5 border-b-2 border-brand text-center">AI小助手</div>
        </div>
        <div className="p-4 flex-1 flex flex-col min-h-0">
          <div className="space-y-4 flex-1 overflow-y-auto mb-4 custom-scrollbar">
            {chatMessages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.sender === 'ai' && (
                  <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0 mr-2 mt-0.5 transition-colors duration-300">
                    <Sparkles className="w-3 h-3 text-brand dark:text-brand-400" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs leading-relaxed shadow-sm transition-colors duration-300 ${
                    msg.sender === 'user'
                      ? 'bg-blue-500 text-white rounded-tr-sm'
                      : 'bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-tl-sm'
                  }`}
                >
                  {msg.text}
                </div>
              </div>
            ))}
          </div>
          <div className="relative flex items-center">
            <input
              type="text"
              placeholder="输入备注或调整指令"
              value={chatInput}
              onChange={(e) => onChatInputChange(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && onSendMessage()}
              className="w-full bg-slate-100/80 dark:bg-slate-900/80 border-transparent rounded-2xl pl-4 pr-12 py-2.5 text-xs focus:bg-white dark:focus:bg-slate-800 focus:border-brand dark:focus:border-brand-500 focus:ring-2 focus:ring-brand/10 dark:focus:ring-brand/20 transition-all outline-none text-slate-800 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500"
            />
            <button
              onClick={onSendMessage}
              disabled={!chatInput.trim()}
              className="absolute right-1.5 w-7 h-7 flex items-center justify-center bg-gradient-to-r from-brand to-brand-hover text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-md hover:shadow-brand/20 transition-all cursor-target"
            >
              <Send className="w-3.5 h-3.5 ml-0.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
