import React, { useRef, useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ChevronLeft, ChevronDown, Download, RefreshCw, Sun, Moon, User, Activity, Brain, Send, MessageSquare, Bot, Sparkles, Search, List, LayoutGrid, X, FileText, Layers, TestTubes, ScanLine, Stethoscope, HeartPulse, ClipboardList, TrendingUp, ArrowLeft, Filter, Calendar, BarChart3 } from 'lucide-react';
import CardSwap, { Card, CardSwapRef } from './CardSwap';
import { GoogleGenAI, Type } from "@google/genai";
import rawReportData from '../../data/healthReportRaw';
import { mapReportData } from '../HealthReport/reportDataMapper';
import { ReportOverview } from '../HealthReport/ReportOverview';
import { ReportDataTable } from '../HealthReport/ReportDataTable';
import { ReportImagingCards } from '../HealthReport/ReportImagingCard';
import { ReportTextSection } from '../HealthReport/ReportTextSection';
import { ReportTrendChart } from '../HealthReport/ReportTrendChart';
import { ImagingCompare } from '../HealthReport/ImagingCompare';
import { ReportFullView } from '../HealthReport/ReportFullView';
import type { DisplayMode, ClinicalGroup, ExamRecord } from '../../types/healthReport';

let ai: InstanceType<typeof GoogleGenAI> | null = null;
try {
  ai = new GoogleGenAI({ apiKey: import.meta.env.VITE_GEMINI_API_KEY ?? '' });
} catch {
  // API key not set — AI features disabled
}

interface MetricData {
  category: string;
  name: string;
  unit: string;
  refRange: string;
  values: Record<string, number | string>;
  judgment: 'high' | 'low' | 'normal';
  trend: string;
}

const TrendChart = ({ m, yearsToShow, className, isExpanded }: { m: MetricData, yearsToShow?: string[], className?: string, isExpanded?: boolean }) => {
  const years = yearsToShow || ['2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026'];
  const vals = years.map(y => Number(m.values[y]));
  const [refMinStr, refMaxStr] = m.refRange.split('-');
  const refMin = parseFloat(refMinStr);
  const refMax = parseFloat(refMaxStr);
  
  const allVals = [...vals, refMin, refMax].filter(v => !isNaN(v));
  const min = Math.min(...allVals) * 0.85;
  const max = Math.max(...allVals) * 1.15;
  const range = max - min || 1;
  
  const width = isExpanded ? 180 : 100;
  const viewBox = isExpanded ? "-15 0 210 50" : "0 0 100 50";
  
  const getY = (v: number) => 42 - ((v - min) / range) * 34; // 42 is bottom, 8 is top
  const getX = (index: number) => 10 + (index / (years.length - 1)) * (width - 20); // Balanced centering
  
  const yRefMin = getY(refMin);
  const yRefMax = getY(refMax);

  const points = vals.map((v, i) => `${getX(i)},${getY(v)}`).join(' ');

  return (
    <svg viewBox={viewBox} className={`w-full overflow-visible ${className || 'h-20'}`}>
      {/* Reference Range Band */}
      {!isNaN(yRefMin) && !isNaN(yRefMax) && (
        <rect 
          x="0" 
          y={yRefMax} 
          width={width} 
          height={Math.max(0, yRefMin - yRefMax)} 
          fill="#10b981" 
          fillOpacity="0.06" 
          rx="1"
        />
      )}
      {/* Reference Range Lines and Labels */}
      {!isNaN(yRefMax) && (
        <>
          <text x="-4" y={yRefMax + 1.5} fontSize={isExpanded ? "5" : "6.5"} fill="#059669" fontWeight="normal" textAnchor="end">上限</text>
          <line x1="0" y1={yRefMax} x2={width} y2={yRefMax} stroke="#10b981" strokeWidth={isExpanded ? "0.4" : "0.6"} strokeDasharray="3 2" />
          <text x={width + 4} y={yRefMax + 1.5} fontSize={isExpanded ? "5" : "6.5"} fill="#059669" fontWeight="normal" textAnchor="start">{refMax}</text>
        </>
      )}
      {!isNaN(yRefMin) && (
        <>
          <text x="-4" y={yRefMin + 1.5} fontSize={isExpanded ? "5" : "6.5"} fill="#059669" fontWeight="normal" textAnchor="end">下限</text>
          <line x1="0" y1={yRefMin} x2={width} y2={yRefMin} stroke="#10b981" strokeWidth={isExpanded ? "0.4" : "0.6"} strokeDasharray="3 2" />
          <text x={width + 4} y={yRefMin + 1.5} fontSize={isExpanded ? "5" : "6.5"} fill="#059669" fontWeight="normal" textAnchor="start">{refMin}</text>
        </>
      )}

      {/* Trend Line */}
      <polyline 
        points={points} 
        fill="none" 
        stroke="#3b82f6" 
        strokeWidth={isExpanded ? "2" : "3.5"} 
        strokeLinecap="round" 
        strokeLinejoin="round" 
      />
      
      {/* Data Points and Values */}
      {vals.map((v, i) => (
        <g key={i}>
          <circle cx={getX(i)} cy={getY(v)} r={isExpanded ? "2" : "3.5"} fill="#3b82f6" stroke="#fff" strokeWidth={isExpanded ? "0.8" : "1.2"} />
          <text x={getX(i)} y={getY(v) - (isExpanded ? 4 : 7)} fontSize={isExpanded ? "6" : "9"} fill="#1d4ed8" textAnchor="middle" fontWeight="medium">{v}</text>
          <text x={getX(i)} y={49} fontSize={isExpanded ? "5" : "6.5"} fill="#64748b" textAnchor="middle" fontWeight="medium">{years[i]}</text>
        </g>
      ))}
    </svg>
  );
};

interface Message {
  role: 'user' | 'ai';
  content: string;
}

interface AIReportComparisonReportViewProps {
  customer: any;
  onBack: () => void;
  isDarkMode: boolean;
  setIsDarkMode: (value: boolean) => void;
}

