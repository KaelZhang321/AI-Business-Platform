import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ChevronLeft, Moon, Sun, Search, FileText, MessageSquare, Info, ChevronDown, Check, Loader2, GripVertical, X, Plus, Sparkles, Send } from 'lucide-react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
  defaultDropAnimationSideEffects,
  useDroppable,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import TargetCursor from './TargetCursor';
import type { AppPage } from '../../navigation';

const MOCK_CLIENTS = [
  { id: '1', name: '张美玲', phone: '138****5678', avatar: 'https://i.pravatar.cc/150?u=zhang' },
  { id: '2', name: '张美玲', phone: '139****1234', avatar: 'https://i.pravatar.cc/150?u=wang' },
  { id: '3', name: '张美玲', phone: '137****8888', avatar: 'https://i.pravatar.cc/150?u=li' },
];

const MOCK_REPORTS: Record<string, { id: string; title: string; date: string }[]> = {
  '1': [
    { id: 'R1', title: '2024年度深度体检报告', date: '2024-03-15' },
    { id: 'R2', title: '2023年度常规体检报告', date: '2023-03-10' },
  ],
  '2': [
    { id: 'R3', title: '2024年第一季度健康监测', date: '2024-01-20' },
  ],
  '3': [
    { id: 'R4', title: '心血管专项筛查报告', date: '2024-02-28' },
  ],
};

const INITIAL_ANALYSIS_RESULTS = {
  monitoring: [
    { id: 'm1', content: '血管抗衰养护 + 重金属螯合' },
    { id: 'm2', content: '代谢管理2025' }
  ],
  intervention: [
    { id: 'i1', content: '肝胆双益' },
    { id: 'i2', content: '粘膜修复' }
  ],
  maintenance: [
    { id: 'ma1', content: '前列腺PET-MRI (PSMA)' },
    { id: 'ma2', content: '男性荷尔蒙调理' },
    { id: 'ma3', content: '食物不耐受90项' }
  ],
  prevention: [
    { id: 'p1', content: '菲净素 (肺结节、甲状腺结节)' }
  ],
  conclusion: "已结合体检报告和医生备注，判断心血管风险与脂代谢异常聚集，需优先处理A级-红色健康预警。",
  clientInfo: "张美玲 / 138****5678",
  reportInfo: "2024年度深度体检报告",
  riskLevel: '中高风险',
  score: 68
};

interface SortableItemProps {
  id: string;
  content: string;
  onRemove: (id: string) => void;
  colorClass: string;
  handleColorClass: string;
  key?: React.Key;
}

