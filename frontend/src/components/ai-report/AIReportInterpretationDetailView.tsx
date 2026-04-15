import React, { useMemo, useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { CUSTOMERS } from '../../data/mockData';
import type { AppPage } from '../../navigation';
import { AIReportComparisonReportView } from './AIReportComparisonReportView';
import { CustomerResults } from './detailView/CustomerResults';
import { DETAIL_STATS } from './detailView/data';
import { DetailHeader } from './detailView/DetailHeader';
import { FilterToolbar } from './detailView/FilterToolbar';
import { StatsGrid } from './detailView/StatsGrid';
import type { CustomerRecord, DetailViewMode } from './detailView/types';
import { aiReportApi } from '../../services/api/aiReportApi';

export { AnimatedList, AnimatedListItem } from './detailView/AnimatedList';

interface AIReportComparisonDetailViewProps {
  setCurrentPage: (page: AppPage) => void;
  isDarkMode: boolean;
  setIsDarkMode: (value: boolean) => void;
}

export const AIReportComparisonDetailView: React.FC<AIReportComparisonDetailViewProps> = ({
  setCurrentPage,
  isDarkMode,
  setIsDarkMode,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [activeStat, setActiveStat] = useState(0);
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerRecord | null>(null);
  const [viewMode, setViewMode] = useState<DetailViewMode>('card');

  // 获取体检报告
  useEffect(() => {
    aiReportApi.getcustomersListApi({
      "queryParams": {},
      "body": {
        "customerInfo": "李新"
      },
      "page": "1",
      "size": "10"
    }).then((res) => {
      console.log('getcustomersListApi response:', res);
      // 转换数据

    }).catch(console.error);
  }, []);

  const filteredCustomers = useMemo(() => {
    const customers = CUSTOMERS as CustomerRecord[];
    return customers.filter((customer) => customer.name.includes(searchTerm));
  }, [searchTerm]);

  return (
    <div className="h-full flex flex-col space-y-6 p-6 bg-slate-50 dark:bg-slate-900 transition-colors duration-300 overflow-y-auto">
      <AnimatePresence mode="wait">
        {selectedCustomer ? (
          <motion.div
            key="detail"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.3 }}
            className="h-full"
          >
            <AIReportComparisonReportView
              customer={selectedCustomer}
              onBack={() => setSelectedCustomer(null)}
              isDarkMode={isDarkMode}
              setIsDarkMode={setIsDarkMode}
            />
          </motion.div>
        ) : (
          <motion.div
            key="list"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3 }}
            className="flex flex-col space-y-6"
          >
            <DetailHeader
              onBack={() => setCurrentPage('function-square')}
              isDarkMode={isDarkMode}
              onToggleDarkMode={() => setIsDarkMode(!isDarkMode)}
            />

            <StatsGrid stats={DETAIL_STATS} activeStat={activeStat} onSelectStat={setActiveStat} />

            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2, ease: 'easeOut' }}
              className="flex-1 transition-colors duration-300 mt-2"
            >
              <FilterToolbar
                viewMode={viewMode}
                searchTerm={searchTerm}
                onSearchTermChange={setSearchTerm}
                onViewModeChange={setViewMode}
              />

              <div className="w-full text-sm">
                <CustomerResults
                  viewMode={viewMode}
                  customers={filteredCustomers}
                  onViewDetails={setSelectedCustomer}
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
