// 顶部栏：展示页面标题、通知轮播、导出能力和当前登录用户。
import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Volume2, Zap, Bell, Stethoscope, Activity } from 'lucide-react';
import { NOTICES } from '../data/mockData';
import type { AppPage } from '../navigation';
import { PAGE_TITLES } from '../navigation';

interface HeaderProps {
  currentNoticeIndex: number;
  currentPage: AppPage;
  currentUserName?: string;
}

export function Header({ currentNoticeIndex, currentPage, currentUserName }: HeaderProps) {

  return (
    <header className="h-20 bg-white/40 backdrop-blur-xl border-b border-slate-200/60 flex items-center justify-between px-8 shrink-0 z-20">

      {/* Greeting */}
      <div className="flex items-center mr-8 shrink-0">
        <div className="w-12 h-12 flex items-center justify-center mr-3">
          {currentPage === 'dashboard' ? (
            <div className="w-12 h-12 rounded-2xl bg-brand flex items-center justify-center shadow-lg shadow-brand/20">
              <Activity className="w-6 h-6 text-white" />
            </div>
          ) : (
            <div className="w-12 h-12 rounded-2xl bg-brand flex items-center justify-center shadow-lg shadow-brand/20">
              <Stethoscope className="w-6 h-6 text-white" />
            </div>
          )}
        </div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">
          {PAGE_TITLES[currentPage]}
        </h1>
      </div>

      {/* Notice Carousel */}
      <div className="flex-1 mr-8 flex items-center bg-slate-50/50 rounded-xl px-4 py-2.5 relative overflow-hidden group border border-slate-100">
        <Volume2 className="w-4 h-4 text-brand mr-4 shrink-0 animate-pulse" />

        <div className="flex-1 overflow-hidden relative h-5">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentNoticeIndex}
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: -20, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="absolute inset-0 flex items-center text-sm text-slate-800 truncate cursor-pointer hover:text-brand transition-colors"
            >
              <span className="font-mono text-brand mr-3 tracking-wider bg-brand/10 px-2 py-0.5 rounded text-xs border border-brand/20 flex items-center">
                <Zap className="w-3 h-3 mr-1 text-brand" />
                {NOTICES[currentNoticeIndex].date}
              </span>
              <span className="tracking-wide font-medium">{NOTICES[currentNoticeIndex].title}</span>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      <div className="flex items-center space-x-4 shrink-0">
        {currentUserName ? (
          <div className="hidden rounded-full border border-slate-200/60 bg-white/60 px-4 py-2 text-sm font-medium text-slate-600 shadow-sm xl:block">
            当前用户：{currentUserName}
          </div>
        ) : null}
        <button className="relative p-2 text-slate-400 hover:text-brand hover:bg-brand-light rounded-xl transition-all">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[#D54941] rounded-full animate-pulse shadow-[0_0_8px_rgba(213,73,65,0.6)]"></span>
        </button>
        <div className="text-sm text-slate-600 font-medium bg-white/60 border border-slate-200/60 px-4 py-2 rounded-full shadow-sm">
          2026年3月16日 星期一
        </div>
      </div>
    </header>
  );
}
