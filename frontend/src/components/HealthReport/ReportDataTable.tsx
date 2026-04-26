import React from 'react';
import { motion } from 'motion/react';
import type { ParsedItem, DisplayMode } from '../../types/healthReport';
import { AbnormalBadge, RangeBar } from './AbnormalBadge';

interface ReportDataTableProps {
  items: ParsedItem[];
  displayMode: DisplayMode;
  searchQuery: string;
  title: string;
}

export function ReportDataTable({ items, displayMode, searchQuery, title }: ReportDataTableProps) {
  const filtered = items.filter(item => {
    if (displayMode === 'abnormal' && (!item.abnormalStatus || item.abnormalStatus === 'normal')) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return item.itemName.toLowerCase().includes(q) ||
             item.itemNameEn.toLowerCase().includes(q) ||
             item.itemCode.includes(q);
    }
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    const aAbn = a.abnormalStatus && a.abnormalStatus !== 'normal' ? 0 : 1;
    const bAbn = b.abnormalStatus && b.abnormalStatus !== 'normal' ? 0 : 1;
    return aAbn - bAbn;
  });

  if (sorted.length === 0) {
    return (
      <div className="bg-white/50 dark:bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-slate-200/60 dark:border-slate-700/60 p-8 text-center">
        <p className="text-sm text-slate-400 dark:text-slate-500">
          {displayMode === 'abnormal' ? '该分组无异常项目' : '无匹配的检查项目'}
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white/50 dark:bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-slate-200/60 dark:border-slate-700/60 overflow-hidden">
      <div className="px-5 py-3.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
        <span className="text-xs text-slate-400 dark:text-slate-500 tabular-nums">{sorted.length} 项</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b-2 border-slate-100 dark:border-slate-800">
              <th className="text-left px-5 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400">项目</th>
              <th className="text-right px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400">结果</th>
              <th className="text-left px-4 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400">参考范围</th>
              <th className="text-center px-3 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 w-28">范围</th>
              <th className="text-center px-3 py-2.5 text-xs font-semibold text-slate-500 dark:text-slate-400 w-20">状态</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((item, idx) => {
              const isAbnormal = item.abnormalStatus && item.abnormalStatus !== 'normal';
              const isHighType = item.abnormalStatus === 'high' || item.abnormalStatus === 'positive' || item.abnormalStatus === 'critical';

              // Improved contrast: stronger backgrounds, no fractional opacity
              const rowBg = isAbnormal
                ? isHighType
                  ? 'bg-red-50 dark:bg-red-950/30'
                  : 'bg-blue-50 dark:bg-blue-950/30'
                : idx % 2 === 0
                  ? 'bg-transparent'
                  : 'bg-slate-50/50 dark:bg-slate-800/30';

              // Stronger left border accent for abnormal rows
              const leftBorder = isAbnormal
                ? isHighType
                  ? 'border-l-2 border-l-red-400 dark:border-l-red-500'
                  : 'border-l-2 border-l-blue-400 dark:border-l-blue-500'
                : 'border-l-2 border-l-transparent';

              return (
                <motion.tr
                  key={`${item.itemCode}-${item.itemName}-${idx}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.15 }}
                  className={`border-b border-slate-100/80 dark:border-slate-800/50 ${rowBg} ${leftBorder} hover:bg-slate-100 dark:hover:bg-slate-800/60 transition-colors duration-150`}
                >
                  {/* Item name + English name merged */}
                  <td className="px-5 py-3">
                    <div className={`text-sm leading-tight ${isAbnormal ? 'font-semibold text-slate-900 dark:text-slate-100' : 'text-slate-700 dark:text-slate-300'}`}>
                      {item.itemName}
                    </div>
                    {item.itemNameEn && (
                      <div className="text-xs text-slate-400 dark:text-slate-500 font-mono mt-0.5">{item.itemNameEn}</div>
                    )}
                  </td>
                  {/* Result + Unit merged */}
                  <td className="px-4 py-3 text-right">
                    <span className={`text-sm font-mono tabular-nums ${
                      isAbnormal
                        ? isHighType
                          ? 'text-red-600 dark:text-red-400 font-bold'
                          : 'text-blue-600 dark:text-blue-400 font-bold'
                        : 'text-slate-800 dark:text-slate-200'
                    }`}>
                      {item.displayValue}
                    </span>
                    {item.unit && (
                      <span className="text-xs text-slate-400 dark:text-slate-500 ml-1">{item.unit}</span>
                    )}
                  </td>
                  {/* Reference range */}
                  <td className="px-4 py-3">
                    <span className="text-xs text-slate-500 dark:text-slate-400 whitespace-nowrap max-w-[180px] truncate block" title={item.referenceRange}>
                      {item.referenceRange || '-'}
                    </span>
                  </td>
                  {/* Range bar */}
                  <td className="px-3 py-3 text-center">
                    <RangeBar value={item.numericValue} min={item.refMin} max={item.refMax} status={item.abnormalStatus} />
                  </td>
                  {/* Status badge */}
                  <td className="px-3 py-3 text-center">
                    <AbnormalBadge status={item.abnormalStatus} text={item.abnormalText} />
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
