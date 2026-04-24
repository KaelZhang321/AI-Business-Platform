import React from 'react';
import { LayoutGrid, List, Search } from 'lucide-react';
import type { DetailViewMode } from './types';

interface FilterToolbarProps {
  viewMode: DetailViewMode;
  searchTerm: string;
  onSearchTermChange: (value: string) => void;
  onViewModeChange: (mode: DetailViewMode) => void;
}

export const FilterToolbar: React.FC<FilterToolbarProps> = ({
  viewMode,
  searchTerm,
  onSearchTermChange,
  onViewModeChange,
}) => {
  return (
    <div className="mb-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold text-slate-900 dark:text-white">客户检索与筛选</h3>
        <div className="flex items-center space-x-4">
          <div className="flex bg-slate-100 dark:bg-slate-900 p-1 rounded-xl">
            <button
              onClick={() => onViewModeChange('card')}
              className={`p-1.5 rounded-lg transition-all ${viewMode === 'card' ? 'bg-white dark:bg-slate-800 text-brand shadow-sm' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'}`}
              title="卡片展示"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              onClick={() => onViewModeChange('list')}
              className={`p-1.5 rounded-lg transition-all ${viewMode === 'list' ? 'bg-white dark:bg-slate-800 text-brand shadow-sm' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'}`}
              title="列表展示"
            >
              <List className="w-4 h-4" />
            </button>
          </div>

          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 w-4 h-4" />
            <input
              type="text"
              placeholder="输入客户姓名搜索客户"
              value={searchTerm}
              onChange={(e) => onSearchTermChange(e.target.value)}
              className="pl-9 pr-4 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 w-64 text-slate-900 dark:text-slate-100 transition-colors"
            />
          </div>

          {/* <button className="px-4 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
            高级筛选
          </button> */}
          <button className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors">导出名单</button>
        </div>
      </div>
    </div>
  );
};
