// 风险看板：展示首页中的关键风险提醒和风险状态概览。
import React from 'react';
import { ShieldAlert, AlertTriangle, Info, CheckCircle2, AlertCircle, X, ExternalLink } from 'lucide-react';
import { RISKS } from '../data/mockData';

/** 风险看板组件：展示首页中的关键风险提醒和风险状态概览 */
export function RiskSection() {
  return (
    <section className="xl:col-span-1 bg-white/40 backdrop-blur-xl border border-white/60 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex flex-col dark:bg-slate-900/60 dark:border-slate-700/60">
      <div className="flex items-center justify-between mb-6 border-b border-slate-100 pb-4 dark:border-slate-700">
        <h2 className="text-lg font-bold flex items-center text-slate-900 dark:text-slate-100">
          <ShieldAlert className="w-5 h-5 mr-2 text-orange-500" />
          AI风险预警
          <span className="ml-2 bg-orange-500 text-white text-[10px] px-1.5 py-0.5 rounded-full leading-none shadow-sm">4</span>
        </h2>
      </div>
      
      <div className="flex-1 flex flex-col space-y-4 overflow-y-auto custom-scrollbar pr-2">
        {RISKS.map(risk => {
          const isCompleted = risk.completed;

          return (
            <div key={risk.id} className={`group relative bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-md transition-all p-5 flex items-start dark:bg-slate-900 dark:border-slate-700 ${isCompleted ? 'opacity-60 grayscale' : ''}`}>
              <div className={`absolute left-0 top-0 bottom-0 w-32 bg-gradient-to-r pointer-events-none rounded-l-2xl ${
                risk.theme === 'red' ? 'from-red-50/50' : 
                risk.theme === 'blue' ? 'from-blue-50/50' : 
                risk.theme === 'green' ? 'from-brand-light/50' : 'from-amber-50/50'
              } to-transparent`}></div>

              <div className="relative z-10 flex items-start w-full">
                <div className={`w-10 h-10 rounded-2xl flex items-center justify-center shrink-0 mr-4 shadow-sm ${
                  risk.theme === 'red' ? 'bg-red-50' : 
                  risk.theme === 'blue' ? 'bg-blue-50' : 
                  risk.theme === 'green' ? 'bg-brand-light' : 'bg-amber-50'
                }`}>
                  {risk.theme === 'red' && <AlertTriangle className="w-5 h-5 text-red-500" />}
                  {risk.theme === 'blue' && <Info className="w-5 h-5 text-blue-500" />}
                  {risk.theme === 'green' && <CheckCircle2 className="w-5 h-5 text-brand" />}
                  {risk.theme === 'yellow' && <AlertCircle className="w-5 h-5 text-amber-500" />}
                </div>

                <div className="flex-1 pr-6">
                  <h3 className="text-base font-bold text-slate-900 mb-1 leading-tight dark:text-slate-100">
                    {risk.title}
                  </h3>
                  <p className="text-sm text-slate-500 leading-relaxed mb-2 dark:text-slate-400">
                    {risk.description}
                  </p>
                  {risk.link && (
                    <button className="flex items-center text-xs font-bold text-slate-800 hover:text-brand transition-colors dark:text-slate-200">
                      {risk.link}
                      <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
                    </button>
                  )}
                </div>

                <button className="absolute top-0 right-0 p-1 text-slate-300 hover:text-slate-500 transition-colors dark:text-slate-500 dark:hover:text-slate-300">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