const SortableItem = ({ id, content, onRemove, colorClass, handleColorClass }: SortableItemProps) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center justify-between p-3 mb-3 bg-white dark:bg-slate-800 rounded-xl border shadow-sm group cursor-target ${colorClass}`}
    >
      <div className="flex items-center flex-1 min-w-0">
        <div
          {...attributes}
          {...listeners}
          className={`cursor-grab active:cursor-grabbing p-1 mr-2 ${handleColorClass}`}
        >
          <GripVertical className="w-4 h-4" />
        </div>
        <span className="text-sm text-slate-700 dark:text-slate-200 truncate">{content}</span>
      </div>
      <button
        onClick={() => onRemove(id)}
        className="w-6 h-6 flex items-center justify-center rounded-full bg-slate-100 dark:bg-slate-700 text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-600 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
};

interface QuadrantProps {
  id: string;
  title: string;
  items: { id: string; content: string }[];
  colorTheme: 'amber' | 'red' | 'blue' | 'orange';
  onRemoveItem: (id: string) => void;
  onAddItem: (content: string) => void;
  isAnalyzing: boolean;
  hasResult: boolean;
}

const Quadrant = ({ id, title, items, colorTheme, onRemoveItem, onAddItem, isAnalyzing, hasResult }: QuadrantProps) => {
  const [newItemContent, setNewItemContent] = useState('');
  const [isAdding, setIsAdding] = useState(false);
  const { setNodeRef } = useDroppable({ id });

  const themeClasses = {
    amber: {
      bg: 'bg-[#FFFBEB] dark:bg-amber-900/10',
      border: 'border-amber-100 dark:border-amber-900/30',
      text: 'text-amber-600 dark:text-amber-500',
      btnBorder: 'border-amber-500',
      btnText: 'text-amber-600',
      itemColor: 'border-amber-100/50 dark:border-amber-800/30 hover:border-amber-200',
      handleColor: 'text-amber-400',
      iconColor: 'text-amber-500'
    },
    red: {
      bg: 'bg-[#FEF2F2] dark:bg-red-900/10',
      border: 'border-red-100 dark:border-red-900/30',
      text: 'text-red-500 dark:text-red-400',
      btnBorder: 'border-red-500',
      btnText: 'text-red-500',
      itemColor: 'border-red-100/50 dark:border-red-800/30 hover:border-red-200',
      handleColor: 'text-red-400',
      iconColor: 'text-red-500'
    },
    blue: {
      bg: 'bg-[#EFF6FF] dark:bg-blue-900/10',
      border: 'border-blue-100 dark:border-blue-900/30',
      text: 'text-blue-600 dark:text-blue-500',
      btnBorder: 'border-blue-500',
      btnText: 'text-blue-600',
      itemColor: 'border-blue-100/50 dark:border-blue-800/30 hover:border-blue-200',
      handleColor: 'text-blue-400',
      iconColor: 'text-blue-500'
    },
    orange: {
      bg: 'bg-[#FFF7ED] dark:bg-orange-900/10',
      border: 'border-orange-100 dark:border-orange-900/30',
      text: 'text-orange-600 dark:text-orange-500',
      btnBorder: 'border-orange-500',
      btnText: 'text-orange-600',
      itemColor: 'border-orange-100/50 dark:border-orange-800/30 hover:border-orange-200',
      handleColor: 'text-orange-400',
      iconColor: 'text-orange-500'
    }
  };

  const theme = themeClasses[colorTheme];

  const handleAdd = () => {
    if (newItemContent.trim()) {
      onAddItem(newItemContent.trim());
      setNewItemContent('');
      setIsAdding(false);
    }
  };

  return (
    <div ref={setNodeRef} className={`rounded-2xl p-5 border flex flex-col overflow-hidden cursor-target ${theme.bg} ${theme.border}`}>
      <div className="flex items-center justify-between mb-4 shrink-0">
        <h4 className={`font-bold text-lg ${theme.text}`}>{title}</h4>
        {hasResult && (
          <button
            onClick={() => setIsAdding(true)}
            className={`px-4 py-1.5 text-xs rounded-full border bg-white dark:bg-slate-800 flex items-center ${theme.btnBorder} ${theme.btnText}`}
          >
            <Plus className="w-3 h-3 mr-1" /> 添加
          </button>
        )}
      </div>

      <div className="flex-1 flex flex-col overflow-y-auto custom-scrollbar pr-1">
        {isAnalyzing ? (
          <div className="flex flex-col items-center justify-center h-full space-y-2 opacity-50">
            <Loader2 className={`w-6 h-6 animate-spin ${theme.iconColor}`} />
            <p className={`text-xs ${theme.text}`}>处理中...</p>
          </div>
        ) : hasResult ? (
          <div className="flex flex-col h-full">
            <SortableContext id={id} items={items.map(i => i.id)} strategy={verticalListSortingStrategy}>
              <div className="flex-1 min-h-[50px]">
                {items.map((item) => (
                  <SortableItem
                    key={item.id}
                    id={item.id}
                    content={item.content}
                    onRemove={onRemoveItem}
                    colorClass={theme.itemColor}
                    handleColorClass={theme.handleColor}
                  />
                ))}
              </div>
            </SortableContext>

            {isAdding && (
              <div className="mt-2 flex items-center space-x-2 bg-white dark:bg-slate-800 p-2 rounded-xl border shadow-sm">
                <input
                  type="text"
                  value={newItemContent}
                  onChange={(e) => setNewItemContent(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
                  placeholder="输入新项..."
                  className="flex-1 px-2 py-1 text-sm border-none bg-transparent text-slate-900 dark:text-white focus:outline-none focus:ring-0"
                  autoFocus
                />
                <button onClick={handleAdd} className="p-1.5 text-green-600 hover:bg-green-50 rounded-lg">
                  <Check className="w-4 h-4" />
                </button>
                <button onClick={() => setIsAdding(false)} className="p-1.5 text-slate-400 hover:bg-slate-100 rounded-lg">
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col justify-center items-center h-full text-center px-4 bg-white/50 dark:bg-slate-800/30 rounded-xl border border-white/50 dark:border-slate-700/30">
            <h5 className="text-slate-500 dark:text-slate-400 font-bold mb-1 text-sm">等待 AI 填充</h5>
            <p className="text-xs text-slate-400 dark:text-slate-500">完成选择后，可补充备注给 AI 进一步校准。</p>
          </div>
        )}
      </div>
    </div>
  );
};

interface AIFourQuadrantViewProps {
  setCurrentPage: (page: AppPage) => void;
  isDarkMode: boolean;
  setIsDarkMode: (value: boolean) => void;
  hideHeader?: boolean;
}

export const AIFourQuadrantView: React.FC<AIFourQuadrantViewProps> = ({ setCurrentPage, isDarkMode, setIsDarkMode, hideHeader = false }) => {
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [notes, setNotes] = useState('');

  const [isClientDropdownOpen, setIsClientDropdownOpen] = useState(false);
  const [isReportDropdownOpen, setIsReportDropdownOpen] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showResults, setShowResults] = useState(false);

  const [chatMessages, setChatMessages] = useState([
    { id: 1, sender: 'ai', text: '补充问诊备注或调整指令，我会联动右侧结果。' },
    { id: 2, sender: 'user', text: '补充：近一周睡眠差，重新判断象限' }
  ]);
  const [chatInput, setChatInput] = useState('');

  const [quadrantData, setQuadrantData] = useState<{
    monitoring: { id: string; content: string }[];
    intervention: { id: string; content: string }[];
    maintenance: { id: string; content: string }[];
    prevention: { id: string; content: string }[];
  }>({
    monitoring: [],
    intervention: [],
    maintenance: [],
    prevention: []
  });

  const [activeId, setActiveId] = useState<string | null>(null);

  const selectedClient = MOCK_CLIENTS.find(c => c.id === selectedClientId);
  const availableReports = selectedClientId ? MOCK_REPORTS[selectedClientId] || [] : [];
  const selectedReport = availableReports.find(r => r.id === selectedReportId);

  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisStep, setAnalysisStep] = useState('');

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleStartAnalysis = async () => {
    if (!selectedClientId || !selectedReportId) return;
    setIsAnalyzing(true);
    setAnalysisProgress(0);
    setQuadrantData({ monitoring: [], intervention: [], maintenance: [], prevention: [] });

    const steps = [
      '正在读取体检报告数据...',
      '正在解析医生面诊备注...',
      '正在匹配健康指标基准...',
      '正在进行多维风险评估...',
      '正在生成四象限建议...',
      '分析完成，正在同步结果...'
    ];

    let stepIdx = 0;
    setAnalysisStep(steps[0]);

    const interval = setInterval(() => {
      setAnalysisProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          return 100;
        }
        const next = prev + (Math.random() * 10 + 2);
        const currentStepIdx = Math.min(Math.floor((next / 100) * steps.length), steps.length - 1);
        if (currentStepIdx !== stepIdx) {
          stepIdx = currentStepIdx;
          setAnalysisStep(steps[stepIdx]);
        }
        return next > 100 ? 100 : next;
      });
    }, 150);

    setTimeout(() => {
      setIsAnalyzing(false);
      setQuadrantData({
        monitoring: [...INITIAL_ANALYSIS_RESULTS.monitoring],
        intervention: [...INITIAL_ANALYSIS_RESULTS.intervention],
        maintenance: [...INITIAL_ANALYSIS_RESULTS.maintenance],
        prevention: [...INITIAL_ANALYSIS_RESULTS.prevention]
      });
      setAnalysisProgress(100);
      setShowResults(true);
    }, 2500);
  };

  const handleReset = () => {
    setShowResults(false);
    setQuadrantData({ monitoring: [], intervention: [], maintenance: [], prevention: [] });
    setSelectedReportId(null);
    setNotes('');
  };

  useEffect(() => {
    setSelectedReportId(null);
    setQuadrantData({ monitoring: [], intervention: [], maintenance: [], prevention: [] });
    setShowResults(false);
  }, [selectedClientId]);

  const handleDragStart = (event: any) => {
    setActiveId(event.active.id);
  };

  const handleDragOver = (event: any) => {
    const { active, over } = event;
    if (!over) return;

    const activeContainer = findContainer(active.id);
    const overContainer = findContainer(over.id) || over.id;

    if (!activeContainer || !overContainer || activeContainer === overContainer) {
      return;
    }

    setQuadrantData((prev) => {
      const activeItems = prev[activeContainer as keyof typeof quadrantData];
      const overItems = prev[overContainer as keyof typeof quadrantData];

      const activeIndex = activeItems.findIndex((item) => item.id === active.id);
      const overIndex = over.id in prev ? overItems.length : overItems.findIndex((item) => item.id === over.id);

      const newActiveItems = [...activeItems];
      const [itemToMove] = newActiveItems.splice(activeIndex, 1);

      const newOverItems = [...overItems];
      newOverItems.splice(overIndex >= 0 ? overIndex : newOverItems.length, 0, itemToMove);

      return {
        ...prev,
        [activeContainer]: newActiveItems,
        [overContainer]: newOverItems,
      };
    });
  };

  const handleDragEnd = (event: any) => {
    const { active, over } = event;
    setActiveId(null);

    if (!over) return;

    const activeContainer = findContainer(active.id);
    const overContainer = findContainer(over.id) || over.id;

    if (!activeContainer || !overContainer || activeContainer !== overContainer) {
      return;
    }

    const items = quadrantData[activeContainer as keyof typeof quadrantData];
    const oldIndex = items.findIndex(item => item.id === active.id);
    const newIndex = items.findIndex(item => item.id === over.id);

    if (oldIndex !== newIndex) {
      setQuadrantData(prev => ({
        ...prev,
        [activeContainer]: arrayMove(items, oldIndex, newIndex),
      }));
    }
  };

  const findContainer = (id: string) => {
    if (id in quadrantData) {
      return id;
    }
    return Object.keys(quadrantData).find(key =>
      quadrantData[key as keyof typeof quadrantData].some(item => item.id === id)
    );
  };

  const handleRemoveItem = (containerId: string, itemId: string) => {
    setQuadrantData(prev => ({
      ...prev,
      [containerId]: prev[containerId as keyof typeof quadrantData].filter(item => item.id !== itemId)
    }));
  };

  const handleAddItem = (containerId: string, content: string) => {
    const newItem = { id: `new-${Date.now()}`, content };
    setQuadrantData(prev => ({
      ...prev,
      [containerId]: [...prev[containerId as keyof typeof quadrantData], newItem]
    }));
  };

  const handleSendMessage = () => {
    if (!chatInput.trim()) return;

    const currentInput = chatInput.trim();
    const newUserMsg = { id: Date.now(), sender: 'user', text: currentInput };
    setChatMessages(prev => [...prev, newUserMsg]);
    setChatInput('');

    setIsAnalyzing(true);
    setAnalysisProgress(0);
    setAnalysisStep('正在结合补充信息重新评估...');

    const interval = setInterval(() => {
      setAnalysisProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          return 100;
        }
        return prev + (Math.random() * 20 + 10);
      });
    }, 200);

    setTimeout(() => {
      clearInterval(interval);
      setIsAnalyzing(false);
      setAnalysisProgress(100);

      if (currentInput === '补充窦性心率异常') {
        const aiResponse = { id: Date.now() + 1, sender: 'ai', text: '已为您将“窦性心率异常”添加到定期检测区。' };
        setChatMessages(prev => [...prev, aiResponse]);

        setQuadrantData(prev => ({
          ...prev,
          monitoring: [...prev.monitoring, { id: `m-${Date.now()}`, content: '窦性心率异常' }]
        }));
      } else {
        const aiResponse = { id: Date.now() + 1, sender: 'ai', text: '已收到您的补充信息，并根据最新情况更新了四象限结果。' };
        setChatMessages(prev => [...prev, aiResponse]);

        setQuadrantData(prev => ({
          ...prev,
          intervention: [...prev.intervention, { id: `i-${Date.now()}`, content: currentInput }]
        }));
      }
    }, 2500);
  };

  const getActiveItemContent = () => {
    if (!activeId) return null;
    for (const key in quadrantData) {
      const item = quadrantData[key as keyof typeof quadrantData].find(i => i.id === activeId);
      if (item) return item.content;
    }
    return null;
  };

  return (
    <div className="space-y-6 h-full flex flex-col relative">
      <TargetCursor targetSelector=".cursor-target" containerSelector=".quadrants-container" />
      {/* Header */}
      {!hideHeader && (
        <div className="flex items-center justify-between px-8 pt-4 shrink-0">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setCurrentPage('function-square')}
              className="p-2 bg-white dark:bg-slate-800 rounded-xl shadow-sm hover:shadow-md transition-all text-slate-500 dark:text-slate-400 hover:text-brand dark:hover:text-brand-400"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <div>
              <div className="flex items-center space-x-3">
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">AI四象限健康评估</h1>
              </div>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">医生进入页面后默认看到空白四象限，先选择客户与体检报告，也可补充当前问诊备注。</p>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <span className="px-3 py-1 bg-blue-50 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400 text-xs rounded-full border border-blue-100 dark:border-blue-800">医生身份</span>
              <span className={`px-3 py-1 text-xs rounded-full border ${selectedClient ? 'bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400 border-green-100 dark:border-green-800' : 'bg-red-50 text-red-500 dark:bg-red-900/30 dark:text-red-400 border-red-100 dark:border-red-800'}`}>
                {selectedClient ? '已选中客户' : '未选中客户'}
              </span>
              <span className="px-3 py-1 bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 text-xs rounded-full border border-slate-200 dark:border-slate-700">等待AI分析</span>
            </div>
            <button
              onClick={() => setIsDarkMode(!isDarkMode)}
              className="p-2 text-slate-400 dark:text-slate-500 hover:text-brand dark:hover:text-brand-400 hover:bg-brand-light dark:hover:bg-brand-900/30 rounded-xl transition-all"
            >
              {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
          </div>
        </div>
      )}

      <div className={`px-8 flex gap-6 flex-1 items-stretch overflow-hidden ${hideHeader ? 'pt-8' : ''}`}>
        {/* Left Sidebar */}
        <div className="w-[360px] shrink-0 flex flex-col">
          <div className="bg-white dark:bg-slate-800 rounded-2xl p-6 shadow-sm border border-slate-100 dark:border-slate-700 h-full flex flex-col">
            {!showResults ? (
              <>
                <div className="mb-6">
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-2">选择输入</h2>
                </div>

                <div className="space-y-4 flex-1">
                  {/* Client Selection */}
                  <div className="space-y-2 relative">
                    <label className="text-sm font-bold text-brand dark:text-brand-400">选择客户</label>
                    <button
                      onClick={() => setIsClientDropdownOpen(!isClientDropdownOpen)}
                      className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand/50 dark:text-white transition-all"
                    >
                      <span className={selectedClient ? 'text-slate-900 dark:text-white' : 'text-slate-400'}>
                        {selectedClient ? `${selectedClient.name} (${selectedClient.phone})` : '请选择客户姓名 / 手机号'}
                      </span>
                      <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${isClientDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>

                    <AnimatePresence>
                      {isClientDropdownOpen && (
                        <motion.div
                          initial={{ opacity: 0, y: -10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -10 }}
                          className="absolute z-50 top-full left-0 w-full mt-2 bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-xl shadow-xl overflow-hidden"
                        >
                          {MOCK_CLIENTS.map(client => (
                            <button
                              key={client.id}
                              onClick={() => {
                                setSelectedClientId(client.id);
                                setIsClientDropdownOpen(false);
                              }}
                              className="w-full flex items-center px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors text-left"
                            >
                              <img src={client.avatar} alt="" className="w-8 h-8 rounded-full mr-3" />
                              <div className="flex-1">
                                <p className="text-sm font-bold text-slate-900 dark:text-white">{client.name}</p>
                                <p className="text-xs text-slate-500">{client.phone}</p>
                              </div>
                              {selectedClientId === client.id && <Check className="w-4 h-4 text-brand" />}
                            </button>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  {/* Report Selection */}
                  <div className="space-y-2 relative">
                    <label className="text-sm font-bold text-brand dark:text-brand-400">体检报告</label>
                    <button
                      disabled={!selectedClientId}
                      onClick={() => setIsReportDropdownOpen(!isReportDropdownOpen)}
                      className={`w-full flex items-center justify-between px-4 py-3 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand/50 dark:text-white transition-all ${!selectedClientId ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      <span className={selectedReport ? 'text-slate-900 dark:text-white' : 'text-slate-400'}>
                        {selectedReport ? selectedReport.title : '请先选择客户后再选择报告'}
                      </span>
                      <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${isReportDropdownOpen ? 'rotate-180' : ''}`} />
                    </button>

                    <AnimatePresence>
                      {isReportDropdownOpen && (
                        <motion.div
                          initial={{ opacity: 0, y: -10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -10 }}
                          className="absolute z-50 top-full left-0 w-full mt-2 bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 rounded-xl shadow-xl overflow-hidden"
                        >
                          {availableReports.map(report => (
                            <button
                              key={report.id}
                              onClick={() => {
                                setSelectedReportId(report.id);
                                setIsReportDropdownOpen(false);
                              }}
                              className="w-full flex items-center px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors text-left"
                            >
                              <div className="flex-1">
                                <p className="text-sm font-bold text-slate-900 dark:text-white">{report.title}</p>
                                <p className="text-xs text-slate-500">{report.date}</p>
                              </div>
                              {selectedReportId === report.id && <Check className="w-4 h-4 text-brand" />}
                            </button>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  {/* Notes Input */}
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-brand dark:text-brand-400">补充备注给AI小助手</label>
                    <textarea
                      placeholder="记录当前症状、近期变化或问诊补充，AI将结合备注和报告综合判断四象限"
                      className="w-full p-4 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-700 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand/50 min-h-[100px] resize-none dark:text-white"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>

                  <button
                    onClick={handleStartAnalysis}
                    className={`w-full py-3 font-bold rounded-xl transition-all flex items-center justify-center space-x-2 ${selectedClientId && selectedReportId && !isAnalyzing
                      ? 'bg-brand text-white hover:bg-brand-hover shadow-lg shadow-brand/20'
                      : 'bg-slate-100 dark:bg-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed'
                      }`}
                    disabled={!selectedClientId || !selectedReportId || isAnalyzing}
                  >
                    {isAnalyzing ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>AI 深度分析中...</span>
                      </>
                    ) : (
                      <>
                        <Search className="w-4 h-4" />
                        <span>开始联合分析</span>
                      </>
                    )}
                  </button>
                </div>

                <div className="mt-8 space-y-3 shrink-0">
                  <h4 className="text-sm font-bold text-slate-900 dark:text-white mb-4">页面提示</h4>
                  <div className="flex items-start space-x-2 text-sm text-slate-600 dark:text-slate-400">
                    <div className="w-1.5 h-1.5 rounded-full bg-brand mt-1.5 shrink-0"></div>
                    <p>客户选定后自动解锁体检报告选择。</p>
                  </div>
                  <div className="flex items-start space-x-2 text-sm text-slate-600 dark:text-slate-400">
                    <div className="w-1.5 h-1.5 rounded-full bg-brand mt-1.5 shrink-0"></div>
                    <p>未完成基础输入时，右侧只展示四象限骨架。</p>
                  </div>
                  <div className="flex items-start space-x-2 text-sm text-slate-600 dark:text-slate-400">
                    <div className="w-1.5 h-1.5 rounded-full bg-brand mt-1.5 shrink-0"></div>
                    <p>报告选中后可补充备注，AI 会结合两类信息自动开始分析。</p>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex flex-col h-full">
                <div className="mb-2">
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-2">报告与统计</h2>
                </div>

                <div className="space-y-4 overflow-y-auto pr-2 custom-scrollbar shrink-0">
                  {/* Client Info Card */}
                  <div className="p-4 bg-white dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-700">
                    <p className="text-xs font-bold text-brand mb-2">客户</p>
                    <p className="text-sm font-bold text-slate-900 dark:text-white">{INITIAL_ANALYSIS_RESULTS.clientInfo}</p>
                  </div>

                  {/* Report Info Card */}
                  <div className="p-4 bg-white dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-700">
                    <p className="text-xs font-bold text-brand mb-2">体检报告</p>
                    <p className="text-sm font-bold text-slate-900 dark:text-white">{INITIAL_ANALYSIS_RESULTS.reportInfo}</p>
                  </div>

                  {/* AI Conclusion Card */}
                  <div className="p-4 bg-white dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-700">
                    <p className="text-xs font-bold text-brand mb-2">AI结论</p>
                    <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                      {INITIAL_ANALYSIS_RESULTS.conclusion}
                    </p>
                  </div>
                </div>

                {/* AI Assistant Chatbox */}
                <div className="mt-2 bg-white dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden flex flex-col flex-1">
                  <div className="flex border-b border-slate-200 dark:border-slate-700">
                    <div className="flex-1 py-2 text-xs font-bold text-brand bg-brand/5 border-b-2 border-brand text-center">AI小助手</div>
                  </div>
                  <div className="p-4 flex-1 flex flex-col min-h-0">
                    <h4 className="text-sm font-bold text-slate-900 dark:text-white mb-4">备注联动四象限</h4>
                    <div className="space-y-4 flex-1 overflow-y-auto mb-4 custom-scrollbar">
                      {chatMessages.map(msg => (
                        <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                          {msg.sender === 'ai' && (
                            <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0 mr-2 mt-0.5 transition-colors duration-300">
                              <Sparkles className="w-3 h-3 text-brand dark:text-brand-400" />
                            </div>
                          )}
                          <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs leading-relaxed shadow-sm transition-colors duration-300 ${msg.sender === 'user'
                            ? 'bg-blue-500 text-white rounded-tr-sm'
                            : 'bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 text-slate-700 dark:text-slate-300 rounded-tl-sm'
                            }`}>
                            {msg.text}
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="relative flex items-center">
                      <input
                        type="text"
                        placeholder="输入备注或调整指令"
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                        className="w-full bg-slate-100/80 dark:bg-slate-900/80 border-transparent rounded-2xl pl-4 pr-12 py-2.5 text-xs focus:bg-white dark:focus:bg-slate-800 focus:border-brand dark:focus:border-brand-500 focus:ring-2 focus:ring-brand/10 dark:focus:ring-brand/20 transition-all outline-none text-slate-800 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500"
                      />
                      <button
                        onClick={handleSendMessage}
                        disabled={!chatInput.trim()}
                        className="absolute right-1.5 w-7 h-7 flex items-center justify-center bg-gradient-to-r from-brand to-brand-hover text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-md hover:shadow-brand/20 transition-all cursor-target"
                      >
                        <Send className="w-3.5 h-3.5 ml-0.5" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Main Area */}
        <div className="flex-1 flex flex-col space-y-6">
          {/* Top Banner */}
          {showResults ? (
            <div className="bg-[#1E293B] dark:bg-slate-800 rounded-2xl p-6 flex items-center justify-between shadow-sm shrink-0">
              <div className="space-y-3">
                <h2 className="text-2xl font-bold text-white">AI 已生成可编辑四象限结果</h2>
                <p className="text-sm text-slate-300">
                  医生可以基于 AI 的初始归类直接做二次判断。添加、删除和拖拽能力都内聚在四象限结果区中。
                </p>
                <div className="flex items-center space-x-3 pt-2">
                  <span className="px-4 py-1.5 bg-slate-700/50 text-slate-300 text-xs rounded-full border border-slate-600">立即干预 4项</span>
                  <span className="px-4 py-1.5 bg-slate-700/50 text-slate-300 text-xs rounded-full border border-slate-600">支持拖拽调整</span>
                  <span className="px-4 py-1.5 bg-slate-700/50 text-slate-300 text-xs rounded-full border border-slate-600">支持手动添加/删除</span>
                </div>
              </div>
              <div className="bg-slate-800/80 border border-slate-600 rounded-xl p-4 w-64 shrink-0">
                <p className="text-xs text-slate-400 mb-2">当前重点</p>
                <p className="text-sm font-bold text-white">结果已生成，可继续人工修正</p>
              </div>
            </div>
          ) : (
            <div className="bg-[#1E293B] dark:bg-slate-800 rounded-2xl p-6 flex items-center justify-between shadow-sm transition-colors duration-300 shrink-0 relative overflow-hidden">
              {isAnalyzing && (
                <motion.div
                  initial={{ x: '-100%' }}
                  animate={{ x: '100%' }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                  className="absolute inset-0 bg-gradient-to-r from-transparent via-brand/10 to-transparent pointer-events-none"
                />
              )}

              <div className="space-y-2 relative z-10">
                <div className="flex items-center space-x-3">
                  <h2 className="text-xl font-bold text-white">
                    {isAnalyzing ? 'AI 正在进行多维联合评估...' : selectedClientId && selectedReportId ? '信息已完善，可开始 AI 联合评估' : '请先完成客户与体检报告选择'}
                  </h2>
                </div>
                <p className="text-sm text-slate-400">
                  {isAnalyzing
                    ? `正在处理：${analysisStep}`
                    : selectedClientId && selectedReportId
                      ? '“开始联合分析”按钮，AI 将结合体检报告与您的备注，自动生成四象限健康评估。'
                      : '页面初始化为未选择状态，右侧仅保留四象限工作区结构；可先录入备注，再由 AI 联合评估。'}
                </p>

                {isAnalyzing && (
                  <div className="w-full max-w-md mt-4">
                    <div className="flex justify-between text-xs text-brand-300 mb-1">
                      <span>分析进度</span>
                      <span>{Math.round(analysisProgress)}%</span>
                    </div>
                    <div className="h-1.5 w-full bg-slate-700 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-brand"
                        initial={{ width: 0 }}
                        animate={{ width: `${analysisProgress}%` }}
                      />
                    </div>
                  </div>
                )}

                <div className="flex items-center space-x-2 pt-2">
                  {selectedClient && (
                    <div className="flex items-center px-3 py-1 bg-slate-700/50 text-slate-300 border border-slate-600 text-xs rounded-full">
                      <img src={selectedClient.avatar} alt="" className="w-4 h-4 rounded-full mr-2" />
                      <span>{selectedClient.name}</span>
                    </div>
                  )}
                  {selectedReport && (
                    <div className="flex items-center px-3 py-1 bg-slate-700/50 text-slate-300 border border-slate-600 text-xs rounded-full">
                      <FileText className="w-3 h-3 mr-2" />
                      <span>{selectedReport.title}</span>
                    </div>
                  )}
                  <span className={`px-3 py-1 text-xs rounded-full border ${notes ? 'bg-brand/20 text-brand-300 border-brand/30' : 'bg-slate-700/50 text-slate-300 border-slate-600'}`}>
                    {notes ? '已填备注' : '无备注'}
                  </span>
                </div>
              </div>
              <div className="bg-slate-800/50 dark:bg-slate-900/50 border border-slate-700 rounded-xl p-4 w-64 shrink-0 relative z-10">
                <p className="text-xs text-slate-400 mb-1">当前状态</p>
                <div className="flex items-center space-x-2">
                  {isAnalyzing ? (
                    <Loader2 className="w-4 h-4 text-brand animate-spin" />
                  ) : (
                    <div className={`w-2 h-2 rounded-full bg-amber-500`} />
                  )}
                  <p className="text-sm font-bold text-white">
                    {isAnalyzing ? 'AI 深度分析中' : '等待激活'}
                  </p>
                </div>
                {isAnalyzing && (
                  <p className="text-[10px] text-slate-500 mt-1 truncate">{analysisStep}</p>
                )}
              </div>
            </div>
          )}

          {/* Quadrants Area */}
          <div className="bg-white dark:bg-slate-800 rounded-2xl p-6 shadow-sm border border-slate-100 dark:border-slate-700 flex-1 flex flex-col overflow-hidden relative quadrants-container cursor-none">
            <div className="flex items-center justify-between mb-6 shrink-0">
              <h3 className="text-xl font-bold text-slate-900 dark:text-white">AI四象限结果</h3>
              {showResults && (
                <div className="flex items-center space-x-3">
                  <button className="px-4 py-2 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 text-sm font-bold rounded-full hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-sm">
                    手动添加指标
                  </button>
                  <button className="px-4 py-2 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 text-sm font-bold rounded-full hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-sm">
                    拖拽调整
                  </button>
                  <button className="px-4 py-2 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 text-sm font-bold rounded-full hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors shadow-sm">
                    复制结论
                  </button>
                </div>
              )}
            </div>

            <div className="flex-1 min-h-0 relative">
              <AnimatePresence>
                {isAnalyzing && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="absolute inset-0 z-20 bg-white/60 dark:bg-slate-800/60 backdrop-blur-[2px] flex flex-col items-center justify-center pointer-events-none"
                  >
                    <motion.div
                      initial={{ top: '0%' }}
                      animate={{ top: '100%' }}
                      transition={{ duration: 2.5, repeat: Infinity, ease: 'linear' }}
                      className="absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-brand to-transparent shadow-[0_0_15px_rgba(var(--brand-rgb),0.5)] z-30"
                    />
                    <div className="relative">
                      <motion.div
                        animate={{ scale: [1, 1.2, 1], opacity: [0.2, 0.5, 0.2] }}
                        transition={{ duration: 2, repeat: Infinity }}
                        className="absolute inset-0 bg-brand/30 rounded-full blur-3xl"
                      />
                      <div className="relative bg-white dark:bg-slate-800 p-8 rounded-[2.5rem] shadow-2xl border border-brand/20 flex flex-col items-center space-y-6 max-w-xs w-full">
                        <div className="relative">
                          <Loader2 className="w-16 h-16 text-brand animate-spin" />
                          <motion.div
                            animate={{ opacity: [0.5, 1, 0.5] }}
                            transition={{ duration: 1.5, repeat: Infinity }}
                            className="absolute inset-0 flex items-center justify-center"
                          >
                            <div className="w-2 h-2 bg-brand rounded-full" />
                          </motion.div>
                        </div>
                        <div className="text-center space-y-2">
                          <p className="text-xl font-black text-slate-900 dark:text-white tracking-tight">AI 深度分析中</p>
                          <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">{analysisStep}</p>
                        </div>
                        <div className="w-full space-y-2">
                          <div className="flex justify-between text-[10px] font-bold text-brand uppercase tracking-widest">
                            <span>Progress</span>
                            <span>{Math.round(analysisProgress)}%</span>
                          </div>
                          <div className="w-full h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden p-0.5">
                            <motion.div
                              className="h-full bg-brand rounded-full shadow-[0_0_10px_rgba(var(--brand-rgb),0.3)]"
                              initial={{ width: 0 }}
                              animate={{ width: `${analysisProgress}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragStart={handleDragStart}
                onDragOver={handleDragOver}
                onDragEnd={handleDragEnd}
              >
                <div className="grid grid-cols-2 gap-6 h-full">
                  <Quadrant
                    id="intervention"
                    title="A级-红色健康预警"
                    items={quadrantData.intervention}
                    colorTheme="red"
                    onRemoveItem={(id) => handleRemoveItem('intervention', id)}
                    onAddItem={(content) => handleAddItem('intervention', content)}
                    isAnalyzing={isAnalyzing}
                    hasResult={showResults}
                  />
                  <Quadrant
                    id="monitoring"
                    title="B级-橙色健康预警"
                    items={quadrantData.monitoring}
                    colorTheme="orange"
                    onRemoveItem={(id) => handleRemoveItem('monitoring', id)}
                    onAddItem={(content) => handleAddItem('monitoring', content)}
                    isAnalyzing={isAnalyzing}
                    hasResult={showResults}
                  />
                  <Quadrant
                    id="prevention"
                    title="C级-黄色健康预警"
                    items={quadrantData.prevention}
                    colorTheme="amber"
                    onRemoveItem={(id) => handleRemoveItem('prevention', id)}
                    onAddItem={(content) => handleAddItem('prevention', content)}
                    isAnalyzing={isAnalyzing}
                    hasResult={showResults}
                  />
                  <Quadrant
                    id="maintenance"
                    title="D级-蓝色健康预警"
                    items={quadrantData.maintenance}
                    colorTheme="blue"
                    onRemoveItem={(id) => handleRemoveItem('maintenance', id)}
                    onAddItem={(content) => handleAddItem('maintenance', content)}
                    isAnalyzing={isAnalyzing}
                    hasResult={showResults}
                  />
                </div>

                <DragOverlay>
                  {activeId ? (
                    <div className="flex items-center justify-between p-2 bg-white dark:bg-slate-800 rounded-lg border shadow-lg opacity-90 scale-105">
                      <div className="flex items-center flex-1 min-w-0">
                        <div className="p-1 mr-1 text-slate-400">
                          <GripVertical className="w-4 h-4" />
                        </div>
                        <span className="text-sm text-slate-700 dark:text-slate-200 truncate">{getActiveItemContent()}</span>
                      </div>
                    </div>
                  ) : null}
                </DragOverlay>
              </DndContext>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
