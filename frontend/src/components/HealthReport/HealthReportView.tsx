import React, { useState, useMemo } from 'react';
import { motion } from 'motion/react';
import { ArrowLeft, Calendar, Package, Hash } from 'lucide-react';
import rawData from '../../data/healthReportRaw.ts';
import { ReportSidebar } from './ReportSidebar';
import { ReportOverview } from './ReportOverview';
import { ReportDataTable } from './ReportDataTable';
import { ReportImagingCards } from './ReportImagingCard';
import { ReportTextSection } from './ReportTextSection';
import { ReportTrendChart } from './ReportTrendChart';
import { ReportFullView } from './ReportFullView';
import { mapReportData } from './reportDataMapper';
import type { DisplayMode, ExamRecord, HealthReportData } from '../../types/healthReport';

interface HealthReportViewProps {
  setCurrentPage: (page: any) => void;
  reportData?: HealthReportData | null;
  examRecords?: ExamRecord[];
  isDarkMode?: boolean;
  setIsDarkMode?: (v: boolean) => void;
  searchQuery?: string;
  onSearchChange?: (value: string) => void;
  displayMode?: DisplayMode;
  onDisplayModeChange?: (mode: DisplayMode) => void;
  showTrend?: boolean;
  onTrendToggle?: (show: boolean) => void;
}

export function HealthReportView({
  setCurrentPage,
  reportData,
  examRecords = [],
  searchQuery,
  onSearchChange,
  displayMode,
  onDisplayModeChange,
  showTrend,
  onTrendToggle,
}: HealthReportViewProps) {
  const [selectedGroupId, setSelectedGroupId] = useState('overview');
  const [selectedSubGroupId, setSelectedSubGroupId] = useState<string | null>(null);
  const [internalDisplayMode, setInternalDisplayMode] = useState<DisplayMode>('all');
  const [internalShowTrend, setInternalShowTrend] = useState(false);
  const [internalSearchQuery, setInternalSearchQuery] = useState('');

  const effectiveDisplayMode = displayMode ?? internalDisplayMode;
  const effectiveShowTrend = showTrend ?? internalShowTrend;
  const effectiveSearchQuery = searchQuery ?? internalSearchQuery;
  const setEffectiveDisplayMode = onDisplayModeChange ?? setInternalDisplayMode;
  const setEffectiveShowTrend = onTrendToggle ?? setInternalShowTrend;
  const setEffectiveSearchQuery = onSearchChange ?? setInternalSearchQuery;

  const activeReportData = useMemo<HealthReportData | null>(() => reportData ?? mapReportData(rawData), [reportData]);

  if (!activeReportData) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-500 dark:text-slate-400">
        暂无体检报告数据。
      </div>
    );
  }

  const handleSelectGroup = (groupId: string, subGroupId?: string | null) => {
    setSelectedGroupId(groupId);
    setSelectedSubGroupId(subGroupId ?? null);
  };

  // Determine which items to show
  const activeContent = useMemo(() => {
    if (selectedGroupId === 'overview') return null;

    const group = activeReportData.clinicalGroups.find(g => g.id === selectedGroupId);
    if (!group) return null;

    if (selectedSubGroupId) {
      const sub = group.subGroups.find(s => s.id === selectedSubGroupId);
      return { group, subGroup: sub || null, items: sub?.items || [] };
    }

    // All items in the group
    const allItems = group.subGroups.flatMap(s => s.items);
    return { group, subGroup: null, items: allItems };
  }, [selectedGroupId, selectedSubGroupId, activeReportData]);

  const renderContent = () => {
    // Overview
    if (selectedGroupId === 'overview') {
      return <ReportOverview data={activeReportData} />;
    }

    if (!activeContent) return null;
    const { group, subGroup, items } = activeContent;
    const title = subGroup ? `${group.name} - ${subGroup.name}` : group.name;

    // Imaging
    if (group.type === 'imaging') {
      return (
        <ReportImagingCards
          sections={activeReportData.imagingSections}
          displayMode={effectiveDisplayMode}
          searchQuery={effectiveSearchQuery}
        />
      );
    }

    // Text-based (specialty, health)
    if (group.type === 'text') {
      return (
        <ReportTextSection
          items={items}
          displayMode={effectiveDisplayMode}
          searchQuery={effectiveSearchQuery}
          title={title}
        />
      );
    }

    // Table (vitals, lab)
    return (
      <ReportDataTable
        items={items}
        displayMode={effectiveDisplayMode}
        searchQuery={effectiveSearchQuery}
        title={title}
      />
    );
  };

  return (
    <div className="flex h-full -mx-8 -mt-8">
      {/* Sidebar */}
      <ReportSidebar
        clinicalGroups={activeReportData.clinicalGroups}
        selectedGroupId={selectedGroupId}
        selectedSubGroupId={selectedSubGroupId}
        onSelectGroup={handleSelectGroup}
        displayMode={effectiveDisplayMode}
        onDisplayModeChange={setEffectiveDisplayMode}
        showTrend={effectiveShowTrend}
        onTrendToggle={setEffectiveShowTrend}
        searchQuery={effectiveSearchQuery}
        onSearchChange={setEffectiveSearchQuery}
        totalAbnormal={activeReportData.totalAbnormal}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 bg-white/40 dark:bg-slate-900/40 backdrop-blur-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setCurrentPage('dashboard')}
                className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-lg font-bold text-slate-800 dark:text-slate-200">体检报告详情</h1>
                <div className="flex items-center gap-4 mt-1">
                  <span className="text-xs text-slate-400 dark:text-slate-500 flex items-center gap-1">
                    <Hash className="w-3 h-3" />{activeReportData.studyId}
                  </span>
                  <span className="text-xs text-slate-400 dark:text-slate-500 flex items-center gap-1">
                    <Calendar className="w-3 h-3" />{activeReportData.examTime}
                  </span>
                  <span className="text-xs text-slate-400 dark:text-slate-500 flex items-center gap-1">
                    <Package className="w-3 h-3" />{activeReportData.packageName}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <div className="text-xs text-slate-400 dark:text-slate-500">异常项目</div>
                <div className="text-lg font-bold text-red-500">{activeReportData.totalAbnormal}</div>
              </div>
              <div className="w-px h-8 bg-slate-200 dark:bg-slate-700" />
              <div className="text-right">
                <div className="text-xs text-slate-400 dark:text-slate-500">检查项目</div>
                <div className="text-lg font-bold text-slate-700 dark:text-slate-300">{activeReportData.totalItems}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Scrollable Content */}
        <motion.div
          key={`${selectedGroupId}-${selectedSubGroupId}`}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="flex-1 overflow-y-auto custom-scrollbar p-6 space-y-4"
        >
          {selectedGroupId === 'overview' && examRecords.length > 0 ? (
            <ReportFullView
              examRecords={examRecords}
              displayMode={effectiveDisplayMode}
              searchQuery={effectiveSearchQuery}
            />
          ) : (
            renderContent()
          )}

          {/* Trend Chart (conditional) */}
          {effectiveShowTrend && <ReportTrendChart />}
        </motion.div>
      </div>
    </div>
  );
}
