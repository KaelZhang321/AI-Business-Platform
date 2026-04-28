import React from 'react';
import { Sparkles, X } from 'lucide-react';
import type { MetricData } from './types';
import { TrendChart } from './TrendChart';

interface FocusedMetricPanelProps {
  metric?: MetricData;
  onClose: () => void;
}

export const FocusedMetricPanel: React.FC<FocusedMetricPanelProps> = ({ metric, onClose }) => {
  if (!metric) {
    return null;
  }

  const val2026 = metric.values['2026'];
  const val2025 = metric.values['2025'];

  const isHigh = typeof val2026 === 'number' && val2026 > parseFloat(metric.refRange.split('-')[1]);
  const isLow = typeof val2026 === 'number' && val2026 < parseFloat(metric.refRange.split('-')[0]);

  const diff = typeof val2026 === 'number' && typeof val2025 === 'number' ? (val2026 - val2025).toFixed(2) : null;
  const isIncrease = diff && parseFloat(diff) > 0;
  const isDecrease = diff && parseFloat(diff) < 0;

  return (
    <div className="flex-1 flex flex-col h-full">
      <div className="flex items-center justify-between mb-8 shrink-0">
        <div className="flex items-center space-x-4">
          <div className="w-14 h-14 rounded-2xl bg-brand/10 flex items-center justify-center">
            <Sparkles className="w-7 h-7 text-brand" />
          </div>
          <div>
            <h2 className="text-2xl font-black text-slate-900 dark:text-white">
              {metric.name}
              <span className="text-sm font-bold text-slate-400 ml-2">深度分析</span>
            </h2>
            <p className="text-sm text-slate-500 font-bold mt-1">参考范围: {metric.refRange} {metric.unit}</p>
          </div>
        </div>
        <button onClick={onClose} className="p-2.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl transition-colors text-slate-500">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-6 mb-8 shrink-0">
        <div className={`p-6 rounded-2xl border ${isHigh ? 'bg-rose-50 border-rose-100 dark:bg-rose-500/10 dark:border-rose-500/20' : isLow ? 'bg-amber-50 border-amber-100 dark:bg-amber-500/10 dark:border-amber-500/20' : 'bg-emerald-50 border-emerald-100 dark:bg-emerald-500/10 dark:border-emerald-500/20'}`}>
          <div className="text-sm font-bold text-slate-500 dark:text-slate-400 mb-2">最新数值 (2026)</div>
          <div className="flex items-end space-x-2">
            <div className={`text-5xl font-black ${isHigh ? 'text-rose-600 dark:text-rose-400' : isLow ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
              {val2026}
            </div>
            <div className="text-sm font-bold text-slate-500 mb-1">{metric.unit}</div>
          </div>
          <div className="mt-4 inline-block px-3 py-1 rounded-lg text-xs font-bold bg-white/60 dark:bg-slate-900/50">
            {isHigh ? '指标偏高' : isLow ? '指标偏低' : '指标正常'}
          </div>
        </div>

        <div className="p-6 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700">
          <div className="text-sm font-bold text-slate-500 dark:text-slate-400 mb-2">上一年度 (2025)</div>
          <div className="flex items-end space-x-2">
            <div className="text-5xl font-black text-slate-700 dark:text-slate-200">{val2025}</div>
            <div className="text-sm font-bold text-slate-500 mb-1">{metric.unit}</div>
          </div>
          {diff && (
            <div className="mt-4 flex items-center space-x-2 text-sm font-bold">
              <span className="text-slate-500">较去年</span>
              <span className={isIncrease ? 'text-rose-500' : isDecrease ? 'text-emerald-500' : 'text-slate-400'}>
                {isIncrease ? '↑' : isDecrease ? '↓' : ''} {Math.abs(parseFloat(diff))}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 bg-white dark:bg-slate-800/30 rounded-2xl border border-slate-100 dark:border-slate-700 p-6 flex flex-col min-h-0 overflow-hidden shadow-sm">
        <h3 className="text-sm font-bold text-slate-500 dark:text-slate-400 mb-6 uppercase tracking-widest shrink-0">历年趋势 (2018-2026)</h3>
        <div className="flex-1 w-full overflow-x-auto custom-scrollbar min-h-0 pb-2">
          <div className="min-w-[600px] w-full h-full flex items-center justify-center">
            <TrendChart m={metric} isExpanded={true} className="h-full w-full max-h-[200px]" />
          </div>
        </div>
        <div className="mt-4 p-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 shrink-0">
          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed font-medium">
            <span className="font-bold text-brand mr-2">AI 分析:</span>
            {metric.trend}
          </p>
        </div>
      </div>
    </div>
  );
};
