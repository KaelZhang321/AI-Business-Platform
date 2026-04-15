import React from 'react';
import type { CustomerRecord } from './types';

interface AnimatedRowProps {
  customer: CustomerRecord;
  onViewDetails: (customer: CustomerRecord) => void;
}

export const AnimatedRow: React.FC<AnimatedRowProps> = ({ customer, onViewDetails }) => {
  return (
    <div className="grid grid-cols-12 gap-4 items-center border-b border-slate-50 dark:border-slate-800/50 last:border-none hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors py-4 px-2 rounded-lg">
      <div className="col-span-2 font-bold text-slate-800 dark:text-slate-200">{customer.name}</div>
      <div className="col-span-2 text-slate-600 dark:text-slate-400">
        {customer.gender} / {customer.age}岁
      </div>
      <div className="col-span-2 text-slate-600 dark:text-slate-400">{customer.lastCheckDate}</div>
      <div className="col-span-2">
        <span
          className={`px-3 py-1 rounded-full text-xs font-medium ${
            customer.aiJudgment === '重点关注'
              ? 'bg-rose-50 text-rose-500 dark:bg-rose-500/10 dark:text-rose-400'
              : customer.aiJudgment === '持续观察'
                ? 'bg-amber-50 text-amber-500 dark:bg-amber-500/10 dark:text-amber-400'
                : customer.aiJudgment === '优先复查'
                  ? 'bg-blue-50 text-blue-500 dark:bg-blue-500/10 dark:text-blue-400'
                  : 'bg-emerald-50 text-emerald-500 dark:bg-emerald-500/10 dark:text-emerald-400'
          }`}
        >
          {customer.aiJudgment}
        </span>
      </div>
      <div className="col-span-3 text-slate-600 dark:text-slate-400 truncate">{customer.keyAbnormal}</div>
      <div className="col-span-1 text-center">
        <button
          onClick={() => onViewDetails(customer)}
          className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700 transition-colors"
        >
          查看详情
        </button>
      </div>
    </div>
  );
};
