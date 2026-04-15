import React from 'react';
import { motion } from 'motion/react';
import { List, LayoutGrid } from 'lucide-react';
import CardSwap, { Card, type CardSwapRef } from '../CardSwap';
import { TrendChart } from './TrendChart';
import type { MetricData } from './types';

interface CardStackPanelProps {
  cardStack: string[];
  viewMode: 'list' | 'trend';
  onChangeViewMode: (mode: 'list' | 'trend') => void;
  metrics: MetricData[];
  cardSwapRef: React.RefObject<CardSwapRef | null>;
  onOpenModal: (year: string) => void;
  onSwapCard: () => void;
  onFocusMetric: (metricName: string) => void;
}

export const CardStackPanel: React.FC<CardStackPanelProps> = ({
  cardStack,
  viewMode,
  onChangeViewMode,
  metrics,
  cardSwapRef,
  onOpenModal,
  onSwapCard,
  onFocusMetric,
}) => {
  return (
    <motion.div
      key="card-swap"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="absolute inset-0 flex items-center justify-center perspective-1000 translate-x-0 translate-y-24 scale-[0.85]"
    >
      <CardSwap
        ref={cardSwapRef}
        width="100%"
        height="100%"
        pauseOnHover={true}
        cardDistance={100}
        verticalDistance={75}
        delay={800}
        skewAmount={5}
        easing="linear"
        onCardClick={onSwapCard}
      >
        {cardStack.map((year) => (
          <Card
            key={year}
            className="bg-gradient-to-b from-white to-slate-50/80 dark:from-slate-800 dark:to-slate-900 rounded-[32px] border-[1.5px] border-t-white border-x-white/80 border-b-white/20 dark:border-t-slate-600 dark:border-x-slate-600/50 dark:border-b-transparent shadow-[0_20px_40px_rgb(0,0,0,0.06)] p-6 flex flex-col transition-colors duration-300 cursor-pointer w-full h-full backdrop-blur-sm"
            onClick={(e: any) => {
              e.stopPropagation();
              onOpenModal(year);
            }}
          >
            <div className="flex flex-col items-center justify-center mb-6 shrink-0 relative">
              <div className="absolute right-0 top-0 flex space-x-1 bg-slate-100 dark:bg-slate-700/50 p-1 rounded-xl">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onChangeViewMode('list');
                  }}
                  className={`p-1.5 rounded-lg transition-colors flex items-center justify-center ${viewMode === 'list' ? 'bg-white dark:bg-slate-800 text-brand shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'}`}
                  title="列表查看"
                >
                  <List className="w-4 h-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onChangeViewMode('trend');
                  }}
                  className={`p-1.5 rounded-lg transition-colors flex items-center justify-center ${viewMode === 'trend' ? 'bg-white dark:bg-slate-800 text-brand shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'}`}
                  title="表单查看"
                >
                  <LayoutGrid className="w-4 h-4" />
                </button>
              </div>
              <h4 className="text-2xl font-bold text-slate-900 dark:text-white text-center">{year}年度体检报告</h4>
              <p className="text-sm text-slate-500 dark:text-slate-400 text-center mt-2">体检时间：{year}年03月18日</p>
            </div>

            <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar flex flex-col">
              {viewMode === 'trend' ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pb-4">
                  {metrics.map((m) => (
                    <div key={m.name} className="bg-white dark:bg-slate-900/30 border border-slate-100 dark:border-slate-700/50 rounded-2xl p-4 flex flex-col shadow-sm hover:shadow-md transition-shadow">
                      <div className="flex justify-between items-start mb-4">
                        <div>
                          <h5 className="font-bold text-slate-900 dark:text-white text-lg">{m.name}</h5>
                          <p className="text-xs text-slate-500 dark:text-slate-400">参考范围 {m.refRange} {m.unit}</p>
                        </div>
                        <span
                          className={`px-2 py-1 rounded text-[10px] font-bold ${m.judgment === 'high' ? 'bg-rose-50 text-rose-500 dark:bg-rose-500/10 dark:text-rose-400' : m.judgment === 'low' ? 'bg-amber-50 text-amber-500 dark:bg-amber-500/10 dark:text-amber-400' : 'bg-emerald-50 text-emerald-500 dark:bg-emerald-500/10 dark:text-emerald-400'}`}
                        >
                          当前{m.judgment === 'high' ? '偏高' : m.judgment === 'low' ? '偏低' : '正常'}
                        </span>
                      </div>

                      <div className="grid grid-cols-3 gap-2 mb-2">
                        <div className="bg-white dark:bg-slate-800 rounded-xl p-2 text-center border border-slate-100 dark:border-slate-700">
                          <div className="text-[10px] text-slate-400 mb-1">2024</div>
                          <div className="font-bold text-slate-900 dark:text-white text-lg">{m.values['2024']}</div>
                        </div>
                        <div className="bg-white dark:bg-slate-800 rounded-xl p-2 text-center border border-slate-100 dark:border-slate-700">
                          <div className="text-[10px] text-slate-400 mb-1">2025</div>
                          <div className="font-bold text-slate-900 dark:text-white text-lg">{m.values['2025']}</div>
                        </div>
                        <div className={`rounded-xl p-2 text-center border ${m.judgment !== 'normal' ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-100 dark:border-blue-800/50' : 'bg-white dark:bg-slate-800 border-slate-100 dark:border-slate-700'}`}>
                          <div className="text-[10px] text-blue-500 dark:text-blue-400 mb-1">2026</div>
                          <div className="font-bold text-blue-600 dark:text-blue-400 text-lg">{m.values['2026']}</div>
                        </div>
                      </div>

                      <div className="w-full overflow-x-auto custom-scrollbar pb-2">
                        <div className="min-w-[320px]">
                          <TrendChart m={m} />
                        </div>
                      </div>

                      <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-2">趋势结论：{m.trend}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <table className="w-full text-base text-center">
                  <thead>
                    <tr className="text-slate-400 text-xs uppercase font-bold border-b border-slate-100 dark:border-slate-700">
                      <th className="py-3 px-1 text-center">指标</th>
                      <th className="py-3 px-1 text-center">单位</th>
                      <th className="py-3 px-1 text-center">参考范围</th>
                      <th className="py-3 px-1 text-center">数值</th>
                      <th className="py-3 px-1 text-center">判断</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50 dark:divide-slate-800/50">
                    {metrics.map((m, i) => {
                      const val = m.values[year];
                      const isHigh = typeof val === 'number' && val > parseFloat(m.refRange.split('-')[1]);
                      const isLow = typeof val === 'number' && val < parseFloat(m.refRange.split('-')[0]);

                      return (
                        <tr key={i} className="group hover:bg-slate-50/50 dark:hover:bg-slate-700/30 transition-colors cursor-pointer" onClick={() => onFocusMetric(m.name)}>
                          <td className="py-3 px-1 font-bold text-slate-800 dark:text-slate-200">{m.name}</td>
                          <td className="py-3 px-1 text-slate-500 dark:text-slate-400">{m.unit}</td>
                          <td className="py-3 px-1 text-slate-500 dark:text-slate-400">{m.refRange}</td>
                          <td className="py-3 px-1 font-bold text-slate-900 dark:text-white text-lg">{val}</td>
                          <td className="py-3 px-1">
                            <span
                              className={`px-3 py-1 rounded text-xs font-bold ${isHigh
                                  ? 'bg-rose-50 dark:bg-rose-500/10 text-rose-500'
                                  : isLow
                                    ? 'bg-amber-50 dark:bg-amber-500/10 text-amber-500'
                                    : 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-500'
                                }`}
                            >
                              {isHigh ? '偏高' : isLow ? '偏低' : '正常'}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </Card>
        ))}
      </CardSwap>
    </motion.div>
  );
};
