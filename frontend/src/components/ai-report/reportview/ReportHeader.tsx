import React from 'react';
import { ChevronLeft, RefreshCw, Sun, Moon } from 'lucide-react';

interface ReportHeaderProps {
  onBack: () => void;
  isDarkMode: boolean;
  onToggleDarkMode: () => void;
  onResetView: () => void;
}

export const ReportHeader: React.FC<ReportHeaderProps> = ({
  onBack,
  isDarkMode,
  onToggleDarkMode,
  onResetView,
}) => {
  return (
    <div className="flex items-center justify-between shrink-0">
      <button
        onClick={onBack}
        className="p-2 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-xl border border-slate-100 dark:border-slate-700 shadow-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors flex items-center space-x-2"
      >
        <ChevronLeft className="w-5 h-5" />
        <span className="text-sm font-bold pr-2">返回</span>
      </button>

      <div className="flex items-center space-x-3">
        <button
          onClick={onResetView}
          className="p-2 bg-white dark:bg-slate-800 text-slate-400 dark:text-slate-500 hover:text-brand dark:hover:text-brand-400 border border-slate-100 dark:border-slate-700 shadow-sm rounded-xl transition-all flex items-center space-x-2"
          title="重置视图"
        >
          <RefreshCw className="w-5 h-5" />
        </button>

        <button
          onClick={onToggleDarkMode}
          className="p-2 bg-white dark:bg-slate-800 text-slate-400 dark:text-slate-500 hover:text-brand dark:hover:text-brand-400 border border-slate-100 dark:border-slate-700 shadow-sm rounded-xl transition-all"
        >
          {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
        </button>
      </div>
    </div>
  );
};