export const AIReportComparisonReportView: React.FC<AIReportComparisonReportViewProps> = ({ customer, onBack, isDarkMode, setIsDarkMode }) => {
  const cardStack = ['2026', '2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018'];
  const cardSwapRef = useRef<CardSwapRef>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<Message[]>([
    { role: 'ai', content: '您好！我是您的 AI 健康助手。您可以询问我关于体检报告中的具体指标（如：血糖、胆固醇等），我会为您实时切换并展示历年的数据对比。' }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [focusedMetricName, setFocusedMetricName] = useState<string | null>(null);
  const [selectedYearForModal, setSelectedYearForModal] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'list' | 'trend'>('list');
  const [modalFilter, setModalFilter] = useState<'all' | 'abnormal'>('all');
  const [modalViewMode, setModalViewMode] = useState<'card' | 'list'>('list');

  // Clinical report state (real data)
  const reportData = useMemo(() => mapReportData(rawReportData), []);
  const [selectedGroupId, setSelectedGroupId] = useState('');
  const [currentCardIdx, setCurrentCardIdx] = useState(0);

  // Exam records (descending by date). Real data first, then mock placeholders.
  const examRecords: ExamRecord[] = useMemo(() => {
    const real: ExamRecord = {
      id: reportData.studyId,
      examTime: reportData.examTime,
      examDate: reportData.examTime.split(' ')[0],
      year: reportData.examTime.split('-')[0],
      packageName: reportData.packageName,
      reportData,
    };
    // Mock placeholder records for demo — no real data
    const placeholders: ExamRecord[] = [
      { id: 'mock-2025-06', examTime: '2025-06-15 09:30:00', examDate: '2025-06-15', year: '2025', packageName: '海-033VIP基础套餐（年中检查）', reportData: null as any },
      { id: 'mock-2024-12', examTime: '2024-12-10 08:20:00', examDate: '2024-12-10', year: '2024', packageName: '海-033VIP精筛套餐', reportData: null as any },
      { id: 'mock-2023-11', examTime: '2023-11-28 08:45:00', examDate: '2023-11-28', year: '2023', packageName: '海-033基础套餐', reportData: null as any },
    ];
    return [real, ...placeholders];
  }, [reportData]);

  const [expandedExams, setExpandedExams] = useState<Record<string, Set<string>>>({});

  const toggleExam = (cardId: string, examId: string) => {
    setExpandedExams(prev => {
      const cardSet = new Set(prev[cardId] ?? [examRecords[0]?.id]);
      if (cardSet.has(examId)) cardSet.delete(examId);
      else cardSet.add(examId);
      return { ...prev, [cardId]: cardSet };
    });
  };

  const isExamExpanded = (cardId: string, examId: string) => {
    const cardSet = expandedExams[cardId];
    if (!cardSet) return examId === examRecords[0]?.id; // default: latest expanded
    return cardSet.has(examId);
  };
  const [selectedSubGroupId, setSelectedSubGroupId] = useState<string | null>(null);
  const [clinicalDisplayMode, setClinicalDisplayMode] = useState<DisplayMode>('all');
  const [showTrend, setShowTrend] = useState(false);
  const [reportSearchQuery, setReportSearchQuery] = useState('');
  const [showImagingCompare, setShowImagingCompare] = useState(false);
  const [showCardSearch, setShowCardSearch] = useState(false);
  const [cardViewMode, setCardViewMode] = useState<'stack' | 'full'>('stack');
  const [selectedExamIds, setSelectedExamIds] = useState<Set<string>>(() => new Set([examRecords[0]?.id].filter(Boolean)));

  const toggleExamSelection = (examId: string) => {
    setSelectedExamIds(prev => {
      const next = new Set(prev);
      if (next.has(examId)) {
        if (next.size > 1) next.delete(examId); // keep at least 1 selected
      } else {
        next.add(examId);
      }
      return next;
    });
  };

  const selectedExamRecords = useMemo(
    () => examRecords.filter(e => selectedExamIds.has(e.id)),
    [examRecords, selectedExamIds]
  );

  const CARD_CONFIG: { id: string; name: string; icon: React.ElementType; gradient: string; iconBg: string }[] = [
    { id: 'overview', name: '综合概况', icon: ClipboardList, gradient: 'from-blue-50 to-indigo-50/80 dark:from-slate-800 dark:to-indigo-900/20', iconBg: 'bg-brand/10 text-brand' },
    { id: 'vitals', name: '基础体征', icon: Activity, gradient: 'from-emerald-50 to-green-50/80 dark:from-slate-800 dark:to-emerald-900/20', iconBg: 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400' },
    { id: 'lab', name: '实验室检验', icon: TestTubes, gradient: 'from-violet-50 to-purple-50/80 dark:from-slate-800 dark:to-violet-900/20', iconBg: 'bg-violet-100 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400' },
    { id: 'imaging', name: '影像检查', icon: ScanLine, gradient: 'from-orange-50 to-amber-50/80 dark:from-slate-800 dark:to-orange-900/20', iconBg: 'bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400' },
    { id: 'specialty', name: '专科检查', icon: Stethoscope, gradient: 'from-rose-50 to-pink-50/80 dark:from-slate-800 dark:to-rose-900/20', iconBg: 'bg-rose-100 text-rose-600 dark:bg-rose-900/30 dark:text-rose-400' },
    { id: 'health', name: '健康评估', icon: HeartPulse, gradient: 'from-cyan-50 to-sky-50/80 dark:from-slate-800 dark:to-cyan-900/20', iconBg: 'bg-cyan-100 text-cyan-600 dark:bg-cyan-900/30 dark:text-cyan-400' },
    { id: 'trend-compare', name: '历年数据对比', icon: TrendingUp, gradient: 'from-slate-50 to-gray-50/80 dark:from-slate-800 dark:to-slate-700/20', iconBg: 'bg-slate-200 text-slate-600 dark:bg-slate-700 dark:text-slate-300' },
  ];

  const handleSelectGroup = (groupId: string, subGroupId?: string | null) => {
    setSelectedGroupId(groupId);
    setSelectedSubGroupId(subGroupId ?? null);
  };

  const activeContent = useMemo(() => {
    if (selectedGroupId === 'overview') return null;
    const group = reportData.clinicalGroups.find(g => g.id === selectedGroupId);
    if (!group) return null;
    if (selectedSubGroupId) {
      const sub = group.subGroups.find(s => s.id === selectedSubGroupId);
      return { group, subGroup: sub || null, items: sub?.items || [] };
    }
    return { group, subGroup: null, items: group.subGroups.flatMap(s => s.items) };
  }, [selectedGroupId, selectedSubGroupId, reportData]);

  const metrics: MetricData[] = [
    { category: '糖尿病检查', name: '空腹血糖', unit: 'mmol/L', refRange: '3.9 - 6.1', values: { '2018': 4.5, '2019': 4.6, '2020': 4.8, '2021': 4.9, '2022': 5.0, '2023': 5.1, '2024': 5.2, '2025': 5.8, '2026': 6.4 }, judgment: 'high', trend: '连续升高，2026已超上限' },
    { category: '血脂检查', name: '总胆固醇', unit: 'mmol/L', refRange: '3.1 - 5.2', values: { '2018': 4.0, '2019': 4.1, '2020': 4.2, '2021': 4.3, '2022': 4.5, '2023': 4.6, '2024': 4.8, '2025': 5.4, '2026': 5.9 }, judgment: 'high', trend: '三年递增，建议结合 LDL-C 复查' },
    { category: '肝功能检查', name: 'ALT', unit: 'U/L', refRange: '9 - 50', values: { '2018': 18, '2019': 20, '2020': 22, '2021': 24, '2022': 25, '2023': 26, '2024': 28, '2025': 42, '2026': 65 }, judgment: 'high', trend: '2026明显上冲，需关注肝功能' },
    { category: '肾功能检查', name: '尿酸', unit: 'μmol/L', refRange: '208 - 428', values: { '2018': 320, '2019': 330, '2020': 340, '2021': 350, '2022': 360, '2023': 370, '2024': 380, '2025': 401, '2026': 435 }, judgment: 'high', trend: '临近上限后突破，存在代谢风险' },
    { category: '血脂检查', name: 'HDL-C', unit: 'mmol/L', refRange: '1.04 - 1.55', values: { '2018': 1.35, '2019': 1.30, '2020': 1.28, '2021': 1.25, '2022': 1.20, '2023': 1.18, '2024': 1.15, '2025': 1.02, '2026': 0.95 }, judgment: 'low', trend: '保护性胆固醇下降' },
    { category: '肾功能检查', name: '肌酐', unit: 'μmol/L', refRange: '57 - 97', values: { '2018': 78, '2019': 79, '2020': 80, '2021': 81, '2022': 81, '2023': 82, '2024': 82, '2025': 84, '2026': 86 }, judgment: 'normal', trend: '保持稳定，在参考范围内' },
    { category: '一般检查', name: '收缩压', unit: 'mmHg', refRange: '90 - 139', values: { '2018': 115, '2019': 118, '2020': 120, '2021': 122, '2022': 124, '2023': 126, '2024': 128, '2025': 136, '2026': 142 }, judgment: 'high', trend: '逐年上升，当前轻度超标' },
    { category: '一般检查', name: 'BMI', unit: 'kg/m²', refRange: '18.5 - 23.9', values: { '2018': 22.5, '2019': 22.8, '2020': 23.1, '2021': 23.5, '2022': 23.8, '2023': 24.1, '2024': 24.4, '2025': 25.1, '2026': 25.8 }, judgment: 'high', trend: '持续高于推荐范围' },
  ];

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Skip if user is typing in an input
      if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') return;

      if (e.key === 'ArrowLeft' && !selectedGroupId) {
        cardSwapRef.current?.swapBack();
        setCurrentCardIdx(prev => prev <= 0 ? CARD_CONFIG.length - 1 : prev - 1);
      } else if (e.key === 'ArrowRight' && !selectedGroupId) {
        cardSwapRef.current?.swap();
        setCurrentCardIdx(prev => prev >= CARD_CONFIG.length - 1 ? 0 : prev + 1);
      } else if (e.key === 'Enter' && !selectedGroupId) {
        const cfg = CARD_CONFIG[currentCardIdx];
        if (cfg) {
          setSelectedGroupId(cfg.id);
          setSelectedSubGroupId(null);
          setReportSearchQuery('');
          setClinicalDisplayMode('all');
        }
      } else if (e.key === 'Escape' && selectedGroupId) {
        setSelectedGroupId('');
        setSelectedSubGroupId(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedGroupId, currentCardIdx, CARD_CONFIG.length]);

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputValue.trim() || isTyping) return;

    const userMsg = inputValue.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInputValue('');
    setIsTyping(true);

    try {
      const response = await ai.models.generateContent({
        model: "gemini-3-flash-preview",
        contents: userMsg,
        config: {
          systemInstruction: `你是一个专业的健康体检报告分析助手。
          当前可查询的指标有：${metrics.map(m => m.name).join(', ')}。
          
          你的任务是：
          1. 分析用户的意图，判断用户是否在询问某个具体的体检指标。
          2. 如果是，请在回复中包含该指标的完整名称。
          3. 必须以 JSON 格式返回，包含两个字段：
             - "reply": 你对用户的自然语言回复，解释该指标的意义或现状。
             - "focusedMetric": 识别到的指标名称（必须是上述列表中的一个，如果没识别到则为 null）。
          
          示例：
          用户：“帮我看看血糖怎么样”
          返回：{"reply": "好的，正在为您调取历年的空腹血糖数据。从趋势看，您的血糖近年来有持续上升的迹象，建议重点关注。", "focusedMetric": "空腹血糖"}`,
          responseMimeType: "application/json",
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              reply: { type: Type.STRING },
              focusedMetric: { type: Type.STRING, nullable: true }
            },
            required: ["reply", "focusedMetric"]
          }
        }
      });

      const result = JSON.parse(response.text || '{}');
      setMessages(prev => [...prev, { role: 'ai', content: result.reply }]);
      if (result.focusedMetric) {
        setFocusedMetricName(result.focusedMetric);
      }
    } catch (error) {
      console.error("AI Chat Error:", error);
      setMessages(prev => [...prev, { role: 'ai', content: '抱歉，我刚才走神了，请再试一次。' }]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleSwapCard = () => {
    cardSwapRef.current?.swap();
  };

  const handleOpenModal = (year: string) => {
    setSelectedYearForModal(year);
  };

  const leftScrollRef = useRef<HTMLDivElement>(null);
  const centerScrollRef = useRef<HTMLDivElement>(null);
  const rightScrollRef = useRef<HTMLDivElement>(null);
  const trendScrollRef = useRef<HTMLDivElement>(null);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const scrollTop = e.currentTarget.scrollTop;
    if (leftScrollRef.current && e.currentTarget !== leftScrollRef.current) {
      leftScrollRef.current.scrollTop = scrollTop;
    }
    if (centerScrollRef.current && e.currentTarget !== centerScrollRef.current) {
      centerScrollRef.current.scrollTop = scrollTop;
    }
    if (rightScrollRef.current && e.currentTarget !== rightScrollRef.current) {
      rightScrollRef.current.scrollTop = scrollTop;
    }
    if (trendScrollRef.current && e.currentTarget !== trendScrollRef.current) {
      trendScrollRef.current.scrollTop = scrollTop;
    }
  };

  const getYearData = (year: string | null) => {
    if (!year) return null;
    return metrics.map(m => ({
      name: m.name,
      unit: m.unit,
      val: m.values[year],
      refRange: m.refRange
    }));
  };

  const renderComparisonColumn = (
    year: string | null, 
    title: string, 
    isCenter: boolean = false, 
    prevYearData: any[] | null = null,
    scrollRef?: React.RefObject<HTMLDivElement>,
    filteredMetrics?: MetricData[]
  ) => {
    if (!year) return (
      <motion.div layout className="flex-1 flex items-center justify-center text-slate-300 dark:text-slate-700 italic text-sm">
        无相关年份数据
      </motion.div>
    );

    const data = (filteredMetrics || metrics).map(m => ({
      name: m.name,
      unit: m.unit,
      val: m.values[year],
      refRange: m.refRange
    }));

    return (
      <motion.div 
        layout
        className={`flex-1 flex flex-col p-6 rounded-2xl border transition-all duration-300 ${
          isCenter 
            ? 'bg-white dark:bg-slate-800 border-brand shadow-xl scale-105 z-10' 
            : 'bg-slate-50/50 dark:bg-slate-900/50 border-slate-100 dark:border-slate-800 opacity-60'
        }`}
      >
        <h3 className={`text-center font-black mb-6 ${isCenter ? 'text-brand text-xl' : 'text-slate-500 text-sm uppercase tracking-widest'}`}>
          {year} 年度报告
        </h3>
        
        <div 
          ref={scrollRef}
          onScroll={handleScroll}
          className={`flex-1 overflow-y-auto pr-2 space-y-4 ${isCenter ? 'custom-scrollbar' : '[&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]'}`}
        >
          {data.map((item) => {
            // Find original index for diff calculation
            const originalIdx = metrics.findIndex(m => m.name === item.name);
            const prevItem = prevYearData ? prevYearData[originalIdx] : null;
            const diff = (prevItem && typeof item.val === 'number' && typeof prevItem.val === 'number') 
              ? (item.val - prevItem.val).toFixed(2) 
              : null;
            const isIncrease = diff && parseFloat(diff) > 0;
            const isDecrease = diff && parseFloat(diff) < 0;

            const isHigh = typeof item.val === 'number' && item.val > parseFloat(item.refRange.split('-')[1]);
            const isLow = typeof item.val === 'number' && item.val < parseFloat(item.refRange.split('-')[0]);
            const judgment = isHigh ? '偏高' : isLow ? '偏低' : '正常';
            const judgmentColor = isHigh ? 'text-rose-500 bg-rose-50 dark:bg-rose-500/10 dark:text-rose-400' : isLow ? 'text-amber-500 bg-amber-50 dark:bg-amber-500/10 dark:text-amber-400' : 'text-emerald-500 bg-emerald-50 dark:bg-emerald-500/10 dark:text-emerald-400';

            return (
              <div key={item.name} className="p-3 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 shadow-sm h-[116px] flex flex-col justify-between">
                <div>
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-xs font-bold text-slate-500">{item.name}</span>
                    <span className="text-[10px] text-slate-400">{item.unit}</span>
                  </div>
                  <div className="flex items-end justify-between mb-2">
                    <div className="text-xl font-black text-slate-900 dark:text-white">
                      {item.val}
                    </div>
                    {isCenter && diff && (
                      <div className={`flex items-center space-x-1 text-xs font-bold ${isIncrease ? 'text-rose-500' : isDecrease ? 'text-emerald-500' : 'text-slate-400'}`}>
                        {isIncrease ? '↑' : isDecrease ? '↓' : ''}
                        <span>{Math.abs(parseFloat(diff))}</span>
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-slate-50 dark:border-slate-700/50">
                  <span className="text-[10px] text-slate-400">参考: {item.refRange}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${judgmentColor}`}>
                    {judgment}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </motion.div>
    );
  };

  const renderTrendColumn = (yearsToShow?: string[], filteredMetrics?: MetricData[]) => {
    const displayMetrics = filteredMetrics || metrics;

    return (
      <motion.div 
        layout
        className="flex-1 flex flex-col p-6 rounded-2xl border transition-all duration-300 bg-slate-50/50 dark:bg-slate-900/50 border-slate-100 dark:border-slate-800 opacity-80"
      >
        <div className="flex flex-col items-center mb-6 space-y-2">
          <h3 className="font-black text-slate-500 text-sm uppercase tracking-widest">
            对比趋势
          </h3>
          <div className="flex items-center space-x-6">
            <div className="flex items-center space-x-2">
              <div className="w-4 h-1.5 bg-emerald-500/20 border border-emerald-500/30 rounded-sm"></div>
              <span className="text-xs font-black text-emerald-600">正常区间</span>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-4 h-1 bg-blue-500 rounded-full"></div>
              <span className="text-xs font-black text-blue-600">数值走势</span>
            </div>
          </div>
        </div>
        
        <div 
          ref={trendScrollRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto pr-2 space-y-4 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]"
        >
          {displayMetrics.map((m) => (
            <div key={m.name} className="p-3 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 shadow-sm h-[116px] flex flex-col">
              <div className="flex justify-between items-start mb-1 shrink-0">
                <span className="text-xs font-bold text-slate-500">{m.name}</span>
              </div>
              <div className="flex-1 flex items-center justify-center min-h-0">
                <TrendChart m={m} yearsToShow={yearsToShow} />
              </div>
            </div>
          ))}
        </div>
      </motion.div>
    );
  };

  return (
    <motion.div 
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      className="h-full flex flex-col space-y-6 p-6 bg-[radial-gradient(ellipse_at_top_left,_var(--tw-gradient-stops))] from-white via-slate-50 to-slate-100 dark:bg-none dark:bg-slate-900 transition-colors duration-300 overflow-hidden"
    >
      {/* Header Section */}
      <div className="flex items-center justify-between shrink-0">
        <button 
          onClick={onBack}
          className="p-2 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-xl border border-slate-100 dark:border-slate-700 shadow-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors flex items-center space-x-2"
        >
          <ChevronLeft className="w-5 h-5" />
          <span className="text-sm font-bold pr-2">返回</span>
        </button>
        
        <div className="flex items-center space-x-3">
          <button 
            onClick={() => {
              setFocusedMetricName(null);
              setMessages([{ role: 'ai', content: '已为您重置视图。您可以继续询问关于体检指标的问题。' }]);
            }}
            className="p-2 bg-white dark:bg-slate-800 text-slate-400 dark:text-slate-500 hover:text-brand dark:hover:text-brand-400 border border-slate-100 dark:border-slate-700 shadow-sm rounded-xl transition-all flex items-center space-x-2"
            title="重置视图"
          >
            <RefreshCw className="w-5 h-5" />
          </button>

          <button 
            onClick={() => setIsDarkMode(!isDarkMode)}
            className="p-2 bg-white dark:bg-slate-800 text-slate-400 dark:text-slate-500 hover:text-brand dark:hover:text-brand-400 border border-slate-100 dark:border-slate-700 shadow-sm rounded-xl transition-all"
          >
            {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
        </div>
      </div>

      <div className="flex-1 flex flex-col lg:flex-row gap-6 min-h-0 overflow-hidden">
        {/* Left Column: Unified Customer Info Block */}
        <div className="w-full lg:w-1/3 flex flex-col min-h-0 overflow-hidden shrink-0">
          <div className="bg-white/80 backdrop-blur-xl dark:bg-slate-800 rounded-2xl border border-white/50 dark:border-slate-700 shadow-[0_8px_30px_rgb(0,0,0,0.04)] flex flex-col h-full overflow-hidden">
            {/* Profile Header */}
            <div className="p-6 border-b border-slate-50 dark:border-slate-700/50">
              <div className="flex items-center space-x-4 mb-6">
                <div className="w-16 h-16 rounded-2xl bg-brand/10 flex items-center justify-center shrink-0">
                  <User className="w-8 h-8 text-brand" />
                </div>
                <div className="space-y-1">
                  <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{customer.name || '张美玲'}</h2>
                  <div className="flex items-center space-x-2 text-sm text-slate-500 dark:text-slate-400">
                    <span>{customer.gender || '男'}</span>
                    <span>•</span>
                    <span>{customer.age || '51'}岁</span>
                  </div>
                  <div className="text-xs text-slate-400 font-mono">HZ-2026-0318-078</div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="px-3 py-2.5 bg-blue-50/50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-xl text-xs font-bold text-center border border-blue-100/50 dark:border-blue-800/30">
                  最近体检 2026-03-18
                </div>
                <div className="px-3 py-2.5 bg-emerald-50/50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 rounded-xl text-xs font-bold text-center border border-emerald-100/50 dark:border-emerald-800/30">
                  近三年报告完整
                </div>
              </div>
            </div>

            {/* Scrollable Content Area */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar flex flex-col">
              {/* AI Conclusion Section */}
              <div className="space-y-3 shrink-0">
                <div className="flex items-center space-x-2 text-brand">
                  <Brain className="w-5 h-5" />
                  <span className="text-sm font-bold uppercase tracking-wider">AI 综合结论分析</span>
                </div>
                <div className="relative p-5 bg-gradient-to-br from-blue-50/50 to-indigo-50/30 dark:from-slate-800 dark:to-slate-900/50 rounded-2xl border border-blue-100/50 dark:border-slate-700 shadow-sm">
                  <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed font-medium italic relative z-10">
                    "较 2024 年，空腹血糖、ALT、尿酸持续上升，2026 年已有 6 项指标异常，建议优先关注代谢与肝功能变化，并在 30 天内进行复查。"
                  </p>
                  <div className="absolute top-2 right-3 text-4xl text-slate-200 dark:text-slate-800 font-serif opacity-50">"</div>
                </div>
              </div>

              {/* Health Overview Section */}
              <div className="space-y-4 shrink-0">
                <div className="flex items-center space-x-2 text-slate-700 dark:text-slate-200">
                  <Activity className="w-5 h-5" />
                  <span className="text-sm font-bold uppercase tracking-wider">健康数据概览</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div
                    onClick={() => { setSelectedGroupId('overview'); setSelectedSubGroupId(null); setCurrentCardIdx(0); }}
                    className="group text-center px-3 py-3 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 hover:border-rose-200 dark:hover:border-rose-900/50 transition-all shadow-[0_2px_10px_rgb(0,0,0,0.02)] hover:shadow-[0_8px_20px_rgb(244,63,94,0.08)] cursor-pointer"
                  >
                    <div className="flex items-center justify-center space-x-1 mb-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.4)]"></div>
                      <span className="text-[9px] text-slate-400 uppercase font-bold tracking-widest">异常指标</span>
                    </div>
                    <div className="text-2xl font-black text-slate-900 dark:text-white group-hover:scale-110 transition-transform">{reportData.totalAbnormal}</div>
                  </div>
                  <div className="group text-center px-3 py-3 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 hover:border-amber-200 dark:hover:border-amber-900/50 transition-all shadow-[0_2px_10px_rgb(0,0,0,0.02)] hover:shadow-[0_8px_20px_rgb(245,158,11,0.08)]">
                    <div className="flex items-center justify-center space-x-1 mb-1">
                      <div className="w-1.5 h-1.5 rounded-full bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)]"></div>
                      <span className="text-[9px] text-slate-400 uppercase font-bold tracking-widest">检查项目</span>
                    </div>
                    <div className="text-2xl font-black text-slate-900 dark:text-white group-hover:scale-110 transition-transform">{reportData.totalItems}</div>
                  </div>
                </div>
              </div>

              {/* AI Chat Interface */}
              <div className="flex flex-col flex-1 min-h-[300px] bg-slate-50 dark:bg-slate-900/30 rounded-2xl border border-slate-100 dark:border-slate-700 overflow-hidden">
                <div className="p-3 border-b border-slate-100 dark:border-slate-700 bg-white/50 dark:bg-slate-800/50 flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <div className="w-6 h-6 rounded-lg bg-brand flex items-center justify-center">
                      <Bot className="w-4 h-4 text-white" />
                    </div>
                    <span className="text-xs font-bold text-slate-700 dark:text-slate-200">AI 实时咨询</span>
                  </div>
                  {focusedMetricName && (
                    <button 
                      onClick={() => setFocusedMetricName(null)}
                      className="text-[10px] text-brand hover:underline font-bold"
                    >
                      重置视图
                    </button>
                  )}
                </div>
                
                <div className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar">
                  {messages.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[85%] p-3 rounded-2xl text-xs leading-relaxed ${
                        msg.role === 'user' 
                          ? 'bg-gradient-to-br from-brand to-brand-600 text-white rounded-tr-none shadow-[0_4px_15px_rgba(var(--brand-rgb),0.2)]' 
                          : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-100 dark:border-slate-700 rounded-tl-none shadow-[0_2px_10px_rgb(0,0,0,0.03)]'
                      }`}>
                        {msg.content}
                      </div>
                    </div>
                  ))}
                  {isTyping && (
                    <div className="flex justify-start">
                      <div className="bg-white dark:bg-slate-800 p-3 rounded-2xl rounded-tl-none border border-slate-100 dark:border-slate-700 shadow-[0_2px_10px_rgb(0,0,0,0.03)]">
                        <div className="flex space-x-1">
                          <div className="w-1 h-1 bg-slate-300 rounded-full animate-bounce"></div>
                          <div className="w-1 h-1 bg-slate-300 rounded-full animate-bounce [animation-delay:0.2s]"></div>
                          <div className="w-1 h-1 bg-slate-300 rounded-full animate-bounce [animation-delay:0.4s]"></div>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>

                <form onSubmit={handleSendMessage} className="p-2 bg-white dark:bg-slate-800 border-t border-slate-100 dark:border-slate-700 flex items-center space-x-2">
                  <input 
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder="咨询指标，如：血糖..."
                    className="flex-1 bg-slate-50/50 dark:bg-slate-900 border border-slate-100 dark:border-slate-700 shadow-inner rounded-xl px-4 py-2.5 text-xs focus:ring-2 focus:ring-brand/20 focus:border-brand outline-none dark:text-white transition-all"
                  />
                  <button 
                    type="submit"
                    disabled={isTyping}
                    className="p-2 bg-brand text-white rounded-xl hover:bg-brand-600 transition-colors disabled:opacity-50"
                  >
                    <Send className="w-4 h-4" />
                  </button>
                </form>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Clinical Group Cards + Detail View */}
        <div className="w-full lg:w-2/3 flex flex-col bg-transparent min-h-[500px] overflow-hidden relative">
          <AnimatePresence mode="wait">
            {/* Expanded Detail View — shown when a clinical group card is clicked */}
            {selectedGroupId ? (
              <motion.div
                key={`detail-${selectedGroupId}-${selectedSubGroupId}`}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="absolute inset-0 bg-white dark:bg-slate-900 rounded-[32px] border border-slate-200 dark:border-slate-800 shadow-xl flex flex-col z-20 overflow-hidden"
              >
                {/* Detail Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800 shrink-0">
                  <div className="flex items-center space-x-3">
                    <button
                      onClick={() => { setSelectedGroupId(''); setSelectedSubGroupId(null); }}
                      className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                    >
                      <ArrowLeft className="w-4 h-4" />
                    </button>
                    <div>
                      <h3 className="text-lg font-black text-slate-900 dark:text-white">
                        {selectedGroupId === 'overview' ? '综合概况' :
                         selectedGroupId === 'trend-compare' ? '历年数据对比' :
                         (() => {
                           const g = reportData.clinicalGroups.find(g => g.id === selectedGroupId);
                           return selectedSubGroupId
                             ? `${g?.name} — ${g?.subGroups.find(s => s.id === selectedSubGroupId)?.name}`
                             : g?.name || '';
                         })()}
                      </h3>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedGroupId !== 'overview' && selectedGroupId !== 'trend-compare' && (
                      <>
                        <div className="relative">
                          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                          <input
                            type="text"
                            value={reportSearchQuery}
                            onChange={e => setReportSearchQuery(e.target.value)}
                            placeholder="搜索..."
                            className="pl-8 pr-3 py-1.5 w-36 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700 text-xs text-slate-700 dark:text-slate-300 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand/30"
                          />
                        </div>
                        <div className="flex bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg">
                          <button
                            onClick={() => setClinicalDisplayMode('all')}
                            className={`px-2.5 py-1 rounded-md text-[10px] font-bold transition-all ${clinicalDisplayMode === 'all' ? 'bg-white dark:bg-slate-700 text-brand shadow-sm' : 'text-slate-500 dark:text-slate-400'}`}
                          >全部</button>
                          <button
                            onClick={() => setClinicalDisplayMode('abnormal')}
                            className={`px-2.5 py-1 rounded-md text-[10px] font-bold transition-all ${clinicalDisplayMode === 'abnormal' ? 'bg-white dark:bg-slate-700 text-red-500 shadow-sm' : 'text-slate-500 dark:text-slate-400'}`}
                          >异常</button>
                        </div>
                      </>
                    )}
                    <button
                      onClick={() => { setSelectedGroupId(''); setSelectedSubGroupId(null); }}
                      className="p-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl transition-colors text-slate-500"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Group Switch Tabs */}
                <div className="flex items-center gap-1 px-5 py-2.5 border-b border-slate-100 dark:border-slate-800 shrink-0 overflow-x-auto hide-scrollbar">
                  {CARD_CONFIG.map((cfg, idx) => {
                    const isActive = selectedGroupId === cfg.id;
                    const Icon = cfg.icon;
                    return (
                      <button
                        key={cfg.id}
                        onClick={() => { setSelectedGroupId(cfg.id); setSelectedSubGroupId(null); setReportSearchQuery(''); setCurrentCardIdx(idx); }}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all duration-150 shrink-0 ${
                          isActive
                            ? 'bg-brand text-white shadow-sm'
                            : 'text-slate-400 dark:text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-300'
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                        {cfg.name}
                      </button>
                    );
                  })}
                </div>

                {/* Detail Content */}
                <div className="flex-1 overflow-hidden flex">
                  {/* Sub-group navigation for lab/imaging */}
                  {activeContent && (activeContent.group.id === 'lab' || activeContent.group.id === 'imaging') && activeContent.group.subGroups.length > 1 && (
                    <div className="w-44 shrink-0 border-r border-slate-100 dark:border-slate-800 overflow-y-auto custom-scrollbar py-3 px-2">
                      <button
                        onClick={() => setSelectedSubGroupId(null)}
                        className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs mb-0.5 transition-all ${!selectedSubGroupId ? 'bg-brand/10 text-brand font-bold' : 'text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800'}`}
                      >全部</button>
                      {activeContent.group.subGroups.map(sub => (
                        <button
                          key={sub.id}
                          onClick={() => setSelectedSubGroupId(sub.id)}
                          className={`w-full text-left px-2.5 py-1.5 rounded-lg text-[11px] mb-0.5 transition-all truncate ${selectedSubGroupId === sub.id ? 'bg-brand/10 text-brand font-bold' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800'}`}
                        >
                          {sub.name}
                          {sub.abnormalCount > 0 && <span className="ml-1 text-red-500 text-[10px]">{sub.abnormalCount}</span>}
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="flex-1 overflow-y-auto custom-scrollbar p-5 space-y-4">
                    {selectedGroupId === 'overview' ? (
                      <ReportOverview data={reportData} />
                    ) : selectedGroupId === 'trend-compare' ? (
                      /* Trend comparison: reuse existing metrics + TrendChart */
                      <div className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {metrics.map(m => (
                            <div key={m.name} className="bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700 rounded-2xl p-4 cursor-pointer hover:shadow-md transition-shadow" onClick={() => setFocusedMetricName(m.name)}>
                              <div className="flex justify-between items-start mb-3">
                                <div>
                                  <h5 className="font-bold text-slate-900 dark:text-white">{m.name}</h5>
                                  <p className="text-[10px] text-slate-400">{m.refRange} {m.unit}</p>
                                </div>
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${m.judgment === 'high' ? 'bg-rose-50 text-rose-500 dark:bg-rose-500/10' : m.judgment === 'low' ? 'bg-amber-50 text-amber-500 dark:bg-amber-500/10' : 'bg-emerald-50 text-emerald-500 dark:bg-emerald-500/10'}`}>
                                  {m.judgment === 'high' ? '偏高' : m.judgment === 'low' ? '偏低' : '正常'}
                                </span>
                              </div>
                              <TrendChart m={m} />
                              <p className="text-[10px] text-slate-500 mt-2">{m.trend}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : activeContent ? (
                      <>
                        {activeContent.group.type === 'imaging' ? (
                          <div className="space-y-4">
                            {/* Imaging Compare Toggle */}
                            {examRecords.filter(e => !!e.reportData).length >= 2 && (
                              <div className="flex justify-end">
                                <button
                                  onClick={() => setShowImagingCompare(!showImagingCompare)}
                                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                                    showImagingCompare ? 'bg-brand text-white shadow-sm' : 'bg-brand/10 text-brand hover:bg-brand/20'
                                  }`}
                                >
                                  <BarChart3 className="w-3.5 h-3.5" />
                                  {showImagingCompare ? '返回列表' : '影像对比'}
                                </button>
                              </div>
                            )}
                            {showImagingCompare ? (
                              <ImagingCompare
                                currentSections={reportData.imagingSections}
                                previousSections={reportData.imagingSections}
                                currentLabel={examRecords[0]?.examDate || ''}
                                previousLabel={examRecords[1]?.examDate || ''}
                                onClose={() => setShowImagingCompare(false)}
                              />
                            ) : (
                              <ReportImagingCards sections={reportData.imagingSections} displayMode={clinicalDisplayMode} searchQuery={reportSearchQuery} />
                            )}
                          </div>
                        ) : activeContent.group.type === 'text' ? (
                          <ReportTextSection items={activeContent.items} displayMode={clinicalDisplayMode} searchQuery={reportSearchQuery} title={activeContent.subGroup ? `${activeContent.group.name} - ${activeContent.subGroup.name}` : activeContent.group.name} />
                        ) : (
                          <ReportDataTable items={activeContent.items} displayMode={clinicalDisplayMode} searchQuery={reportSearchQuery} title={activeContent.subGroup ? `${activeContent.group.name} - ${activeContent.subGroup.name}` : activeContent.group.name} />
                        )}
                      </>
                    ) : null}
                  </div>
                </div>
              </motion.div>
            ) : focusedMetricName ? (
              <motion.div
                key="focused-view"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="absolute inset-0 top-10 bg-white dark:bg-slate-900 rounded-[32px] border border-slate-200 dark:border-slate-800 shadow-xl p-8 flex flex-col z-20 overflow-hidden"
              >
                {(() => {
                  const m = metrics.find(m => m.name === focusedMetricName);
                  if (!m) return null;
                  const val2026 = m.values['2026'];
                  const val2025 = m.values['2025'];
                  
                  const isHigh = typeof val2026 === 'number' && val2026 > parseFloat(m.refRange.split('-')[1]);
                  const isLow = typeof val2026 === 'number' && val2026 < parseFloat(m.refRange.split('-')[0]);
                  
                  const diff = (typeof val2026 === 'number' && typeof val2025 === 'number') ? (val2026 - val2025).toFixed(2) : null;
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
                            <h2 className="text-2xl font-black text-slate-900 dark:text-white">{m.name} <span className="text-sm font-bold text-slate-400 ml-2">深度分析</span></h2>
                            <p className="text-sm text-slate-500 font-bold mt-1">参考范围: {m.refRange} {m.unit}</p>
                          </div>
                        </div>
                        <button 
                          onClick={() => setFocusedMetricName(null)}
                          className="p-2.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl transition-colors text-slate-500"
                        >
                          <X className="w-5 h-5" />
                        </button>
                      </div>

                      <div className="grid grid-cols-2 gap-6 mb-8 shrink-0">
                        {/* 2026 Card */}
                        <div className={`p-6 rounded-2xl border ${isHigh ? 'bg-rose-50 border-rose-100 dark:bg-rose-500/10 dark:border-rose-500/20' : isLow ? 'bg-amber-50 border-amber-100 dark:bg-amber-500/10 dark:border-amber-500/20' : 'bg-emerald-50 border-emerald-100 dark:bg-emerald-500/10 dark:border-emerald-500/20'}`}>
                          <div className="text-sm font-bold text-slate-500 dark:text-slate-400 mb-2">最新数值 (2026)</div>
                          <div className="flex items-end space-x-2">
                            <div className={`text-5xl font-black ${isHigh ? 'text-rose-600 dark:text-rose-400' : isLow ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
                              {val2026}
                            </div>
                            <div className="text-sm font-bold text-slate-500 mb-1">{m.unit}</div>
                          </div>
                          <div className="mt-4 inline-block px-3 py-1 rounded-lg text-xs font-bold bg-white/60 dark:bg-slate-900/50">
                            {isHigh ? '指标偏高' : isLow ? '指标偏低' : '指标正常'}
                          </div>
                        </div>

                        {/* 2025 Card */}
                        <div className="p-6 rounded-2xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700">
                          <div className="text-sm font-bold text-slate-500 dark:text-slate-400 mb-2">上一年度 (2025)</div>
                          <div className="flex items-end space-x-2">
                            <div className="text-5xl font-black text-slate-700 dark:text-slate-200">
                              {val2025}
                            </div>
                            <div className="text-sm font-bold text-slate-500 mb-1">{m.unit}</div>
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

                      <div className="flex-1 bg-slate-50 dark:bg-slate-800/30 rounded-2xl border border-slate-100 dark:border-slate-700 p-6 flex flex-col min-h-0 overflow-hidden">
                        <h3 className="text-sm font-bold text-slate-500 dark:text-slate-400 mb-6 uppercase tracking-widest shrink-0">历年趋势 (2018-2026)</h3>
                        <div className="flex-1 w-full overflow-x-auto custom-scrollbar min-h-0 pb-2">
                          <div className="min-w-[600px] w-full h-full flex items-center justify-center">
                            <TrendChart m={m} isExpanded={true} className="h-full w-full max-h-[200px]" />
                          </div>
                        </div>
                        <div className="mt-4 p-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 shrink-0">
                          <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed font-medium">
                            <span className="font-bold text-brand mr-2">AI 分析:</span>
                            {m.trend}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })()}
              </motion.div>
            ) : cardViewMode === 'full' ? (
              <motion.div
                key="full-view"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 flex flex-col overflow-hidden"
              >
                {/* Full View Toolbar */}
                <div className="shrink-0 z-10 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border-b border-slate-100 dark:border-slate-800 rounded-t-2xl px-4 py-2.5">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      {/* View Mode Toggle */}
                      <div className="flex bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg">
                        <button
                          onClick={() => setCardViewMode('stack')}
                          className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                          title="卡片模式"
                        >
                          <Layers className="w-3.5 h-3.5" />
                        </button>
                        <button
                          className="p-1.5 rounded-md bg-brand text-white shadow-sm"
                          title="全览模式"
                        >
                          <List className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <div className="w-px h-5 bg-slate-200 dark:bg-slate-700 mx-1" />
                      {/* Exam Record Pills */}
                      <div className="flex items-center gap-1 overflow-x-auto hide-scrollbar">
                        {examRecords.map((exam, i) => {
                          const isSelected = selectedExamIds.has(exam.id);
                          const hasData = !!exam.reportData;
                          return (
                            <button
                              key={exam.id}
                              onClick={() => toggleExamSelection(exam.id)}
                              disabled={!hasData}
                              className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-semibold whitespace-nowrap transition-all duration-150 shrink-0 ${
                                isSelected
                                  ? 'bg-brand text-white shadow-sm'
                                  : hasData
                                    ? 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                                    : 'text-slate-300 dark:text-slate-600 cursor-not-allowed'
                              }`}
                              title={exam.packageName}
                            >
                              {exam.examDate}
                              {i === 0 && <span className="text-[9px] opacity-70">最新</span>}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {/* Display Mode */}
                      <div className="flex bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg">
                        <button
                          onClick={() => setClinicalDisplayMode('all')}
                          className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-150 ${clinicalDisplayMode === 'all' ? 'bg-white dark:bg-slate-700 text-slate-700 dark:text-slate-200 shadow-sm' : 'text-slate-400 dark:text-slate-500'}`}
                        >全部</button>
                        <button
                          onClick={() => setClinicalDisplayMode('abnormal')}
                          className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-all duration-150 ${clinicalDisplayMode === 'abnormal' ? 'bg-white dark:bg-slate-700 text-red-500 shadow-sm' : 'text-slate-400 dark:text-slate-500'}`}
                        >异常</button>
                      </div>
                      {/* Search */}
                      <div className="relative">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                        <input
                          type="text"
                          value={reportSearchQuery}
                          onChange={e => setReportSearchQuery(e.target.value)}
                          placeholder="搜索指标..."
                          className="pl-8 pr-3 py-1.5 w-44 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700 text-xs text-slate-700 dark:text-slate-300 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand/30"
                        />
                      </div>
                    </div>
                  </div>
                </div>
                {/* Full View Content */}
                <div className="flex-1 overflow-hidden bg-white dark:bg-slate-900 rounded-b-2xl border border-t-0 border-slate-200 dark:border-slate-700">
                  <ReportFullView
                    examRecords={selectedExamRecords}
                    displayMode={clinicalDisplayMode}
                    searchQuery={reportSearchQuery}
                  />
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="card-swap-clinical"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 flex flex-col overflow-hidden"
              >
                {/* Unified Toolbar — nav arrows + tabs + search, solid background */}
                <div className="shrink-0 z-10 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border-b border-slate-100 dark:border-slate-800 rounded-t-2xl px-3 py-2.5 space-y-2">
                  {/* Tab Row: view toggle + arrows + group tabs + counter */}
                  <div className="flex items-center gap-1.5">
                    {/* View Mode Toggle */}
                    <div className="flex bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg shrink-0 mr-1">
                      <button
                        className="p-1.5 rounded-md bg-brand text-white shadow-sm"
                        title="卡片模式"
                      >
                        <Layers className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => setCardViewMode('full')}
                        className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                        title="全览模式"
                      >
                        <List className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <button
                      onClick={() => { cardSwapRef.current?.swapBack(); setCurrentCardIdx(prev => prev <= 0 ? CARD_CONFIG.length - 1 : prev - 1); }}
                      className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors duration-150 shrink-0"
                      title="上一张"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>

                    <div className="flex-1 flex items-center gap-1 overflow-x-auto hide-scrollbar">
                      {CARD_CONFIG.map((cfg, idx) => {
                        const group = reportData.clinicalGroups.find(g => g.id === cfg.id);
                        const hasAbnormal = (group?.abnormalCount ?? 0) > 0 || (cfg.id === 'overview' && reportData.totalAbnormal > 0) || (cfg.id === 'trend-compare' && metrics.some(m => m.judgment !== 'normal'));
                        const Icon = cfg.icon;
                        const isActive = idx === currentCardIdx;
                        return (
                          <button
                            key={cfg.id}
                            onClick={() => {
                              setSelectedGroupId(cfg.id);
                              setSelectedSubGroupId(null);
                              setReportSearchQuery('');
                              setClinicalDisplayMode('all');
                              setCurrentCardIdx(idx);
                            }}
                            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all duration-150 shrink-0 ${
                              isActive
                                ? 'bg-brand text-white shadow-sm'
                                : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-200'
                            }`}
                          >
                            <Icon className="w-3.5 h-3.5" />
                            <span className="hidden lg:inline">{cfg.name}</span>
                            {hasAbnormal && !isActive && (
                              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0" />
                            )}
                          </button>
                        );
                      })}
                    </div>

                    <button
                      onClick={() => { cardSwapRef.current?.swap(); setCurrentCardIdx(prev => prev >= CARD_CONFIG.length - 1 ? 0 : prev + 1); }}
                      className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors duration-150 shrink-0"
                      title="下一张"
                    >
                      <ChevronLeft className="w-4 h-4 rotate-180" />
                    </button>

                    <button
                      onClick={() => { setShowCardSearch(p => !p); if (showCardSearch) setReportSearchQuery(''); }}
                      className={`p-1.5 rounded-lg transition-colors duration-150 shrink-0 ml-1 ${
                        showCardSearch ? 'bg-brand/10 text-brand' : 'text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-600 dark:hover:text-slate-300'
                      }`}
                      title="搜索"
                    >
                      <Search className="w-3.5 h-3.5" />
                    </button>

                    <span className="text-xs text-slate-400 dark:text-slate-500 font-semibold tabular-nums shrink-0">
                      {currentCardIdx + 1}/{CARD_CONFIG.length}
                    </span>
                  </div>

                  {/* Search Row — toggled by search button */}
                  {showCardSearch && (
                    <div className="relative">
                      <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                      <input
                        type="text"
                        autoFocus
                        value={reportSearchQuery}
                        onChange={e => setReportSearchQuery(e.target.value)}
                        placeholder="搜索检查项目..."
                        className="w-full pl-8 pr-8 py-1.5 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700 text-xs text-slate-700 dark:text-slate-300 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand/30"
                      />
                      {reportSearchQuery && (
                        <button
                          onClick={() => setReportSearchQuery('')}
                          className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {/* Card Stack */}
                <div className="flex-1 relative flex items-center justify-center perspective-1000 translate-y-10 scale-[0.92]">
                  <CardSwap
                    ref={cardSwapRef}
                    width="100%"
                    height="100%"
                    pauseOnHover={false}
                    cardDistance={80}
                    verticalDistance={60}
                    delay={0}
                    skewAmount={4}
                    easing="linear"
                  >
                {CARD_CONFIG.map((cfg) => {
                  const group = reportData.clinicalGroups.find(g => g.id === cfg.id);
                  const abnormalCount = group?.abnormalCount ?? (cfg.id === 'overview' ? reportData.totalAbnormal : cfg.id === 'trend-compare' ? metrics.filter(m => m.judgment !== 'normal').length : 0);
                  const totalCount = group?.totalCount ?? (cfg.id === 'overview' ? reportData.totalItems : cfg.id === 'trend-compare' ? metrics.length : 0);
                  const Icon = cfg.icon;

                  // Accent color per card (top border stripe)
                  const accentMap: Record<string, string> = {
                    overview: 'border-t-brand', vitals: 'border-t-emerald-500', lab: 'border-t-violet-500',
                    imaging: 'border-t-orange-500', specialty: 'border-t-rose-500', health: 'border-t-cyan-500',
                    'trend-compare': 'border-t-slate-500',
                  };
                  const accent = accentMap[cfg.id] || 'border-t-brand';

                  return (
                    <Card
                      key={cfg.id}
                      className={`bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl rounded-2xl border border-slate-200 dark:border-slate-700 ${accent} border-t-[3px] shadow-[0_8px_30px_rgb(0,0,0,0.08)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.3)] p-5 flex flex-col cursor-pointer w-full h-full transition-shadow duration-200 hover:shadow-[0_12px_40px_rgb(0,0,0,0.12)]`}
                      onClick={(e: any) => {
                        e.stopPropagation();
                        setSelectedGroupId(cfg.id);
                        setSelectedSubGroupId(null);
                        setReportSearchQuery('');
                        setClinicalDisplayMode('all');
                      }}
                    >
                      {/* Card Header */}
                      <div className="flex items-start justify-between mb-4 shrink-0">
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${cfg.iconBg}`}>
                            <Icon className="w-5 h-5" />
                          </div>
                          <div>
                            <h4 className="text-base font-bold text-slate-900 dark:text-white">{cfg.name}</h4>
                            <div className="flex items-center gap-1.5 mt-1">
                              <span className="text-xs text-slate-400 dark:text-slate-500 tabular-nums">
                                {examRecords[examRecords.length - 1]?.year}–{examRecords[0]?.year}
                              </span>
                              <span className="text-slate-300 dark:text-slate-600">·</span>
                              <span className="text-xs text-slate-500 dark:text-slate-400 tabular-nums">{totalCount} 项</span>
                            </div>
                          </div>
                        </div>
                        {abnormalCount > 0 && (
                          <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-400 tabular-nums">
                            {abnormalCount}
                          </span>
                        )}
                      </div>

                      {/* Card Content — Exam Record Accordion */}
                      <div className="flex-1 overflow-y-auto pr-1 custom-scrollbar space-y-1.5">
                        {(() => {
                          let lastYear = '';
                          return examRecords.map((exam) => {
                            const isExpanded = isExamExpanded(cfg.id, exam.id);
                            const hasData = !!exam.reportData;
                            const examGroup = hasData ? exam.reportData.clinicalGroups.find(g => g.id === cfg.id) : null;
                            const examAbnormal = examGroup?.abnormalCount ?? (cfg.id === 'overview' && hasData ? exam.reportData.totalAbnormal : cfg.id === 'trend-compare' ? metrics.filter(m => m.judgment !== 'normal').length : 0);
                            const showYearDivider = exam.year !== lastYear;
                            lastYear = exam.year;

                            const examTopItems = !hasData ? [] :
                              cfg.id === 'overview'
                                ? exam.reportData.conclusions.slice(0, 6).map(c => c.text)
                                : cfg.id === 'trend-compare'
                                ? metrics.map(m => `${m.name}: ${m.values['2026']} ${m.unit}`)
                                : examGroup?.subGroups.slice(0, 8).map(s => `${s.name}${s.abnormalCount > 0 ? ` (${s.abnormalCount}异常)` : ''}`) ?? [];

                            return (
                              <div key={exam.id}>
                                {showYearDivider && (
                                  <div className="flex items-center gap-2 px-1 pt-2 pb-1">
                                    <span className="text-xs font-bold text-slate-300 dark:text-slate-600 tabular-nums">{exam.year}</span>
                                    <div className="flex-1 h-px bg-slate-100 dark:bg-slate-800" />
                                  </div>
                                )}
                                <div className={`rounded-lg overflow-hidden transition-all duration-150 ${
                                  isExpanded && hasData
                                    ? 'bg-slate-50 dark:bg-slate-800/60 ring-1 ring-slate-200 dark:ring-slate-700'
                                    : 'hover:bg-slate-50/50 dark:hover:bg-slate-800/30'
                                }`}>
                                  {/* Exam Header */}
                                  <div className="flex items-center justify-between px-3 py-2">
                                    <button
                                      onClick={(e) => { e.stopPropagation(); toggleExam(cfg.id, exam.id); }}
                                      className="flex items-center gap-2 flex-1 min-w-0"
                                    >
                                      <div className={`w-1 h-4 rounded-full shrink-0 ${hasData ? (isExpanded ? 'bg-brand' : 'bg-slate-300 dark:bg-slate-600') : 'bg-slate-200 dark:bg-slate-700'}`} />
                                      <span className={`text-sm font-semibold tabular-nums ${hasData ? (isExpanded ? 'text-slate-900 dark:text-white' : 'text-slate-700 dark:text-slate-300') : 'text-slate-400 dark:text-slate-600'}`}>
                                        {exam.examDate}
                                      </span>
                                      {hasData && examAbnormal > 0 && (
                                        <span className="w-5 h-5 rounded-full text-xs font-bold bg-red-100 text-red-600 dark:bg-red-950/50 dark:text-red-400 flex items-center justify-center shrink-0 tabular-nums">
                                          {examAbnormal}
                                        </span>
                                      )}
                                      {!hasData && (
                                        <span className="text-xs text-slate-400 dark:text-slate-600">—</span>
                                      )}
                                      <ChevronDown className={`w-3.5 h-3.5 ml-auto transition-transform duration-200 shrink-0 ${isExpanded ? 'rotate-180 text-slate-600 dark:text-slate-300' : 'text-slate-300 dark:text-slate-600'}`} />
                                    </button>
                                    {isExpanded && hasData && (
                                      <button
                                        onClick={(e) => { e.stopPropagation(); setSelectedYearForModal(exam.year); }}
                                        className="flex items-center gap-1 px-2 py-1 rounded-md text-xs font-semibold text-brand hover:bg-brand/10 transition-colors duration-150 shrink-0 ml-1"
                                        title={`${exam.examDate} 历年对比`}
                                      >
                                        <BarChart3 className="w-3 h-3" />
                                        对比
                                      </button>
                                    )}
                                  </div>
                                  {/* Exam Content */}
                                  {isExpanded && (
                                    <div className="px-3 pb-2.5 space-y-1">
                                      {hasData ? (
                                        examTopItems.map((item, idx) => {
                                          const matchedMetric = metrics.find(m => item.includes(m.name));
                                          const isAbnItem = item.includes('异常') || item.includes('偏高') || item.includes('↑');
                                          const isLowItem = item.includes('偏低') || item.includes('↓');
                                          return (
                                            <div
                                              key={idx}
                                              onClick={(e) => { if (matchedMetric) { e.stopPropagation(); setFocusedMetricName(matchedMetric.name); } }}
                                              className={`flex items-center gap-2.5 px-2.5 py-2 rounded-md transition-all duration-150 ${
                                                matchedMetric
                                                  ? 'cursor-pointer hover:bg-white dark:hover:bg-slate-700 hover:shadow-sm group'
                                                  : ''
                                              } ${isAbnItem ? 'bg-red-50/60 dark:bg-red-950/20' : isLowItem ? 'bg-blue-50/60 dark:bg-blue-950/20' : 'bg-white/60 dark:bg-slate-800/30'}`}
                                            >
                                              <div className={`w-0.5 h-3.5 rounded-full shrink-0 ${isAbnItem ? 'bg-red-400' : isLowItem ? 'bg-blue-400' : 'bg-emerald-400'}`} />
                                              <span className={`text-xs truncate flex-1 ${isAbnItem ? 'text-red-700 dark:text-red-300 font-medium' : isLowItem ? 'text-blue-700 dark:text-blue-300 font-medium' : 'text-slate-600 dark:text-slate-400'}`}>{item}</span>
                                              {matchedMetric && (
                                                <Sparkles className="w-3 h-3 text-slate-300 group-hover:text-brand transition-colors shrink-0" />
                                              )}
                                            </div>
                                          );
                                        })
                                      ) : (
                                        <div className="text-center py-3 text-xs text-slate-400 dark:text-slate-600">
                                          暂未录入数据
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              </div>
                            );
                          });
                        })()}
                      </div>

                      {/* Card Footer */}
                      <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800 shrink-0 flex items-center justify-between">
                        <span className="text-xs text-slate-400 dark:text-slate-500">点击展开完整报告</span>
                        <span className="text-xs font-semibold text-brand">
                          查看详情 →
                        </span>
                      </div>
                    </Card>
                  );
                })}
              </CardSwap>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Comparison Modal */}
      <AnimatePresence>
        {selectedYearForModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-900/60 backdrop-blur-sm">
            <motion.div 
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="bg-white dark:bg-slate-900 w-full max-w-[90vw] h-[85vh] rounded-[32px] shadow-2xl flex flex-col overflow-hidden border border-slate-200 dark:border-slate-700"
            >
              {/* Modal Header */}
              <div className="p-6 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-white dark:bg-slate-900 z-20">
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 rounded-2xl bg-brand/10 flex items-center justify-center">
                    <Activity className="w-6 h-6 text-brand" />
                  </div>
                  <div>
                    <h2 className="text-xl font-black text-slate-900 dark:text-white">历年指标深度对比</h2>
                    <p className="text-xs text-slate-500 font-bold uppercase tracking-widest">以 {selectedYearForModal} 年度为核心</p>
                  </div>
                </div>
                
                <div className="flex items-center space-x-6">
                  {/* View Mode Toggle */}
                  <div className="flex bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
                    <button 
                      onClick={() => setModalViewMode('card')}
                      className={`p-1.5 rounded-lg transition-all ${modalViewMode === 'card' ? 'bg-white dark:bg-slate-700 text-brand shadow-sm' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'}`}
                      title="卡片展示"
                    >
                      <LayoutGrid className="w-4 h-4" />
                    </button>
                    <button 
                      onClick={() => setModalViewMode('list')}
                      className={`p-1.5 rounded-lg transition-all ${modalViewMode === 'list' ? 'bg-white dark:bg-slate-700 text-brand shadow-sm' : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'}`}
                      title="列表展示"
                    >
                      <List className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Filter Tabs - Optimized Style and Moved to Right */}
                  <div className="flex bg-slate-100 dark:bg-slate-800 p-1 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-inner">
                    <button 
                      onClick={() => setModalFilter('all')}
                      className={`px-6 py-2 rounded-xl text-xs font-black transition-all flex items-center space-x-3 ${modalFilter === 'all' ? 'bg-white dark:bg-slate-700 text-brand shadow-md scale-[1.02]' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}
                    >
                      <span>全部指标</span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] ${modalFilter === 'all' ? 'bg-brand/10 text-brand' : 'bg-slate-200 dark:bg-slate-600 text-slate-500'}`}>
                        {metrics.length}
                      </span>
                    </button>
                    <button 
                      onClick={() => setModalFilter('abnormal')}
                      className={`px-6 py-2 rounded-xl text-xs font-black transition-all flex items-center space-x-3 ${modalFilter === 'abnormal' ? 'bg-rose-500 text-white shadow-md scale-[1.02]' : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'}`}
                    >
                      <span>异常关注</span>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] ${modalFilter === 'abnormal' ? 'bg-white/20 text-white' : 'bg-rose-100 dark:bg-rose-900/30 text-rose-500'}`}>
                        {metrics.filter(m => {
                          if (!selectedYearForModal) return false;
                          const val = m.values[selectedYearForModal];
                          if (val === undefined || val === null || val === '') return false;
                          const numVal = Number(val);
                          if (isNaN(numVal)) return false;
                          const [minStr, maxStr] = m.refRange.split('-');
                          const isHigh = numVal > parseFloat(maxStr);
                          const isLow = numVal < parseFloat(minStr);
                          return isHigh || isLow;
                        }).length}
                      </span>
                    </button>
                  </div>

                  <button 
                    onClick={() => setSelectedYearForModal(null)}
                    className="p-2.5 bg-slate-100 dark:bg-slate-800 hover:bg-rose-50 dark:hover:bg-rose-900/30 rounded-2xl transition-all text-slate-400 hover:text-rose-500 group border border-transparent hover:border-rose-200 dark:hover:border-rose-800"
                    title="关闭对比"
                  >
                    <X className="w-6 h-6 transition-transform group-hover:rotate-90" />
                  </button>
                </div>
              </div>

              {/* Modal Content - Four Columns */}
              <div className="flex-1 flex p-8 bg-slate-50/30 dark:bg-slate-900/30 overflow-hidden">
                {(() => {
                  const years = ['2018', '2019', '2020', '2021', '2022', '2023', '2024', '2025', '2026'];
                  const currentIdx = years.indexOf(selectedYearForModal);
                  const prevYear = currentIdx > 0 ? years[currentIdx - 1] : null;
                  const nextYear = currentIdx < years.length - 1 ? years[currentIdx + 1] : null;
                  const prevYearData = getYearData(prevYear);

                  const yearsToShow = [prevYear, selectedYearForModal, nextYear].filter(y => y !== null) as string[];

                  // Calculate which metrics to show based on filter
                  const filteredMetrics = modalFilter === 'all' 
                    ? metrics 
                    : metrics.filter(m => {
                        if (!selectedYearForModal) return false;
                        const val = m.values[selectedYearForModal];
                        if (val === undefined || val === null || val === '') return false;
                        const numVal = Number(val);
                        if (isNaN(numVal)) return false;
                        const [minStr, maxStr] = m.refRange.split('-');
                        const isHigh = numVal > parseFloat(maxStr);
                        const isLow = numVal < parseFloat(minStr);
                        return isHigh || isLow;
                      });

                  const handleDragEnd = (e: any, info: any) => {
                    if (info.offset.x > 100 && prevYear) {
                      setSelectedYearForModal(prevYear);
                    } else if (info.offset.x < -100 && nextYear) {
                      setSelectedYearForModal(nextYear);
                    }
                  };

                  if (modalViewMode === 'list') {
                    // Group metrics by category
                    const groupedMetrics = filteredMetrics.reduce((acc, metric) => {
                      if (!acc[metric.category]) {
                        acc[metric.category] = [];
                      }
                      acc[metric.category].push(metric);
                      return acc;
                    }, {} as Record<string, MetricData[]>);

                    return (
                      <div className="w-full h-full overflow-auto custom-scrollbar bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm">
                        <table className="w-full text-left border-collapse min-w-max">
                          <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900/90 backdrop-blur-md z-10 border-b border-slate-200 dark:border-slate-700">
                            <tr>
                              <th className="py-4 px-6 text-sm font-bold text-slate-500 dark:text-slate-400">检查科室</th>
                              <th className="py-4 px-6 text-sm font-bold text-slate-500 dark:text-slate-400">指标项名称</th>
                              <th className="py-4 px-6 text-sm font-bold text-slate-500 dark:text-slate-400">正常范围</th>
                              {years.map(year => (
                                <th key={year} className="py-4 px-6 text-sm font-bold text-slate-500 dark:text-slate-400 text-center">{year}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 dark:divide-slate-700/50">
                            {Object.entries(groupedMetrics).map(([category, categoryMetrics]) => (
                              categoryMetrics.map((m, idx) => (
                                <tr key={`${category}-${idx}`} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors">
                                  {idx === 0 && (
                                    <td rowSpan={categoryMetrics.length} className="py-5 px-6 font-bold text-slate-600 dark:text-slate-400 border-r border-slate-100 dark:border-slate-700/50 align-top bg-slate-50/30 dark:bg-slate-800/30">
                                      {category}
                                    </td>
                                  )}
                                  <td className="py-5 px-6 font-bold text-slate-900 dark:text-white">{m.name}</td>
                                  <td className="py-5 px-6">
                                    <div className="text-sm text-slate-600 dark:text-slate-300">{m.refRange}</div>
                                    <div className="text-xs text-slate-400">{m.unit}</div>
                                  </td>
                                  {years.map(year => {
                                    const val = m.values[year];
                                    if (val === undefined || val === null || val === '') {
                                      return <td key={year} className="py-5 px-6 text-center text-slate-400">-</td>;
                                    }
                                    const numVal = Number(val);
                                    const [minStr, maxStr] = m.refRange.split('-');
                                    const isHigh = numVal > parseFloat(maxStr);
                                    const isLow = numVal < parseFloat(minStr);
                                    
                                    let statusColor = 'text-emerald-500';
                                    let statusText = '正常';
                                    if (isHigh) {
                                      statusColor = 'text-rose-500';
                                      statusText = '偏高';
                                    } else if (isLow) {
                                      statusColor = 'text-amber-500';
                                      statusText = '偏低';
                                    }

                                    return (
                                      <td key={year} className="py-5 px-6 text-center">
                                        <div className="font-bold text-slate-900 dark:text-white text-base mb-1">{val}</div>
                                        <div className={`text-[10px] font-bold px-2 py-0.5 rounded-full inline-block ${
                                          isHigh ? 'bg-rose-100 dark:bg-rose-500/10 text-rose-500' :
                                          isLow ? 'bg-amber-100 dark:bg-amber-500/10 text-amber-500' :
                                          'bg-emerald-100 dark:bg-emerald-500/10 text-emerald-500'
                                        }`}>{statusText}</div>
                                      </td>
                                    );
                                  })}
                                </tr>
                              ))
                            ))}
                          </tbody>
                        </table>
                      </div>
                    );
                  }

                  return (
                    <motion.div 
                      className="flex-1 flex gap-8 w-full h-full cursor-grab active:cursor-grabbing"
                      drag="x"
                      dragConstraints={{ left: 0, right: 0 }}
                      dragElastic={0.2}
                      onDragEnd={handleDragEnd}
                    >
                      {renderComparisonColumn(prevYear, '前一年度', false, null, leftScrollRef, filteredMetrics)}
                      {renderComparisonColumn(selectedYearForModal, '选中年度', true, prevYearData, centerScrollRef, filteredMetrics)}
                      {renderComparisonColumn(nextYear, '后一年度', false, null, rightScrollRef, filteredMetrics)}
                      {renderTrendColumn(yearsToShow, filteredMetrics)}
                    </motion.div>
                  );
                })()}
              </div>

              {/* Modal Footer */}
              <div className="p-6 bg-slate-50 dark:bg-slate-800/50 border-t border-slate-100 dark:border-slate-700 flex justify-center">
                <div className="flex items-center space-x-12 text-sm font-black">
                  <div className="flex items-center space-x-3">
                    <div className="w-4 h-4 rounded-full bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.4)]"></div>
                    <span className="text-slate-600 dark:text-slate-300">数值上升</span>
                  </div>
                  <div className="flex items-center space-x-3">
                    <div className="w-4 h-4 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.4)]"></div>
                    <span className="text-slate-600 dark:text-slate-300">数值下降</span>
                  </div>
                  <div className="flex items-center space-x-3">
                    <div className="w-4 h-4 rounded-full bg-slate-400 shadow-[0_0_10px_rgba(148,163,184,0.4)]"></div>
                    <span className="text-slate-600 dark:text-slate-300">保持稳定</span>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};
