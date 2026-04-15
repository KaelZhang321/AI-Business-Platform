import React from 'react';
import { AnimatedList } from './AnimatedList';
import { AnimatedRow } from './AnimatedRow';
import { ReflectiveCard } from './ReflectiveCard';
import type { CustomerRecord, DetailViewMode } from './types';

interface CustomerResultsProps {
  viewMode: DetailViewMode;
  customers: CustomerRecord[];
  onViewDetails: (customer: CustomerRecord) => void;
}

export const CustomerResults: React.FC<CustomerResultsProps> = ({ viewMode, customers, onViewDetails }) => {
  if (viewMode === 'list') {
    return (
      <>
        <div className="grid grid-cols-12 gap-4 text-slate-400 dark:text-slate-500 text-xs uppercase tracking-wider border-b border-slate-100 dark:border-slate-700 py-4 px-2 font-semibold">
          <div className="col-span-2 text-left">客户姓名</div>
          <div className="col-span-2 text-left">性别 / 年龄</div>
          <div className="col-span-2 text-left">最近体检日期</div>
          <div className="col-span-2 text-left">AI综合判断</div>
          <div className="col-span-3 text-left">关键异常指标</div>
          <div className="col-span-1 text-center">操作</div>
        </div>

        <div className="relative h-[600px]">
          <div className="absolute top-0 left-0 right-0 h-8 bg-gradient-to-b from-white dark:from-slate-800 to-transparent z-10 pointer-events-none transition-colors duration-300"></div>
          <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-white dark:from-slate-800 to-transparent z-10 pointer-events-none transition-colors duration-300"></div>

          <div className="w-full h-full overflow-y-auto hide-scrollbar pb-8 pt-2">
            <AnimatedList className="flex flex-col w-full">
              {customers.map((customer) => (
                <AnimatedRow key={customer.id} customer={customer} onViewDetails={onViewDetails} />
              ))}
            </AnimatedList>
          </div>
        </div>
      </>
    );
  }

  return (
    <div className="py-4 h-[750px] overflow-y-auto hide-scrollbar custom-scrollbar pr-2">
      <AnimatedList className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 w-full">
        {customers.map((customer) => (
          <ReflectiveCard key={customer.id} customer={customer} onViewDetails={onViewDetails} />
        ))}
      </AnimatedList>
    </div>
  );
};
