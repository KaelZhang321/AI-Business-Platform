import React from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Search, X } from 'lucide-react';
import { AnimatedList } from '../../ai-report/AIReportInterpretationDetailView';
import { CustomerRow } from './CustomerRow';
import type { CustomerRecord } from './types';

interface CustomerSelectionModalProps {
  isOpen: boolean;
  searchTerm: string;
  filteredCustomers: CustomerRecord[];
  onSearchTermChange: (value: string) => void;
  onSelectCustomer: (customer: CustomerRecord) => void;
  onClose: () => void;
}

export const CustomerSelectionModal: React.FC<CustomerSelectionModalProps> = ({
  isOpen,
  searchTerm,
  filteredCustomers,
  onSearchTermChange,
  onSelectCustomer,
  onClose,
}) => {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-6 backdrop-blur-sm"
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            className="flex h-[80vh] w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl dark:border-slate-800 dark:bg-slate-900"
          >
            <div className="flex items-center justify-between border-b border-slate-100 p-6 dark:border-slate-800">
              <div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-white">选择客户</h3>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">从列表中选择要分析的客户，或通过姓名、手机号、身份证号检索</p>
              </div>
              <button
                onClick={onClose}
                className="rounded-full p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
              >
                <X className="h-6 w-6" />
              </button>
            </div>

            <div className="border-b border-slate-100 bg-slate-50/50 p-6 dark:border-slate-800 dark:bg-slate-800/30">
              <div className="relative max-w-md">
                <Search className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="输入客户姓名、手机号或身份证号搜索..."
                  value={searchTerm}
                  onChange={(e) => onSearchTermChange(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white py-3 pl-10 pr-4 text-sm text-slate-900 shadow-sm outline-none transition-colors focus:ring-2 focus:ring-blue-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                />
              </div>
            </div>

            <div className="flex flex-1 flex-col overflow-hidden bg-slate-50 dark:bg-slate-900/50">
              <div className="grid grid-cols-12 gap-4 border-b border-slate-200 bg-white px-8 py-4 text-xs font-semibold uppercase tracking-wider text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500">
                <div className="col-span-2 text-left">客户姓名</div>
                <div className="col-span-2 text-left">性别 / 年龄</div>
                <div className="col-span-2 text-left">最近体检日期</div>
                <div className="col-span-2 text-left">AI综合判断</div>
                <div className="col-span-3 text-left">关键异常指标</div>
                <div className="col-span-1 text-center">操作</div>
              </div>

              <div className="custom-scrollbar flex-1 overflow-y-auto p-6">
                <AnimatedList className="flex w-full flex-col space-y-2">
                  {filteredCustomers.map((customer) => (
                    <CustomerRow key={customer.id} customer={customer} onViewDetails={onSelectCustomer} />
                  ))}
                  {filteredCustomers.length === 0 && <div className="py-12 text-center text-slate-500 dark:text-slate-400">没有找到匹配的客户</div>}
                </AnimatedList>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
