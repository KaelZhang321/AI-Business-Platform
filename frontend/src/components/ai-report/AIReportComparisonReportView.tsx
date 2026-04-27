import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  Activity,
  ArrowLeft,
  BarChart3,
  Bot,
  Brain,
  ChevronDown,
  ChevronLeft,
  Layers,
  List,
  Search,
  Send,
  Sparkles,
  TestTubeDiagonal,
  User,
  Waves,
  HeartPulse,
  Stethoscope,
  ClipboardList,
  X,
} from 'lucide-react';
import { GoogleGenAI, Type } from '@google/genai';
import { aiReportApi } from '../../services/api/aiReportApi';
import CardSwap, { Card, type CardSwapRef } from './CardSwap';
import type { CustomerRecord } from './detailView/types';
import { ReportHeader } from './reportview/ReportHeader';
import { TrendChart } from './reportview/TrendChart';
import { ReportOverview } from '../HealthReport/ReportOverview';
import { ReportDataTable } from '../HealthReport/ReportDataTable';
import { ReportImagingCards } from '../HealthReport/ReportImagingCard';
import { ReportTextSection } from '../HealthReport/ReportTextSection';
import { ReportFullView } from '../HealthReport/ReportFullView';
import { ImagingCompare } from '../HealthReport/ImagingCompare';
import {
  mapMetricSeriesFromExamRecords,
  mapReportSessionsToExamRecords,
} from '../HealthReport/reportDataMapper';
import type {
  DisplayMode,
  ExamRecord,
  MetricSeries,
} from '../../types/healthReport';

type ChatMessage = {
  role: 'user' | 'ai';
  content: string;
};

type MetricData = {
  name: string;
  unit: string;
  refRange: string;
  values: Record<string, number | string>;
  judgment: 'high' | 'low' | 'normal';
  trend: string;
};

type BatchSessionResponse = {
  studyId?: string | null;
  orderCode?: string | null;
  examTime?: string | null;
  packageCode?: string | null;
  packageName?: string | null;
  abnormalSummary?: string | null;
  finalConclusion?: string | null;
  abnormalCount?: number | null;
  departments?: Array<{
    departmentCode?: string | null;
    departmentName?: string | null;
    sourceTable?: string | null;
    items?: Array<{
      majorItemCode?: string | null;
      majorItemName?: string | null;
      itemCode?: string | null;
      itemName?: string | null;
      itemNameEn?: string | null;
      resultValue?: string | null;
      unit?: string | null;
      referenceRange?: string | null;
      abnormalFlag?: string | null;
    }>;
  }>;
};

type PatientExamSessionSummary = {
  studyId?: string | null;
  examTime?: string | null;
  packageName?: string | null;
  abnormalSummary?: string | null;
  finalConclusion?: string | null;
  abnormalCount?: number | null;
};

type CardConfig = {
  id: string;
  name: string;
  icon: React.ElementType;
  iconBg: string;
  accent: string;
};

const DEFAULT_MESSAGES: ChatMessage[] = [
  {
    role: 'ai',
    content: '您好！我是您的 AI 健康助手。您可以询问我关于体检报告中的具体指标，我会结合已加载的多次体检结果给出趋势解读。',
  },
];

let ai: GoogleGenAI | null = null;
try {
  ai = new GoogleGenAI({ apiKey: import.meta.env.VITE_GEMINI_API_KEY ?? '' });
} catch {
  ai = null;
}

