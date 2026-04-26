import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { GoogleGenAI, Type } from '@google/genai';
import { aiReportApi } from '../../services/api/aiReportApi';
import type { CustomerRecord } from './detailView/types';
import { ReportHeader } from './reportview/ReportHeader';
import type { Message } from './reportview/types';
import {
  mapMetricSeriesFromExamRecords,
  mapReportSessionsToExamRecords,
} from '../HealthReport/reportDataMapper';
import { HealthReportView } from '../HealthReport/HealthReportView';
import type { DisplayMode, ExamRecord, MetricSeries } from '../../types/healthReport';

const ai = new GoogleGenAI({ apiKey: import.meta.env.VITE_GEMINI_API_KEY ?? '' });

const DEFAULT_MESSAGES: Message[] = [
  {
    role: 'ai',
    content: '您好！我是您的 AI 健康助手。您可以询问我关于体检报告中的具体指标，我会结合已加载的多次体检报告给出趋势解读。',
  },
];

interface AIReportComparisonReportViewProps {
  customer: CustomerRecord;
  onBack: () => void;
  isDarkMode: boolean;
  setIsDarkMode: (value: boolean) => void;
}

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

export const AIReportComparisonReportView: React.FC<AIReportComparisonReportViewProps> = ({
  customer,
  onBack,
  isDarkMode,
  setIsDarkMode,
}) => {
  const chatEndRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<Message[]>(DEFAULT_MESSAGES);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [reportSearchQuery, setReportSearchQuery] = useState('');
  const [clinicalDisplayMode, setClinicalDisplayMode] = useState<DisplayMode>('all');
  const [showTrend, setShowTrend] = useState(false);
  const [selectedExamIds, setSelectedExamIds] = useState<Set<string>>(new Set());
  const [examRecords, setExamRecords] = useState<ExamRecord[]>([]);
  const [isLoadingReports, setIsLoadingReports] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

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
          setSelectedExamIds(new Set(mappedRecords.slice(0, Math.min(2, mappedRecords.length)).map((record) => record.id)));
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
  const selectedExamRecords = useMemo(() => {
    if (selectedExamIds.size === 0) {
      return examRecords.slice(0, 1);
    }
    return examRecords.filter((record) => selectedExamIds.has(record.id));
  }, [examRecords, selectedExamIds]);

  const trendSummary = useMemo(() => buildTrendSummary(metricSeries), [metricSeries]);

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
      const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: userMessage,
        config: {
          systemInstruction: `你是专业体检报告分析助手。请严格基于提供的体检报告摘要回答，不要编造不存在的指标或年份。\n${JSON.stringify(buildAiContext(examRecords))}`,
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              reply: { type: Type.STRING },
            },
            required: ['reply'],
          },
        },
      });

      const result = JSON.parse(response.text || '{}');
      setMessages((prev) => [...prev, { role: 'ai', content: result.reply || '已结合当前报告为您整理分析。' }]);
    } catch (error) {
      console.error('AI Chat Error:', error);
      setMessages((prev) => [...prev, { role: 'ai', content: '抱歉，当前无法完成智能分析，请稍后重试。' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const resetView = () => {
    setClinicalDisplayMode('all');
    setShowTrend(false);
    setReportSearchQuery('');
    setMessages(DEFAULT_MESSAGES);
  };

  const renderReportBody = () => {
    if (isLoadingReports) {
      return (
        <div className="flex min-h-[480px] items-center justify-center rounded-[32px] border border-slate-200 bg-white/80 text-sm text-slate-500 shadow-sm dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-400">
          正在加载体检报告...
        </div>
      );
    }

    if (loadError) {
      return (
        <div className="flex min-h-[480px] flex-col items-center justify-center gap-4 rounded-[32px] border border-rose-200 bg-white/80 px-6 text-center shadow-sm dark:border-rose-900/60 dark:bg-slate-900/80">
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
    }

    if (!latestReport) {
      return (
        <div className="flex min-h-[480px] items-center justify-center rounded-[32px] border border-slate-200 bg-white/80 text-sm text-slate-500 shadow-sm dark:border-slate-800 dark:bg-slate-900/80 dark:text-slate-400">
          暂无可展示的体检报告。
        </div>
      );
    }

    return (
      <div className="grid min-h-[480px] gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <section className="flex min-h-0 flex-col overflow-hidden rounded-[32px] border border-slate-200 bg-white/80 shadow-sm dark:border-slate-800 dark:bg-slate-900/80">
          <div className="border-b border-slate-100 px-6 py-5 dark:border-slate-800">
            <div className="text-2xl font-bold text-slate-900 dark:text-white">{customer.name}</div>
            <div className="mt-1 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              <span>{customer.gender || '未知'}</span>
              <span>•</span>
              <span>{customer.age || '-'}岁</span>
              {customer.idCardObfuscated ? (
                <>
                  <span>•</span>
                  <span>{customer.idCardObfuscated}</span>
                </>
              ) : null}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <InfoPill label="最近体检" value={latestReport.examTime.split(' ')[0]} accent="blue" />
              <InfoPill label="异常项目" value={String(latestReport.totalAbnormal)} accent="rose" />
            </div>
          </div>

          <div className="space-y-5 overflow-y-auto p-6 custom-scrollbar">
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-brand">AI 综合结论</div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 text-sm leading-6 text-slate-700 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-200">
                {latestReport.conclusions[0]?.text ?? trendSummary}
              </div>
            </div>

            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">趋势摘要</div>
              <div className="rounded-2xl border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-700 dark:border-slate-700 dark:bg-slate-800/70 dark:text-slate-200">
                {trendSummary}
              </div>
            </div>

            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">体检记录</div>
              <div className="space-y-2">
                {examRecords.map((record) => {
                  const isSelected = selectedExamIds.has(record.id);
                  return (
                    <button
                      key={record.id}
                      type="button"
                      onClick={() => toggleExamSelection(record.id)}
                      className={`w-full rounded-2xl border px-4 py-3 text-left transition-all ${
                        isSelected
                          ? 'border-brand bg-brand/5 shadow-sm'
                          : 'border-slate-200 bg-white hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800/60 dark:hover:border-slate-600'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold text-slate-900 dark:text-white">{record.examDate}</div>
                          <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{record.packageName}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs text-slate-400">异常</div>
                          <div className="text-sm font-bold text-rose-500">{record.reportData?.totalAbnormal ?? 0}</div>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex min-h-[280px] flex-col rounded-2xl border border-slate-200 bg-slate-50/80 dark:border-slate-700 dark:bg-slate-800/60">
              <div className="border-b border-slate-200 px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:border-slate-700">
                AI 实时咨询
              </div>
              <div className="flex-1 space-y-3 overflow-y-auto p-4 custom-scrollbar">
                {messages.map((message, index) => (
                  <div key={`${message.role}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                        message.role === 'user'
                          ? 'bg-brand text-white'
                          : 'border border-slate-200 bg-white text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200'
                      }`}
                    >
                      {message.content}
                    </div>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>
              <form onSubmit={handleSendMessage} className="flex items-center gap-2 border-t border-slate-200 p-3 dark:border-slate-700">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(event) => setInputValue(event.target.value)}
                  placeholder="输入问题，如：最近哪些指标需要重点关注？"
                  className="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none transition-all focus:border-brand focus:ring-2 focus:ring-brand/20 dark:border-slate-700 dark:bg-slate-900 dark:text-white"
                />
                <button
                  type="submit"
                  disabled={isTyping}
                  className="rounded-xl bg-brand px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  发送
                </button>
              </form>
            </div>
          </div>
        </section>

        <section className="min-h-0 overflow-hidden rounded-[32px] border border-slate-200 bg-white/80 shadow-sm dark:border-slate-800 dark:bg-slate-900/80">
          <HealthReportView
            setCurrentPage={() => undefined}
            reportData={latestReport}
            examRecords={selectedExamRecords}
            isDarkMode={isDarkMode}
            setIsDarkMode={setIsDarkMode}
            searchQuery={reportSearchQuery}
            onSearchChange={setReportSearchQuery}
            displayMode={clinicalDisplayMode}
            onDisplayModeChange={setClinicalDisplayMode}
            showTrend={showTrend}
            onTrendToggle={setShowTrend}
          />
        </section>
      </div>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="h-full flex flex-col space-y-6 p-6 bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-white via-slate-50 to-slate-100 dark:bg-none dark:bg-slate-900 transition-colors duration-300 overflow-hidden"
    >
      <ReportHeader
        onBack={onBack}
        isDarkMode={isDarkMode}
        onToggleDarkMode={() => setIsDarkMode(!isDarkMode)}
        onResetView={resetView}
      />

      {renderReportBody()}
    </motion.div>
  );
};

function InfoPill({ label, value, accent }: { label: string; value: string; accent: 'blue' | 'rose' }) {
  const accentClass =
    accent === 'blue'
      ? 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-300'
      : 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-300';

  return (
    <div className={`rounded-2xl border px-4 py-3 ${accentClass}`}>
      <div className="text-[11px] font-semibold uppercase tracking-wider opacity-80">{label}</div>
      <div className="mt-1 text-sm font-bold">{value}</div>
    </div>
  );
}
