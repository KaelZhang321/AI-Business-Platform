import React from 'react';
import { motion } from 'motion/react';
import { FileText } from 'lucide-react';
import type { ParsedItem, DisplayMode } from '../../types/healthReport';
import { AbnormalBadge } from './AbnormalBadge';

interface ReportTextSectionProps {
  items: ParsedItem[];
  displayMode: DisplayMode;
  searchQuery: string;
  title: string;
}

export function ReportTextSection({ items, displayMode, searchQuery, title }: ReportTextSectionProps) {
  const filtered = items.filter(item => {
    if (displayMode === 'abnormal' && (!item.abnormalStatus || item.abnormalStatus === 'normal')) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return item.itemName.toLowerCase().includes(q) ||
             (item.rawValue || '').toLowerCase().includes(q);
    }
    return true;
  });

  if (filtered.length === 0) {
    return (
      <div className="bg-white/50 dark:bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/60 dark:border-slate-800/60 p-8 text-center">
        <p className="text-sm text-slate-400 dark:text-slate-500">
          {displayMode === 'abnormal' ? '该分组无异常项目' : '无匹配的检查项目'}
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white/50 dark:bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/60 dark:border-slate-800/60 overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
          <FileText className="w-4 h-4 text-brand" />
          {title}
        </h3>
        <span className="text-xs text-slate-400">{filtered.length} 项</span>
      </div>
      <div className="divide-y divide-slate-100 dark:divide-slate-800/50">
        {filtered.map((item, idx) => (
          <motion.div
            key={`${item.itemCode}-${item.itemName}-${idx}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: idx * 0.03 }}
            className="px-5 py-3 hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{item.itemName}</span>
                  <AbnormalBadge status={item.abnormalStatus} text={item.abnormalText} />
                </div>
                {item.rawValue && (
                  <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed whitespace-pre-line">
                    {item.rawValue.replace(/\r\n/g, '\n')}
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