const CARD_CONFIGS: CardConfig[] = [
  { id: 'overview', name: '综合概况', icon: ClipboardList, iconBg: 'bg-brand/10 text-brand', accent: 'border-t-brand' },
  { id: 'vitals', name: '基础体征', icon: Activity, iconBg: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300', accent: 'border-t-emerald-500' },
  { id: 'lab', name: '实验室检验', icon: TestTubeDiagonal, iconBg: 'bg-violet-100 text-violet-600 dark:bg-violet-950/40 dark:text-violet-300', accent: 'border-t-violet-500' },
  { id: 'imaging', name: '影像检查', icon: Waves, iconBg: 'bg-amber-100 text-amber-600 dark:bg-amber-950/40 dark:text-amber-300', accent: 'border-t-amber-500' },
  { id: 'specialty', name: '专科检查', icon: Stethoscope, iconBg: 'bg-rose-100 text-rose-600 dark:bg-rose-950/40 dark:text-rose-300', accent: 'border-t-rose-500' },
  { id: 'health', name: '健康评估', icon: HeartPulse, iconBg: 'bg-cyan-100 text-cyan-600 dark:bg-cyan-950/40 dark:text-cyan-300', accent: 'border-t-cyan-500' },
  { id: 'trend-compare', name: '历年数据对比', icon: BarChart3, iconBg: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300', accent: 'border-t-slate-500' },
];

interface AIReportComparisonReportViewProps {
  customer: CustomerRecord;
  onBack: () => void;
  isDarkMode: boolean;
  setIsDarkMode: (value: boolean) => void;
}

function buildAiContext(examRecords: ExamRecord[]) {
  const latest = examRecords[0];
  const metrics = mapMetricSeriesFromExamRecords(examRecords).slice(0, 40);
  return {
    patient: latest
      ? {
          examDate: latest.examDate,
          packageName: latest.packageName,
          totalAbnormal: latest.reportData?.totalAbnormal ?? 0,
          conclusions: latest.reportData?.conclusions.map((item) => item.text).slice(0, 10) ?? [],
        }
      : null,
    metrics: metrics.map((metric) => ({
      name: metric.name,
      unit: metric.unit,
      referenceRange: metric.refRange,
      trend: metric.trend,
      latestValue: metric.latestValue,
      abnormalYears: metric.abnormalYears,
      values: metric.values,
    })),
  };
}

function buildTrendSummary(metricSeries: MetricSeries[]) {
  const abnormalMetrics = metricSeries.filter((metric) => metric.judgment !== 'normal');
  if (abnormalMetrics.length === 0) {
    return '近几次体检未发现明确的连续异常指标。';
  }

  return abnormalMetrics
    .slice(0, 6)
    .map((metric) => `${metric.name}${metric.trend ? `：${metric.trend}` : ''}`)
    .join('；');
}

function toMetricData(metricSeries: MetricSeries[]): MetricData[] {
  return metricSeries
    .filter((metric) => Object.keys(metric.values).length > 0)
    .map((metric) => ({
      name: metric.name,
      unit: metric.unit,
      refRange: metric.refRange,
      values: metric.values,
      judgment: metric.judgment,
      trend: metric.trend,
    }));
}

function getYearLabel(examRecords: ExamRecord[]) {
  const years = Array.from(new Set(examRecords.map((record) => record.year).filter(Boolean))).sort((a, b) => Number(b) - Number(a));
  if (years.length === 0) return '暂无数据';
  if (years.length === 1) return years[0];
  return `${years[years.length - 1]}-${years[0]}`;
}

function getMetricValue(metric: MetricData, year: string | undefined) {
  if (!year) return null;
  const value = metric.values[year];
  return value == null ? null : value;
}

function parseRefRange(refRange: string) {
  const parts = refRange.split(/[-–~]/).map((part) => Number(part.trim()));
  return {
    min: Number.isFinite(parts[0]) ? parts[0] : null,
    max: Number.isFinite(parts[1]) ? parts[1] : null,
  };
}

function judgeMetric(metric: MetricData, year: string | undefined) {
  const value = getMetricValue(metric, year);
  const numeric = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(numeric)) return 'normal' as const;
  const { min, max } = parseRefRange(metric.refRange);
  if (max != null && numeric > max) return 'high' as const;
  if (min != null && numeric < min) return 'low' as const;
  return 'normal' as const;
}

function getJudgmentLabel(judgment: 'high' | 'low' | 'normal') {
  if (judgment === 'high') return '偏高';
  if (judgment === 'low') return '偏低';
  return '正常';
}

function getJudgmentClass(judgment: 'high' | 'low' | 'normal') {
  if (judgment === 'high') return 'bg-rose-50 text-rose-600 dark:bg-rose-950/40 dark:text-rose-300';
  if (judgment === 'low') return 'bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-300';
  return 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300';
}

function getGroupForExam(exam: ExamRecord, groupId: string) {
  return exam.reportData?.clinicalGroups.find((group) => group.id === groupId) ?? null;
}

function buildGroupPreviewLines(exam: ExamRecord, groupId: string, metrics: MetricData[]) {
  if (!exam.reportData) return [] as string[];

  if (groupId === 'overview') {
    return exam.reportData.conclusions.slice(0, 5).map((item) => item.text);
  }

  if (groupId === 'trend-compare') {
    return metrics.slice(0, 5).map((metric) => {
      const value = getMetricValue(metric, exam.year);
      return `${metric.name}：${value ?? '-'}${metric.unit ? ` ${metric.unit}` : ''}`;
    });
  }

  const group = getGroupForExam(exam, groupId);
  if (!group) return [];

  return group.subGroups.slice(0, 6).map((subGroup) => {
    if (subGroup.abnormalCount > 0) {
      return `${subGroup.name}（${subGroup.abnormalCount}异常）`;
    }
    return subGroup.name;
  });
}

function buildFallbackReply(metricName: string | null) {
  if (!metricName) {
    return '已结合当前体检记录完成初步分析。您也可以直接询问某个具体指标，例如空腹血糖、尿酸、ALT。';
  }
  return `已切换到 ${metricName} 的历年趋势视图，您可以继续追问该指标的风险、变化原因或复查建议。`;
}

export const AIReportComparisonReportView: React.FC<AIReportComparisonReportViewProps> = ({
  customer,
  onBack,
  isDarkMode,
  setIsDarkMode,
}) => {
  const chatEndRef = useRef<HTMLDivElement>(null);
  const cardSwapRef = useRef<CardSwapRef>(null);

  const [messages, setMessages] = useState<ChatMessage[]>(DEFAULT_MESSAGES);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [reportSearchQuery, setReportSearchQuery] = useState('');
  const [clinicalDisplayMode, setClinicalDisplayMode] = useState<DisplayMode>('all');
  const [selectedExamIds, setSelectedExamIds] = useState<Set<string>>(new Set());
  const [examRecords, setExamRecords] = useState<ExamRecord[]>([]);
  const [isLoadingReports, setIsLoadingReports] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [focusedMetricName, setFocusedMetricName] = useState<string | null>(null);
  const [selectedGroupId, setSelectedGroupId] = useState<string>('');
  const [selectedSubGroupId, setSelectedSubGroupId] = useState<string | null>(null);
  const [selectedYearForModal, setSelectedYearForModal] = useState<string | null>(null);
  const [cardViewMode, setCardViewMode] = useState<'stack' | 'full'>('stack');
  const [currentCardIdx, setCurrentCardIdx] = useState(0);
  const [expandedExams, setExpandedExams] = useState<Record<string, Set<string>>>({});
  const [showCardSearch, setShowCardSearch] = useState(false);
  const [showImagingCompare, setShowImagingCompare] = useState(false);
  const [modalFilter, setModalFilter] = useState<'all' | 'abnormal'>('all');

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    let cancelled = false;

    const loadReports = async () => {
      const encryptedIdCard = customer.encryptedIdCard?.trim();
      if (!encryptedIdCard) {
        setLoadError('当前客户缺少可查询的身份证信息，无法加载体检报告。');
        setIsLoadingReports(false);
        return;
      }

      setIsLoadingReports(true);
      setLoadError(null);

      try {
        const rawSessions = await aiReportApi.getPatientExamSessionsApi({ idCard: encryptedIdCard });
        const sessions = (Array.isArray(rawSessions) ? rawSessions : []) as PatientExamSessionSummary[];
        const studyIds = sessions
          .map((session) => session.studyId?.trim())
          .filter((studyId): studyId is string => Boolean(studyId))
          .slice(0, 10);

        if (studyIds.length === 0) {
          if (!cancelled) {
            setExamRecords([]);
            setSelectedExamIds(new Set());
            setLoadError('未查询到该客户的体检记录。');
          }
          return;
        }

        const rawResults = await aiReportApi.getPatientExamListApi({
          idCard: encryptedIdCard,
          studyIds,
        });

        const sessionsWithResults = (Array.isArray(rawResults) ? rawResults : []) as BatchSessionResponse[];
        const mappedRecords = mapReportSessionsToExamRecords(sessionsWithResults);

        if (!cancelled) {
          setExamRecords(mappedRecords);
          const defaultSelected = new Set(mappedRecords.slice(0, Math.min(2, mappedRecords.length)).map((record) => record.id));
          setSelectedExamIds(defaultSelected);
          setExpandedExams(
            Object.fromEntries(
              CARD_CONFIGS.map((config) => [config.id, new Set(mappedRecords[0] ? [mappedRecords[0].id] : [])]),
            ),
          );
          if (mappedRecords.length === 0) {
            setLoadError('体检结果接口返回为空。');
          }
        }
      } catch (error) {
        console.error('loadReports error:', error);
        if (!cancelled) {
          setExamRecords([]);
          setSelectedExamIds(new Set());
          setLoadError('体检报告加载失败，请稍后重试。');
        }
      } finally {
        if (!cancelled) {
          setIsLoadingReports(false);
        }
      }
    };

    void loadReports();

    return () => {
      cancelled = true;
    };
  }, [customer.encryptedIdCard]);

  const latestReport = examRecords[0]?.reportData ?? null;
  const metricSeries = useMemo(() => mapMetricSeriesFromExamRecords(examRecords), [examRecords]);
  const metrics = useMemo(() => toMetricData(metricSeries), [metricSeries]);
  const trendSummary = useMemo(() => buildTrendSummary(metricSeries), [metricSeries]);
  const availableYearsDesc = useMemo(
    () => Array.from(new Set(examRecords.map((record) => record.year).filter(Boolean))).sort((a, b) => Number(b) - Number(a)),
    [examRecords],
  );
  const availableYearsAsc = useMemo(() => [...availableYearsDesc].reverse(), [availableYearsDesc]);
  const yearRangeLabel = useMemo(() => getYearLabel(examRecords), [examRecords]);
  const selectedExamRecords = useMemo(() => {
    if (selectedExamIds.size === 0) {
      return examRecords.slice(0, 1);
    }
    return examRecords.filter((record) => selectedExamIds.has(record.id));
  }, [examRecords, selectedExamIds]);

  const activeContent = useMemo(() => {
    if (!latestReport || !selectedGroupId || selectedGroupId === 'overview' || selectedGroupId === 'trend-compare') {
      return null;
    }
    const group = latestReport.clinicalGroups.find((item) => item.id === selectedGroupId);
    if (!group) return null;
    if (selectedSubGroupId) {
      const subGroup = group.subGroups.find((item) => item.id === selectedSubGroupId) ?? null;
      return { group, subGroup, items: subGroup?.items ?? [] };
    }
    return { group, subGroup: null, items: group.subGroups.flatMap((item) => item.items) };
  }, [latestReport, selectedGroupId, selectedSubGroupId]);

  const focusedMetric = useMemo(
    () => metrics.find((metric) => metric.name === focusedMetricName) ?? null,
    [focusedMetricName, metrics],
  );

  const latestYear = availableYearsDesc[0];
  const previousYear = availableYearsDesc[1];
  const currentModalMetrics = useMemo(() => {
    if (!selectedYearForModal) return metrics;
    if (modalFilter === 'all') return metrics;
    return metrics.filter((metric) => judgeMetric(metric, selectedYearForModal) !== 'normal');
  }, [metrics, modalFilter, selectedYearForModal]);

  const completenessLabel = availableYearsDesc.length >= 3 ? '近三年报告完整' : `已加载 ${availableYearsDesc.length} 次记录`;

  const toggleExamSelection = (examId: string) => {
    setSelectedExamIds((prev) => {
      const next = new Set(prev);
      if (next.has(examId)) {
        if (next.size > 1) {
          next.delete(examId);
        }
      } else {
        next.add(examId);
      }
      return next;
    });
  };

  const toggleExpandedExam = (cardId: string, examId: string) => {
    setExpandedExams((prev) => {
      const current = new Set(prev[cardId] ?? []);
      if (current.has(examId)) {
        current.delete(examId);
      } else {
        current.add(examId);
      }
      return { ...prev, [cardId]: current };
    });
  };

  const isExpandedExam = (cardId: string, examId: string) => {
    const set = expandedExams[cardId];
    if (!set) return examRecords[0]?.id === examId;
    return set.has(examId);
  };

  const handleSendMessage = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (!inputValue.trim() || isTyping) {
      return;
    }

    const userMessage = inputValue.trim();
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
    setInputValue('');
    setIsTyping(true);

    try {
      let reply = '';
      let focusedMetricFromAi: string | null = null;

      if (ai) {
        const response = await ai.models.generateContent({
          model: 'gemini-2.5-flash',
          contents: userMessage,
          config: {
            systemInstruction: `你是专业体检报告分析助手。请严格基于提供的体检报告摘要回答，不要编造不存在的指标或年份。\n可识别的重点指标包括：${metrics.map((metric) => metric.name).join('、')}。\n${JSON.stringify(buildAiContext(examRecords))}`,
            responseMimeType: 'application/json',
            responseSchema: {
              type: Type.OBJECT,
              properties: {
                reply: { type: Type.STRING },
                focusedMetric: { type: Type.STRING, nullable: true },
              },
              required: ['reply', 'focusedMetric'],
            },
          },
        });
        const result = JSON.parse(response.text || '{}') as { reply?: string; focusedMetric?: string | null };
        reply = result.reply || '';
        focusedMetricFromAi = result.focusedMetric ?? null;
      }

      if (!focusedMetricFromAi) {
        focusedMetricFromAi = metrics.find((metric) => userMessage.includes(metric.name))?.name ?? null;
      }
      if (!reply) {
        reply = buildFallbackReply(focusedMetricFromAi);
      }

      setMessages((prev) => [...prev, { role: 'ai', content: reply }]);
      if (focusedMetricFromAi) {
        setFocusedMetricName(focusedMetricFromAi);
      }
    } catch (error) {
      console.error('AI Chat Error:', error);
      setMessages((prev) => [...prev, { role: 'ai', content: '抱歉，当前无法完成智能分析，请稍后重试。' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const resetView = () => {
    setClinicalDisplayMode('all');
    setReportSearchQuery('');
    setMessages(DEFAULT_MESSAGES);
    setFocusedMetricName(null);
    setSelectedGroupId('');
    setSelectedSubGroupId(null);
    setSelectedYearForModal(null);
    setCardViewMode('stack');
    setShowCardSearch(false);
    setShowImagingCompare(false);
  };

  const renderLoadingState = () => (
    <div className="flex min-h-[560px] items-center justify-center rounded-[32px] border border-slate-200 bg-white/80 text-sm text-slate-500 shadow-sm dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-400">
      正在加载体检报告...
    </div>
  );

  const renderErrorState = () => (
    <div className="flex min-h-[560px] flex-col items-center justify-center gap-4 rounded-[32px] border border-rose-200 bg-white/80 px-6 text-center shadow-sm dark:border-rose-900/60 dark:bg-slate-900/80">
      <div className="text-base font-semibold text-rose-600 dark:text-rose-400">{loadError}</div>
      <button
        type="button"
        onClick={onBack}
        className="rounded-xl bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
      >
        返回客户列表
      </button>
    </div>
  );

  const renderEmptyState = () => (
    <div className="flex min-h-[560px] items-center justify-center rounded-[32px] border border-slate-200 bg-white/80 text-sm text-slate-500 shadow-sm dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-400">
      暂无可展示的体检报告。
    </div>
  );

  const renderDetailContent = () => {
    if (!latestReport) return null;

    if (selectedGroupId === 'overview') {
      return <ReportOverview data={latestReport} />;
    }

    if (selectedGroupId === 'trend-compare') {
      return (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {metrics.map((metric) => {
            const judgment = judgeMetric(metric, latestYear);
            return (
              <button
                key={metric.name}
                type="button"
                onClick={() => setFocusedMetricName(metric.name)}
                className="rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md dark:border-slate-700 dark:bg-slate-800/60"
              >
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <div className="text-base font-bold text-slate-900 dark:text-white">{metric.name}</div>
                    <div className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                      参考范围 {metric.refRange} {metric.unit}
                    </div>
                  </div>
                  <span className={`rounded-lg px-2 py-1 text-[10px] font-bold ${getJudgmentClass(judgment)}`}>
                    {getJudgmentLabel(judgment)}
                  </span>
                </div>
                <TrendChart m={metric} yearsToShow={availableYearsAsc} />
                <div className="mt-3 text-xs leading-5 text-slate-500 dark:text-slate-300">{metric.trend}</div>
              </button>
            );
          })}
        </div>
      );
    }

    if (!activeContent) {
      return null;
    }

    if (activeContent.group.type === 'imaging') {
      const previousReport = examRecords[1]?.reportData ?? null;
      return (
        <div className="space-y-4">
          {previousReport ? (
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setShowImagingCompare((prev) => !prev)}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${showImagingCompare ? 'bg-brand text-white' : 'bg-brand/10 text-brand hover:bg-brand/20'}`}
              >
                <BarChart3 className="h-3.5 w-3.5" />
                {showImagingCompare ? '返回列表' : '影像对比'}
              </button>
            </div>
          ) : null}
          {showImagingCompare && previousReport ? (
            <ImagingCompare
              currentSections={latestReport.imagingSections}
              previousSections={previousReport.imagingSections}
              currentLabel={examRecords[0]?.examDate || ''}
              previousLabel={examRecords[1]?.examDate || ''}
              onClose={() => setShowImagingCompare(false)}
            />
          ) : (
            <ReportImagingCards sections={latestReport.imagingSections} displayMode={clinicalDisplayMode} searchQuery={reportSearchQuery} />
          )}
        </div>
      );
    }

    if (activeContent.group.type === 'text') {
      return (
        <ReportTextSection
          items={activeContent.items}
          displayMode={clinicalDisplayMode}
          searchQuery={reportSearchQuery}
          title={activeContent.subGroup ? `${activeContent.group.name} - ${activeContent.subGroup.name}` : activeContent.group.name}
        />
      );
    }

    return (
      <ReportDataTable
        items={activeContent.items}
        displayMode={clinicalDisplayMode}
        searchQuery={reportSearchQuery}
        title={activeContent.subGroup ? `${activeContent.group.name} - ${activeContent.subGroup.name}` : activeContent.group.name}
      />
    );
  };

  const renderFocusedMetricOverlay = () => {
    if (!focusedMetric) return null;
    const latestValue = getMetricValue(focusedMetric, latestYear);
    const previousValue = getMetricValue(focusedMetric, previousYear);
    const judgment = judgeMetric(focusedMetric, latestYear);
    const latestNumeric = typeof latestValue === 'number' ? latestValue : Number(latestValue);
    const previousNumeric = typeof previousValue === 'number' ? previousValue : Number(previousValue);
    const diff = Number.isFinite(latestNumeric) && Number.isFinite(previousNumeric) ? latestNumeric - previousNumeric : null;

    return (
      <motion.div
        key="focused-metric"
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        className="absolute inset-0 z-20 overflow-hidden rounded-[32px] border border-slate-200 bg-white p-8 shadow-xl dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="flex h-full flex-col">
          <div className="mb-8 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand/10 text-brand">
                <Sparkles className="h-7 w-7" />
              </div>
              <div>
                <h2 className="text-2xl font-black text-slate-900 dark:text-white">{focusedMetric.name}</h2>
                <p className="mt-1 text-sm font-semibold text-slate-500 dark:text-slate-400">
                  参考范围：{focusedMetric.refRange} {focusedMetric.unit}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setFocusedMetricName(null)}
              className="rounded-xl bg-slate-100 p-2.5 text-slate-500 transition-colors hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className={`rounded-2xl border p-6 ${judgment === 'high' ? 'border-rose-200 bg-rose-50 dark:border-rose-900/40 dark:bg-rose-950/20' : judgment === 'low' ? 'border-amber-200 bg-amber-50 dark:border-amber-900/40 dark:bg-amber-950/20' : 'border-emerald-200 bg-emerald-50 dark:border-emerald-900/40 dark:bg-emerald-950/20'}`}>
              <div className="text-sm font-bold text-slate-500 dark:text-slate-400">最新数值（{latestYear ?? '-'}）</div>
              <div className="mt-3 flex items-end gap-2">
                <div className="text-5xl font-black text-slate-900 dark:text-white">{latestValue ?? '-'}</div>
                <div className="mb-1 text-sm font-bold text-slate-500 dark:text-slate-400">{focusedMetric.unit}</div>
              </div>
              <div className={`mt-4 inline-flex rounded-lg px-3 py-1 text-xs font-bold ${getJudgmentClass(judgment)}`}>
                {getJudgmentLabel(judgment)}
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-6 dark:border-slate-700 dark:bg-slate-800/60">
              <div className="text-sm font-bold text-slate-500 dark:text-slate-400">上一年度（{previousYear ?? '-'}）</div>
              <div className="mt-3 flex items-end gap-2">
                <div className="text-5xl font-black text-slate-900 dark:text-white">{previousValue ?? '-'}</div>
                <div className="mb-1 text-sm font-bold text-slate-500 dark:text-slate-400">{focusedMetric.unit}</div>
              </div>
              {diff != null ? (
                <div className={`mt-4 text-sm font-bold ${diff > 0 ? 'text-rose-500' : diff < 0 ? 'text-emerald-500' : 'text-slate-400'}`}>
                  较去年 {diff > 0 ? '↑' : diff < 0 ? '↓' : ''} {Math.abs(diff).toFixed(2)}
                </div>
              ) : null}
            </div>
          </div>

          <div className="flex min-h-0 flex-1 flex-col rounded-2xl border border-slate-200 bg-slate-50 p-6 dark:border-slate-700 dark:bg-slate-800/40">
            <div className="mb-5 text-sm font-bold uppercase tracking-widest text-slate-500 dark:text-slate-400">历年趋势</div>
            <div className="min-h-0 flex-1 overflow-x-auto pb-2 custom-scrollbar">
              <div className="flex h-full min-w-[720px] items-center justify-center">
                <TrendChart m={focusedMetric} yearsToShow={availableYearsAsc} isExpanded={true} className="h-full w-full max-h-[220px]" />
              </div>
            </div>
            <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
              <span className="mr-2 font-bold text-brand">AI 分析：</span>
              {focusedMetric.trend}
            </div>
          </div>
        </div>
      </motion.div>
    );
  };

  const renderComparisonModal = () => {
    if (!selectedYearForModal) return null;

    return (
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[120] flex items-center justify-center bg-slate-950/60 p-6 backdrop-blur-sm"
        >
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.96 }}
            className="flex h-[86vh] w-full max-w-[92vw] flex-col overflow-hidden rounded-[32px] border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900"
          >
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5 dark:border-slate-700">
              <div>
                <div className="text-xl font-black text-slate-900 dark:text-white">历年指标深度对比</div>
                <div className="mt-1 text-xs font-semibold uppercase tracking-widest text-slate-500 dark:text-slate-400">
                  以 {selectedYearForModal} 年度为核心
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
                  <button
                    type="button"
                    onClick={() => setModalFilter('all')}
                    className={`rounded-lg px-4 py-2 text-xs font-bold transition-all ${modalFilter === 'all' ? 'bg-white text-brand shadow-sm dark:bg-slate-700' : 'text-slate-500 dark:text-slate-400'}`}
                  >
                    全部指标
                  </button>
                  <button
                    type="button"
                    onClick={() => setModalFilter('abnormal')}
                    className={`rounded-lg px-4 py-2 text-xs font-bold transition-all ${modalFilter === 'abnormal' ? 'bg-rose-500 text-white shadow-sm' : 'text-slate-500 dark:text-slate-400'}`}
                  >
                    异常关注
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedYearForModal(null)}
                  className="rounded-xl bg-slate-100 p-2.5 text-slate-500 transition-colors hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-auto p-6 custom-scrollbar">
              <table className="min-w-full border-separate border-spacing-0 overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-700">
                <thead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-900">
                  <tr>
                    <th className="border-b border-slate-200 px-4 py-3 text-left text-xs font-bold uppercase tracking-wider text-slate-500 dark:border-slate-700">指标项</th>
                    <th className="border-b border-slate-200 px-4 py-3 text-left text-xs font-bold uppercase tracking-wider text-slate-500 dark:border-slate-700">参考范围</th>
                    {availableYearsAsc.map((year) => (
                      <th key={year} className="border-b border-slate-200 px-4 py-3 text-center text-xs font-bold uppercase tracking-wider text-slate-500 dark:border-slate-700">
                        {year}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {currentModalMetrics.map((metric) => (
                    <tr key={metric.name} className="bg-white transition-colors hover:bg-slate-50 dark:bg-slate-900 dark:hover:bg-slate-800/50">
                      <td className="border-b border-slate-100 px-4 py-3 text-sm font-bold text-slate-900 dark:border-slate-800 dark:text-white">{metric.name}</td>
                      <td className="border-b border-slate-100 px-4 py-3 text-sm text-slate-500 dark:border-slate-800 dark:text-slate-400">{metric.refRange}</td>
                      {availableYearsAsc.map((year) => {
                        const judgment = judgeMetric(metric, year);
                        return (
                          <td key={`${metric.name}-${year}`} className="border-b border-slate-100 px-4 py-3 text-center text-sm dark:border-slate-800">
                            <div className="font-bold text-slate-900 dark:text-white">{getMetricValue(metric, year) ?? '-'}</div>
                            <div className={`mt-1 inline-flex rounded-md px-2 py-0.5 text-[10px] font-bold ${getJudgmentClass(judgment)}`}>
                              {getJudgmentLabel(judgment)}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.div>
        </motion.div>
      </AnimatePresence>
    );
  };

  const renderRightPanel = () => {
    if (!latestReport) return null;

    return (
      <div className="relative min-h-[620px] w-full overflow-hidden">
        <AnimatePresence mode="wait">
          {selectedGroupId ? (
            <motion.div
              key={`detail-${selectedGroupId}-${selectedSubGroupId}`}
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.97 }}
              className="absolute inset-0 z-10 flex flex-col overflow-hidden rounded-[32px] border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900"
            >
              <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 dark:border-slate-800">
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedGroupId('');
                      setSelectedSubGroupId(null);
                    }}
                    className="rounded-xl p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
                  >
                    <ArrowLeft className="h-4 w-4" />
                  </button>
                  <div>
                    <div className="text-lg font-black text-slate-900 dark:text-white">
                      {selectedGroupId === 'overview'
                        ? '综合概况'
                        : selectedGroupId === 'trend-compare'
                          ? '历年数据对比'
                          : activeContent?.subGroup
                            ? `${activeContent.group.name} - ${activeContent.subGroup.name}`
                            : activeContent?.group.name || ''}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {selectedGroupId !== 'overview' && selectedGroupId !== 'trend-compare' ? (
                    <>
                      <div className="relative">
                        <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                        <input
                          type="text"
                          value={reportSearchQuery}
                          onChange={(event) => setReportSearchQuery(event.target.value)}
                          placeholder="搜索..."
                          className="w-40 rounded-lg border border-slate-100 bg-slate-50 py-1.5 pl-8 pr-3 text-xs text-slate-700 outline-none transition-all focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                        />
                      </div>
                      <div className="flex rounded-lg bg-slate-100 p-0.5 dark:bg-slate-800">
                        <button
                          type="button"
                          onClick={() => setClinicalDisplayMode('all')}
                          className={`rounded-md px-2.5 py-1 text-[10px] font-bold transition-all ${clinicalDisplayMode === 'all' ? 'bg-white text-brand shadow-sm dark:bg-slate-700' : 'text-slate-500 dark:text-slate-400'}`}
                        >
                          全部
                        </button>
                        <button
                          type="button"
                          onClick={() => setClinicalDisplayMode('abnormal')}
                          className={`rounded-md px-2.5 py-1 text-[10px] font-bold transition-all ${clinicalDisplayMode === 'abnormal' ? 'bg-white text-rose-500 shadow-sm dark:bg-slate-700' : 'text-slate-500 dark:text-slate-400'}`}
                        >
                          异常
                        </button>
                      </div>
                    </>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedGroupId('');
                      setSelectedSubGroupId(null);
                    }}
                    className="rounded-xl bg-slate-100 p-2 text-slate-500 transition-colors hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div className="hide-scrollbar flex items-center gap-1 overflow-x-auto border-b border-slate-100 px-5 py-3 dark:border-slate-800">
                {CARD_CONFIGS.map((config, index) => {
                  const Icon = config.icon;
                  const isActive = selectedGroupId === config.id;
                  return (
                    <button
                      key={config.id}
                      type="button"
                      onClick={() => {
                        setSelectedGroupId(config.id);
                        setSelectedSubGroupId(null);
                        setCurrentCardIdx(index);
                        setReportSearchQuery('');
                        setShowImagingCompare(false);
                      }}
                      className={`inline-flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${isActive ? 'bg-brand text-white shadow-sm' : 'text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'}`}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      {config.name}
                    </button>
                  );
                })}
              </div>

              <div className="flex min-h-0 flex-1 overflow-hidden">
                {activeContent && (activeContent.group.id === 'lab' || activeContent.group.id === 'imaging') && activeContent.group.subGroups.length > 1 ? (
                  <div className="custom-scrollbar w-48 shrink-0 overflow-y-auto border-r border-slate-100 px-2 py-3 dark:border-slate-800">
                    <button
                      type="button"
                      onClick={() => setSelectedSubGroupId(null)}
                      className={`mb-1 w-full rounded-lg px-2.5 py-1.5 text-left text-xs transition-all ${!selectedSubGroupId ? 'bg-brand/10 font-bold text-brand' : 'text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800'}`}
                    >
                      全部
                    </button>
                    {activeContent.group.subGroups.map((subGroup) => (
                      <button
                        key={subGroup.id}
                        type="button"
                        onClick={() => setSelectedSubGroupId(subGroup.id)}
                        className={`mb-1 w-full rounded-lg px-2.5 py-1.5 text-left text-[11px] transition-all ${selectedSubGroupId === subGroup.id ? 'bg-brand/10 font-bold text-brand' : 'text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800'}`}
                      >
                        {subGroup.name}
                        {subGroup.abnormalCount > 0 ? <span className="ml-1 text-[10px] text-rose-500">{subGroup.abnormalCount}</span> : null}
                      </button>
                    ))}
                  </div>
                ) : null}

                <div className="custom-scrollbar min-h-0 flex-1 overflow-y-auto p-5">{renderDetailContent()}</div>
              </div>
            </motion.div>
          ) : focusedMetric ? (
            renderFocusedMetricOverlay()
          ) : cardViewMode === 'full' ? (
            <motion.div
              key="full-view"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 flex flex-col overflow-hidden rounded-[32px] border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900"
            >
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-800">
                <div className="flex items-center gap-2">
                  <div className="flex rounded-lg bg-slate-100 p-0.5 dark:bg-slate-800">
                    <button
                      type="button"
                      onClick={() => setCardViewMode('stack')}
                      className="rounded-md p-1.5 text-slate-400 transition-colors hover:text-slate-600 dark:hover:text-slate-300"
                      title="卡片模式"
                    >
                      <Layers className="h-3.5 w-3.5" />
                    </button>
                    <button type="button" className="rounded-md bg-brand p-1.5 text-white shadow-sm" title="全览模式">
                      <List className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div className="mx-1 h-5 w-px bg-slate-200 dark:bg-slate-700" />
                  <div className="hide-scrollbar flex items-center gap-1 overflow-x-auto">
                    {examRecords.map((exam, index) => {
                      const isSelected = selectedExamIds.has(exam.id);
                      return (
                        <button
                          key={exam.id}
                          type="button"
                          onClick={() => toggleExamSelection(exam.id)}
                          className={`shrink-0 rounded-md px-2 py-1 text-xs font-semibold transition-all ${isSelected ? 'bg-brand text-white shadow-sm' : 'text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'}`}
                        >
                          {exam.examDate}
                          {index === 0 ? <span className="ml-1 text-[9px] opacity-75">最新</span> : null}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex rounded-lg bg-slate-100 p-0.5 dark:bg-slate-800">
                    <button
                      type="button"
                      onClick={() => setClinicalDisplayMode('all')}
                      className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-all ${clinicalDisplayMode === 'all' ? 'bg-white text-slate-700 shadow-sm dark:bg-slate-700 dark:text-slate-200' : 'text-slate-400 dark:text-slate-500'}`}
                    >
                      全部
                    </button>
                    <button
                      type="button"
                      onClick={() => setClinicalDisplayMode('abnormal')}
                      className={`rounded-md px-2.5 py-1 text-xs font-semibold transition-all ${clinicalDisplayMode === 'abnormal' ? 'bg-white text-rose-500 shadow-sm dark:bg-slate-700' : 'text-slate-400 dark:text-slate-500'}`}
                    >
                      异常
                    </button>
                  </div>
                  <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                    <input
                      type="text"
                      value={reportSearchQuery}
                      onChange={(event) => setReportSearchQuery(event.target.value)}
                      placeholder="搜索指标..."
                      className="w-44 rounded-lg border border-slate-100 bg-slate-50 py-1.5 pl-8 pr-3 text-xs text-slate-700 outline-none transition-all focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                    />
                  </div>
                </div>
              </div>
              <div className="min-h-0 flex-1 overflow-hidden rounded-b-[32px]">
                <ReportFullView examRecords={selectedExamRecords} displayMode={clinicalDisplayMode} searchQuery={reportSearchQuery} />
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="stack-view"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 flex flex-col overflow-hidden"
            >
              <div className="space-y-2 rounded-t-[32px] border border-b-0 border-slate-200 bg-white/92 px-3 py-2.5 backdrop-blur-md dark:border-slate-700 dark:bg-slate-900/92">
                <div className="flex items-center gap-1.5">
                  <div className="mr-1 flex shrink-0 rounded-lg bg-slate-100 p-0.5 dark:bg-slate-800">
                    <button type="button" className="rounded-md bg-brand p-1.5 text-white shadow-sm" title="卡片模式">
                      <Layers className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setCardViewMode('full')}
                      className="rounded-md p-1.5 text-slate-400 transition-colors hover:text-slate-600 dark:hover:text-slate-300"
                      title="全览模式"
                    >
                      <List className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      cardSwapRef.current?.swapBack();
                      setCurrentCardIdx((prev) => (prev <= 0 ? CARD_CONFIGS.length - 1 : prev - 1));
                    }}
                    className="shrink-0 rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <div className="hide-scrollbar flex flex-1 items-center gap-1 overflow-x-auto">
                    {CARD_CONFIGS.map((config, index) => {
                      const Icon = config.icon;
                      const group = latestReport.clinicalGroups.find((item) => item.id === config.id);
                      const hasAbnormal = config.id === 'overview'
                        ? latestReport.totalAbnormal > 0
                        : config.id === 'trend-compare'
                          ? metrics.some((metric) => metric.judgment !== 'normal')
                          : (group?.abnormalCount ?? 0) > 0;
                      return (
                        <button
                          key={config.id}
                          type="button"
                          onClick={() => {
                            setSelectedGroupId(config.id);
                            setSelectedSubGroupId(null);
                            setCurrentCardIdx(index);
                            setReportSearchQuery('');
                            setClinicalDisplayMode('all');
                            setShowImagingCompare(false);
                          }}
                          className={`inline-flex shrink-0 items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-all ${index === currentCardIdx ? 'bg-brand text-white shadow-sm' : 'text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'}`}
                        >
                          <Icon className="h-3.5 w-3.5" />
                          <span className="hidden lg:inline">{config.name}</span>
                          {hasAbnormal && index !== currentCardIdx ? <span className="h-1.5 w-1.5 rounded-full bg-rose-500" /> : null}
                        </button>
                      );
                    })}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      cardSwapRef.current?.swap();
                      setCurrentCardIdx((prev) => (prev >= CARD_CONFIGS.length - 1 ? 0 : prev + 1));
                    }}
                    className="shrink-0 rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
                  >
                    <ChevronLeft className="h-4 w-4 rotate-180" />
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowCardSearch((prev) => !prev);
                      if (showCardSearch) {
                        setReportSearchQuery('');
                      }
                    }}
                    className={`ml-1 shrink-0 rounded-lg p-1.5 transition-colors ${showCardSearch ? 'bg-brand/10 text-brand' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300'}`}
                  >
                    <Search className="h-3.5 w-3.5" />
                  </button>
                  <span className="shrink-0 text-xs font-semibold tabular-nums text-slate-400 dark:text-slate-500">
                    {currentCardIdx + 1}/{CARD_CONFIGS.length}
                  </span>
                </div>
                {showCardSearch ? (
                  <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
                    <input
                      type="text"
                      value={reportSearchQuery}
                      onChange={(event) => setReportSearchQuery(event.target.value)}
                      placeholder="搜索检查项目..."
                      className="w-full rounded-lg border border-slate-100 bg-slate-50 py-1.5 pl-8 pr-8 text-xs text-slate-700 outline-none transition-all focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                    />
                    {reportSearchQuery ? (
                      <button
                        type="button"
                        onClick={() => setReportSearchQuery('')}
                        className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <div className="relative min-h-0 flex-1 rounded-b-[32px] border border-slate-200 border-t-0 bg-white/95 shadow-xl dark:border-slate-700 dark:bg-slate-900/95">
                <div className="pointer-events-none absolute inset-0 flex items-stretch justify-stretch overflow-hidden px-3 pb-3 pt-8">
                  <div className="h-full w-full scale-[0.88] perspective-1000">
                    <CardSwap
                      ref={cardSwapRef}
                      width="100%"
                      height="100%"
                      pauseOnHover={false}
                      cardDistance={88}
                      verticalDistance={60}
                      delay={0}
                      skewAmount={4}
                      easing="linear"
                    >
                      {CARD_CONFIGS.map((config) => {
                        const Icon = config.icon;
                        const group = latestReport.clinicalGroups.find((item) => item.id === config.id) ?? null;
                        const abnormalCount = config.id === 'overview'
                          ? latestReport.totalAbnormal
                          : config.id === 'trend-compare'
                            ? metrics.filter((metric) => metric.judgment !== 'normal').length
                            : group?.abnormalCount ?? 0;
                        const totalCount = config.id === 'overview'
                          ? latestReport.totalItems
                          : config.id === 'trend-compare'
                            ? metrics.length
                            : group?.totalCount ?? 0;

                        return (
                          <Card
                            key={config.id}
                            className={`pointer-events-auto flex h-full w-full cursor-pointer flex-col rounded-2xl border border-slate-200 bg-white/96 p-5 shadow-[0_10px_36px_rgba(15,23,42,0.10)] backdrop-blur-sm dark:border-slate-700 dark:bg-slate-900/96 ${config.accent} border-t-[3px]`}
                            onClick={(event: React.MouseEvent) => {
                              event.stopPropagation();
                              setSelectedGroupId(config.id);
                              setSelectedSubGroupId(null);
                              setReportSearchQuery('');
                              setClinicalDisplayMode('all');
                              setShowImagingCompare(false);
                            }}
                          >
                            <div className="mb-4 flex items-start justify-between gap-3">
                              <div className="flex items-center gap-3">
                                <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${config.iconBg}`}>
                                  <Icon className="h-5 w-5" />
                                </div>
                                <div>
                                  <div className="text-base font-bold text-slate-900 dark:text-white">{config.name}</div>
                                  <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                                    <span>{yearRangeLabel}</span>
                                    <span>·</span>
                                    <span>{totalCount} 项</span>
                                  </div>
                                </div>
                              </div>
                              {abnormalCount > 0 ? (
                                <span className="rounded-lg bg-rose-50 px-2.5 py-1 text-xs font-bold text-rose-600 dark:bg-rose-950/40 dark:text-rose-300">
                                  {abnormalCount}
                                </span>
                              ) : null}
                            </div>

                            <div className="custom-scrollbar min-h-0 flex-1 overflow-y-auto pr-1">
                              {examRecords.map((exam, index) => {
                                const isExpanded = isExpandedExam(config.id, exam.id);
                                const examGroup = config.id === 'overview' ? null : getGroupForExam(exam, config.id);
                                const examAbnormalCount = config.id === 'overview'
                                  ? exam.reportData?.totalAbnormal ?? 0
                                  : config.id === 'trend-compare'
                                    ? metrics.filter((metric) => judgeMetric(metric, exam.year) !== 'normal').length
                                    : examGroup?.abnormalCount ?? 0;
                                const previewLines = buildGroupPreviewLines(exam, config.id, metrics);

                                return (
                                  <div key={exam.id} className="mb-2 overflow-hidden rounded-xl border border-slate-100 bg-slate-50/80 dark:border-slate-800 dark:bg-slate-800/40">
                                    <div className="flex items-center justify-between gap-2 px-3 py-2.5">
                                      <button
                                        type="button"
                                        onClick={(event) => {
                                          event.stopPropagation();
                                          toggleExpandedExam(config.id, exam.id);
                                        }}
                                        className="flex min-w-0 flex-1 items-center gap-2 text-left"
                                      >
                                        <div className={`h-4 w-1 rounded-full ${isExpanded ? 'bg-brand' : 'bg-slate-300 dark:bg-slate-600'}`} />
                                        <span className="text-sm font-semibold tabular-nums text-slate-900 dark:text-white">{exam.examDate}</span>
                                        {examAbnormalCount > 0 ? (
                                          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-rose-100 text-[10px] font-bold text-rose-600 dark:bg-rose-950/40 dark:text-rose-300">
                                            {examAbnormalCount}
                                          </span>
                                        ) : null}
                                        {index === 0 ? <span className="text-[10px] font-semibold text-brand">最新</span> : null}
                                        <ChevronDown className={`ml-auto h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                                      </button>
                                      {isExpanded ? (
                                        <button
                                          type="button"
                                          onClick={(event) => {
                                            event.stopPropagation();
                                            setSelectedYearForModal(exam.year);
                                          }}
                                          className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-brand transition-colors hover:bg-brand/10"
                                        >
                                          <BarChart3 className="h-3 w-3" />
                                          对比
                                        </button>
                                      ) : null}
                                    </div>
                                    {isExpanded ? (
                                      <div className="space-y-1 px-3 pb-3">
                                        {previewLines.length > 0 ? (
                                          previewLines.map((line, lineIndex) => (
                                            <div key={`${exam.id}-${lineIndex}`} className="truncate text-xs leading-5 text-slate-600 dark:text-slate-300">
                                              {line}
                                            </div>
                                          ))
                                        ) : (
                                          <div className="text-xs text-slate-400 dark:text-slate-500">暂无更多摘要信息</div>
                                        )}
                                      </div>
                                    ) : null}
                                  </div>
                                );
                              })}
                            </div>
                          </Card>
                        );
                      })}
                    </CardSwap>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  };

  const renderContent = () => {
    if (isLoadingReports) return renderLoadingState();
    if (loadError) return renderErrorState();
    if (!latestReport) return renderEmptyState();

    return (
      <div className="grid min-h-[620px] gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <section className="flex min-h-0 flex-col overflow-hidden rounded-[32px] border border-slate-200 bg-white/82 shadow-sm dark:border-slate-800 dark:bg-slate-900/82">
          <div className="border-b border-slate-100 px-6 py-6 dark:border-slate-800">
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand/10 text-brand">
                <User className="h-8 w-8" />
              </div>
              <div>
                <div className="text-2xl font-black text-slate-900 dark:text-white">{customer.name}</div>
                <div className="mt-1 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                  <span>{customer.gender || '未知'}</span>
                  <span>•</span>
                  <span>{customer.age || '-'}岁</span>
                </div>
                <div className="mt-1 text-xs font-mono text-slate-400">{customer.customerId || customer.idCardObfuscated || customer.id}</div>
              </div>
            </div>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <InfoPill label="最近体检" value={examRecords[0]?.examDate || '-'} accent="blue" />
              <InfoPill label={completenessLabel} value={yearRangeLabel} accent="emerald" />
            </div>
          </div>

          <div className="custom-scrollbar flex min-h-0 flex-1 flex-col space-y-6 overflow-y-auto p-6">
            <div>
              <div className="mb-3 flex items-center gap-2 text-brand">
                <Brain className="h-5 w-5" />
                <div className="text-sm font-bold uppercase tracking-wider">AI 综合结论分析</div>
              </div>
              <div className="relative rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50/70 to-indigo-50/40 p-5 text-sm italic leading-7 text-slate-700 shadow-sm dark:border-slate-700 dark:from-slate-800 dark:to-slate-900/50 dark:text-slate-200">
                “{latestReport.conclusions[0]?.text ?? trendSummary}”
              </div>
            </div>

            <div>
              <div className="mb-3 flex items-center gap-2 text-slate-700 dark:text-slate-200">
                <Activity className="h-5 w-5" />
                <div className="text-sm font-bold uppercase tracking-wider">健康数据概览</div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-slate-100 bg-white px-3 py-3 text-center shadow-[0_2px_10px_rgb(0,0,0,0.02)] dark:border-slate-700 dark:bg-slate-800">
                  <div className="mb-1 flex items-center justify-center gap-1 text-[9px] font-bold uppercase tracking-widest text-slate-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />异常指标
                  </div>
                  <div className="text-2xl font-black text-slate-900 dark:text-white">{latestReport.totalAbnormal}</div>
                </div>
                <div className="rounded-xl border border-slate-100 bg-white px-3 py-3 text-center shadow-[0_2px_10px_rgb(0,0,0,0.02)] dark:border-slate-700 dark:bg-slate-800">
                  <div className="mb-1 flex items-center justify-center gap-1 text-[9px] font-bold uppercase tracking-widest text-slate-400">
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />检查项目
                  </div>
                  <div className="text-2xl font-black text-slate-900 dark:text-white">{latestReport.totalItems}</div>
                </div>
              </div>
            </div>

            <div className="flex min-h-[320px] flex-1 flex-col overflow-hidden rounded-2xl border border-slate-100 bg-slate-50 dark:border-slate-700 dark:bg-slate-900/30">
              <div className="flex items-center justify-between border-b border-slate-100 bg-white/60 px-3 py-3 dark:border-slate-700 dark:bg-slate-800/50">
                <div className="flex items-center gap-2">
                  <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-brand text-white">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div className="text-xs font-bold text-slate-700 dark:text-slate-200">AI 实时咨询</div>
                </div>
                {focusedMetricName ? (
                  <button type="button" onClick={() => setFocusedMetricName(null)} className="text-[10px] font-bold text-brand hover:underline">
                    重置视图
                  </button>
                ) : null}
              </div>
              <div className="custom-scrollbar min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
                {messages.map((message, index) => (
                  <div key={`${message.role}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[88%] rounded-2xl px-4 py-3 text-xs leading-6 ${message.role === 'user' ? 'rounded-tr-none bg-brand text-white shadow-[0_4px_15px_rgba(79,110,255,0.20)]' : 'rounded-tl-none border border-slate-100 bg-white text-slate-700 shadow-[0_2px_10px_rgb(0,0,0,0.03)] dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200'}`}
                    >
                      {message.content}
                    </div>
                  </div>
                ))}
                {isTyping ? (
                  <div className="flex justify-start">
                    <div className="rounded-2xl rounded-tl-none border border-slate-100 bg-white p-3 shadow-[0_2px_10px_rgb(0,0,0,0.03)] dark:border-slate-700 dark:bg-slate-800">
                      <div className="flex gap-1">
                        <div className="h-1 w-1 animate-bounce rounded-full bg-slate-300" />
                        <div className="h-1 w-1 animate-bounce rounded-full bg-slate-300 [animation-delay:0.2s]" />
                        <div className="h-1 w-1 animate-bounce rounded-full bg-slate-300 [animation-delay:0.4s]" />
                      </div>
                    </div>
                  </div>
                ) : null}
                <div ref={chatEndRef} />
              </div>
              <form onSubmit={handleSendMessage} className="flex items-center gap-2 border-t border-slate-100 bg-white p-2 dark:border-slate-700 dark:bg-slate-800">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(event) => setInputValue(event.target.value)}
                  placeholder="咨询指标，如：空腹血糖..."
                  className="flex-1 rounded-xl border border-slate-100 bg-slate-50/70 px-4 py-2.5 text-xs outline-none transition-all focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                />
                <button type="submit" disabled={isTyping} className="rounded-xl bg-brand p-2 text-white transition-colors hover:bg-brand-600 disabled:opacity-50">
                  <Send className="h-4 w-4" />
                </button>
              </form>
            </div>
          </div>
        </section>

        {renderRightPanel()}
      </div>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="flex h-full flex-col space-y-6 overflow-hidden bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-white via-slate-50 to-slate-100 p-6 transition-colors duration-300 dark:bg-none dark:bg-slate-900"
    >
      <ReportHeader onBack={onBack} isDarkMode={isDarkMode} onToggleDarkMode={() => setIsDarkMode(!isDarkMode)} onResetView={resetView} />
      {renderContent()}
      {renderComparisonModal()}
    </motion.div>
  );
};

function InfoPill({ label, value, accent }: { label: string; value: string; accent: 'blue' | 'emerald' }) {
  const accentClass =
    accent === 'blue'
      ? 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-300'
      : 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-300';

  return (
    <div className={`rounded-2xl border px-4 py-3 ${accentClass}`}>
      <div className="text-[11px] font-semibold uppercase tracking-wider opacity-80">{label}</div>
      <div className="mt-1 text-sm font-bold">{value}</div>
    </div>
  );
}
