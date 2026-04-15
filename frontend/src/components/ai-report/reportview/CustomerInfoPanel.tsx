import React from 'react';
import { User, Brain, Activity, Bot, Send } from 'lucide-react';
import type { Message } from './types';

interface CustomerInfoPanelProps {
  customer: any;
  messages: Message[];
  inputValue: string;
  isTyping: boolean;
  focusedMetricName: string | null;
  chatEndRef: React.RefObject<HTMLDivElement | null>;
  onInputChange: (value: string) => void;
  onSubmit: (e?: React.FormEvent) => void;
  onResetFocus: () => void;
}

export const CustomerInfoPanel: React.FC<CustomerInfoPanelProps> = ({
  customer,
  messages,
  inputValue,
  isTyping,
  focusedMetricName,
  chatEndRef,
  onInputChange,
  onSubmit,
  onResetFocus,
}) => {
  return (
    <div className="w-full lg:w-1/3 flex flex-col min-h-0 overflow-hidden shrink-0">
      <div className="bg-white/80 backdrop-blur-xl dark:bg-slate-800 rounded-2xl border border-white/50 dark:border-slate-700 shadow-[0_8px_30px_rgb(0,0,0,0.04)] flex flex-col h-full overflow-hidden">
        <div className="p-6 border-b border-slate-50 dark:border-slate-700/50">
          <div className="flex items-center space-x-4 mb-6">
            <div className="w-16 h-16 rounded-2xl bg-brand/10 flex items-center justify-center shrink-0">
              <User className="w-8 h-8 text-brand" />
            </div>
            <div className="space-y-1">
              <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{customer.name || '王五'}</h2>
              <div className="flex items-center space-x-2 text-sm text-slate-500 dark:text-slate-400">
                <span>{customer.gender || '男'}</span>
                <span>•</span>
                <span>{customer.age || '51'}岁</span>
              </div>
              <div className="text-xs text-slate-400 font-mono">HZ-2026-0318-078</div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="px-3 py-2.5 bg-blue-50/50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-xl text-xs font-bold text-center border border-blue-100/50 dark:border-blue-800/30">
              最近体检 2026-03-18
            </div>
            <div className="px-3 py-2.5 bg-emerald-50/50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 rounded-xl text-xs font-bold text-center border border-emerald-100/50 dark:border-emerald-800/30">
              近三年报告完整
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar flex flex-col">
          <div className="space-y-3 shrink-0">
            <div className="flex items-center space-x-2 text-brand">
              <Brain className="w-5 h-5" />
              <span className="text-sm font-bold uppercase tracking-wider">AI 综合结论分析</span>
            </div>
            <div className="relative p-5 bg-gradient-to-br from-blue-50/50 to-indigo-50/30 dark:from-slate-800 dark:to-slate-900/50 rounded-2xl border border-blue-100/50 dark:border-slate-700 shadow-sm">
              <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed font-medium italic relative z-10">
                "较 2024 年，空腹血糖、ALT、尿酸持续上升，2026 年已有 6 项指标异常，建议优先关注代谢与肝功能变化，并在 30 天内进行复查。"
              </p>
              <div className="absolute top-2 right-3 text-4xl text-slate-200 dark:text-slate-800 font-serif opacity-50">"</div>
            </div>
          </div>

          <div className="space-y-4 shrink-0">
            <div className="flex items-center space-x-2 text-slate-700 dark:text-slate-200">
              <Activity className="w-5 h-5" />
              <span className="text-sm font-bold uppercase tracking-wider">健康数据概览</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="group text-center px-3 py-3 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 hover:border-rose-200 dark:hover:border-rose-900/50 transition-all shadow-[0_2px_10px_rgb(0,0,0,0.02)] hover:shadow-[0_8px_20px_rgb(244,63,94,0.08)]">
                <div className="flex items-center justify-center space-x-1 mb-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.4)]"></div>
                  <span className="text-[9px] text-slate-400 uppercase font-bold tracking-widest">异常指标</span>
                </div>
                <div className="text-2xl font-black text-slate-900 dark:text-white group-hover:scale-110 transition-transform">6</div>
              </div>
              <div className="group text-center px-3 py-3 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 hover:border-amber-200 dark:hover:border-amber-900/50 transition-all shadow-[0_2px_10px_rgb(0,0,0,0.02)] hover:shadow-[0_8px_20px_rgb(245,158,11,0.08)]">
                <div className="flex items-center justify-center space-x-1 mb-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]"></div>
                  <span className="text-[9px] text-slate-400 uppercase font-bold tracking-widest">持续上升</span>
                </div>
                <div className="text-2xl font-black text-slate-900 dark:text-white group-hover:scale-110 transition-transform">5</div>
              </div>
            </div>
          </div>

          <div className="flex flex-col flex-1 min-h-[300px] bg-white dark:bg-slate-900/30 rounded-2xl border border-slate-100 dark:border-slate-700 overflow-hidden shadow-sm">
            <div className="p-3 border-b border-slate-100 dark:border-slate-700 bg-white/50 dark:bg-slate-800/50 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <div className="w-6 h-6 rounded-lg bg-brand flex items-center justify-center">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <span className="text-xs font-bold text-slate-700 dark:text-slate-200">AI 实时咨询</span>
              </div>
              {focusedMetricName && (
                <button onClick={onResetFocus} className="text-[10px] text-brand hover:underline font-bold">
                  重置视图
                </button>
              )}
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar">
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div
                    className={`max-w-[85%] p-3 rounded-2xl text-xs leading-relaxed ${
                      msg.role === 'user'
                        ? 'bg-gradient-to-br from-brand to-brand-600 text-white rounded-tr-none shadow-[0_4px_15px_rgba(var(--brand-rgb),0.2)]'
                        : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-100 dark:border-slate-700 rounded-tl-none shadow-[0_2px_10px_rgb(0,0,0,0.03)]'
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
              {isTyping && (
                <div className="flex justify-start">
                  <div className="bg-white dark:bg-slate-800 p-3 rounded-2xl rounded-tl-none border border-slate-100 dark:border-slate-700 shadow-[0_2px_10px_rgb(0,0,0,0.03)]">
                    <div className="flex space-x-1">
                      <div className="w-1 h-1 bg-slate-300 rounded-full animate-bounce"></div>
                      <div className="w-1 h-1 bg-slate-300 rounded-full animate-bounce [animation-delay:0.2s]"></div>
                      <div className="w-1 h-1 bg-slate-300 rounded-full animate-bounce [animation-delay:0.4s]"></div>
                    </div>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <form onSubmit={onSubmit} className="p-2 bg-white dark:bg-slate-800 border-t border-slate-100 dark:border-slate-700 flex items-center space-x-2">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => onInputChange(e.target.value)}
                placeholder="咨询指标，如：血糖..."
                className="flex-1 bg-slate-50/50 dark:bg-slate-900 border border-slate-100 dark:border-slate-700 shadow-inner rounded-xl px-4 py-2.5 text-xs focus:ring-2 focus:ring-brand/20 focus:border-brand outline-none dark:text-white transition-all"
              />
              <button type="submit" disabled={isTyping} className="p-2 bg-brand text-white rounded-xl hover:bg-brand-600 transition-colors disabled:opacity-50">
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
