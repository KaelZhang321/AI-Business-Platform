import React from 'react';
import type { CustomerRecord } from './types';

/** 客户行组件属性 */
interface CustomerRowProps {
  /** 客户记录数据 */
  customer: CustomerRecord;
  /** 查看详情回调 */
  onViewDetails: (customer: CustomerRecord) => void;
}

/** 客户行组件：在客户列表中展示单条客户的姓名、性别年龄、体检日期和摘要 */
export const CustomerRow: React.FC<CustomerRowProps> = ({ customer, onViewDetails }) => (
  <div className="grid grid-cols-12 items-center gap-4 rounded-lg border-b border-slate-50 px-2 py-4 transition-colors last:border-none hover:bg-slate-50/50 dark:border-slate-800/50 dark:hover:bg-slate-800/50">
    <div className="col-span-2 font-bold text-slate-800 dark:text-slate-200">{customer.name}</div>
    <div className="col-span-2 text-slate-600 dark:text-slate-400">
      {customer.gender ?? '--'} / {customer.age ?? '--'}岁
    </div>
    <div className="col-span-2 text-slate-600 dark:text-slate-400">{customer.lastCheckDate || '--'}</div>
    {/* <div className="col-span-2">
      <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-600 dark:bg-blue-500/10 dark:text-blue-400">
        {customer.aiJudgment || '待评估'}
      </span>
    </div> */}
    <div className="col-span-5 truncate text-slate-600 dark:text-slate-400">
      {customer.keyAbnormal || customer.phone || customer.idCard || '--'}
    </div>
    <div className="col-span-1 text-center">
      <button
        onClick={() => onViewDetails(customer)}
        className="rounded-lg bg-blue-600 px-4 py-1.5 text-xs text-white transition-colors hover:bg-blue-700"
      >
        进入
      </button>
    </div>
  </div>
);
