// 常用功能区：展示首页中的快捷入口与业务系统按钮。
import React from 'react';
import { Layers } from 'lucide-react';
import { SYSTEMS } from '../data/mockData';

interface CommonFunctionsProps {
  setIsReceptionModalOpen: (open: boolean) => void;
}

export function CommonFunctions({ setIsReceptionModalOpen }: CommonFunctionsProps) {
  return (
    <section className="xl:col-span-2 bg-white/40 backdrop-blur-xl border border-white/60 rounded-[32px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)] flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-bold text-slate-900 flex items-center">
          <Layers className="w-5 h-5 mr-2 text-brand" />
          常用功能
        </h2>
        <span className="text-xs font-bold text-brand bg-brand-light px-2.5 py-1 rounded-lg border border-brand-border uppercase tracking-wider">
          AI 已自动授权
        </span>
      </div>
      <div className="grid grid-cols-5 gap-y-6 justify-items-center py-4">
        {SYSTEMS.map((sys, index) => {
          const isActive = index === 0;
          return (
            <div 
              key={sys.id} 
              onClick={() => {
                if (sys.name === '到院接待') {
                  setIsReceptionModalOpen(true);
                }
              }}
              className={`flex flex-col items-center justify-center cursor-pointer group transition-all duration-300 ${
              isActive 
                ? 'w-[88px] h-[104px] bg-gradient-to-b from-brand to-brand-hover rounded-[24px] shadow-[0_12px_30px_-8px_rgba(59,130,246,0.6)] hover:-translate-y-1.5' 
                : 'w-[76px] h-[104px] hover:-translate-y-1.5'
            }`}>
              <div className={`w-[48px] h-[48px] rounded-2xl flex items-center justify-center mb-3 transition-all duration-300 relative ${
                isActive 
                  ? 'bg-white shadow-sm' 
                  : 'bg-white shadow-[0_8px_24px_-6px_rgba(0,0,0,0.06)] group-hover:shadow-[0_12px_28px_-6px_rgba(0,0,0,0.12)]'
              }`}>
                {sys.count > 0 && (
                  <span className="absolute -top-1.5 -right-1.5 bg-gradient-to-r from-[#D54941] to-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full shadow-md z-20 border-2 border-white">
                    {sys.count}
                  </span>
                )}
                <sys.icon 
                  className={`w-[24px] h-[24px] ${sys.color} transition-transform duration-300 group-hover:scale-110`} 
                  strokeWidth={2.5}
                />
              </div>
              <span className={`text-sm font-bold text-center whitespace-nowrap transition-colors ${
                isActive ? 'text-white' : 'text-slate-600 group-hover:text-slate-900'
              }`}>
                {sys.name}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
