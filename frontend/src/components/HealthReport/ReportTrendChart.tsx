import React from 'react';
import { TrendingUp, Clock } from 'lucide-react';

export function ReportTrendChart() {
  return (
    <div className="bg-white/50 dark:bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/60 dark:border-slate-800/60 p-8">
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <div className="w-16 h-16 rounded-2xl bg-brand/10 dark:bg-brand/20 flex items-center justify-center mb-4">
          <TrendingUp className="w-8 h-8 text-brand" />
        </div>
        <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300 mb-2">趋势对比</h3>
        <p className="text-xs text-slate-400 dark:text-slate-500 max-w-xs mb-4">
          当多次体检数据可用时，此处将展示关键指标的历史变化趋势折线图，包括参考范围区间和异常标记。
        </p>
        <div className="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500">
          <Clock className="w-3.5 h-3.5" />
          <span>暂无历史数据，预留功能接口</span>
        </div>
      </div>
    </div>
  );
}
