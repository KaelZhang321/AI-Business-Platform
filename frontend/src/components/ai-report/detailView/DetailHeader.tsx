import React from 'react';
import { ArrowLeft, Moon, Sun } from 'lucide-react';

interface DetailHeaderProps {
  onBack: () => void;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
}

export const DetailHeader: React.FC<DetailHeaderProps> = ({ onBack, isDarkMode, onToggleDarkMode }) => {
  return (
    <div className="flex items-center justify-between">
      <div>
        <div className="flex items-center space-x-3">
          <button
            onClick={onBack}
            className="p-2 hover:bg-slate-200 dark:hover:bg-slate-800 rounded-lg transition-colors text-slate-500 dark:text-slate-400"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">AI报告对比</h2>
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 ml-11">支持按客户姓名搜索，并进入客户近三年体检报告对比详情。</p>
      </div>

      <div className="flex items-center space-x-2 text-sm">
        <button
          onClick={onToggleDarkMode}
          className="relative p-2 text-slate-400 dark:text-slate-500 hover:text-brand dark:hover:text-brand-400 hover:bg-brand-light dark:hover:bg-brand-900/30 rounded-xl transition-all mr-2"
        >
          {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>
        <span className="bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-400 px-3 py-1 rounded-full font-medium">数据范围 2024-2026</span>
        <span className="bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-3 py-1 rounded-full font-medium">最近同步 2026-03-31 09:40</span>
        <span className="bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 px-3 py-1 rounded-full font-medium">管理员 张永亮</span>
      </div>
    </div>
  );
};
