import React from 'react';
import { Save, Search } from 'lucide-react';

interface WorkbenchHeaderSectionProps {
  hasCards: boolean;
  isLayoutSaved: boolean;
  onSaveLayout: () => void;
  onOpenCustomerModal: () => void;
}

export const WorkbenchHeaderSection: React.FC<WorkbenchHeaderSectionProps> = ({
  hasCards,
  isLayoutSaved,
  onSaveLayout,
  onOpenCustomerModal,
}) => {
  return (
    <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 transition-colors duration-300 dark:text-white">我的AI工作台</h2>
        <p className="text-sm text-slate-500 transition-colors duration-300 dark:text-slate-400">
          AI业务中台 | 仅展示我负责的客户与客户信息
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 xl:justify-end">
        {hasCards && (
          <button
            onClick={onSaveLayout}
            className={`rounded-full px-4 py-2 transition-colors flex items-center space-x-2 ${
              isLayoutSaved
                ? 'bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-blue-50 text-blue-600 hover:bg-blue-100 dark:bg-blue-900/30 dark:text-blue-400 dark:hover:bg-blue-900/50'
            }`}
          >
            <Save className="h-4 w-4" />
            <span className="text-sm font-medium">{isLayoutSaved ? '已保存布局' : '收藏当前布局'}</span>
          </button>
        )}

        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="搜索客户姓名/ID..."
            onClick={onOpenCustomerModal}
            readOnly
            className="w-full cursor-pointer rounded-3xl border border-slate-200 bg-white py-2 pl-9 pr-4 text-sm text-slate-900 outline-none transition-colors duration-300 placeholder-slate-400 focus:ring-2 focus:ring-brand dark:border-slate-700 dark:bg-slate-800 dark:text-white sm:w-64"
          />
        </div>

        <button className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white p-2 transition-colors duration-300 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700">
          <span className="text-sm font-medium text-slate-600 dark:text-slate-300">筛</span>
        </button>
      </div>
    </div>
  );
};
