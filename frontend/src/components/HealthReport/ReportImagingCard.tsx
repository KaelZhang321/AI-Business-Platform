import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ScanLine, ChevronDown, AlertCircle, CheckCircle } from 'lucide-react';
import type { ImagingSection, DisplayMode } from '../../types/healthReport';
import { GradingBadge } from './AbnormalBadge';

interface ReportImagingCardsProps {
  sections: ImagingSection[];
  displayMode: DisplayMode;
  searchQuery: string;
}

export function ReportImagingCards({ sections, displayMode, searchQuery }: ReportImagingCardsProps) {
  const filtered = sections.filter(s => {
    if (displayMode === 'abnormal' && !s.hasAbnormal) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return s.title.toLowerCase().includes(q) ||
             s.findings.toLowerCase().includes(q);
    }
    return true;
  });

  if (filtered.length === 0) {
    return (
      <div className="bg-white/50 dark:bg-slate-900/50 backdrop-blur-xl rounded-2xl border border-white/60 dark:border-slate-800/60 p-8 text-center">
        <p className="text-sm text-slate-400 dark:text-slate-500">
          {displayMode === 'abnormal' ? '无异常影像发现' : '无匹配的影像检查'}
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {filtered.map((section, idx) => (
        <ImagingCard key={section.title} section={section} index={idx} />
      ))}
    </div>
  );
}

function ImagingCard({ section, index }: { key?: React.Key; section: ImagingSection; index: number }) {
  const [expanded, setExpanded] = useState(section.hasAbnormal);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className={`bg-white/50 dark:bg-slate-900/50 backdrop-blur-xl rounded-2xl border overflow-hidden transition-all hover:shadow-md ${
        section.hasAbnormal
          ? 'border-orange-200 dark:border-orange-800/60'
          : 'border-white/60 dark:border-slate-800/60'
      }`}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 text-left"
      >
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${
            section.hasAbnormal
              ? 'bg-orange-100 dark:bg-orange-900/30'
              : 'bg-emerald-50 dark:bg-emerald-900/20'
          }`}>
            <ScanLine className={`w-4.5 h-4.5 ${
              section.hasAbnormal ? 'text-orange-500' : 'text-emerald-500'
            }`} />
          </div>
          <div>
            <h4 className="text-sm font-bold text-slate-800 dark:text-slate-200">{section.title}</h4>
            <div className="flex items-center gap-2 mt-0.5">
              {section.hasAbnormal ? (
                <span className="text-[10px] text-orange-600 dark:text-orange-400 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />有异常发现
                </span>
              ) : (
                <span className="text-[10px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                  <CheckCircle className="w-3 h-3" />未见明显异常
                </span>
              )}
              {section.grading && (
                <GradingBadge system={section.grading.system} level={section.grading.level} />
              )}
            </div>
          </div>
        </div>
        <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </button>

      {/* Content */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 space-y-3">
              {/* Findings */}
              <div>
                <div className="text-[10px] font-medium text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-1">检查结论</div>
                <div className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed whitespace-pre-line bg-slate-50/80 dark:bg-slate-800/40 rounded-xl p-3">
                  {section.findings.replace(/\r\n/g, '\n')}
                </div>
              </div>

              {/* Description */}
              {section.description && (
                <div>
                  <div className="text-[10px] font-medium text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-1">检查描述</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed whitespace-pre-line bg-slate-50/50 dark:bg-slate-800/20 rounded-xl p-3 max-h-48 overflow-y-auto custom-scrollbar">
                    {section.description.replace(/\r\n/g, '\n')}
                  </div>
                </div>
              )}

              {/* Recommendation */}
              {section.recommendation && (
                <div className="flex items-start gap-2 p-3 rounded-xl bg-brand/5 dark:bg-brand/10 border border-brand/20">
                  <AlertCircle className="w-4 h-4 text-brand shrink-0 mt-0.5" />
                  <span className="text-xs text-brand font-medium">{section.recommendation}</span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
