// 系统宫格：用于渲染一组可点击的业务系统图标入口。
import React from 'react';
import { Layers } from 'lucide-react';
import { System } from '../types';

interface SystemGridProps {
  systems: System[];
  onReceptionClick: () => void;
}

export function SystemGrid({ systems, onReceptionClick }: SystemGridProps) {
  return (
    <section className="xl:col-span-2 bg-white/40 backdrop-blur-xl border border-white/60 rounded-3xl p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-slate-800 flex items-center">
          <Layers className="w-5 h-5 mr-2 text-brand" />
          常用功能
        </h2>
        <span className="text-xs font-medium text-brand bg-brand-light px-2 py-1 rounded-md border border-brand-border">
          AI 已自动授权
        </span>
      </div>
      <div className="grid grid-cols-5 gap-y-6 justify-items-center py-4">
        {systems.map((sys, index) => {
          const isActive = index === 0;
          return (
            <button
              type="button"
              key={sys.id} 
              onClick={() => isActive && onReceptionClick()}
              disabled={!isActive}
              aria-label={isActive ? `打开${sys.name}` : `${sys.name}暂不可用`}
              className="flex flex-col items-center group cursor-pointer disabled:cursor-not-allowed"
            >
              <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-2.5 transition-all duration-300 relative ${
                isActive 
                  ? 'bg-brand text-white shadow-lg shadow-brand/30 scale-110' 
                  : 'bg-white border border-slate-100 text-slate-400 group-hover:border-brand-border group-hover:text-brand group-hover:shadow-md'
              }`}>
                <sys.icon className={`w-6 h-6 ${isActive ? 'text-white' : sys.color}`} />
                {sys.count > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full border-2 border-white">
                    {sys.count}
                  </span>
                )}
              </div>
              <span className={`text-[13px] font-bold transition-colors ${isActive ? 'text-slate-900' : 'text-slate-500 group-hover:text-slate-900'}`}>
                {sys.name}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
