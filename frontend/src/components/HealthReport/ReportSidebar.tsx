import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Search, ChevronRight, Activity, TestTubes, ScanLine,
  Stethoscope, HeartPulse, Filter, TrendingUp, ClipboardList,
} from 'lucide-react';
import type { ClinicalGroup, DisplayMode } from '../../types/healthReport';

const ICON_MAP: Record<string, React.ElementType> = {
  Activity, TestTubes, ScanLine, Stethoscope, HeartPulse, ClipboardList,
};

interface ReportSidebarProps {
  clinicalGroups: ClinicalGroup[];
  selectedGroupId: string;
  selectedSubGroupId: string | null;
  onSelectGroup: (groupId: string, subGroupId?: string | null) => void;
  displayMode: DisplayMode;
  onDisplayModeChange: (mode: DisplayMode) => void;
  showTrend: boolean;
  onTrendToggle: (show: boolean) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  totalAbnormal: number;
}

export function ReportSidebar({
  clinicalGroups, selectedGroupId, selectedSubGroupId,
  onSelectGroup, displayMode, onDisplayModeChange,
  showTrend, onTrendToggle, searchQuery, onSearchChange, totalAbnormal,
}: ReportSidebarProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(['lab', 'imaging']));

  const toggleExpand = (id: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const allGroups = useMemo(() => {
    const overview: ClinicalGroup = {
      id: 'overview', name: '综合概况', icon: 'ClipboardList',
      subGroups: [], abnormalCount: totalAbnormal, totalCount: 0, type: 'overview',
    };
    return [overview, ...clinicalGroups];
  }, [clinicalGroups, totalAbnormal]);

  return (
    <div className="w-80 shrink-0 flex flex-col h-full bg-white/60 dark:bg-slate-900/60 backdrop-blur-xl border-r border-white/60 dark:border-slate-800/60">
      {/* Search */}
      <div className="p-4 border-b border-slate-100 dark:border-slate-800">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => onSearchChange(e.target.value)}
            placeholder="搜索检查项目..."
            className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-sm text-slate-700 dark:text-slate-300 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand/30 focus:border-brand transition-all"
          />
        </div>
      </div>

      {/* Display Mode */}
      <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-2 mb-2">
          <Filter className="w-3.5 h-3.5 text-slate-400" />
          <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">显示模式</span>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onDisplayModeChange('all')}
            className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium transition-all ${
              displayMode === 'all'
                ? 'bg-brand text-white shadow-sm'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
            }`}
          >
            全部数据
          </button>
          <button
            onClick={() => onDisplayModeChange('abnormal')}
            className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium transition-all ${
              displayMode === 'abnormal'
                ? 'bg-red-500 text-white shadow-sm'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
            }`}
          >
            仅异常项
          </button>
        </div>
      </div>

      {/* Navigation Tree */}
      <nav className="flex-1 overflow-y-auto custom-scrollbar px-2 py-3">
        <div className="px-2 mb-2">
          <span className="text-xs font-medium text-slate-400 dark:text-slate-500 uppercase tracking-wider">临床分组</span>
        </div>
        {allGroups.map(group => {
          const Icon = ICON_MAP[group.icon] || ClipboardList;
          const isSelected = selectedGroupId === group.id && !selectedSubGroupId;
          const isExpanded = expandedGroups.has(group.id);
          const hasSubGroups = group.subGroups.length > 1;

          return (
            <div key={group.id} className="mb-0.5">
              <button
                onClick={() => {
                  onSelectGroup(group.id, null);
                  if (hasSubGroups) toggleExpand(group.id);
                }}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-sm transition-all group ${
                  isSelected
                    ? 'bg-brand/10 text-brand font-medium dark:bg-brand/20'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Icon className={`w-4 h-4 shrink-0 ${isSelected ? 'text-brand' : 'text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300'}`} />
                  <span className="truncate">{group.name}</span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {group.abnormalCount > 0 && (
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                      isSelected ? 'bg-brand text-white' : 'bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400'
                    }`}>
                      {group.abnormalCount}
                    </span>
                  )}
                  {hasSubGroups && (
                    <ChevronRight className={`w-3.5 h-3.5 transition-transform text-slate-400 ${isExpanded ? 'rotate-90' : ''}`} />
                  )}
                </div>
              </button>

              {/* Sub-groups */}
              <AnimatePresence initial={false}>
                {hasSubGroups && isExpanded && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="ml-6 pl-3 border-l border-slate-200 dark:border-slate-700 py-1">
                      {group.subGroups.map(sub => {
                        const isSubSelected = selectedGroupId === group.id && selectedSubGroupId === sub.id;
                        return (
                          <button
                            key={sub.id}
                            onClick={() => onSelectGroup(group.id, sub.id)}
                            className={`w-full flex items-center justify-between px-3 py-1.5 rounded-lg text-xs transition-all ${
                              isSubSelected
                                ? 'bg-brand/10 text-brand font-medium dark:bg-brand/20'
                                : 'text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-slate-700 dark:hover:text-slate-300'
                            }`}
                          >
                            <span className="truncate">{sub.name}</span>
                            {sub.abnormalCount > 0 && (
                              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400">
                                {sub.abnormalCount}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </nav>

      {/* Trend Toggle */}
      <div className="p-4 border-t border-slate-100 dark:border-slate-800">
        <button
          onClick={() => onTrendToggle(!showTrend)}
          className={`w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-xs font-medium transition-all ${
            showTrend
              ? 'bg-brand text-white shadow-sm'
              : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          趋势对比 {showTrend ? '(已开启)' : '(关闭)'}
        </button>
      </div>
    </div>
  );
}
