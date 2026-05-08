import React, { useRef } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Activity, LayoutGrid, List, X } from 'lucide-react';
import type { MetricData } from './types';
import { TrendChart } from './TrendChart';

interface ComparisonModalProps {
  selectedYearForModal: string | null;
  metrics: MetricData[];
  modalFilter: 'all' | 'abnormal';
  modalViewMode: 'card' | 'list';
  onModalFilterChange: (mode: 'all' | 'abnormal') => void;
  onModalViewModeChange: (mode: 'card' | 'list') => void;
  onSelectYear: (year: string | null) => void;
  onClose: () => void;
}

export const ComparisonModal: React.FC<ComparisonModalProps> = ({
  selectedYearForModal,
  metrics,
  modalFilter,
  modalViewMode,
  onModalFilterChange,
  onModalViewModeChange,
  onSelectYear,
  onClose,
}) => {
  const leftScrollRef = useRef<HTMLDivElement>(null);
  const centerScrollRef = useRef<HTMLDivElement>(null);
  const rightScrollRef = useRef<HTMLDivElement>(null);
  const trendScrollRef = useRef<HTMLDivElement>(null);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const scrollTop = e.currentTarget.scrollTop;
    if (leftScrollRef.current && e.currentTarget !== leftScrollRef.current) {
      leftScrollRef.current.scrollTop = scrollTop;
    }
    if (centerScrollRef.current && e.currentTarget !== centerScrollRef.current) {
      centerScrollRef.current.scrollTop = scrollTop;
    }
    if (rightScrollRef.current && e.currentTarget !== rightScrollRef.current) {
      rightScrollRef.current.scrollTop = scrollTop;
    }
    if (trendScrollRef.current && e.currentTarget !== trendScrollRef.current) {
      trendScrollRef.current.scrollTop = scrollTop;
    }
  };

  const getYearData = (year: string | null) => {
    if (!year) {
      return null;
    }

    return metrics.map((m) => ({
      name: m.name,
      unit: m.unit,
      val: m.values[year],
      refRange: m.refRange,
    }));
  };

  const isMetricAbnormalAtYear = (metric: MetricData, year: string) => {
    const val = metric.values[year];
    if (val === undefined || val === null || val === '') {
      return false;
    }

    const numVal = Number(val);
    if (isNaN(numVal)) {
      return false;
    }

    const [minStr, maxStr] = metric.refRange.split('-');
    const isHigh = numVal > parseFloat(maxStr);
    const isLow = numVal < parseFloat(minStr);
    return isHigh || isLow;
  };

  const renderComparisonColumn = (
    year: string | null,
    isCenter = false,
    prevYearData: Array<{ name: string; unit: string; val: number | string; refRange: string }> | null = null,
    scrollRef?: React.RefObject<HTMLDivElement>,
    filteredMetrics?: MetricData[],
  ) => {
    if (!year) {
      return (
        <motion.div layout className="flex-1 flex items-center justify-center text-slate-300 dark:text-slate-700 italic text-sm">
          无相关年份数据
        </motion.div>
      );
    }

    const data = (filteredMetrics || metrics).map((m) => ({
      name: m.name,
      unit: m.unit,
      val: m.values[year],
      refRange: m.refRange,
    }));

    return (
      <motion.div
        layout
        className={`flex-1 flex flex-col p-6 rounded-2xl border transition-all duration-300 ${
          isCenter
            ? 'bg-white dark:bg-slate-800 border-brand shadow-xl scale-105 z-10'
            : 'bg-slate-50/50 dark:bg-slate-900/50 border-slate-100 dark:border-slate-800 opacity-60'
        }`}
      >
        <h3 className={`text-center font-black mb-6 ${isCenter ? 'text-brand text-xl' : 'text-slate-500 text-sm uppercase tracking-widest'}`}>
          {year} 年度报告
        </h3>

        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className={`flex-1 overflow-y-auto pr-2 space-y-4 ${isCenter ? 'custom-scrollbar' : '[&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]'}`}
        >
          {data.map((item) => {
            const originalIdx = metrics.findIndex((m) => m.name === item.name);
            const prevItem = prevYearData ? prevYearData[originalIdx] : null;
            const diff =
              prevItem && typeof item.val === 'number' && typeof prevItem.val === 'number'
                ? (item.val - prevItem.val).toFixed(2)
                : null;

            const isIncrease = diff && parseFloat(diff) > 0;
            const isDecrease = diff && parseFloat(diff) < 0;

            const isHigh = typeof item.val === 'number' && item.val > parseFloat(item.refRange.split('-')[1]);
            const isLow = typeof item.val === 'number' && item.val < parseFloat(item.refRange.split('-')[0]);
            const judgment = isHigh ? '偏高' : isLow ? '偏低' : '正常';
            const judgmentColor = isHigh
              ? 'text-rose-500 bg-rose-50 dark:bg-rose-500/10 dark:text-rose-400'
              : isLow
                ? 'text-amber-500 bg-amber-50 dark:bg-amber-500/10 dark:text-amber-400'
                : 'text-emerald-500 bg-emerald-50 dark:bg-emerald-500/10 dark:text-emerald-400';

            return (
              <div
                key={item.name}
                className="p-3 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 shadow-sm h-[116px] flex flex-col justify-between"
              >
                <div>
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-xs font-bold text-slate-500">{item.name}</span>
                    <span className="text-[10px] text-slate-400">{item.unit}</span>
                  </div>
                  <div className="flex items-end justify-between mb-2">
                    <div className="text-xl font-black text-slate-900 dark:text-white">{item.val}</div>
                    {isCenter && diff && (
                      <div className={`flex items-center space-x-1 text-xs font-bold ${isIncrease ? 'text-rose-500' : isDecrease ? 'text-emerald-500' : 'text-slate-400'}`}>
                        {isIncrease ? '↑' : isDecrease ? '↓' : ''}
                        <span>{Math.abs(parseFloat(diff))}</span>
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-slate-50 dark:border-slate-700/50">
                  <span className="text-[10px] text-slate-400">参考: {item.refRange}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${judgmentColor}`}>{judgment}</span>
                </div>
              </div>
            );
          })}
        </div>
      </motion.div>
    );
  };

  const renderTrendColumn = (yearsToShow?: string[], filteredMetrics?: MetricData[]) => {
    const displayMetrics = filteredMetrics || metrics;

    return (
      <motion.div
        layout
        className="flex-1 flex flex-col p-6 rounded-2xl border transition-all duration-300 bg-slate-50/50 dark:bg-slate-900/50 border-slate-100 dark:border-slate-800 opacity-80"
      >
        <div className="flex flex-col items-center mb-6 space-y-2">
          <h3 className="font-black text-slate-500 text-sm uppercase tracking-widest">对比趋势</h3>
          <div className="flex items-center space-x-6">
            <div className="flex items-center space-x-2">
              <div className="w-4 h-1.5 bg-emerald-500/20 border border-emerald-500/30 rounded-sm"></div>
              <span className="text-xs font-black text-emerald-600">正常区间</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-4 h-1 bg-blue-500 rounded-full"></div>
              <span className="text-xs font-black text-blue-600">数值走势</span>
            </div>
          </div>
        </div>

        <div
          ref={trendScrollRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto pr-2 space-y-4 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]"
        >
          {displayMetrics.map((m) => (
            <div key={m.name} className="p-3 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 shadow-sm h-[116px] flex flex-col">
              <div className="flex justify-between items-start mb-1 shrink-0">
                <span className="text-xs font-bold text-slate-500">{m.name}</span>
              </div>
              <div className="flex-1 flex items-center justify-center min-h-0">
                <TrendChart m={m} yearsToShow={yearsToShow} />
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    );
  };

  return (
    <AnimatePresence>
      {selectedYearForModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-900/60 backdrop-blur-sm">
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="bg-white dark:bg-slate-900 w-full max-w-[90vw] h-[85vh] rounded-[32px] shadow-2xl flex flex-col overflow-hidden border border-slate-200 dark:border-slate-700"
          >
            <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-white dark:bg-slate-900 z-20">
              <div className="flex items-center space-x-4">
                <div className="w-12 h-12 rounded-2xl bg-brand/10 flex items-center justify-center">
                  <Activity className="w-6 h-6 text-brand" />
                </div>
                <div>
                  <h2 className="text-xl font-black text-slate-900 dark:text-white">历年指标深度对比</h2>
                  <p className="text-xs text-slate-500 font-bold uppercase tracking-widest">以 {selectedYearForModal} 年度为核心</p>
                </div>
              </div>

              <div className="flex items-center space-x-6">
                <div className="flex bg-slate-100 dark:bg-slate-800 p-1 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-inner">
                  <button
                    onClick={() => onModalViewModeChange('card')}
                    className={`p-2 rounded-xl transition-all ${modalViewMode === 'card' ? 'bg-white dark:bg-slate-700 text-brand shadow-md scale-[1.02]' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}
                    title="卡片查看"
                  >
                    <LayoutGrid className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => onModalViewModeChange('list')}
                    className={`p-2 rounded-xl transition-all ${modalViewMode === 'list' ? 'bg-white dark:bg-slate-700 text-brand shadow-md scale-[1.02]' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}
                    title="列表查看"
                  >
                    <List className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex bg-slate-100 dark:bg-slate-800 p-1 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-inner">
                  <button
                    onClick={() => onModalFilterChange('all')}
                    className={`px-6 py-2 rounded-xl text-xs font-black transition-all flex items-center space-x-3 ${modalFilter === 'all' ? 'bg-white dark:bg-slate-700 text-brand shadow-md scale-[1.02]' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}
                  >
                    <span>全部指标</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] ${modalFilter === 'all' ? 'bg-brand/10 text-brand' : 'bg-slate-200 dark:bg-slate-600 text-slate-500'}`}>
                      {metrics.length}
                    </span>
                  </button>
                  <button
                    onClick={() => onModalFilterChange('abnormal')}
                    className={`px-6 py-2 rounded-xl text-xs font-black transition-all flex items-center space-x-3 ${modalFilter === 'abnormal' ? 'bg-rose-500 text-white shadow-md scale-[1.02]' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}
                  >
                    <span>异常关注</span>
                    <span className={`px-2 py-0.5 rounded-full text-[10px] ${modalFilter === 'abnormal' ? 'bg-white/20 text-white' : 'bg-rose-100 dark:bg-rose-900/30 text-rose-500'}`}>
                      {metrics.filter((m) => isMetricAbnormalAtYear(m, selectedYearForModal)).length}
                    </span>
                  </button>
                </div>

                <button
                  onClick={onClose}
                  className="p-2.5 bg-slate-100 dark:bg-slate-800 hover:bg-rose-50 dark:hover:bg-rose-900/30 rounded-2xl transition-all text-slate-400 hover:text-rose-500 group border border-transparent hover:border-rose-200 dark:hover:border-rose-800"
                  title="关闭对比"
                >
                  <X className="w-6 h-6 transition-transform group-hover:rotate-90" />
                </button>
              </div>
            </div>

            <div className="flex-1 flex p-8 bg-slate-50/30 dark:bg-slate-900/30 overflow-hidden">
              {(() => {
                const years = ['2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026'];
                const currentIdx = years.indexOf(selectedYearForModal);
                const prevYear = currentIdx > 0 ? years[currentIdx - 1] : null;
                const nextYear = currentIdx < years.length - 1 ? years[currentIdx + 1] : null;
                const prevYearData = getYearData(prevYear);
                const yearsToShow = [prevYear, selectedYearForModal, nextYear].filter((y) => y !== null) as string[];

                const filteredMetrics = modalFilter === 'all' ? metrics : metrics.filter((m) => isMetricAbnormalAtYear(m, selectedYearForModal));

                const handleDragEnd = (_e: any, info: any) => {
                  if (info.offset.x > 100 && prevYear) {
                    onSelectYear(prevYear);
                  } else if (info.offset.x < -100 && nextYear) {
                    onSelectYear(nextYear);
                  }
                };

                if (modalViewMode === 'list') {
                  return (
                    <div className="w-full h-full overflow-auto custom-scrollbar bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-700">
                      <table className="w-full text-sm text-left relative">
                        <thead className="text-xs text-slate-500 uppercase bg-slate-50 dark:bg-slate-900/50 sticky top-0 z-20">
                          <tr>
                            <th className="px-6 py-4 font-bold border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 sticky left-0 z-30 w-[160px] min-w-[160px]">指标项名称</th>
                            <th className="px-6 py-4 font-bold border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50 sticky left-[160px] z-30 w-[140px] min-w-[140px] shadow-[1px_0_0_0_rgba(226,232,240,1)] dark:shadow-[1px_0_0_0_rgba(51,65,85,1)]">正常范围</th>
                            {years.map((year) => (
                              <th key={year} className="px-6 py-4 font-bold border-b border-slate-200 dark:border-slate-700 text-center min-w-[120px]">
                                {year}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {filteredMetrics.map((m, idx) => (
                            <tr key={idx} className="border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors group">
                              <td className="px-6 py-4 font-bold text-slate-900 dark:text-white sticky left-0 bg-white dark:bg-slate-800 z-10 group-hover:bg-slate-50/50 dark:group-hover:bg-slate-800/50 transition-colors w-[160px] min-w-[160px]">
                                {m.name}
                              </td>
                              <td className="px-6 py-4 text-slate-600 dark:text-slate-300 sticky left-[160px] bg-white dark:bg-slate-800 z-10 shadow-[1px_0_0_0_rgba(241,245,249,1)] dark:shadow-[1px_0_0_0_rgba(51,65,85,0.5)] group-hover:bg-slate-50/50 dark:group-hover:bg-slate-800/50 transition-colors w-[140px] min-w-[140px]">
                                <div className="font-medium">{m.refRange}</div>
                                <div className="text-xs text-slate-400 mt-0.5">{m.unit}</div>
                              </td>
                              {years.map((year) => {
                                const val = m.values[year];
                                let status = '正常';
                                let statusColor = 'text-emerald-500 bg-emerald-50 dark:bg-emerald-500/10';

                                if (val !== undefined && val !== null && val !== '') {
                                  const numVal = Number(val);
                                  if (!isNaN(numVal)) {
                                    const [minStr, maxStr] = m.refRange.split('-');
                                    if (numVal > parseFloat(maxStr)) {
                                      status = '偏高';
                                      statusColor = 'text-rose-500 bg-rose-50 dark:bg-rose-500/10';
                                    } else if (numVal < parseFloat(minStr)) {
                                      status = '偏低';
                                      statusColor = 'text-amber-500 bg-amber-50 dark:bg-amber-500/10';
                                    }
                                  }
                                } else {
                                  status = '-';
                                  statusColor = 'text-slate-400';
                                }

                                return (
                                  <td key={year} className="px-6 py-4 text-center">
                                    {val !== undefined && val !== null && val !== '' ? (
                                      <div className="flex flex-col items-center justify-center space-y-1.5">
                                        <span className="font-bold text-slate-700 dark:text-slate-200 text-base">{val}</span>
                                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${statusColor}`}>{status}</span>
                                      </div>
                                    ) : (
                                      <span className="text-slate-300 dark:text-slate-600">-</span>
                                    )}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  );
                }

                return (
                  <motion.div
                    className="flex-1 flex gap-8 w-full h-full cursor-grab active:cursor-grabbing"
                    drag="x"
                    dragConstraints={{ left: 0, right: 0 }}
                    dragElastic={0.2}
                    onDragEnd={handleDragEnd}
                  >
                    {renderComparisonColumn(prevYear, false, null, leftScrollRef, filteredMetrics)}
                    {renderComparisonColumn(selectedYearForModal, true, prevYearData, centerScrollRef, filteredMetrics)}
                    {renderComparisonColumn(nextYear, false, null, rightScrollRef, filteredMetrics)}
                    {renderTrendColumn(yearsToShow, filteredMetrics)}
                  </motion.div>
                );
              })()}
            </div>

            <div className="p-6 bg-slate-50 dark:bg-slate-800/50 border-t border-slate-100 dark:border-slate-700 flex justify-center">
              <div className="flex items-center space-x-12 text-sm font-black">
                <div className="flex items-center space-x-3">
                  <div className="w-4 h-4 rounded-full bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.4)]"></div>
                  <span className="text-slate-600 dark:text-slate-300">数值上升</span>
                </div>
                <div className="flex items-center space-x-3">
                  <div className="w-4 h-4 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.4)]"></div>
                  <span className="text-slate-600 dark:text-slate-300">数值下降</span>
                </div>
                <div className="flex items-center space-x-3">
                  <div className="w-4 h-4 rounded-full bg-slate-400 shadow-[0_0_10px_rgba(148,163,184,0.4)]"></div>
                  <span className="text-slate-600 dark:text-slate-300">保持稳定</span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
