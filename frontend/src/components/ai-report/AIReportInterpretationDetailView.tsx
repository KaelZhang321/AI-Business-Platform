import React, { useMemo, useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'motion/react';
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

const PAGE_SIZE = 10;

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
  const [customers, setCustomers] = useState<CustomerRecord[]>([]);
  const [isLoadingCustomers, setIsLoadingCustomers] = useState(false);
  const [isLoadingMoreCustomers, setIsLoadingMoreCustomers] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [currentPageNo, setCurrentPageNo] = useState(1);
  const [hasMoreCustomers, setHasMoreCustomers] = useState(true);

  const resolveAiJudgment = (latestExamDate?: string | null) => {
    if (!latestExamDate) return '优先复查';
    const examTime = new Date(latestExamDate).getTime();
    if (Number.isNaN(examTime)) return '持续观察';
    const sixMonthsMs = 1000 * 60 * 60 * 24 * 180;
    return Date.now() - examTime > sixMonthsMs ? '优先复查' : '持续观察';
  };

  const resolveKeyAbnormal = (record: {
    typeName?: string | null;
    storeName?: string | null;
    mainTeacherName?: string | null;
    subTeacherName?: string | null;
  }) => {
    const parts = [record.typeName, record.storeName].filter(Boolean);
    const teacher = [record.mainTeacherName, record.subTeacherName].filter(Boolean).join(' / ');
    if (teacher) {
      parts.push(`带教: ${teacher}`);
    }
    return parts.length > 0 ? parts.join(' · ') : '待补充';
  };

  type RawCustomerItem = {
    customerId?: string | number | null;
    patientName?: string | null;
    gender?: string | null;
    age?: number | string | null;
    encryptedIdCard?: string | null;
    idCardObfuscated?: string | null;
    encryptedPhone?: string | null;
    phoneObfuscated?: string | null;
    typeName?: string | null;
    storeName?: string | null;
    mainTeacherName?: string | null;
    subTeacherName?: string | null;
    latestExamDate?: string | null;
  };

  type CustomerListApiResponse = {
    data?: RawCustomerItem[] | { data?: RawCustomerItem[]; total?: number | string };
    total?: number | string;
  };

  const toSafeNumber = (value: unknown) => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === 'string' && value.trim()) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : undefined;
    }
    return undefined;
  };

  const mapCustomer = (item: RawCustomerItem): CustomerRecord => {
    const idValue = item.customerId != null ? String(item.customerId) : `${Date.now()}-${Math.random()}`;
    const name = item.patientName?.trim() || '未知客户';
    const lastCheckDate = item.latestExamDate || '暂无';
    const aiJudgment = resolveAiJudgment(item.latestExamDate);

    return {
      id: idValue,
      customerId: item.customerId != null ? String(item.customerId) : undefined,
      name,
      gender: item.gender || '未知',
      age: Number(item.age ?? 0),
      lastCheckDate,
      aiJudgment,
      keyAbnormal: resolveKeyAbnormal(item),
      encryptedIdCard: item.encryptedIdCard ?? null,
      idCardObfuscated: item.idCardObfuscated ?? null,
      encryptedPhone: item.encryptedPhone ?? null,
      phoneObfuscated: item.phoneObfuscated ?? null,
      typeName: item.typeName ?? null,
      storeName: item.storeName ?? null,
      mainTeacherName: item.mainTeacherName ?? null,
      subTeacherName: item.subTeacherName ?? null,
      latestExamDate: item.latestExamDate ?? null,
    };
  };

  const fetchCustomers = async (pageNo: number, append = false) => {
    if (append) {
      if (isLoadingMoreCustomers || isLoadingCustomers || !hasMoreCustomers) {
        return;
      }
      setIsLoadingMoreCustomers(true);
    } else {
      setIsLoadingCustomers(true);
      setLoadError(null);
    }

    try {
      const res = await aiReportApi.getcustomersListApi({
        queryParams: {},
        body: {
          customerInfo: '李新',
        },
        page: String(pageNo),
        size: String(PAGE_SIZE),
      });

      const payload = res as CustomerListApiResponse | RawCustomerItem[] | undefined;

      let rawList: RawCustomerItem[] = [];
      let total: number | undefined;

      if (Array.isArray(payload)) {
        rawList = payload;
      } else if (Array.isArray(payload?.data)) {
        rawList = payload.data;
        total = toSafeNumber(payload.total);
      } else if (payload?.data && typeof payload.data === 'object') {
        const nested = payload.data as { data?: RawCustomerItem[]; total?: number | string };
        if (Array.isArray(nested.data)) {
          rawList = nested.data;
        }
        total = toSafeNumber(nested.total ?? payload.total);
      }

      const mapped = rawList.map(mapCustomer);
      const base = append ? customers : [];
      const merged = Array.from(new Map([...base, ...mapped].map((item) => [String(item.id), item])).values());
      setCustomers(merged);
      setCurrentPageNo(pageNo);

      if (typeof total === 'number') {
        setHasMoreCustomers(merged.length < total);
      } else {
        setHasMoreCustomers(mapped.length >= PAGE_SIZE);
      }
    } catch (error) {
      console.error('getcustomersListApi error:', error);
      if (!append) {
        setLoadError('客户列表加载失败，请稍后重试');
        setCustomers([]);
      }
    } finally {
      if (append) {
        setIsLoadingMoreCustomers(false);
      } else {
        setIsLoadingCustomers(false);
      }
    }
  };

  // 首屏获取客户列表
  useEffect(() => {
    fetchCustomers(1, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredCustomers = useMemo(() => {
    const keyword = searchTerm.trim();
    if (!keyword) return customers;
    return customers.filter((customer) => customer.name.includes(keyword));
  }, [customers, searchTerm]);

  const handleLoadMoreCustomers = () => {
    fetchCustomers(currentPageNo + 1, true);
  };

  return (
    <div className="h-full min-h-0 flex flex-col space-y-6 p-6 bg-slate-50 dark:bg-slate-900 transition-colors duration-300 overflow-hidden">
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
            className="flex flex-col min-h-0 space-y-6"
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
              className="flex flex-col flex-1 min-h-0 transition-colors duration-300 mt-2 overflow-hidden"
            >
              <FilterToolbar
                viewMode={viewMode}
                searchTerm={searchTerm}
                onSearchTermChange={setSearchTerm}
                onViewModeChange={setViewMode}
              />

              <div className="w-full flex-1 min-h-0 text-sm overflow-hidden">
                {isLoadingCustomers ? (
                  <div className="py-16 text-center text-slate-500 dark:text-slate-400">客户列表加载中...</div>
                ) : loadError ? (
                  <div className="py-16 text-center text-rose-500 dark:text-rose-400">{loadError}</div>
                ) : filteredCustomers.length === 0 ? (
                  <div className="py-16 text-center text-slate-500 dark:text-slate-400">暂无匹配客户</div>
                ) : null}
                <CustomerResults
                  viewMode={viewMode}
                  customers={filteredCustomers}
                  onViewDetails={setSelectedCustomer}
                  onLoadMore={handleLoadMoreCustomers}
                  hasMore={hasMoreCustomers}
                  isLoadingMore={isLoadingMoreCustomers}
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
